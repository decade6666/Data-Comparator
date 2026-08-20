# 数据集对比（Dataset Comparator）

高效的数据集比对工具，专为 Excel (.xlsx/.xlsm) 文件的跨版本差异分析而设计，以 Linux Web/API 运行入口为主，复用多线程处理与可视化高亮标记能力，适合业务与研发协同使用。

## 主要特性
- 多工作表对比：逐表读取与处理，自动识别 新增/删除/更新 三类变更
- 表头与锚点行可配置：支持自定义表头行（SASFieldLabel）与锚点行（SASFieldName）
- 锚点（主键）灵活：可设置默认锚点列与“按表单指定锚点列”
- 列级增删检测：自动识别新增/删除列，并在表头高亮标注
- 单元格级高亮：仅对“更新”行的变更单元格进行高亮，新增/删除行整行高亮
- 指定表单比对：`include_sheets` 非空时只比对/输出列表内的表单
- 忽略比对字段：`ignore_cols` / `sheet_ignore_cols` 指定的字段照常输出，但其变化不计入差异
- 输出表单顺序：`sheet_order` 按指定顺序排列输出文件中的表单
- 大文件与多线程优化：可配置最大线程数，内置条件 GC 与内存峰值保护
- Excel 预处理：自动清理筛选器、可选择排除指定 Sheet，处理“受保护的来源”标记
- 配置管理：JSON 配置持久化与内置模板（CIMS/TM），保存在用户数据目录下
- 过程可停止：支持随时停止任务，保证 API 调用可响应
- Web/API 入口：提供 FastAPI 服务，可在 Linux 环境通过外部 Web 访问触发比对

## 环境要求
- Linux（当前运行目标）
- Python 3.8 及以上
- 依赖（节选）：pandas、numpy、openpyxl、fastapi、pydantic、uvicorn、appdirs（可选：psutil/xlrd/xlsxwriter）

建议通过项目的 pyproject 安装：

```bash
# 开发模式安装（包含测试与质量工具）
pip install -e .[dev]
# 包含可选的性能增强
pip install -e .[performance]
```

## 快速上手

### 方式一：浏览器 Web UI（推荐）

1. 构建前端（需要 Node.js ≥ 18）：
   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```
2. 启动服务（`frontend/dist` 由 FastAPI 自动托管）：
   ```bash
   DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8000 dataset-comparator-web
   ```
3. 浏览器打开 `http://127.0.0.1:8000/` 即可使用。

前端开发模式（Vite 热更新，代理 `/api` 到后端 8000 端口）：
```bash
cd frontend && npm run dev
```

部署说明：静态目录可通过环境变量 `DATASET_COMPARATOR_STATIC_DIR` 覆盖（默认指向仓库内 `frontend/dist`）；子路径部署需在构建时设置 `VITE_BASE_PATH`。

### 生产环境部署（后台运行）

生产环境建议使用 `systemd` 管理服务。以下示例约定：

- 项目目录：`/opt/dataset-comparator`
- 服务账号：`dataset-comparator`
- Excel 文件和报告目录：`/data/dataset-comparator`
- 服务端口：`8000`
- 用户数据根目录：`/var/lib/dataset-comparator/data`（SQLite、配置、上传文件、结果均按用户隔离）

认证密钥与首次启动管理员建议写入仅服务账号可读的 `/etc/dataset-comparator.env`：

```bash
sudo install -o dataset-comparator -g dataset-comparator -m 600 /dev/null \
  /etc/dataset-comparator.env
sudoedit /etc/dataset-comparator.env
```

至少配置以下变量（不要把真实值提交到仓库）：

```text
DATASET_COMPARATOR_SECRET_KEY=<随机长密钥>
DATASET_COMPARATOR_ADMIN_USERNAME=<初始管理员用户名>
DATASET_COMPARATOR_ADMIN_PASSWORD=<至少 8 位的初始密码>
DATASET_COMPARATOR_DATA_DIR=/var/lib/dataset-comparator/data
DATASET_COMPARATOR_MAX_CONCURRENT_JOBS=2
```

#### 1. 准备运行目录和 Python 环境

只需首次部署时创建运行账号和目录；如果已经存在则跳过对应命令：

```bash
sudo useradd --system --user-group \
  --home-dir /var/lib/dataset-comparator \
  --shell /usr/sbin/nologin dataset-comparator

sudo install -d -o dataset-comparator -g dataset-comparator \
  /opt/dataset-comparator \
  /var/lib/dataset-comparator \
  /var/lib/dataset-comparator/logs \
  /data/dataset-comparator
```

将项目代码部署到 `/opt/dataset-comparator` 后，安装 Python 依赖：

```bash
sudo chown -R dataset-comparator:dataset-comparator /opt/dataset-comparator

sudo -u dataset-comparator -H python3 -m venv \
  /opt/dataset-comparator/.venv
sudo -u dataset-comparator -H \
  /opt/dataset-comparator/.venv/bin/python -m pip install --upgrade pip
sudo -u dataset-comparator -H sh -c '
  cd /opt/dataset-comparator &&
  .venv/bin/python -m pip install .
'
```

