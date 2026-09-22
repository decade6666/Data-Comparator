# Implement · 修复比对任务笛卡尔积爆炸与停止无响应

先读 `prd.md` 与 `design.md`。按顺序执行，每步后跑一次 `pytest` 保持绿灯。

## 步骤 0 · 先写失败测试（TDD，CLAUDE.md 强制要求）

项目 CLAUDE.md：「`data_comparison.py` 是复杂核心文件，修改前必须先阅读相关测试并增加针对性用例」。

先读：
- `tests/test_processing_control.py:219-327` —— `test_perform_full_comparison_propagates_interrupted_error`，
  大量 monkeypatch 假模块（pandas/openpyxl/psutil）的写法，**新测试可直接复用这套 fixture 套路**。
  注意它在 `:301-303` 把 `create_anchor_by_sas_names` 替换成 `lambda *args: args[0]`。
- `tests/test_highlight_optimizer.py` —— 轻量 `Cell` / `Sheet` 假对象，高亮相关测试的既有风格。
- `tests/test_compare_scope_and_order.py` —— 端到端跑真实 Excel 的写法（如需集成级验证）。

新建 `tests/test_anchor_guard.py`：

- `test_anchor_missing_sas_names_raises` —— df 无 `attrs['sas_file_name']` → `AnchorUnavailableError`。
- `test_anchor_no_matched_keys_raises` —— key 与 SAS 列无交集 → `AnchorUnavailableError`，
  断言消息含表单名与期望 key。
- `test_anchor_key_not_in_columns_raises` —— matched key 不在 `df.columns` → 抛异常。
- `test_anchor_duplicate_values_still_allowed` —— **锚点重复是合法的**，不得抛异常（AC3 防误伤）。
- `test_perform_full_comparison_skips_merge_on_anchor_failure` —— monkeypatch `pd.merge`
  为会 `raise AssertionError("merge 不应被调用")` 的桩，断言 `AnchorUnavailableError` 先抛出。
  **这是笛卡尔积回归的核心保护。**
- `test_process_single_sheet_marks_failure_not_raise` —— 断言 `success=False`、
  `error_message` 含「锚点」，且**没有**异常逃逸（AC2：单表单失败不拖垮任务）。
- `test_anchor_guard_blocks_double_collapse` / `test_anchor_guard_allows_normal_duplicates`
  —— 防爆闸的拦与放。

新建 `tests/test_highlight_stop_and_perf.py`：

- `test_apply_highlight_raises_on_stop_flag` —— `stop_flag` 置位 → `InterruptedError`。
  行数要够多以越过 `check_stop` 的 100 次节流。
- `test_apply_highlight_without_stop_flag_unchanged` —— 不传 `stop_flag` 时行为不变（兼容性）。
- `test_apply_highlight_result_equivalence` —— 构造含「更新」「新增」「删除」行与
  `diff_info` 的假 worksheet，断言每个单元格的 `fill` / `font` 与改动前一致（AC4 等价性）。

跑 `pytest tests/test_anchor_guard.py tests/test_highlight_stop_and_perf.py`，确认**全部失败**。

## 步骤 1 · `excel_utils.py` 高亮修复（最低风险，先做）

文件：`src/backend/domain/excel_utils.py`

1. 顶部 import `check_stop`（来自 `.processing_control`，注意与既有相对 import 风格一致）。
2. `apply_highlight_to_worksheet`（`:60-69`）签名末尾加 `stop_flag=None`；docstring 补该参数。
3. 在 `:134` 的 `for row_idx, row in enumerate(ws.iter_rows(...))` **之前**：
   ```python
   diff_keys = {int(k): v for k, v in diff_info.items()} if diff_info else {}
   stop_counter = [0]
   ```
4. 循环体内 `:156-158` 删掉重复构建，改用外层 `diff_keys`；
   把 `if diff_info:` 判断改为 `if diff_keys:`（语义等价，`diff_info` 为空时 `diff_keys` 也为空）。
5. 循环开头插入 `check_stop(log_func, stop_flag, stop_counter)`。

