[根目录](../CLAUDE.md) > **src**

# src 模块指南

## 模块职责

`src` 是 Data-Comparator 的 Python 包根目录，聚合 Web/API 运行入口、后端分层、前端适配层和共享契约。当前项目为 Linux Web/API 运行，新能力默认优先接入 Web/API 路径。

## 入口与启动

- `src/main_web.py`：Web/API 启动入口，读取 `DATASET_COMPARATOR_WEB_HOST` 与 `DATASET_COMPARATOR_WEB_PORT`，通过 Uvicorn 加载 `src.frontend.web_api:app`。
- `pyproject.toml` 暴露命令：`dataset-comparator`、`dataset-comparator-web`（均指向 `src.main_web:main`）。

## 对外接口

`src` 本身不直接定义业务 API；对外接口由子模块提供：

- Web/API：`src/frontend/web_api.py` 中的 `GET /health` 与 `POST /api/compare`。
- 应用编排：`src/backend/application/comparison_runner.py` 中的 `run_comparison`。
- 领域流程：`src/backend/domain/data_comparison.py` 中的 `process_edc_multithreaded`。

## 关键依赖与配置

- 依赖与入口配置集中在 `pyproject.toml`。
- 运行时配置由 `src/backend/infrastructure/config_manager.py` 管理。

## 数据模型

- 共享入参契约定义在 `src/shared/contracts.py`，核心类型为 `ParameterDocument` 与 `ParameterColors`。
- 单 Sheet 处理结果定义在 `src/backend/domain/sheet_process_result.py`。
- Web 请求模型定义在 `src/frontend/web_api.py`，并转换为 `ParameterDocument` 后进入应用层。

## 测试与质量

- 导入烟测：`tests/test_import_smoke.py`。
- Web/API：`tests/test_web_api.py`。
- 应用层：`tests/test_comparison_runner.py`、`tests/test_processing_service.py`。
- 运行测试：`pytest` 或 `pytest -v --tb=short --strict-markers`。

## 常见问题 (FAQ)

### 新功能应该接入哪里？

优先接入 `src/frontend/web_api.py`、`src/backend/application` 与 `src/backend/domain`。

### 修改公共参数时需要同步哪些位置？

同步检查 `src/shared/contracts.py`、`src/frontend/web_api.py`、`src/backend/infrastructure/config_manager.py` 与相关测试。

## 相关文件清单

- `src/main_web.py`
- `src/__init__.py`
- `src/backend/`
- `src/frontend/`
- `src/shared/`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `src` 模块 Claude 指南。 |
