# Verified Color Flow and Regression Evidence

## Evidence Status

Inspected from committed `main` at `b28b458` during planning on 2026-10-15. Findings below are static code evidence, not executed test results. Recheck line anchors when implementing against a newer revision.

## Source Anchors

| Question | Verified evidence |
| --- | --- |
| Which setting is presented to users as addition color? | `frontend/src/components/ColorSettings.vue:8-12`: labels map update to `highlight_fill`, deletion to `missing_sheet_tab`, and addition to `new_sheet_tab`. `src/shared/contracts.py:6-10` defines those same three fields. |
| Are defaults and overrides reusable without a new setting? | `src/backend/infrastructure/config_manager.py:31-37` normalizes color strings; `:60-78` applies default/overridden colors to the existing fills. The frontend defaults agree in `frontend/src/composables/useConfig.js:4-8`. |
| Why are added data rows wrong? | `src/backend/domain/excel_utils.py:154-160`: markers `新增` and `删除` share one branch whose row loop always assigns `config.highlight_fill`. |
| What must stay correct for updated records? | `src/backend/domain/excel_utils.py:161-177`: updated records use the position-based diff dictionary and apply update fill only to named changed cells. `:137-148` keeps diff-key normalization outside the loop and cancellation inside it. |
| Are added-column headers already correct? | `src/backend/domain/excel_utils.py:97-118`: header positions resolve SAS field names; added headers use `new_sheet_tab_fill`, deleted headers use `missing_sheet_tab_fill`; ordinary headers keep the existing blue. |
| Are new-sheet tabs already correct? | `src/backend/domain/data_comparison.py:1583-1595`: `new` uses addition color, `missing` uses deletion color, `data_changed` uses update color. |
| Will one shared row-fill change reach new-sheet data? | `src/backend/domain/data_comparison.py:189-217` and `:299-335` route new-only and empty-to-populated sheets to `process_new_sheet`; `:544-570` sets markers and metadata; `:1546-1557` calls the shared highlighter for collected results. |

## Existing Tests to Reuse, Not Replace

- `tests/test_highlight_stop_and_perf.py:53-86`: cancellation and an unset stop flag. Its added row is not checked against an exact addition color.
- `tests/test_highlight_stop_and_perf.py:89-115`: updated-cell-only fill and deleted-row `highlight_fill` compatibility. This task deliberately preserves the deletion assertion.
- `tests/test_highlight_stop_and_perf.py:118-175`: equivalent output for different diff-key types and only one diff-key construction.
- `tests/test_merge_deleted_data_alignment.py:45-86`: filtered output indices and positional diff ownership.
- `tests/test_merge_deleted_data_alignment.py:89-167`: small synthetic workbook helper and saved-report checks for merge-disabled alignment / merge-enabled record markers.
- `tests/test_compare_scope_and_order.py:15-38`: compact real-workbook and `ConfigManager` pipeline setup; `:79-102` demonstrates the registered integration marker and summary-first sheet ordering.
- `tests/test_highlight_optimizer.py` and `tests/test_processing_control.py`: existing auxiliary highlighting and stop-control coverage included in the focused regression command.

## Constraints for the New Tests

- Add a task-specific `tests/test_highlight_colors.py`; do not use the optimizer's cache as a proxy for the actual workbook writer.
- Assert exact configured RGB/ARGB plus solid fill. Checking only `fill_type` would miss the present wrong-color defect.
- Use distinct palette values so addition/update/deletion cannot accidentally compare equal. Include default and overridden palettes.
- Use SAS metadata different from visible labels in a header test to protect the existing field-name lookup.
- Test saved/reopened workbooks, not only a stubbed sheet type or in-memory helper.
- Keep each test focused on one behavior; parameterize independent input variations and avoid global mutable workbooks.
- Only `slow` and `integration` markers are registered (`pyproject.toml:106-115`). Follow the existing convention rather than changing test configuration to add markers.
- Overall coverage has not been measured in this planning turn. Preserve the global minimum/no-decrease requirement and report an incompatible pre-existing baseline explicitly.

## Scope Interpretation

The repair proposal fixes whole-row additions only, following the recommendation immediately preceding the user's request to create a task. No deletion-color or added-column-body redesign is implied. New-sheet ordinary headers stay ordinary headers; a new sheet's data rows are additions. Final implementation approval remains pending.
