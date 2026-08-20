[根目录](../../CLAUDE.md) > [src](../CLAUDE.md) > **frontend**

# frontend 模块指南

## 模块职责

`src/frontend` 是 Web API 层，通过 FastAPI 暴露 Linux Web/API 入口。

## 入口与启动

- `web_api.py`
  - 定义 FastAPI `app`。
  - 提供健康检查与比对接口。
  - 将 Web 请求转换为后端 `ParameterDocument`。

Web 服务由 `src/main_web.py` 通过 Uvicorn 启动：

```bash
DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8888 python -m src.main_web
```

## 对外接口

FastAPI 接口：

- `GET /health`
  - 返回：`{"status": "ok"}`。
- `POST /api/compare`
  - 请求体由 `CompareRequest` 建模。
  - 成功返回 `CompareResponse`，包含 `output_path`。
- `POST /api/jobs`（异步任务）
  - 请求体由 `JobSubmitRequest` 建模（复用 `CompareRequest` 字段，路径字段可省略）。
  - 成功返回 `JobSubmitResponse`（`job_id` / `status`）。
  - 同一时间只允许一个任务运行（`JobManager` 单任务串行，冲突返回 409）。
- `GET /api/jobs/{job_id}`：轮询任务状态（`?since=N` 只返回新增日志）。
- `POST /api/jobs/{job_id}/cancel`：停止任务。
- `GET /api/jobs/{job_id}/download`：下载比对报告。
- `POST /api/upload`：上传 Excel（`.xlsx`/`.xls`，默认 200MB）。
- `GET /api/browse`：浏览服务器目录（白名单 `DATASET_COMPARATOR_BROWSE_ROOTS`）。
- `GET /api/sheets`：读取文件 Sheet 名称。
- `GET/PUT/DELETE /api/configs` 系列：配置预设 CRUD、复制、导入、导出。
- `GET /`、`GET /assets/{path}`：托管 `frontend/dist` 静态资源（`DATASET_COMPARATOR_STATIC_DIR` 可覆盖）。

异常映射：

- `FileNotFoundError` -> HTTP 404
- `ValueError` -> HTTP 400
- `InterruptedError` -> HTTP 409
- `OSError` / `RuntimeError` -> HTTP 500
- 未知异常 -> HTTP 500

## 关键依赖与配置

- `fastapi`：HTTP API 框架。
- `pydantic`：请求与响应模型。
- `uvicorn`：由 `src/main_web.py` 启动 ASGI 应用。
- `python-multipart`：文件上传解析。
- 环境变量：`DATASET_COMPARATOR_WEB_HOST`、`DATASET_COMPARATOR_WEB_PORT`、`DATASET_COMPARATOR_DEV_RELOAD`、`DATASET_COMPARATOR_MAX_UPLOAD_MB`、`DATASET_COMPARATOR_BROWSE_ROOTS`、`DATASET_COMPARATOR_STATIC_DIR`。

## 数据模型

`web_api.py` 中定义：

- `CompareColors`
- `CompareRequest` / `CompareResponse`
- `JobSubmitRequest` / `JobSubmitResponse` / `JobStatusResponse`
- `UploadResponse` / `BrowseEntry` / `BrowseResponse`

`CompareRequest.to_parameter_document()` 会转换为 `src/shared/contracts.py` 中的 `ParameterDocument`，再进入应用层。

## 测试与质量

对应测试：

- `tests/test_web_api.py`
- `tests/test_web_api_jobs.py`
- `tests/test_web_api_upload.py`
- `tests/test_web_api_browse.py`
- `tests/test_web_api_sheets.py`
- `tests/test_web_api_configs.py`
- `tests/test_import_smoke.py`

重点行为：

- `/health` 必须轻量且稳定。
- `/api/compare` 不应直接实现业务算法，只调用应用层。
- Web 边界输入使用 Pydantic 校验，缺少必要路径应返回 422。
- 任务端点只做 HTTP 适配，任务生命周期由 `src/backend/application/job_manager.py` 管理。
- 目录浏览与静态资源必须经过 `src/backend/infrastructure/path_security.py` 的白名单校验。
- 不要在响应或日志中泄露用户 Excel 内容。

## 常见问题 (FAQ)

### 新接口应该放在哪里？

Web 接口放在 `web_api.py`，但业务编排应放在 `backend/application`，核心算法应放在 `backend/domain`。

### 为什么用户停止映射为 409？

`InterruptedError` 表示任务被用户主动停止，不是输入格式错误，也不是资源不存在，因此当前 API 映射为冲突状态。

## 相关文件清单

- `web_api.py`
- `__init__.py`
- `tests/test_web_api.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-08-18 | feat | 新增任务/上传/浏览/Sheet 发现/配置 CRUD 端点与静态资源托管，支持浏览器 Web UI。 |
| 2026-05-24T03:25:49 | docs | 初始化 `frontend` 模块 Claude 指南。 |
