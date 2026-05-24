[根目录](../../../CLAUDE.md) > [src](../../CLAUDE.md) > [backend](../CLAUDE.md) > **domain**

# backend/domain 模块指南

## 模块职责

`src/backend/domain` 是 Excel 数据集比对核心领域层，负责读取 Sheet、解析 SASFieldName/SASFieldLabel、构造锚点、识别新增/删除/更新、写入结果、高亮差异、处理停止信号并返回单 Sheet 处理结果。

该目录包含项目最复杂的业务逻辑。`data_comparison.py` 体量较大，是后续维护和重构的主要风险点。

## 入口与启动

核心入口：

- `data_comparison.py`
  - `process_edc_multithreaded(...)`：多线程 Excel 比对主流程。
  - `perform_full_comparison(...)`：执行完整差异识别。
  - `process_single_sheet_complete(...)`：处理单个共同 Sheet。
  - `process_missing_sheet(...)`：处理旧文件存在、新文件缺失的 Sheet。
  - `process_new_sheet(...)`：处理新文件新增 Sheet。
  - `create_anchor_by_sas_names(...)`：按 SASFieldName 构造 `_ANCHOR`。
  - `compare_columns_by_sas_names(...)`：按 SASFieldName 比较列变化。
- `excel_header_utils.py`
  - `read_single_sheet_from_excel(...)`：读取 Sheet 数据与 SAS 元数据。
- `excel_utils.py`
  - `replace_worksheet_headers(...)`
  - `apply_highlight_to_worksheet(...)`
- `processing_control.py`
  - `check_stop_frequently(...)`：检测停止标志并抛 `InterruptedError`。

## 对外接口

领域层被以下模块调用：

- `src/backend/application/comparison_runner.py`：默认调用 `process_edc_multithreaded`。
- `src/gui/main_window.py`：历史 GUI 后台线程调用领域流程。
- `src/backend/infrastructure/file_runtime.py`：与文件运行时能力协同处理 Excel 文件。

领域层不直接暴露 HTTP API，也不负责用户输入协议建模。

## 关键依赖与配置

- `pandas`：承载 Sheet 数据与行列差异计算。
- `openpyxl`：读取 workbook、写入结果、应用样式和 Sheet tab 色。
- `ThreadPoolExecutor`：并发处理多个 Sheet。
- `ConfigManager`：提供锚点行、表头行、排除 Sheet、默认键、颜色、线程数等配置。
- `log_func`、`progress_func`、`stop_flag`：由上层注入，用于观测进度和支持取消。

## 数据模型

- `SheetProcessResult`：单 Sheet 结果容器。
- pandas `DataFrame`：核心数据结构。
- `DataFrame.attrs`：保存 SAS 元数据，例如：
  - `sas_file_name`
  - `sas_file_label`
  - `sas_name_to_label`
  - `_add_sas_names`
  - `_del_sas_names`
- `_ANCHOR`：内部锚点列，用于按关键字段识别行级变化。

## 测试与质量

对应测试：

- `tests/test_processing_control.py`
- `tests/test_sheet_process_result.py`
- `tests/test_highlight_optimizer.py`
- `tests/test_import_smoke.py`

质量注意：

- `InterruptedError` 是用户停止操作的正常控制流，必须继续传播。
- 不要把停止异常包进普通失败结果，也不要在 broad `Exception` 中吞掉。
- `read_single_sheet_from_excel` 需要在异常或中断时关闭 workbook。
- 大数据处理逻辑应避免不必要的全量复制；但共享参数对象不要就地修改。
- 修改高亮、锚点或列比较逻辑前，应增加最小 Excel/DataFrame 级单元测试。

## 常见问题 (FAQ)

### 锚点列 `_ANCHOR` 从哪里来？

`create_anchor_by_sas_names` 根据配置中的关键 SAS 字段，在 DataFrame 中拼接匹配列生成 `_ANCHOR`。如果缺少 SASFieldName 信息，会记录告警并置空锚点。

### 新增/删除 Sheet 如何表现？

领域层分别通过 `process_new_sheet` 与 `process_missing_sheet` 处理，并在输出 workbook 中保留数据、标记 Sheet 状态和颜色。

### 为什么中断要用 `InterruptedError`？

测试已覆盖中断传播。上层 Web/API 会将 `InterruptedError` 映射为 HTTP 409，GUI 会用它恢复 UI 与记录用户停止。

### `data_comparison.py` 是否适合直接继续扩展？

可以小步修改，但不建议继续堆叠大函数。新增复杂逻辑应优先抽小函数并补测试，避免扩大核心文件维护风险。

## 相关文件清单

- `data_comparison.py`
- `excel_header_utils.py`
- `excel_utils.py`
- `highlight_optimizer.py`
- `highlight_utils.py`
- `dataframe_utils.py`
- `processing_control.py`
- `sheet_process_result.py`
- `__init__.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `backend/domain` 模块 Claude 指南。 |
