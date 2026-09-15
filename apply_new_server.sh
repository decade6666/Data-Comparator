#!/usr/bin/env bash
# =============================================================================
# apply_new_server.sh —— 在【新服务器】用打包产物覆盖数据并重启服务
#
# 流程：
#   1) 参数：<数据包.tar.gz> [secret.env]；可选 --data-dir/--project-dir/--env-file/--no-start
#   2) 若存在同名的 .sha256 则先校验和
#   3) 解包到暂存目录并定位 dataset_comparator.db；顺手再折叠一次 WAL 兜底
#   4) 校验数据库完整性并列出用户，供核对
#   5) 定位目标数据根目录（--data-dir > $DATASET_COMPARATOR_DATA_DIR > appdirs/XDG 默认）
#   6) 停止运行中的服务 → 把当前 db 与 users/ 移到时间戳备份目录 → 安装新数据
#   7) 若提供了 secret.env，把 DATASET_COMPARATOR_SECRET_KEY 写进 env 文件（600）
#   8) 重启服务（systemd 优先；否则用 <项目目录>/.venv 起后台 uvicorn）并做 /health 检查
#
# 说明：覆盖前的数据完整备份到 $TMPDIR/dc-apply-backup-<时间戳>，可随时回滚。
#
# 用法：
#   bash apply_new_server.sh <数据包.tar.gz> [secret.env] [选项]
#   示例：
#     bash apply_new_server.sh dc-data.tgz secret.env
#     bash apply_new_server.sh dc-data.tgz --data-dir /var/lib/dataset-comparator/data --no-start
#
# 环境要求：bash、python3（stdlib 即可）、tar、sha256sum、curl。
# =============================================================================
set -euo pipefail

TB=""
SECRET=""
DATA_DIR=""
PROJ_DIR="$(pwd)"
ENV_FILE="${HOME}/.config/dataset-comparator/local.env"
NO_START=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir)   shift; DATA_DIR="$1" ;;
    --project-dir) shift; PROJ_DIR="$1" ;;
    --env-file)   shift; ENV_FILE="$1" ;;
    --no-start)   NO_START="1" ;;
    --*)          echo "未知参数: $1" >&2; exit 2 ;;
    *)            if [[ -z "$TB" ]]; then TB="$1"; elif [[ -z "$SECRET" ]]; then SECRET="$1"; else echo "多余的位置参数: $1" >&2; exit 2; fi ;;
  esac
  shift
done
[[ -n "$TB" ]] || { echo "用法: bash apply_new_server.sh <数据包.tar.gz> [secret.env] [选项]"; exit 2; }
[[ -f "$TB" ]] || { echo "错误：找不到数据包 $TB" >&2; exit 1; }

# ---- 2. 校验和 ----
if [[ -f "$TB.sha256" ]]; then
  echo "[apply] 校验 sha256 ..."
  ( cd "$(dirname "$TB")" && sha256sum -c --quiet "$(basename "$TB").sha256" ) \
    || { echo "错误：sha256 校验失败（传输可能损坏）" >&2; exit 1; }
  echo "[apply] sha256 OK"
fi

# ---- 3. 解包 + WAL 兜底折叠 ----
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
tar xzf "$TB" -C "$STAGE"

DATA_TREE=""
if [[ -f "$STAGE/dataset_comparator.db" ]]; then
  DATA_TREE="$STAGE"
else
  DATA_TREE=$(find "$STAGE" -maxdepth 3 -name dataset_comparator.db -print -quit 2>/dev/null | xargs -r dirname)
fi
[[ -n "$DATA_TREE" ]] && [[ -f "$DATA_TREE/dataset_comparator.db" ]] || { echo "错误：数据包内没有 dataset_comparator.db" >&2; exit 1; }

python3 - "$DATA_TREE/dataset_comparator.db" <<'PY'
import sqlite3, os, sys
db = sys.argv[1]
con = sqlite3.connect(db)
try:
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.execute("PRAGMA journal_mode=DELETE")
    con.commit()
