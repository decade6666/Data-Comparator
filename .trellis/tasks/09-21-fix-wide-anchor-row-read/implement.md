# Implement: 修复锚点行宽于数据行导致整表读取失败并误判为缺失表单

## 工作区

**所有代码改动在 worktree 内进行，不在 main 上改代码：**

```bash
cd /root/github/Data-Comparator/.claude/worktrees/fix+wide-anchor-row-read   # 分支 fix/wide-anchor-row-read
```

Trellis 任务产物（`prd.md` / `design.md` / `implement.md` / `research/`）保留在主检出
`/root/github/Data-Comparator/.trellis/tasks/09-21-fix-wide-anchor-row-read/`，实现子代理以绝对路径读取。

改动文件白名单（超出需回到规划）：

- `src/backend/domain/excel_header_utils.py`
- `src/backend/domain/data_comparison.py`
- `tests/test_excel_header_utils.py`
- `tests/test_sheet_read_failure.py`（新建）

---

## Stage 1 — L1 双向列宽对齐

### 1.1 RED：先写失败测试

在 `tests/test_excel_header_utils.py` 追加（复用既有 `_make_workbook` / `_force_dimension_a1` fixture 风格）：

| 测试名 | 构造 | 断言 |
|---|---|---|
| `test_styled_empty_tail_in_anchor_row_does_not_break_read` | dimension **正确**的 4 行 3 列表，第 1、2 行 D/E/F 加 `PatternFill` 不填值 | 返回非 `None`；`df.shape == (2, 3)`；`list(df.columns) == ["K1","K2","K3"]` |
| `test_declared_but_dataless_tail_fields_are_kept` | 锚点行 5 个**真实字段名**，数据行只有 3 列 | `df.shape == (n, 5)`；后 2 列全为 NaN；`df.attrs["sas_file_name"]` 含全部 5 个名字（R1.4） |
| `test_no_empty_or_duplicate_column_names` | 锚点行含 2 个**中段空洞**（如 `["K1","","K3","","K5"]`） | `df.columns` 无空串；`len(set(df.columns)) == len(df.columns)`；空洞位为 `Unnamed_1` / `Unnamed_3`（绝对下标） |
| `test_label_and_name_lengths_stay_aligned` | 表头行比锚点行长 | `len(df.attrs["sas_file_label"]) == len(df.attrs["sas_file_name"]) == len(df.columns)` |

```bash
pytest tests/test_excel_header_utils.py -v --tb=short   # 预期：4 条新增全红，4 条既有全绿
```

**门禁**：新增测试必须先失败。若某条一开始就通过，说明构造没复现场景，回头改构造而不是改断言。

### 1.2 GREEN：改 `excel_header_utils.py`

按 `design.md` L1 三步实现：

1. 模块级加两个私有辅助函数 `_is_blank(value) -> bool` 与 `_trim_trailing_empty(values) -> List[Any]`（带类型标注，PEP 8）。
2. 表头行读取（`:71-80`）后对 `sas_field_label` / `sas_field_name` 各自裁尾 —— **裁尾必须在 `:94-110` 锚点重复检查之后**，不要改动该检查的位置与逻辑。
3. 数据行读取（`:117-136`）后对每条 `row_values` 裁尾。注意空行终止判定（`:127-134`）保持在裁尾**之前**执行，语义不变。
4. 用 `design.md` 给出的第 2 步代码替换现有 `:168-183` 的单向补齐；第 3 步的 `Unnamed_{i}` 规范化紧随其后、在 `:187` 构造 DataFrame 之前。

```bash
pytest tests/test_excel_header_utils.py -v --tb=short   # 预期：8 条全绿
```

### 1.3 验证根因确已消除

```bash
python3 /tmp/repro_wide_anchor.py    # 预期：不再输出 "❌ 读取Sheet [S1] 失败"，返回 DataFrame
```

**回滚点 A**：Stage 1 单独提交。此时线上 4 个表单的崩溃已止血，L2 未做也可独立交付。

---

## Stage 2 — L2 区分读失败与表单不存在

### 2.1 RED：先写失败测试

新建 `tests/test_sheet_read_failure.py`：

| 测试名 | 构造 | 断言 |
|---|---|---|
| `test_missing_sheet_still_returns_none` | 请求不存在的 sheet 名 | 返回 `None`（既有语义不变，防回归） |
| `test_read_failure_raises_sheet_read_error` | 锚点行重复列名（触发 `:110` 的 `ValueError`） | 抛 `SheetReadError`，**不**返回 `None` |
| `test_interrupted_error_still_propagates` | 复用 `tests/test_processing_control.py` 的 stop_flag 手法 | 抛 `InterruptedError`，未被 `SheetReadError` 吞掉（R4） |
| `test_read_failure_does_not_become_missing_sheet` | mock `read_single_sheet_from_excel` 对新文件抛 `SheetReadError` | `process_single_sheet_complete` 返回 `success=False`、`error_message` 非空、`change_type != "missing"`（R2 核心） |
| `test_failed_sheets_logged_in_summary` | 聚合流程含 1 个失败表单 | 日志出现 `⚠️ 共 1 个表单处理失败:` 与该表单名 + 原因；**报告不新增任何工作表**（R3，用户选定日志方案） |
| `test_report_structure_unchanged_when_no_failure` | 全部表单正常 | 输出 workbook 的 sheetnames 与改动前一致，无多余表 |