如需使用 Web UI，再构建前端；只提供 API 时可以跳过：

```bash
sudo -u dataset-comparator -H sh -c '
  cd /opt/dataset-comparator/frontend &&
  npm ci &&
  npm run build
'
```

#### 2. 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/dataset-comparator.service >/dev/null <<'EOF'
[Unit]
Description=Dataset Comparator Web/API
After=network.target

[Service]
Type=simple
User=dataset-comparator
Group=dataset-comparator
WorkingDirectory=/opt/dataset-comparator
Environment="HOME=/var/lib/dataset-comparator"
Environment="PATH=/opt/dataset-comparator/.venv/bin"
EnvironmentFile=/etc/dataset-comparator.env
Environment="DATASET_COMPARATOR_WEB_HOST=127.0.0.1"
Environment="DATASET_COMPARATOR_WEB_PORT=8000"
Environment="DATASET_COMPARATOR_STATIC_DIR=/opt/dataset-comparator/frontend/dist"
ExecStart=/opt/dataset-comparator/.venv/bin/python -m src.main_web
Restart=on-failure
RestartSec=5
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
```

加载并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dataset-comparator
sudo systemctl status dataset-comparator --no-pager
curl http://127.0.0.1:8000/health
```

常用运维命令：

```bash
# 查看实时日志
sudo journalctl -u dataset-comparator -f

# 重启或停止服务
sudo systemctl restart dataset-comparator
sudo systemctl stop dataset-comparator
```

默认只监听 `127.0.0.1`，建议在前面配置反向代理并启用 HTTPS。若不使用反向代理而需要从其他机器访问，将 `DATASET_COMPARATOR_WEB_HOST` 改为 `0.0.0.0`，并通过防火墙限制访问来源。当前异步任务状态保存在进程内，服务应保持单进程运行，不要直接扩展为多个 worker。

#### 3. 没有 systemd 时使用 nohup

`nohup` 适合临时或没有 systemd 的环境；进程异常退出时不会自动重启，生产环境优先使用上面的 systemd 方式：

```bash
sudo -u dataset-comparator -H sh -c '
  cd /opt/dataset-comparator &&
  set -a && . /etc/dataset-comparator.env && set +a &&
  nohup env \
    HOME=/var/lib/dataset-comparator \
    DATASET_COMPARATOR_WEB_HOST=127.0.0.1 \
    DATASET_COMPARATOR_WEB_PORT=8000 \
    DATASET_COMPARATOR_STATIC_DIR=/opt/dataset-comparator/frontend/dist \
    .venv/bin/python -m src.main_web \
    >> /var/lib/dataset-comparator/logs/web.log 2>&1 &
  echo $! > /var/lib/dataset-comparator/dataset-comparator.pid
'

curl http://127.0.0.1:8000/health
```

查看日志或停止 `nohup` 进程：

```bash
tail -f /var/lib/dataset-comparator/logs/web.log
sudo kill "$(sudo cat /var/lib/dataset-comparator/dataset-comparator.pid)"
```

### 方式二：纯 API

- 启动 Web/API 服务：
  ```bash
  DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8000 dataset-comparator-web
  ```
  未安装脚本时可直接运行：
  ```bash
  python -m src.main_web
  ```

- 健康检查：
  ```bash
  curl http://127.0.0.1:8000/health
  ```

- 认证：
  - `POST /api/auth/login`：用户名密码登录，返回 Bearer token。
  - 除 `/health`、登录和静态资源外，其余 API 都需要 `Authorization: Bearer <token>`。
  - `DATASET_COMPARATOR_SECRET_KEY` 缺失时服务启动失败；首次启动使用 `DATASET_COMPARATOR_ADMIN_USERNAME` / `DATASET_COMPARATOR_ADMIN_PASSWORD` 创建管理员。

- 上传并异步比对：
  ```bash
  TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"username":"<管理员用户名>","password":"<管理员密码>"}' | jq -r .access_token)

  OLD_ID=$(curl -s -X POST http://127.0.0.1:8000/api/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F 'file=@/data/old.xlsx' | jq -r .upload_id)
  NEW_ID=$(curl -s -X POST http://127.0.0.1:8000/api/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F 'file=@/data/new.xlsx' | jq -r .upload_id)

  curl -X POST http://127.0.0.1:8000/api/jobs \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"old_file_upload_id\":\"$OLD_ID\",\"new_file_upload_id\":\"$NEW_ID\"}"
  ```

提示：首次运行会在 `DATASET_COMPARATOR_DATA_DIR`（默认用户数据目录）创建 SQLite、按用户隔离的配置/上传/结果目录。

### 异步任务 API（Web UI 使用）

Web UI 基于异步任务接口实现进度显示与停止：

