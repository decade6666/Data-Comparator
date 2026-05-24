[根目录](../../CLAUDE.md) > [src](../CLAUDE.md) > **shared**

# shared 模块指南

## 模块职责

`src/shared` 提供跨层共享契约和轻量工具，避免 Web/API、GUI、应用层和领域层重复定义参数结构、日志回调和资源路径解析逻辑。

## 入口与启动

主要文件：

- `contracts.py`：共享类型定义。
- `log_utils.py`：统一日志输出与回调委托。
- `resource_utils.py`：资源路径解析，兼容 PyInstaller `_MEIPASS`。

`shared` 不包含独立启动入口。

## 对外接口

- `ParameterDocument`：贯穿 Web/API、应用层、GUI 与配置管理的参数文档。
- `ParameterColors`：颜色配置子文档。
- `LogFunc`：日志回调类型。
- `log(msg, log_func)`：打印并委托日志回调。
- `get_resource_path(relative_path)`：解析资源文件路径。

## 关键依赖与配置

- 仅依赖 Python 标准库类型、路径和系统模块。
- `resource_utils.py` 兼容 PyInstaller 运行时路径。
- 不应在 `shared` 中引入 pandas、openpyxl、FastAPI、Tkinter 等重依赖，避免跨层耦合。

## 数据模型

`ParameterDocument` 字段包括：

- 文件路径：`old_file_path`、`new_file_path`、`output_directory`
- 行配置：`anchor_row_num`、`header_row_num`
- 内容标记：`anchor_row_content`、`header_row_content`
- 并发与合并：`max_workers`、`merge_deleted_data`
- 比对参数：`common_cols`、`exclude_sheets`、`default_keys`、`sheet_key_map`
- 颜色：`colors`

## 测试与质量

对应测试：

- `tests/test_log_utils.py`
- `tests/test_import_smoke.py`

质量注意：

- 共享类型变更影响面大，必须同步 Web/API 模型、GUI 参数收集、配置管理和测试。
- `log` 应保持轻量，不要引入业务逻辑。
- 资源路径函数应兼容源码运行和打包运行。

## 常见问题 (FAQ)

### 为什么参数类型放在 shared？

因为 Web/API、GUI、应用层和配置仓储都需要共享同一组字段。集中定义可以减少漂移。

### 能否在 shared 中添加业务函数？

不建议。业务算法应放在 `backend/domain`，应用编排放在 `backend/application`，`shared` 只放跨层契约和轻量通用工具。

### 修改 `ParameterDocument` 后需要检查哪里？

至少检查 `frontend/web_api.py`、`backend/application`、`backend/infrastructure/config_manager.py`、`gui/parameter_manager.py` 和对应测试。

## 相关文件清单

- `contracts.py`
- `log_utils.py`
- `resource_utils.py`
- `__init__.py`
- `tests/test_log_utils.py`
- `tests/test_import_smoke.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `shared` 模块 Claude 指南。 |
