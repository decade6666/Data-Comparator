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

- 同步触发比对：
  ```bash
  curl -X POST http://127.0.0.1:8000/api/compare \
    -H 'Content-Type: application/json' \
    -d '{
      "old_file_path": "/data/old.xlsx",
      "new_file_path": "/data/new.xlsx",
      "output_directory": "/data/output",
      "config_name": "web",
      "anchor_row_num": 1,
      "header_row_num": 1,
      "merge_deleted_data": true,
      "common_cols": [],
      "exclude_sheets": [],
      "default_keys": [],
      "sheet_key_map": {},
      "include_sheets": [],
      "ignore_cols": [],
      "sheet_ignore_cols": {},
      "sheet_order": [],
      "colors": {
        "highlight_fill": "#FFE5E5",
        "missing_sheet_tab": "#DC143C",
        "new_sheet_tab": "#00FF00"
      }
    }'
  ```

提示：首次运行会在用户数据目录创建临时与配置子目录（例如 `PyDataCompare/temp/configs`）。

### 异步任务 API（Web UI 使用）

Web UI 基于异步任务接口实现进度显示与停止：

- `POST /api/jobs`：提交比对任务（字段与 `/api/compare` 一致；也可传 `old_file_upload_id` / `new_file_upload_id` 走上传模式，输出目录缺省为临时目录），返回 `job_id`。同一时间只允许一个任务运行，冲突返回 409。
- `GET /api/jobs/{job_id}?since=N`：轮询状态与新增日志，返回 `status` / `progress_percent` / `progress_message` / `log_lines` / `output_path`。
- `POST /api/jobs/{job_id}/cancel`：请求停止任务（底层设置停止标志，领域层抛出 `InterruptedError` 后任务标记为 `cancelled`）。
- `GET /api/jobs/{job_id}/download`：任务完成后下载比对报告。
- `POST /api/upload`：上传 Excel 文件（`.xlsx`/`.xls`，默认上限 200MB，可用 `DATASET_COMPARATOR_MAX_UPLOAD_MB` 调整）。
- `GET /api/browse?path=...`：浏览服务器目录（白名单由 `DATASET_COMPARATOR_BROWSE_ROOTS` 配置，默认用户主目录）。
- `GET /api/sheets`：读取 Excel 文件的 Sheet 名称（`file_path` 或 `upload_id`）。
- `GET/PUT/DELETE /api/configs/...`：配置预设的加载、保存、删除、复制、导入、导出；内置模板（CIMS/TM）受保护不可覆盖删除。

## 比对配置说明

| 参数 | 说明 |
|---|---|
| `include_sheets` | 指定表单：非空时只比对/输出列表内的表单；与 `exclude_sheets` 同时存在时，先按 include 过滤、再按 exclude 排除 |
| `ignore_cols` | 忽略比对字段（全局）：字段照常输出，但不产生差异、不高亮、不影响行级标记、不计入汇总 |
| `sheet_ignore_cols` | 按表单覆盖全局忽略字段：整体替换语义（不是追加合并）；未命中的表单回退到全局 `ignore_cols` |
| `sheet_order` | 输出表单顺序：按指定顺序排列输出文件中的表单；优先级为 sheet_order > include_sheets > 源文件顺序 |

## 目录结构（摘要）
- `frontend/`：Vue 3 + Vite + Element Plus 浏览器 UI（设计令牌与暗色模式参考 CRF-Editor）
- `src/main_web.py`：Linux Web/API 程序入口
- `src/frontend/`：FastAPI Web API 层（web_api.py，含任务/上传/浏览/配置端点与静态资源托管）
- `src/backend/application/`：应用编排服务，如路径校验、输出路径生成与异步任务管理（job_manager.py）
- `src/backend/domain/`：比对领域逻辑、Excel 读取/渲染、高亮与停止控制
- `src/backend/infrastructure/`：配置、进度、临时目录、上传存储与路径安全校验等运行时适配
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