- `POST /api/jobs`：提交比对任务（文件只接受 `old_file_upload_id` / `new_file_upload_id`，输出目录缺省为当前用户结果目录），返回 `job_id`。每用户同一时间至多一个运行中任务，冲突返回 409；不同用户可并发，全局并发上限由 `DATASET_COMPARATOR_MAX_CONCURRENT_JOBS`（默认 2）控制，超额任务排队等待。
- `GET /api/jobs/{job_id}?since=N`：轮询状态与新增日志，返回 `status` / `progress_percent` / `progress_message` / `log_lines` / `output_path`。只能查询自己的任务，他人任务返回 404。
- `POST /api/jobs/{job_id}/cancel`：请求停止任务（底层设置停止标志，领域层抛出 `InterruptedError` 后任务标记为 `cancelled`）。
- `GET /api/jobs/{job_id}/download`：任务完成后下载比对报告。
- `POST /api/upload`：上传 Excel 文件（`.xlsx`/`.xls`，默认上限 200MB，可用 `DATASET_COMPARATOR_MAX_UPLOAD_MB` 调整），返回 `upload_id`，文件保存在当前用户的上传目录。
- `GET /api/sheets?upload_id=...`：读取已上传 Excel 文件的 Sheet 名称（仅支持 `upload_id`；上传成功后由前端自动扫描）。
- `GET/PUT/DELETE /api/configs/...`：配置预设的加载、保存、删除、复制、导入、导出；内置模板（CIMS/TM）为全局只读常量，受保护不可覆盖删除，也不落入用户配置目录。
- 用户管理（仅管理员）：`GET/POST /api/users`、`PUT /api/users/{user_id}/password`、`PUT /api/users/{user_id}/status`。

## 比对配置说明

| 参数 | 说明 |
|---|---|
| `include_sheets` | 比对表单（界面「比对表单」勾选项）：非空时只比对/输出列表内的表单；与 `exclude_sheets` 同时存在时，先按 include 过滤、再按 exclude 排除 |
| `exclude_sheets` | 比对表单（界面未勾选项）：模板提供的默认排除表单在扫描后自动取消勾选并保留到此处；换文件后未扫描到的原排除项继续生效 |
| `ignore_cols` | 忽略字段（全局，界面填「忽略字段」单参数行）：字段照常输出，但不产生差异、不高亮、不影响行级标记、不计入汇总 |
| `sheet_ignore_cols` | 忽略字段（指定表单，界面填「忽略字段」表单+字段双参数行）：整体替换全局忽略字段（不是追加合并）；未命中的表单回退到全局 `ignore_cols` |
| `default_keys` | 锚点（全局，界面填「锚点」单参数行）：默认主键列 |
| `sheet_key_map` | 锚点（指定表单，界面填「锚点」表单+字段双参数行）：按表单指定主键列，未命中的表单回退到 `default_keys` |
| `sheet_order` | 输出表单顺序（界面「表单顺序」拖拽列表，内容为勾选后的比对表单）：优先级为 sheet_order > include_sheets > 源文件顺序 |

## 目录结构（摘要）
- `frontend/`：Vue 3 + Vite + Element Plus 浏览器 UI（设计令牌与暗色模式参考 CRF-Editor，含登录与管理员用户管理）
- `src/main_web.py`：Linux Web/API 程序入口
- `src/frontend/`：FastAPI Web API 层（web_api.py，含任务/上传/配置/静态资源端点；routers/ 含认证与用户管理路由）
- `src/frontend/dependencies.py`：JWT 认证依赖（`get_current_user` / `require_admin`）
- `src/backend/application/`：应用编排服务，如认证、用户管理、路径校验、输出路径生成与异步任务管理（job_manager.py）
- `src/backend/domain/`：比对领域逻辑、Excel 读取/渲染、高亮与停止控制
- `src/backend/infrastructure/`：配置、进度、临时目录、上传存储、SQLite 数据库与路径安全校验等运行时适配
- `src/shared/`：跨层契约与日志转发
- `tests/`：pytest 测试资产

## 输出说明（概览）
- 结果文件为 Excel 工作簿：
  - 新增/删除列在表头以颜色标注
  - “更新情况（标记）”列置于第 1 列；新增/删除行整行高亮；更新行仅高亮变更单元格
  - 缺失/新增 Sheet 在标签色上区分
- 输出目录由 `output_directory` 参数决定；未设置时使用应用临时目录（AppData）
- 表单排列顺序：默认按源文件顺序（新文件为主，旧文件独有表单追加在后）；配置 `sheet_order` 后按指定顺序；仅配置 `include_sheets` 时按列表内顺序

## 常见问题
- xls 旧格式：建议另存为 .xlsx 再处理；`xlrd` 不再支持 .xlsx
- 表头/锚点行不正确导致列名重复：请调整 anchor_row_num/header_row_num 参数，避免 `SASFieldName` 重复
- 来自互联网的受保护 Excel 无法读取：程序会尝试移除 Zone.Identifier；若失败，请手动解除文件阻止
- 大文件内存压力：适当降低线程数、关闭非必要的应用、预留磁盘空间