跑 `pytest tests/test_highlight_stop_and_perf.py` → 应转绿。

## 步骤 2 · `data_comparison.py` 锚点快速失败

文件：`src/backend/domain/data_comparison.py`

1. 在 `create_anchor_by_sas_names`（`:908`）**之前**定义 `AnchorUnavailableError(Exception)`。
2. 按 design.md 的表格，把 `:926` / `:936` / `:946` / `:965` 四处 `df["_ANCHOR"] = ""` + `return df`
   改成 `raise AnchorUnavailableError(...)`。错误信息含表单名 + 期望 key + 缺失列名，
   **不含单元格内容**。`:961` 的 `except Exception as e` 分支用 `raise ... from e` 保留原因。
3. **保留** `:955` 的「锚点重复」告警分支不变。
4. `perform_full_comparison`：在 `:890` 的 `except InterruptedError: raise` 之后、
   `:892` 的 `except Exception` **之前**插入 `except AnchorUnavailableError: raise`。
   ⚠️ except 子句按源码顺序匹配，位置错了就会被宽 except 吞掉 —— 这是本任务最容易出错的一步。

跑 `pytest tests/test_anchor_guard.py` → 除防爆闸两条外应转绿。

## 步骤 3 · merge 防爆闸

同文件，新增模块级辅助函数（放在 `perform_full_comparison` 之前）：

```python
def _guard_anchor_cardinality(new_df, old_df, sheet_name, log_func, max_product=1_000_000):
    """双侧锚点均塌缩为单一值时，外连接会退化为笛卡尔积，提前拦截。"""
```

规则严格按 design.md：**仅当**新旧两侧 `_ANCHOR` 去重基数**均为 1** 且
`len(new_df) * len(old_df) > max_product` 时抛 `AnchorUnavailableError`。
其余一律放行（保护 AC3 不误伤）。

在 `:656` 的 `pd.merge` 调用**之前**插入调用。

跑 `pytest tests/test_anchor_guard.py` → 全绿。

## 步骤 4 · 接线 stop_flag

`data_comparison.py:1473-1482` 的 `apply_highlight_to_worksheet(...)` 调用补 `stop_flag=stop_flag`。
确认该处作用域内 `stop_flag` 可见（`process_edc_multithreaded` 的入参）。

## 步骤 5 · 全量验证

```bash
pytest
```

重点确认不回归：
- `tests/test_processing_control.py::test_perform_full_comparison_propagates_interrupted_error`
- `tests/test_compare_scope_and_order.py`
- `tests/test_highlight_optimizer.py`

再跑一次质量工具：`black --check src tests`、`isort --check-only src tests`、`mypy src`
（配置见 `pyproject.toml`）。

## 步骤 6 · 端到端复现验证

用本次事故的真实输入（**只读复制到临时目录，不要动原文件**）：
```
~/.local/share/PyDataCompare/users/7/uploads/4c9f6f72b363450a_*20260602.xlsx   (旧)
~/.local/share/PyDataCompare/users/7/uploads/8c8d336dea1e4666_*20260914.xlsx   (新)
```
配置取 `users/7/configs/羟尼酮IIIc医学审阅列表比对.json`
（`default_keys = [SUBJID, VISITNUM, FORMSEQ, TOPICSEQ]`）。

**预期**：分钟级内完成，日志含 48 条锚点失败记录，报告只含锚点有效的表单，
进程内存维持在正常量级（对照 9/14 那次 8 分钟 / 2.9 MB 的成功运行）。
**不应**再出现 GB 级内存增长或小时级运行。

## 回滚点

三组改动互相独立，可单独回滚：
- 步骤 1（`excel_utils.py`）—— 纯性能与停止响应，语义等价，最安全。
- 步骤 2+3（锚点快速失败 + 防爆闸）—— 有行为变化，是主要风险面。
- 步骤 4（接线）—— 一行。

若步骤 2 导致非预期的表单被跳过，可先只保留步骤 1+3+4：性能问题解决、爆炸被闸门拦住，
锚点兜底维持原状，再单独重新评估步骤 2。
