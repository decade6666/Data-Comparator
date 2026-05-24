[根目录](../../CLAUDE.md) > [src](../CLAUDE.md) > **frontend**

# frontend 模块指南

## 模块职责

`src/frontend` 是前端适配层。当前最重要的职责是通过 FastAPI 暴露 Linux Web/API 入口；同时保留 GUI 主线程更新队列与窗口工具，用于历史桌面 GUI。

## 入口与启动

- `web_api.py`
  - 定义 FastAPI `app`。
  - 提供健康检查与比对接口。
  - 将 Web 请求转换为后端 `ParameterDocument`。
- `gui_update_manager.py`
  - 定义 GUI 更新消息类型与队列处理器。
- `window_utils.py`
  - 为历史 GUI 设置窗口图标。

Web 服务由 `src/main_web.py` 通过 Uvicorn 启动：

```bash
DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8000 python -m src.main_web
```

## 对外接口

FastAPI 接口：

- `GET /health`
  - 返回：`{"status": "ok"}`。
- `POST /api/compare`
  - 请求体由 `CompareRequest` 建模。
  - 成功返回 `CompareResponse`，包含 `output_path`。

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
- 环境变量：`DATASET_COMPARATOR_WEB_HOST`、`DATASET_COMPARATOR_WEB_PORT`。

## 数据模型

`web_api.py` 中定义：

- `CompareColors`
- `CompareRequest`
- `CompareResponse`

`CompareRequest.to_parameter_document()` 会转换为 `src/shared/contracts.py` 中的 `ParameterDocument`，再进入应用层。

## 测试与质量

对应测试：

- `tests/test_web_api.py`
- `tests/test_import_smoke.py`

重点行为：

- `/health` 必须轻量且稳定。
- `/api/compare` 不应直接实现业务算法，只调用应用层。
- Web 边界输入使用 Pydantic 校验，缺少必要路径应返回 422。
- 不要在响应或日志中泄露用户 Excel 内容。

## 常见问题 (FAQ)

### 新接口应该放在哪里？

Web 接口放在 `web_api.py`，但业务编排应放在 `backend/application`，核心算法应放在 `backend/domain`。

### 为什么用户停止映射为 409？

`InterruptedError` 表示任务被用户主动停止，不是输入格式错误，也不是资源不存在，因此当前 API 映射为冲突状态。

### GUI 更新队列是否服务于 Web？

不是。`gui_update_manager.py` 面向历史 Tkinter GUI，Web/API 不应依赖 GUI 更新队列。

## 相关文件清单

- `web_api.py`
- `gui_update_manager.py`
- `window_utils.py`
- `__init__.py`
- `tests/test_web_api.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `frontend` 模块 Claude 指南。 |
