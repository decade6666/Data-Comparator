#!/usr/bin/env bash
# =============================================================================
# pack_old_server.sh —— 在【旧服务器】上打包 Data-Comparator 数据根目录用于迁移
#
# 流程：
#   1) 探测数据根目录（位置参数 > $DATASET_COMPARATOR_DATA_DIR > 常见路径 > find .db）
#   2) 停止运行中的服务（systemd 单位的 dataset-comparator，或监听 8888 的进程）
#   3) 在临时副本里把 WAL 折叠进 .db——单文件即完整，不丢最近写入
#   4) 校验数据库完整性并列出用户，供迁移前后核对
#   5) 打包整个数据根（dataset_comparator.db + users/ + temp/）为 tar.gz，附 sha256
#   6) 从环境/常见 env 文件提取 DATASET_COMPARATOR_SECRET_KEY 到独立文件 secret.env(600)
#   7) systemd 管理的服务默认自动恢复；手动起的请按原命令重启
#
# 说明：打包基于副本，不修改旧服务器原有数据。
#
# 用法：
#   bash pack_old_server.sh [数据根目录] [--out 输出目录] [--no-stop]
#   示例：
#     bash pack_old_server.sh
#     bash pack_old_server.sh /var/lib/dataset-comparator/data --out /tmp
#
# 产物（默认输出到当前目录）：
#   dataset-comparator-data-<主机名>-<时间戳>.tar.gz   （含 db + users + temp）
#   同名 .sha256                                        （供新服务器校验）
#   secret.env                                          （DATASET_COMPARATOR_SECRET_KEY，权限 600）
# =============================================================================
set -euo pipefail

DATA_DIR=""
OUT_DIR="$(pwd)"
NO_STOP=""
_SERVICE_UNIT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)      shift; OUT_DIR="$1" ;;
    --no-stop)  NO_STOP="1" ;;
    --*)        echo "未知参数: $1" >&2; exit 2 ;;
    *)          if [[ -z "$DATA_DIR" ]]; then DATA_DIR="$1"; else echo "多余的位置参数: $1" >&2; exit 2; fi ;;
  esac
  shift
done

# ---- 1. 定位数据根目录 ----
detect_data_dir() {
  if [[ -n "$DATA_DIR" ]] && [[ -d "$DATA_DIR" ]]; then
    DATA_DIR=$(readlink -f "$DATA_DIR"); return 0
  fi
  if [[ -n "${DATASET_COMPARATOR_DATA_DIR:-}" ]] && [[ -d "$DATASET_COMPARATOR_DATA_DIR" ]]; then
    DATA_DIR=$(readlink -f "$DATASET_COMPARATOR_DATA_DIR"); return 0
  fi
  local db
  db=$(timeout 20 find "$HOME" -maxdepth 6 -name dataset_comparator.db -type f \
       -print -quit 2>/dev/null || true)
  if [[ -n "$db" ]]; then
    DATA_DIR=$(dirname "$db"); return 0
  fi
  echo "错误：无法定位数据根目录（含 dataset_comparator.db 的目录），请显式作为第一个参数传入。" >&2
  exit 1
}
detect_data_dir
[[ -e "$DATA_DIR/dataset_comparator.db" ]] || {
  echo "错误：$DATA_DIR 下未找到 dataset_comparator.db" >&2; exit 1
}
echo "[pack] 待打包数据根目录: $DATA_DIR"

# ---- 2. 停止服务 ----
stop_service() {
  local unit pid
  unit=$(timeout 5 systemctl list-unit-files 2>/dev/null \
         | awk '$1 ~ /dataset-comparator/ {print $1; exit}' || true)
  if [[ -n "$unit" ]]; then
    echo "[stop] 停止 systemd 服务: $unit"
    systemctl stop "$unit" || echo "[stop] systemctl stop 返回非零，请手动确认服务已停止" >&2
    _SERVICE_UNIT="$unit"
    return 0
  fi
  pid=$(timeout 5 ss -ltnp 2>/dev/null \
        | awk '/:8888/{match($0, /pid=([0-9]+)/, m); print m[1]}' | head -1 || true)
  if [[ -n "$pid" ]]; then
    echo "[stop] 停止监听 8888 的进程: $pid"
    kill "$pid" 2>/dev/null || true
    for _ in {1..10}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    return 0
  fi
  echo "[stop] 未探测到活动服务，继续。若服务以前台/其他端口运行，请先确认已停止。" >&2
}
if [[ -z "$NO_STOP" ]]; then stop_service; fi

