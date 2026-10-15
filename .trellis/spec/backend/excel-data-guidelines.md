# Excel Data Guidelines

> Conventions for Excel dataset comparison, output sheet ordering, and ignore-column handling.

---

## Overview

The comparison pipeline in `src/backend/domain/data_comparison.py` reads old/new Excel workbooks,
produces a diff report with highlighting, and writes it to an output workbook.
This file documents the output sheet ordering rules and the ignore-column semantics introduced in 1.7.0.

---

## Output Sheet Ordering and Ignore-Cols (since 1.7.0)

### Output sheet order priority

The order of sheets in the output workbook follows this priority:

1. `sheet_order` — the configured explicit order, if non-empty
2. `include_sheets` — the listed-sheet order is inherited when `sheet_order` is empty
3. source-file order — new-file sheet order first, with old-only sheets appended in their old-file relative order

Sheets not present in the chosen order list are appended at the end by title order,
so the result stays stable and predictable.

The ordering is implemented as `final_wb._sheets.sort(...)` in `process_edc_multithreaded`
and runs BEFORE the summary sheet is created.
The summary sheet relies on that position: it is created with `create_sheet(index=0)` and later
readers assume it lives at `worksheets[1:]` (i.e. it must remain the first sheet).
Formatting is order-independent, so re-sorting existing sheets is safe.

### ignore_cols / sheet_ignore_cols

Columns listed in `ignore_cols` (global) or `sheet_ignore_cols` (per-sheet) stay in the output
workbook but are excluded from diff generation.

- Filtering happens at exactly one point: `compare_columns_by_sas_names` builds
  `non_anchor_compare_cols` without the ignored set.
- Per-sheet resolution uses replace semantics (like `sheet_key_map`): a sheet listed in
  `sheet_ignore_cols` replaces the global `ignore_cols` entirely; unmatched sheets fall back to
  the global set. The resolution happens in `process_single_sheet_complete`.
- Unmatched sheet names are logged, and names are converged against the new file's
  `sas_file_name` before the compare call.
- Column add/delete detection is NOT affected by ignore configuration: added/deleted columns
  are still detected and marked even when they are ignored for diff judgment.

### common_cols / sheet_common_cols

Columns listed in `common_cols` (global) or `sheet_common_cols` (per-sheet) are physically
dropped at READ time — earlier than anchor resolution and diff comparison — so they never appear
in the output workbook and can never serve as anchor columns.

- Drop happens exactly at `read_single_sheet_from_excel` via `cols_to_drop` (keyword arg),
  called from `process_single_sheet_complete`; new/missing-sheet branches receive the
  already-dropped DataFrames.
