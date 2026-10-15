# Use Configured Addition Color for New Rows

## Goal

Make rows marked `新增` use the configured addition color in generated Excel reports, so users can visually distinguish added records from updated or deleted records without changing saved configurations.

## Background and Confirmed Evidence

- The UI labels `colors.new_sheet_tab` as `新增`, `colors.highlight_fill` as `更新`, and `colors.missing_sheet_tab` as `删除` (`frontend/src/components/ColorSettings.vue:8-12`).
- Default colors are addition `#00FF00`, update `#FFE5E5`, and deletion `#DC143C`; `ConfigManager` converts both defaults and configured overrides into fills (`src/backend/infrastructure/config_manager.py:60-78`).
- Added and deleted data rows currently share `config.highlight_fill`, so added rows ignore the configured addition color (`src/backend/domain/excel_utils.py:154-160`). This is the defect owned by R1.
- Added-column headers already use `config.new_sheet_tab_fill` (`src/backend/domain/excel_utils.py:109-118`), and new-sheet tabs already use its start color (`src/backend/domain/data_comparison.py:1583-1595`).
- New-only sheets and existing sheets that go from empty to populated both call `process_new_sheet` (`src/backend/domain/data_comparison.py:189-217`, `src/backend/domain/data_comparison.py:299-335`). That function marks their data rows `新增` and includes the marker in SAS column metadata (`src/backend/domain/data_comparison.py:530-570`); the common writer applies the shared highlighter (`src/backend/domain/data_comparison.py:1546-1557`).

## Requirements

| ID | Requirement |
| --- | --- |
| R1 | Every output data row whose marker is `新增` must use the configured addition color across the entire row, including the marker cell and empty cells. Apply this consistently in common-sheet comparisons, new-only sheets, and empty-to-populated sheets. |
| R2 | Preserve the existing addition color of new-sheet tabs and added-column headers. Existing normal headers must retain their current styling. |
| R3 | Honor both defaults and saved custom colors. Reuse the current three color settings; introduce no new fields, defaults, API contracts, migrations, or dependencies. |
| R4 | Preserve unrelated behavior: deleted rows keep their current `highlight_fill`; updated rows keep highlighting only their changed cells with `highlight_fill`; unchanged cells remain unhighlighted. Preserve marker text/font, row classification, summary semantics, sheet ordering, and `merge_deleted_data` behavior. |
| R5 | Preserve cooperative cancellation, diff-key normalization outside the row loop, and position-based diff alignment after deleted-row filtering. |

## Acceptance Criteria

- [ ] **AC1 — R1/R3:** With default settings, every cell of an added data row has solid addition fill (`FF00FF00` in the normalized workbook color). With three distinct custom colors, the row instead matches the configured `new_sheet_tab_fill`, not a hard-coded green or either other fill.
- [ ] **AC2 — R1/R2:** A saved-and-reopened report containing a new-only sheet has both an addition-colored tab and addition-colored data rows. Its ordinary headers retain existing styling.
- [ ] **AC3 — R1:** A sheet that exists in both inputs but changes from header-only to populated uses the same added-row color as AC1.
- [ ] **AC4 — R2/R3:** Added-column headers retain the configured addition color, including when display labels differ from SAS field names. Deleted-column and ordinary headers retain their existing colors. Added-column body cells continue to follow the existing row/diff rules; the entire column is not newly repainted.
- [ ] **AC5 — R4:** Mixed added/updated/deleted/unchanged records have the expected values and markers; only added rows change fill relative to existing behavior. Verify both `merge_deleted_data=True` and `False` without shifting updated-cell highlights.
- [ ] **AC6 — R5:** Existing cancellation, diff-key single-build, key-type equivalence, and deleted-row alignment regressions remain passing.
- [ ] **AC7 — R1-R5:** Follow RED/GREEN regression testing, run focused and full tests, review the actual diff, and measure coverage against the pre-change baseline. Overall coverage must not decrease and must satisfy the project/global 80% minimum. Report a pre-existing baseline below that floor or missing tools as blockers rather than widening this task silently.

## Out of Scope

- Recoloring deleted rows or redesigning update/deletion color semantics.
- Coloring every added-column body cell with the addition color, or changing cell-level `新增` differences inside a row marked `更新`.
- Repainting all headers of a new sheet with the addition color.
- Adding color settings, changing the frontend, changing comparison/anchor algorithms, or unrelated signature/refactor/formatting work.
- Editing the original checkout's pre-existing Trellis changes, installing dependencies, committing, merging, pushing, or deleting worktrees/branches without the applicable explicit authorization.

## Planning and Handoff Boundary

The user requested task creation and a repair plan for later Sonnet execution, not implementation in this turn. The task stays `planning`; no `task.py start`, product code edits, or code tests are authorized by this planning delivery. A subsequent explicit approval of the final scope is required before execution.

The proposed scope follows the preceding minimal-fix recommendation: fix added-row fills and protect the already-correct tab/header behavior. Any expansion of added-column or deletion coloring requires a new scope decision.

Execution details live in `design.md` and `implement.md`; verified source anchors and test reuse notes live in `research/color-flow.md`.
