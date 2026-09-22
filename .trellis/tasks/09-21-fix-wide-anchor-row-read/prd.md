# 修复锚点行宽于数据行导致整表读取失败并误判为缺失表单

## Goal

让「锚点/表头行比数据行宽」的 Excel 表单能被正常读取并参与比对；当读取确实失败时，失败必须显式可见，而不是被伪装成「该表单已被删除」并让任务报成功。

用户价值：报告不再凭空宣称整张表被删除；真出问题时用户能第一时间看到，而不是拿着一份看似成功、实则错误的报告做决策。

## Background / 已确认事实

线上日志（4 个表单全中）：

```
❌ 读取Sheet [AE--不良事件] 失败: 22 columns passed, passed data had 16 columns
ℹ️ 检测到缺失Sheet: [AE--不良事件]，跳过比对
✅ Sheet [AE--不良事件] 处理完成。
...
✅ 文件保存完成
```

崩溃链路（已逐行核对 + 本机复现）：

1. `src/backend/domain/excel_header_utils.py:45-46` **无条件**调用 `ws.reset_dimensions()`。
2. openpyxl 3.1.5：`ReadOnlyWorksheet.iter_rows` 中 `max_col = max_col or self.max_column`；`reset_dimensions()` 把 `_max_column` 置 `None` 后 **`max_column` 属性不会自动重算**（`calculate_dimension()` 不带 `force=True` 直接抛 `ValueError`，而 `iter_rows` 没有调用它）。于是 `_cells_by_row` 传 `max_col=None`，`_get_row` 落到 `max_col = max_col or row[-1]['column']` —— **每行按自己最后一个单元格定宽，行宽不齐**。
3. `excel_header_utils.py:168-183` 的补齐逻辑只有 `if len(sas_field_name) < actual_num_cols` 一侧（补 `Unnamed_i`）。注释写的是「进行填充或截断」，但**实际没有截断代码**，管不到「列名比数据宽」。
4. `excel_header_utils.py:187` `pd.DataFrame(data_rows, columns=sas_field_name)` → `ValueError: N columns passed, passed data had M columns`。
5. `excel_header_utils.py:246-253` broad `except Exception` → 打印 `❌ 读取Sheet [...] 失败` → `return None`。
6. `data_comparison.py:155-156` 把 `None` 与「sheet 不存在」等同；`:207-231` 走缺失分支 → `process_missing_sheet`（`:480`）给旧表**每一行**打 `更新情况（标记）= "删除"` → `result.success = True` → 任务终态 ✅。

### 本机复现（关键修正）

复现脚本 `/tmp/repro_wide_anchor.py`：一个 **dimension 声明完全正确**（`A1:F4`）的 4 行 3 列工作簿，仅在第 1、2 行的 D/E/F 列加底色不填值：

```
dimension 声明 : A1:F4
reset_dimensions 后逐行宽度 : [6, 6, 3, 3]
返回值 : None
LOG: ❌ 读取Sheet [S1] 失败: 6 columns passed, passed data had 3 columns
```

**结论：本缺陷与 CRF-Editor 的畸形 `<dimension ref="A1"/>` 无关。** 因为 `reset_dimensions()` 是无条件调用的，任何文件只要锚点/表头行比数据行多出尾部单元格（哪怕只有样式、没有值）就会触发。影响面远大于畸形 dimension 文件。

### 与历史任务的关系

`08-23-fix-empty-read-and-project-state` 引入了 `reset_dimensions()`，其 PRD 的 Risks 一节写道：

> `reset_dimensions()` 后行宽可能不齐：现有代码已按 `max(len(row))` 补 `Unnamed_i` 列名、DataFrame 以 NaN 补齐（已实测），**无需额外处理**。

该判断只覆盖了「数据宽于列名」一侧，遗漏了反方向。本任务是那条风险的兑现，**修复不得回退 `reset_dimensions()`**，否则 `08-23` 的「成片均为空」缺陷会复发。

### 现有测试缺口

`tests/test_excel_header_utils.py` 4 条全过。其中 `test_ragged_rows_are_padded_after_dimension_reset`（`:117`）只覆盖「数据宽于列名」一侧，反方向无覆盖。

## Requirements

- **R1 双向列宽对齐**：`read_single_sheet_from_excel` 在构造 DataFrame 前必须同时处理两个方向的宽度不一致，不得抛 `ValueError`。
  - R1.1 数据宽于列名（现状已支持）：行为**逐字节不变**，继续补 `Unnamed_i`。
  - R1.2 列名宽于数据（本次修复）：正常返回 DataFrame。
  - R1.3 尾部「有样式无值」单元格产生的空列名，不得进入最终 DataFrame 的列集合而污染下游（具体裁剪/补名策略见 `design.md`，依赖 research 结论）。
  - R1.4 锚点行尾部**真实声明但无数据**的 SAS 字段名不得被丢弃 —— 这类字段是已声明 schema 的一部分，参与列级新增/删除判定。