finally:
    con.close()
for suf in ("-wal", "-shm"):
    p = db + suf
    if os.path.exists(p):
        os.remove(p)
con = sqlite3.connect(db)
print("[apply] integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
if "user" in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    users = con.execute("SELECT id, username FROM user ORDER BY id").fetchall()
    print(f"[apply] 数据包含用户 {len(users)} 个: {', '.join(u[1] for u in users)}")
con.close()
print("[apply] 单文件 db 大小:", os.path.getsize(db))
PY

# ---- 5. 定位目标数据根目录 ----
resolve_target() {
  if [[ -n "$DATA_DIR" ]]; then return 0; fi
  if [[ -n "${DATASET_COMPARATOR_DATA_DIR:-}" ]]; then DATA_DIR="$DATASET_COMPARATOR_DATA_DIR"; return 0; fi
  DATA_DIR=$(python3 - <<'PY' 2>/dev/null || true
try:
    from appdirs import user_data_dir
    print(user_data_dir("PyDataCompare", "YourCompanyOrAuthor"))
except Exception:
    pass
PY
)
  if [[ -z "$DATA_DIR" ]]; then DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/PyDataCompare"; fi
}
resolve_target
mkdir -p "$DATA_DIR"
echo "[apply] 目标数据根目录: $DATA_DIR"

# ---- 6. 停止服务 → 备份 → 安装 ----
stop_service() {
  local unit pid
  unit=$(systemctl list-unit-files 2>/dev/null | awk '$1 ~ /dataset-comparator/ {print $1; exit}')
  if [[ -n "$unit" ]]; then
    echo "[stop] 停止 systemd 服务: $unit"
    systemctl stop "$unit" || echo "[stop] systemctl stop 返回非零，请确认已停止" >&2
    return 0
  fi
  pid=$(ss -ltnp 2>/dev/null | awk '/:8888/{match($0, /pid=([0-9]+)/, m); print m[1]}' | head -1 || true)
  if [[ -n "$pid" ]]; then
    echo "[stop] 停止监听 8888 的进程: $pid"
    kill "$pid" 2>/dev/null || true
    for _ in {1..10}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    return 0
  fi
  echo "[stop] 未探测到活动服务。" >&2
}
stop_service

TS=$(date +%Y%m%d-%H%M%S)
BACKUP="${TMPDIR:-/tmp}/dc-apply-backup-${TS}"
mkdir -p "$BACKUP"
echo "[apply] 覆盖前备份 -> $BACKUP"
if compgen -G "$DATA_DIR/dataset_comparator.db*" >/dev/null; then
  mv "$DATA_DIR"/dataset_comparator.db* "$BACKUP/"
fi
if [[ -d "$DATA_DIR/users" ]]; then
  mv "$DATA_DIR/users" "$BACKUP/users"
fi

echo "[apply] 安装新数据..."
cp "$DATA_TREE/dataset_comparator.db" "$DATA_DIR/dataset_comparator.db"
chmod 664 "$DATA_DIR/dataset_comparator.db"
if [[ -d "$DATA_TREE/users" ]]; then
  cp -a "$DATA_TREE/users" "$DATA_DIR/"
fi
if [[ -d "$DATA_TREE/temp" ]] && [[ ! -e "$DATA_DIR/temp" ]]; then
  cp -a "$DATA_TREE/temp" "$DATA_DIR/"
fi
CHOWN_USER="${SUDO_USER:-$(id -un)}"
chown -R "$CHOWN_USER" "$DATA_DIR" 2>/dev/null || echo "[apply] 警告：chown 失败，请确认数据目录属主正确" >&2

python3 - "$DATA_DIR/dataset_comparator.db" <<'PY'
import sqlite3, sys
db = sys.argv[1]
con = sqlite3.connect(db)
print("[apply] 安装后 integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
if "user" in [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    users = con.execute("SELECT id, username FROM user ORDER BY id").fetchall()
    print(f"[apply] 已安装用户 {len(users)} 个: {', '.join(u[1] for u in users)}")
con.close()
PY

# ---- 7. 写 SECRET_KEY ----
apply_secret() {
  local src="$SECRET" key
  if [[ -z "$src" ]] && [[ -f "$DATA_TREE/secret.env" ]]; then src="$DATA_TREE/secret.env"; fi
  [[ -f "$src" ]] || { echo "[apply] 未提供 secret.env，跳过密钥同步。" >&2; return 0; }
  key=$(grep -E '^[[:space:]]*DATASET_COMPARATOR_SECRET_KEY=' "$src" \
        | head -1 | sed -E 's/^[^=]*=[[:space:]]*//; s/["'\'' ]+$//')
  if [[ -z "$key" ]]; then echo "[apply] secret.env 无有效密钥，跳过。" >&2; return 0; fi
  mkdir -p "$(dirname "$ENV_FILE")"
  python3 - "$ENV_FILE" "$key" <<'PY'
import os, sys
envf, key = sys.argv[1], sys.argv[2]
lines = []
if os.path.exists(envf):
    with open(envf, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
out, replaced = [], False
for ln in lines:
    if ln.strip().startswith("DATASET_COMPARATOR_SECRET_KEY="):
        out.append(f"DATASET_COMPARATOR_SECRET_KEY={key}")
        replaced = True
    else:
        out.append(ln)
if not replaced:
    out.append(f"DATASET_COMPARATOR_SECRET_KEY={key}")
with open(envf, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
os.chmod(envf, 0o600)
print(f"[apply] 已更新 SECRET_KEY -> {envf}")
PY
}
apply_secret

# ---- 8. 启动 + 健康检查 ----
if [[ -n "$NO_START" ]]; then
  echo "[apply] --no-start：未启动服务。数据已就位，可自行启动。"
else
  unit=$(systemctl list-unit-files 2>/dev/null | awk '$1 ~ /dataset-comparator/ {print $1; exit}')
  if [[ -n "$unit" ]]; then
    systemctl start "$unit" && echo "[apply] 已启动服务: $unit"
  elif [[ -x "$PROJ_DIR/.venv/bin/python" ]] && [[ -f "$PROJ_DIR/src/main_web.py" ]]; then
    echo "[apply] nohup 启动服务（项目目录 $PROJ_DIR）..."
    ( cd "$PROJ_DIR" && set -a && [[ -f "$ENV_FILE" ]] && source "$ENV_FILE"; set +a; \
      DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8888 \
      nohup .venv/bin/python -m src.main_web >> migrate-server.log 2>&1 & echo $! > /tmp/dc-server.pid )
    echo "[apply]     PID: $(cat /tmp/dc-server.pid)，日志: $PROJ_DIR/migrate-server.log"
  else
    echo "[apply] 未找到可自动启动方式。请手动启动：" >&2
    echo "  DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8888 $PROJ_DIR/.venv/bin/python -m src.main_web" >&2
  fi
  sleep 4
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 5 http://127.0.0.1:8888/health || true)
  if [[ "$code" == "200" ]]; then
    echo "[apply] /health = 200，迁移完成 ✅"
  else
    echo "[apply] /health 未就绪（code=$code）。日志尾部：" >&2
    tail -n 15 "$PROJ_DIR/migrate-server.log" 2>/dev/null || true
    echo "[apply] 回滚：把 $BACKUP 里的 db 与 users 原样放回 $DATA_DIR，再启动旧版本/旧命令即可。" >&2
    exit 1
  fi
fi

echo
echo "========== 完成 =========="
echo "数据目录: $DATA_DIR"
echo "覆盖前备份（如需回滚）: $BACKUP"
echo "服务地址: http://0.0.0.0:8888/health"