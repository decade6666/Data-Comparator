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

`create_anchor_by_sas_names` 根据配置中的关键 SAS 字段，在 DataFrame 中拼接匹配列生成 `_ANCHOR`。

若无法构造有效锚点（缺少 SASFieldName 信息、一个关键字段都匹配不上、匹配到的字段不在实际列中、拼接过程出错），会抛出 `AnchorUnavailableError` **快速失败**，由 `process_single_sheet_complete` 标记该表单 `success=False` 并跳过，其余表单照常比对。

**不要退回到「置空锚点后继续」的写法**：全表同值的 `_ANCHOR` 会让 `perform_full_comparison` 的 `pd.merge(on="_ANCHOR", how="outer")` 退化为笛卡尔积（N_new × N_old）。2026-09-15 线上事故即由此引发——1MB 以内的输入文件跑出 12.9 GB 内存、3 小时 CPU 时间且无法结束。

注意 `AnchorUnavailableError` 必须在 `perform_full_comparison` 里显式重抛（排在宽 `except Exception` 之前），否则会被吞掉并返回空元组，导致调用方把表单误判为「处理成功但无数据」。

锚点**重复**是合法场景，只告警不失败。`_guard_anchor_cardinality` 作为纵深防御，仅在新旧两侧锚点都塌缩为单一取值且行数乘积超阈值时拦截。

### 高亮写回有哪些性能与中断约束？

`apply_highlight_to_worksheet` 的差异字典 `diff_keys` 必须在行循环**外**只构建一次；放进循环会让复杂度退化为 O(行数 × 差异数)。该函数接受 `stop_flag`，并用 `check_stop`（带计数器节流）在行循环内定期检查，使大表单的高亮阶段也能响应「停止比对」。

### `diff_dict` 的键为什么必须跟着行过滤一起重映射？

高亮是**按位置**反查的：写 Excel 用 `dataframe_to_rows` 按位置顺序写，`apply_highlight_to_worksheet` 用 `data_row_idx = row_idx - 2` 反算位置。因此 `diff_dict` 的键必须始终等于**输出 DataFrame 中的位置**。

`perform_full_comparison` 在 `merge_deleted_data=False` 时会剔除「删除」行，这会让后续行的位置整体前移。**任何删除或重排输出行的操作，都必须同步重映射 `diff_dict` 的键**，否则从第一条被剔除的记录往后，每一行都会取到别人的差异集——未变的单元格被标成变化，真正变化的被漏掉；新增/删除行的「整行差异集」被更新行读到时症状尤其明显（整行铺色）。

只 `reset_index(drop=True)` 不够：那只改了 DataFrame 的索引，`diff_dict` 的键不会跟着变。回归测试见 `tests/test_merge_deleted_data_alignment.py`。

### 新增/删除 Sheet 如何表现？

领域层分别通过 `process_new_sheet` 与 `process_missing_sheet` 处理，并在输出 workbook 中保留数据、标记 Sheet 状态和颜色。

### 为什么中断要用 `InterruptedError`？

测试已覆盖中断传播。上层 Web/API 会将 `InterruptedError` 映射为 HTTP 409。

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
| 2026-09-21 | fix | `perform_full_comparison` 在 `merge_deleted_data=False` 剔除「删除」行后，同步把 `diff_dict` 的键从「过滤前行索引」重映射到「过滤后位置」。此前只有行被剔除、键没变，导致从第一条删除记录往后高亮整体错位（真实数据：908 个更新行中 302 行高亮错误）。 |
| 2026-09-15 | fix | 锚点不可用改为抛 `AnchorUnavailableError` 快速失败（此前置空 `_ANCHOR` 继续，导致 `pd.merge` 退化为笛卡尔积）；`perform_full_comparison` 显式重抛该异常并在 merge 前加 `_guard_anchor_cardinality` 防爆闸；`apply_highlight_to_worksheet` 的 `diff_keys` 提出行循环（O(N×M) → O(N+M)）并新增 `stop_flag` 支持。 |
| 2026-05-24T03:25:49 | docs | 初始化 `backend/domain` 模块 Claude 指南。 |
