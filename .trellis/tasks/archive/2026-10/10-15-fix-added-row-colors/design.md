# Design: Added-Row Fill Selection

## Boundary and Data Flow

`colors.new_sheet_tab` -> `ConfigManager.new_sheet_tab_fill` -> shared workbook highlighter -> saved Excel cell fills.

The same highlighter already receives common-sheet results and `process_new_sheet` results. Keep this single write-back path. The row marker, not the sheet type or a cell-level difference flag, determines whether an entire data row is an addition.

## Minimal Change

In `src/backend/domain/excel_utils.py::apply_highlight_to_worksheet`, retain the shared branch for markers `新增` and `删除`, its bold red marker font, and its single loop over row cells. Select the fill once for that row:

- `新增`: `config.new_sheet_tab_fill`.
- `删除`: `config.highlight_fill`, preserving current behavior.

Do not allocate new `PatternFill` objects per cell, hard-code green, add a second pass over all rows, or create a new configuration abstraction. Update only immediately affected comments/docstrings if needed. Keep the function signature and all call sites unchanged.

The production patch should be confined to this selection. `data_comparison.py` and `config_manager.py` are evidence/read targets, not planned implementation targets. If round-trip regression tests expose another necessary dependency change, explain it and review its scope before expanding the patch.

## Color and Precedence Contract

| Report element | Expected fill/color after this repair |
| --- | --- |
| Data row marked `新增`, including its marker and blank cells | `new_sheet_tab_fill` for every cell |
| Data row marked `删除` | Existing `highlight_fill` for every cell |
| Data row marked `更新` | Existing `highlight_fill` only for columns in its positional diff entry |
| Unchanged data cells | Existing unhighlighted behavior |
| Added-column header | Existing `new_sheet_tab_fill` |
| Deleted-column header | Existing `missing_sheet_tab_fill` |
| Ordinary header, including a new sheet's ordinary headers | Existing blue header styling |
| New-sheet tab | Existing `new_sheet_tab_fill.start_color` |
| Common-sheet tab with changes / missing-sheet tab | Existing update / missing colors |

Added-column body cells do not receive a new unconditional column fill. For example, a non-empty added field inside a row marked `更新` continues to use the existing changed-cell highlighting. Whole added rows still take their addition fill in every column.

## Compatibility and Invariants

- Keep the three persisted color keys, frontend models, API requests, and defaults unchanged. Older configurations continue to receive the existing default/backfill behavior.
- Compare fills to the configured objects' normalized ARGB values in tests. Existing tests sometimes construct six-digit `PatternFill` values directly; do not rewrite unrelated fixtures merely to normalize their alpha prefix.
- Preserve marker text and bold red font. Fill color is the only intended visible change for added rows.
- Do not move `diff_keys` into the row loop, alter positional row lookup, or remove `check_stop` calls.
- Do not alter row detection, anchors, add/delete column detection, source data, counts, or summary ordering.
- New reports gain the corrected fills; previously generated reports are not migrated or overwritten.

## Test Strategy

Use `tests/test_highlight_colors.py` as one cohesive regression file with local fixtures and distinct unit behaviors. Mark workbook pipeline/round-trip cases with the already-registered `pytest.mark.integration`. Do not add an unregistered `unit` or `e2e` marker: `--strict-markers` is enabled.

1. Unit tests call the real shared highlighter with actual worksheets and `ConfigManager` fills, using default and three distinct custom colors. Cover added rows with blank cells, unchanged/updated/deleted preservation, and headers mapped through SAS names rather than display text.
2. Integration/report end-to-end tests create synthetic input workbooks under `tmp_path`, run the real `process_edc_multithreaded`, reopen the saved report, and assert resulting colors/markers. Cover mixed records under both merge settings, a new-only sheet, an empty-to-populated sheet, and an added-column header/body distinction.
3. Reuse existing cancellation/performance, filtered-row alignment, and scope/order regression suites unchanged unless an expectation demonstrably encodes the intentionally changed added-row behavior. In particular, the deleted-row `highlight_fill` assertion in `tests/test_highlight_stop_and_perf.py:110-115` must remain valid.

No browser validation is needed for the scoped patch: neither the UI nor the API contract changes. Actual serialized workbook inspection is required; in-memory cell assertions alone are insufficient evidence for the report behavior.

## Risk and Rollback

The main risks are accidentally recoloring deletions, hard-coding the default instead of honoring custom colors, and asserting only that a cell is filled rather than checking the exact fill. The matrix above and saved-workbook tests address these risks.

If rollback is necessary, apply a reviewed inverse change only to this task's implementation hunk; retain the diagnostic tests and planning record. Do not reset the branch, discard other changes, or overwrite the original checkout's Trellis toolchain edits.