```bash
pytest tests/test_sheet_read_failure.py -v --tb=short   # 预期：全红
```

### 2.2 GREEN：改两个文件

`src/backend/domain/excel_header_utils.py`：

- 模块级新增 `class SheetReadError(Exception)`。
- `:246-253` 的 broad except：保留 workbook 关闭清理，把 `log_func(...)` + `return None` 换成
  `raise SheetReadError(f"读取Sheet [{sheet_name}] 失败: {e}") from e`（读取层不再自己打 ❌，由上游统一打，避免一条失败两行日志）。
- `:37-39`「sheet 不存在 → `None`」与 `:239-245` `InterruptedError` 分支**一行都不动**。
- 更新 docstring 的 Returns 段，写明三态语义。

`src/backend/domain/data_comparison.py`（只碰两处，不动比对算法与分支结构）：

- 聚合循环 `:1412-1416` 的 `if not result.success:` 内追加 `failed_sheets.append((sheet_name, result.error_message or "未知原因"))`；在循环外初始化 `failed_sheets: List[Tuple[str, str]] = []`。
- 保存前（`log_func("所有表单处理完成，开始保存最终文件...")` 之后、创建「比对结果汇总」`:1590` 之前）打醒目多行汇总日志。
- **不新增任何工作表**（用户决策：日志方案）。`_sheets.sort()`（`:1575`/`:1584`）与汇总表创建（`:1590`）一行都不动。
- 不改 `:450-457` 的异常分支、不改 `:458-462` 的 `finally` 进度更新 —— 它们已经把 `SheetReadError` 处理成 `success=False` + 进度「失败」。

```bash
pytest tests/test_sheet_read_failure.py -v --tb=short   # 预期：全绿
```

**回滚点 B**：Stage 2 单独提交，可独立 `git revert` 而不影响 Stage 1 的止血。

---

## Stage 3 — 全量回归与质量门禁

```bash
pytest -v --tb=short --strict-markers
pytest --cov=src --cov-report=term-missing        # 覆盖率不得低于改动前，且不低于 80%
python3 -m black --check src tests
python3 -m isort --check-only src tests
python3 -m mypy src/backend/domain/excel_header_utils.py   # 按项目现有 mypy 配置
```

重点盯这几个既有测试文件不得回归：

- `tests/test_excel_header_utils.py`（`08-23` 的 dimension A1 回归锁，**绝不能因为本次改动而放松**）
- `tests/test_processing_control.py`（`InterruptedError` 传播链）
- `tests/test_compare_scope_and_order.py`（sheet 顺序与 ignore/common cols；本次动了保存前的 sheet 插入位置）
- `tests/test_xlsx_filter_cleaner.py`（未改动，作为无关性证据）

---

## Stage 4 — 真实文件端到端

```bash
# 用户那两个文件 + 对应配置（锚点行/表头行按项目参数）
```

预期：

- 日志中不再出现 `❌ 读取Sheet [AE--不良事件] 失败: 22 columns passed, passed data had 16 columns`（4 个表单同）。
- 日志中不再出现这 4 个表单的 `ℹ️ 检测到缺失Sheet`。
- 报告中 AE / PR / CM / MH 有真实比对结果，而非整表「删除」标记。
- 报告工作表集合与修复前的「正常情形」一致（本次无失败，故无 `⚠️ 共 N 个表单处理失败` 汇总行）。

**阻塞说明**：Stage 4 需要用户提供那两个真实 xlsx（`.trellis` 与仓库内都没有）。
若拿不到，Stage 1-3 仍可独立完成并交付，Stage 4 记为「未执行」并在最终报告中明示，**不得声称已端到端验证**。

---

## 评审门禁

- Stage 1 完成后：用 `git diff` 人工核对 `excel_header_utils.py` 的裁尾/补齐/规范化三步顺序是否与 `design.md` 一致（顺序错了功能表面正常但留隐患）。
- Stage 2 完成后：确认 `data_comparison.py` 的 diff 只有三处，未触碰比对算法。
- Stage 3 后：跑 `trellis-check`。
- 全部完成后：`code-reviewer`。

## 明确不做

- 不回退 `reset_dimensions()`。
- 不改 `xlsx_filter_cleaner.py`、`file_runtime.py`、前端、Web API 契约、配置契约。
- 不新增任务终态「部分失败」，不新增 sheet 进度状态串。
- 不修 `validate_excel_file` 对 `autoFilter ref="1:1"` 的误判（历史待办）。
- 不清理 `replace_worksheet_headers`（research 证实主流程无调用方的死代码，另记待办）。
