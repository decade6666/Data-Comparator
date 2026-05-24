[根目录](../../CLAUDE.md) > [src](../CLAUDE.md) > **gui**

# gui 模块指南

## 模块职责

`src/gui` 是历史桌面 GUI 层，基于 Tkinter 与 ttkbootstrap。它负责配置选择、参数编辑、文件路径选择、日志展示、进度更新、开始/停止比对和高级设置。当前项目未来方向是 Linux Web Runtime，因此 GUI 应作为兼容路径维护，非明确需求不应成为新能力默认入口。

## 入口与启动

- `src/main.py`：创建主窗口并初始化 `DatasetComparatorGUI`。
- `run.py`：仓库根目录历史启动脚本。
- `main_window.py`
  - `DatasetComparatorGUI`：主窗口与比对线程编排。
  - `_AdvancedSettingsDialog`、`_ListEditorDialog`、`_DictEditorDialog` 等内部对话框。
- `parameter_manager.py`
  - `ParameterManager`：配置加载、保存、模板和参数管理。

## 对外接口

GUI 不暴露 HTTP API。主要调用后端能力：

- `validate_processing_paths`：开始处理前校验路径。
- `apply_processing_paths`：把校验后的路径合并到参数文档。
- `process_edc_multithreaded`：后台线程执行比对。
- `ConfigManager` 与 `JsonParameterRepository`：管理配置。

## 关键依赖与配置

- `tkinter` / `ttkbootstrap`：桌面 UI。
- `threading.Event`：停止标志。
- `threading.Thread`：后台处理线程。
- `queue`：GUI 主线程更新队列。
- 内置模板：`【模板】CIMS数据集`、`【模板】TM数据集`。

## 数据模型

- GUI 参数最终被收集为与 `ParameterDocument` 兼容的 dict。
- `ParameterManager` 管理的配置包含通用排除列、排除 Sheet、默认锚点、Sheet 级锚点映射、颜色等。
- `DatasetComparatorGUI.stop_flag` 用于请求中断，领域层会转换为 `InterruptedError`。

## 测试与质量

当前 GUI 主要通过导入烟测与后端测试间接覆盖。相关测试：

- `tests/test_import_smoke.py`
- `tests/test_processing_service.py`
- `tests/test_processing_control.py`

质量注意：

- GUI 回调不能直接阻塞主线程；耗时比对必须在后台线程执行。
- UI 状态恢复需要考虑异常和用户中断。
- 停止按钮只设置 stop flag，实际中断由领域层周期检查完成。
- GUI 代码体量较大，修改前应明确是否可改为 Web/API 层能力。

## 常见问题 (FAQ)

### 新能力是否应该先做 GUI？

通常不应。当前项目目标是 Linux Web Runtime，应优先实现 Web/API 与后端能力，再视需求补 GUI。

### 用户点击停止后为什么不会立即结束？

停止是协作式取消。GUI 设置 `stop_flag`，领域层在读取、比较和写入流程中的检查点抛出 `InterruptedError`。

### 内置模板可以修改或删除吗？

不应通过 GUI 修改或删除内置模板。`ParameterManager` 中有保护逻辑。

## 相关文件清单

- `main_window.py`
- `parameter_manager.py`
- `components/top_operations_bar.py`
- `components/parameter_card_frame.py`
- `components/scrollable_frame.py`
- `dialogs/error_dialog.py`
- `dialogs/help_dialog.py`
- `__init__.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `gui` 模块 Claude 指南。 |
