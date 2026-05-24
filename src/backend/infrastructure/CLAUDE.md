[根目录](../../../CLAUDE.md) > [src](../../CLAUDE.md) > [backend](../CLAUDE.md) > **infrastructure**

# backend/infrastructure 模块指南

## 模块职责

`src/backend/infrastructure` 是基础设施层，负责运行时配置、JSON 配置持久化、Excel 文件运行时处理、临时目录、AutoFilter 清理和线程安全进度管理。它为应用层和领域层提供稳定的文件系统与配置能力。

## 入口与启动

主要入口：

- `config_manager.py`
  - `ConfigManager`：管理锚点行、表头行、排除列、排除 Sheet、颜色、线程数等运行配置。
- `parameter_repository.py`
  - `JsonParameterRepository`：保存、加载、列出、删除 JSON 配置，并创建内置模板。
- `file_runtime.py`
  - `check_and_remove_file_protection(...)`
  - `validate_excel_file(...)`
  - `get_sheet_names(...)`
  - `get_app_temp_dir(...)`
  - `cleanup_nofilter_files(...)`
  - `remove_auto_filters_from_xlsx(...)`
- `progress_manager.py`
  - `ThreadSafeProgressManager`：多线程 Sheet 处理中的进度聚合。

## 对外接口

调用方：

- `src/backend/application/comparison_runner.py` 创建 `ConfigManager`。
- `src/backend/domain/data_comparison.py` 使用配置、文件运行时和进度管理能力。
- `src/gui/parameter_manager.py` 和 GUI 配置流程使用参数仓储能力。

## 关键依赖与配置

- `openpyxl`：读取 workbook、处理 Sheet 和过滤器。
- `appdirs`：定位用户数据目录。
- `threading.Lock`：保护进度状态。
- JSON 文件：用户配置持久化格式。
- 默认配置：锚点行与表头行默认 `1`，锚点内容默认 `SASFieldName`，表头内容默认 `SASFieldLabel`。

## 数据模型

- JSON 配置文档：与 `ParameterDocument` 字段保持兼容。
- 内置模板：由 `JsonParameterRepository.ensure_builtin_templates` 创建。
- 进度状态：`ThreadSafeProgressManager` 维护总 Sheet 数、已完成数量和最终状态。

## 测试与质量

对应测试：

- `tests/test_parameter_repository.py`
- `tests/test_progress_manager.py`
- `tests/test_processing_control.py` 中覆盖 `file_runtime` 的中断传播行为。

质量注意：

- 文件系统写入前必须确保目录存在。
- 非对象 JSON 配置应抛 `ValueError`。
- 进度回调失败应记录日志，不应破坏主流程。
- 文件保护与 AutoFilter 清理中遇到 `InterruptedError` 必须传播，不要走 fallback。

## 常见问题 (FAQ)

### 用户配置保存在哪里？

由 `JsonParameterRepository.get_configs_dir` 决定，通常通过 `appdirs.user_data_dir` 获取用户级数据目录。

### 默认线程数如何确定？

`ConfigManager` 默认使用 CPU 核心数减一，至少为 `1`。

### 为什么文件运行时逻辑不放在领域层？

文件保护、临时目录、AutoFilter 清理属于环境和文件系统细节，放在基础设施层可避免污染领域算法。

## 相关文件清单

- `config_manager.py`
- `parameter_repository.py`
- `file_runtime.py`
- `progress_manager.py`
- `__init__.py`
- `tests/test_parameter_repository.py`
- `tests/test_progress_manager.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `backend/infrastructure` 模块 Claude 指南。 |