- Per-sheet resolution uses replace semantics (like `sheet_ignore_cols`): `if sheet_name in
  sheet_common_cols` (membership test, not truthiness — `{"AE": []}` means "drop nothing for
  AE"); unmatched sheets fall back to the global `common_cols`.
- Because dropping is physical and precedes anchor parsing, a dropped anchor column silently
  disables the sheet's anchor; a `⚠️` warning log fires when the effective drop list intersects
  the resolved key columns.
- Do NOT add `sheet_common_cols` to `_EXPORT_STRIP_FIELDS` (config export) or
  `_STRIP_PARAMETER_FIELDS` (history snapshot) — both must keep per-sheet parameters.

### Tests

`tests/test_compare_scope_and_order.py` covers include_sheets / ignore_cols / sheet_order
behavior end-to-end.

---

## Ragged Rows After `reset_dimensions()` (invariant)

`read_single_sheet_from_excel` calls `ws.reset_dimensions()` **unconditionally**
(`src/backend/domain/excel_header_utils.py`). This is required: CRF-Editor exports hard-code
`<dimension ref="A1"/>`, and openpyxl's read-only mode would otherwise truncate every sheet to 1x1.
**Do not remove or make this call conditional** — doing so reintroduces the "所有表单均为空" defect.

The consequence must be handled every time: after `reset_dimensions()`, `ReadOnlyWorksheet.iter_rows`
computes `max_col = max_col or self.max_column`, and `max_column` is `None` with no automatic
recalculation (`calculate_dimension()` raises unless `force=True`, and `iter_rows` never calls it).
`_get_row` then falls back to `max_col = row[-1]['column']`, so **each row is sized by its own last
populated-or-styled cell** and row widths are not uniform.

pandas hits the same problem and solves it in `OpenpyxlReader.get_sheet_data` with two steps.
This module mirrors them, plus a third step this codebase needs:

1. **Trim trailing blanks per row**, independently for the label row, the anchor row, and every data
   row. This removes styled-but-valueless tail cells, which are common in EDC exports and otherwise
   inflate the anchor row's width beyond the data width.
2. **Pad everything to one global width** = max(label width, anchor width, widest data row).
   Column names pad with `Unnamed_{i}`; data rows pad with `None`.
3. **Normalize blank column names to `Unnamed_{i}`** using the **absolute** index.

Constraints when touching this code:

- The blank predicate must treat `None` as blank. `_normalize_value` returns `None` for empty cells,
  so pandas' `== ""` predicate alone is a no-op here.
- Step order is fixed. Padding before trimming manufactures blank column names instead of removing
  them, and two or more blank names collide.
- Trimming must stay **after** the anchor duplicate-name check and **after** the empty-row
  termination check, so neither changes behavior.
- Pad data rows with `None`, not `""` — this matches `_normalize_value` and keeps NaN semantics.

### Why column names must be unique and non-blank

Blank (`""`) column names are not cosmetic. With two or more of them, `merged_df[col]` returns a
DataFrame instead of a Series and the diff path raises; `.loc[row, col]` returns a Series and
`pd.notna(...)` raises "truth value is ambiguous"; `.loc` assignment raises "cannot reindex on an
axis with duplicate labels". Even a single blank name causes silent wrong output: it enters the
`sas_file_name` set comparison and produces phantom added/deleted columns, forcing
`change_type = data_changed` and mis-highlighting blank-named headers.

Never "fix" a width mismatch by truncating column names to the data width. That silently drops
declared-but-dataless SAS fields, creates phantom deleted columns when old/new truncate
asymmetrically, and — if an anchor key falls in the truncated range — nullifies the anchor entirely,
degrading the merge into a same-key cartesian product.

---

## Row / Header / Tab Color Contract

The single write-back path for report coloring is `apply_highlight_to_worksheet`
(`src/backend/domain/excel_utils.py`), called from the shared writer in
`process_edc_multithreaded` for common, new-only, and empty-to-populated sheets alike.
The three persisted settings reach it through `ConfigManager`: `highlight_fill` (更新),
`missing_sheet_tab_fill` (删除), `new_sheet_tab_fill` (新增, default `#00FF00`).

| Report element | Fill/color |
| --- | --- |
| Data row marked 新增 (marker cell and blank cells included) | `config.new_sheet_tab_fill` on every cell |
| Data row marked 删除 | `config.highlight_fill` on every cell |
| Data row marked 更新 | `config.highlight_fill` only on columns named in its positional diff entry |
| Unchanged cells | no fill |
| Added / deleted column header | `new_sheet_tab_fill` / `missing_sheet_tab_fill`, resolved by SAS field name, not the displayed label |
| Ordinary header (including a new sheet's headers) | built-in blue `A6C9EC` |
| Sheet tab | new → `new_sheet_tab_fill`, missing → `missing_sheet_tab_fill`, data_changed → `highlight_fill` (set in `process_edc_multithreaded`) |

Constraints verified by `tests/test_highlight_colors.py`:

- Whole-row additions are decided by the row marker alone, not by sheet type or cell-level flags.
  New-only and empty-to-populated sheets route through `process_new_sheet` and reach the same
  shared highlighter, so one fill-selection change covers all three sheet paths. `SheetProcessResult`
  leaves `add_sas_names` empty for those branches, which is why a new sheet's ordinary headers
  stay blue — do not "fix" that by populating the list.
- Do not collapse the 新增/删除 branch back to a single shared fill: added rows use the addition
  color while deleted rows keep the update color.
- `diff_keys` normalization stays outside the row loop; the `data_row_idx = row_idx - 2`
  positional lookup and the in-loop `check_stop` calls are load-bearing (see the alignment and
  stop/perf suites).
- Color tests must assert exact solid ARGB, not just fill presence. `ConfigManager` normalizes
  6-digit hex to `FF`-prefixed ARGB, while raw 6-digit `PatternFill` values get a `00` prefix from
  openpyxl — compare cells against the config object's own normalized value.

---