# ---- 3. 副本 + WAL 折叠 ----
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

echo "[pack] 数据根目录: $DATA_DIR"
echo "[pack] 复制到暂存区（不改动原数据）..."
cp -a "$DATA_DIR/." "$STAGE/"
STAGE_DB="$STAGE/dataset_comparator.db"

python3 - "$STAGE_DB" <<'PY'
import sqlite3, os, sys
db = sys.argv[1]
# 连接即自动恢复 WAL；再切回 DELETE 模式把 WAL 折叠进主库并清理 -wal/-shm
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
print("[pack] integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("[pack] tables:", ", ".join(tables))
if "user" in tables:
    users = con.execute("SELECT id, username FROM user ORDER BY id").fetchall()
    print(f"[pack] 用户 {len(users)} 个: {', '.join(u[1] for u in users)}")
con.close()
print("[pack] 单文件 db 大小:", os.path.getsize(db))
PY

# ---- 4. 打包 + 校验和 ----
TS=$(date +%Y%m%d-%H%M%S)
HOST=$(hostname -s 2>/dev/null || echo host)
BUNDLE="dataset-comparator-data-${HOST}-${TS}.tar.gz"
mkdir -p "$OUT_DIR"
tar czf "$OUT_DIR/$BUNDLE" -C "$STAGE" .
( cd "$OUT_DIR" && sha256sum "$BUNDLE" > "$BUNDLE.sha256" )
echo "[pack] 打包完成: $OUT_DIR/$BUNDLE"
echo "[pack] 校验和:   $OUT_DIR/$BUNDLE.sha256"

# ---- 5. 导出 SECRET_KEY（独立文件，不进 tar.gz） ----
extract_secret() {
  local k="" f
  if [[ -n "${DATASET_COMPARATOR_SECRET_KEY:-}" ]]; then
    k="${DATASET_COMPARATOR_SECRET_KEY}"
  else
    for f in /etc/dataset-comparator.env \
             "$HOME/.config/dataset-comparator/local.env" \
             "${DATA_DIR}/.env" \
             /opt/dataset-comparator/.env; do
      [[ -f "$f" ]] || continue
      k=$(grep -E '^[[:space:]]*DATASET_COMPARATOR_SECRET_KEY=' "$f" \
          | head -1 | sed -E 's/^[^=]*=[[:space:]]*//; s/["'\'' ]+$//')
      [[ -n "$k" ]] && break
    done
  fi
  umask 077
  if [[ -n "$k" ]]; then
    printf 'DATASET_COMPARATOR_SECRET_KEY=%s\n' "$k" > "$OUT_DIR/secret.env"
    echo "[pack] 已导出 SECRET_KEY -> $OUT_DIR/secret.env (600)"
  else
    printf '# 未在旧环境找到 DATASET_COMPARATOR_SECRET_KEY；可手动补充或跳过。\n' > "$OUT_DIR/secret.env"
    echo "[pack] 警告：未找到 SECRET_KEY，secret.env 留空。用户仍可用原密码重新登录，但已签发 JWT 会失效。" >&2
  fi
  chmod 600 "$OUT_DIR/secret.env"
}
extract_secret

# ---- 6. 恢复旧服务 ----
if [[ -n "$_SERVICE_UNIT" ]]; then
  echo "[pack] 恢复服务: systemctl start $_SERVICE_UNIT"
  systemctl start "$_SERVICE_UNIT" || echo "[pack] 恢复失败，请手动启动 $_SERVICE_UNIT" >&2
elif [[ -z "$NO_STOP" ]]; then
  echo "[pack] 旧服务非 systemd 管理，请按原方式手动重启（如 uvicorn）。"
fi

echo
echo "========== 下一步 =========="
echo "把 $OUT_DIR/$BUNDLE 与 $OUT_DIR/secret.env 传到新服务器，然后执行："
echo "  bash apply_new_server.sh <数据包.tar.gz> <secret.env>"