- **R2 读失败不再伪装成缺失表单**：`read_single_sheet_from_excel` 的返回值必须让调用方能区分三种情况：读成功、sheet 不存在、读取失败。`data_comparison.py` 的缺失/新增分支只允许在「sheet 不存在」时进入。

- **R3 失败必须可见**：任一 sheet 读取失败时，失败表单不得以「整表删除」的错误形态出现在报告中，
  且日志末尾必须有一条集中的失败汇总（表单名 + 原因），而不是只有散落在滚动日志中间的单行 ❌。
  **用户决策（2026-09-21）**：采用日志汇总方案，**报告结构完全不变**，不新增「读取失败表单」工作表。
  已知并接受的残留：任务终态仍为 `completed`。

- **R4 不破坏停止语义**：`InterruptedError` 必须继续无损传播，不得被 R2/R3 的新分支捕获或降级（现有约定见 `excel_header_utils.py:239-245`）。

- **R5 不扩大改动面**：不重写 `reset_dimensions()` 策略，不改 `xlsx_filter_cleaner`，不改比对算法本身。

## Acceptance Criteria

- [ ] 新增回归测试：锚点行 6 宽（含 3 个有样式无值的尾部单元格）、数据行 3 宽、**dimension 声明正确**的工作簿，`read_single_sheet_from_excel` 返回非 None 且数据完整；该测试在修复前失败、修复后通过。
- [ ] 新增回归测试：锚点行尾部是**真实字段名**（非空）但无对应数据列时，这些字段保留在 `df.columns` / `df.attrs['sas_file_name']` 中，对应数据为 NaN/None（覆盖 R1.4）。
- [ ] 新增回归测试：最终 `df.columns` 不含空字符串列名，且无重复列名（覆盖 R1.3）。
- [ ] 现有 `tests/test_excel_header_utils.py` 4 条全部仍通过（R1.1 不回归）。
- [ ] 新增测试：读取失败时 `data_comparison` **不**进入缺失/新增表单分支，不会把旧表整表标记为「删除」（覆盖 R2）。
- [ ] 新增测试：读取失败的 sheet 被聚合层收集，保存前日志出现 `⚠️ 共 N 个表单处理失败:` 汇总及逐条原因（覆盖 R3）。
- [ ] 新增测试：无失败表单时，输出 workbook 的工作表集合与改动前一致（报告结构不变，覆盖 R3 的「不新增工作表」约束）。
- [ ] 新增测试：读取过程中 `InterruptedError` 仍原样抛出，未被新增分支吞掉（覆盖 R4）。
- [ ] `pytest` 全量通过；后端覆盖率不低于改动前。
- [ ] 真实文件端到端复跑用户那两个文件：4 个表单（AE / PR / CM / MH）不再出现 `❌ 读取Sheet ... 失败` 与 `检测到缺失Sheet`，报告中这些表单有真实比对结果。

## Out of Scope

- 回退或重做 `reset_dimensions()` 策略（会导致 `08-23` 缺陷复发）。
- 修改 `xlsx_filter_cleaner.py` 筛选器清理逻辑。
- 修改比对算法（锚点构造、差异识别、高亮）本身。
- 收敛 `read_single_sheet_from_excel` 里其他与本缺陷无关的 broad `except`。
- `validate_excel_file` 对 `autoFilter ref="1:1"` 的误判（历史遗留待办）。

## Risks

- **R2/R3 改的是错误语义，影响面比 R1 大**：`None` 的含义变化会波及 `data_comparison.py` 的分支判断与结果聚合。必须先由 research 摸清 `SheetProcessResult` 与 `process_edc_multithreaded` 的汇总方式，沿用既有惯例而非另造一套。
- **补齐可能造成空列名 / 重名列**：pandas 允许重名列，但 `df[col]` 会返回 DataFrame 而非 Series，`drop(columns=)`、`name_to_label_map` 字典推导会互相覆盖。R1.3 必须在 design 阶段确定裁剪顺序（先裁后补，不能反）。
- **前端可能有 sheet 状态枚举映射**：若 R3 引入新状态串，需同步前端，否则出现未知状态显示异常。

## 参考（file:line）

- `src/backend/domain/excel_header_utils.py:45-46`（无条件 reset_dimensions）、`:73-80`（表头行读取）、`:117-136`（数据行读取）、`:168-183`（单向补齐）、`:187`（DataFrame 构造）、`:239-245`（InterruptedError 传播）、`:246-253`（broad except → None）
- `src/backend/domain/data_comparison.py:136-156`（两次读取与 None 归一）、`:173-231`（均不存在 / 新增 / 缺失三分支）、`:467-497`（process_missing_sheet 整表标记删除）
- `tests/test_excel_header_utils.py:117-137`（只覆盖反方向的 ragged 测试）
- 历史任务：`.trellis/tasks/archive/2026-08/08-23-fix-empty-read-and-project-state/prd.md`（Risks 一节的错误判断）
- 复现脚本：`/tmp/repro_wide_anchor.py`
