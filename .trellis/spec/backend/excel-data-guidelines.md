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
