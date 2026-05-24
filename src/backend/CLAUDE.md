[根目录](../../CLAUDE.md) > [src](../CLAUDE.md) > **backend**

# backend 模块指南

## 模块职责

`src/backend` 是后端分层聚合目录，包含应用编排层、领域层和基础设施层。它承接 Web/API 与历史 GUI 的请求，把外部参数转换为可执行的 Excel 数据集比对流程。

## 入口与启动

- 应用入口：`application/comparison_runner.py` 中的 `run_comparison`。
- 核心领域入口：`domain/data_comparison.py` 中的 `process_edc_multithreaded`。
- 基础设施入口：`infrastructure/config_manager.py`、`infrastructure/parameter_repository.py`、`infrastructure/file_runtime.py`。

## 对外接口

`backend` 不直接暴露 HTTP 接口；它被以下上层调用：

- `src/frontend/web_api.py`：Web/API 请求转为 `ParameterDocument` 后调用应用层。
- `src/gui/main_window.py`：历史 GUI 收集参数后调用领域处理流程。

核心内部接口：

- `run_comparison(...) -> str`：应用层统一编排入口，返回输出报告路径。
- `validate_processing_paths(...)`：路径与输出目录校验。
- `process_edc_multithreaded(...)`：多 Sheet Excel 比对主流程。

## 关键依赖与配置

- `pandas`、`numpy`：数据表处理与差异计算。
- `openpyxl`：Excel 读取、写入、样式、高亮和 Sheet tab 处理。
- `appdirs`：用户级配置与临时目录。
- `ConfigManager`：运行参数、颜色、线程数和默认配置。
- `JsonParameterRepository`：JSON 配置持久化。

## 数据模型

- `ParameterDocument`：共享参数文档，定义在 `src/shared/contracts.py`。
- `SheetProcessResult`：单 Sheet 处理结果容器，定义在 `domain/sheet_process_result.py`。
- `ProcessingPaths`：应用层路径校验后的路径对象，定义在 `application/processing_service.py`。
- pandas `DataFrame.attrs`：承载 `sas_file_name`、`sas_file_label`、`sas_name_to_label` 等 Excel 元数据。

## 测试与质量

后端相关测试集中在：

- `tests/test_comparison_runner.py`
- `tests/test_processing_service.py`
- `tests/test_parameter_repository.py`
- `tests/test_progress_manager.py`
- `tests/test_processing_control.py`
- `tests/test_sheet_process_result.py`
- `tests/test_highlight_optimizer.py`

质量注意：

- 用户停止语义依赖 `InterruptedError`，不要被宽泛异常处理吞掉。
- 应用层优先返回新对象，避免就地修改共享参数。
- 领域层大文件较多，修改前先补针对性测试。

## 常见问题 (FAQ)

### Web/API 和 GUI 是否共享后端？

是。Web/API 通过 `run_comparison` 调用后端；GUI 目前部分路径直接调用领域流程，但仍复用应用层路径校验和配置管理能力。

### 应该在哪一层做输入校验？

外部输入先在系统边界校验：Web/API 使用 Pydantic，随后应用层使用 `validate_processing_paths` 校验路径和输出目录。

### 文件运行时问题归哪层处理？

Excel 文件保护、Sheet 名读取、临时文件、AutoFilter 清理属于 `backend/infrastructure/file_runtime.py`。

## 相关文件清单

- `src/backend/application/`
- `src/backend/domain/`
- `src/backend/infrastructure/`
- `src/backend/__init__.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `backend` 模块 Claude 指南。 |
