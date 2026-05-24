# brainstorm: frontend backend split

## Goal

Perform a full frontend/backend migration refactor for this desktop Python app while keeping the overall UI behavior and user-visible interface unchanged, so that the codebase ends with a cleaner package boundary between Tkinter UI concerns and non-UI application/comparison logic.

## What I already know

* This repository is a desktop Python application, not a web service. In this project, “backend” means non-UI logic under `src/core/`, `src/utils/`, and selected runtime/config code rather than HTTP/API layers.
* Current documented architecture already intends a split: `src/gui/` for UI, `src/core/` for Excel comparison workflow, `src/utils/` for helpers, and `src/config/` for low-level defaults.
* The current implementation is only partially split:
  * `src/gui/main_window.py` is 2175 lines and currently mixes widget creation, config CRUD, runtime parameter collection, processing start/stop, log file lifecycle, output naming, and success/error UI handling.
  * `src/core/data_comparison.py` is 1363 lines and owns the comparison pipeline plus file preprocessing, thread-pool orchestration, and workbook output writing.
  * `src/gui/parameter_manager.py` is 570 lines and mixes config persistence with Tkinter-centric ownership (`main_app` reference).
  * `src/utils/gui_update_manager.py` imports Tkinter and still lives outside `src/gui/`, so the current “backend vs frontend” boundary is not clean.
* GUI orchestration currently happens in `src/gui/main_window.py`:
  * manager initialization at `src/gui/main_window.py:293`
  * processing entry at `src/gui/main_window.py:954`
  * background thread orchestration at `src/gui/main_window.py:1054`
* Runtime config flow currently crosses layers like this:
  * UI collects values in `_collect_current_gui_parameters()` at `src/gui/main_window.py:862`
  * GUI saves JSON config via `ParameterManager.save_config_as(...)` at `src/gui/main_window.py:1007`
  * GUI updates `ConfigManager` at `src/gui/main_window.py:1101`
  * GUI invokes `process_edc_multithreaded(...)` at `src/gui/main_window.py:1121`
* Comparison core currently depends on util-side progress/config abstractions, but not on `src/gui/*` imports directly.
* There is no database layer; persistence is JSON config files plus Excel workbooks and temp files.
* The user selected **Approach C**: complete migration/reorganization, with the explicit constraint that the overall UI must stay unchanged.

## Assumptions (temporary)

* “frontend” means Tkinter views, dialogs, `StringVar`/widget state, and direct user interaction.
* “backend” means comparison use-cases, runtime parameter normalization, config persistence rules, output naming, and callback-based progress/logging contracts.
* “UI unchanged” means the visual layout, main workflows, dialog behavior, and output workbook behavior should remain stable from the user's perspective unless a hidden refactor necessity is discovered and approved.

## Open Questions

* None at the architecture-boundary level.

## Requirements (evolving)

* Keep Tkinter widgets, dialogs, and direct `messagebox` interactions in the frontend layer.
* Keep workbook comparison rules in non-UI modules.
* Preserve current config compatibility for saved JSON files and built-in templates.
* Preserve current stop/progress behavior for long-running comparison flows.
* Avoid introducing HTTP/controller/repository abstractions that do not fit this desktop app.
* Complete the migration as a real boundary refactor, not just a small extraction.
* Use explicit top-level packages: `src/frontend`, `src/backend`, and `src/shared`.
* Use a mixed `src/shared` boundary: only pure helpers and truly cross-layer contracts belong there.
* Keep file/JSON persistence, config assembly, runtime adapters, and backend-facing progress/logging adapters out of `src/shared`; they belong in `src/backend/infrastructure` unless they are frontend-only.
* Keep Tkinter-specific runtime helpers in `src/frontend`.
* Keep the overall UI unchanged from the user's perspective.
* Use direct import-path replacement rather than a temporary compatibility layer, unless a hard blocker is discovered during validation.
* Prefer a migration plan that can still be validated incrementally even if the target architecture is a full reorganization.

## Acceptance Criteria (evolving)

* [x] A concrete definition of “frontend/backend split” is agreed for this repo.
* [x] The full-migration target boundary is explicit: which modules end up in frontend, backend, and shared infrastructure.
* [x] The selected delivery strategy is explicit: direct path replacement, not compatibility-first.
* [x] The target package shape is explicit: `src/frontend`, `src/backend`, `src/shared`.
* [x] The backend internal layering depth is explicit: `application` / `domain` / `infrastructure`.
* [x] The exact boundary of `src/shared` is explicit: pure helpers + cross-layer contracts only.
* [x] The implementation plan is broken into dependency-ordered phases with validation after each phase.
* [ ] The selected approach preserves config compatibility, thread-safe UI updates, and current comparison behavior.
* [ ] The overall UI layout and interaction flow remain unchanged after refactor.
* [ ] Packaging, startup entrypoints, and docs remain consistent after the rename.

## Definition of Done (team quality bar)

* Import-smoke tests exist for migrated modules and pass at each phase boundary
* Manual validation covers the desktop golden path because UI behavior must remain unchanged
  * start app from `python run.py`
  * start app from module entrypoint
  * select old/new files and output directory
  * run one successful compare flow
  * stop one in-flight compare flow
  * save/load builtin and custom configs
  * verify import/export/copy/rename/delete config flows
  * verify success and error dialogs still behave normally
* Packaging validation is explicit when entrypoints or package layout change
  * `python -m build`
  * PyInstaller spec validation
* Lint / formatting / narrow validation completed for changed files
* Docs/notes updated if the module boundary meaning changes
* Rollback scope is clear if the refactor becomes too broad

## Out of Scope (explicit)

* Converting the app into a web service or adding HTTP/API layers
* Rewriting the Excel comparison algorithm itself unless required by the split
* Replacing Tkinter/ttkbootstrap with another UI framework
* User-visible UI redesign, workflow changes, or behavior changes unless explicitly approved

## Technical Approach

### Operating rules

* Delivery strategy is still **direct import-path replacement**, but it is applied **per phase**, not as a single unsafe big-bang edit.
* Every phase boundary must leave the app runnable without compatibility shims.
* The first time a package or entrypoint path changes, the corresponding startup/build/docs references must be updated in the same phase.
* New package directories must include `__init__.py` so discovery/build steps do not silently miss them.
* Each phase ends with narrow validation plus `__pycache__` cleanup before the next phase begins.

### Target end-state

* Top-level package shape: `src/frontend`, `src/backend`, `src/shared`.
* Backend layering depth: `src/backend/application`, `src/backend/domain`, `src/backend/infrastructure`.
* `frontend/GUI layer`
  * Tkinter windows, dialogs, widgets, `StringVar` state, theme handling
  * GUI-only update dispatching and message presentation
* `backend/application layer`
  * start/stop use-cases
  * runtime parameter normalization
  * output naming, log-file lifecycle, orchestration of validation + comparison pipeline
  * transitional runtime state previously carried as global config, until fully removed
* `backend/domain layer`
  * Excel comparison pipeline and sheet-level comparison behavior
  * sheet result models and comparison-specific data contracts
* `backend/infrastructure layer`
  * file/JSON persistence
  * runtime service adapters
  * backend-facing progress/logging/config adapters
  * openpyxl-backed config/highlight/output helpers that are not pure domain logic
* `shared layer`
  * pure helpers and cross-layer contracts only
  * no Tkinter knowledge, no persistence ownership, no backend runtime orchestration

### Fixed mapping decisions before coding

* `src/utils/gui_update_manager.py` -> `src/frontend`
* `src/core/data_comparison.py` / `src/core/excel_header_utils.py` / `src/core/excel_utils.py` / `src/core/highlight_utils.py` -> `src/backend/domain`
* `src/utils/config_manager.py` -> `src/backend/infrastructure`
* `src/config/global_config.py` -> transitional `src/backend/application` state, then remove if made obsolete
* `src/utils/progress_manager.py` -> `src/backend/infrastructure`, with its cross-layer contract exposed from `src/shared`
* `src/gui/parameter_manager.py` -> split into frontend-facing controller flow plus backend persistence/repository pieces
* `src/utils/file_utils.py` -> split by symbol, not by file name preservation

### Critical symbol-level decisions

* `read_single_sheet_from_excel` stays canonically owned by the Excel/header module in `src/backend/domain`; stop re-exporting it through `file_utils`
* `set_window_icon` is frontend-only
* `get_resource_path` is a shared helper, but any packaged-layout assumptions must be validated together with build entrypoints
* `BUILTIN_TEMPLATE_CIMS` / `BUILTIN_TEMPLATE_TM` should become shared constants or part of the parameter document contract
* `HighlightOptimizer` must have one canonical implementation before any directory move
* `ParameterDocument`, `ParameterRepository`, `ProgressReporter`, and `LogFunc` become explicit contracts before the larger split proceeds

### Draft mapping from current modules

* `src/gui/main_window.py` -> mostly `src/frontend/main_window.py`, with orchestration extracted to `src/backend/application`
* `src/gui/parameter_manager.py` -> split between `src/frontend` and backend persistence/repository pieces
* `src/utils/gui_update_manager.py` -> `src/frontend`
* `src/core/data_comparison.py` -> `src/backend/domain`
* `src/core/excel_header_utils.py` / `src/core/excel_utils.py` / `src/core/highlight_utils.py` -> `src/backend/domain`
* `src/utils/config_manager.py` -> `src/backend/infrastructure`
* `src/utils/file_utils.py` -> split: pure path/helper pieces to `src/shared`, persistence/runtime/file-preprocessing pieces to `src/backend/infrastructure`, Tkinter/icon-facing pieces to `src/frontend`
* `src/utils/logger.py` / `src/utils/stop_flag_utils.py` -> `src/shared` if they remain pure and UI-agnostic
* `src/utils/progress_manager.py` -> `src/backend/infrastructure`, with a shared-facing progress contract

## Validation Strategy

### Automated minimum bar

* Add import-smoke tests for migrated modules under `tests/`
* Add at least one narrow test that catches broken import graphs and missing package files
* Run targeted pytest after each phase

### Manual smoke checklist per phase

* `python run.py`
* module entrypoint startup
* one successful compare flow
* one stop-in-flight flow
* builtin/custom config save-load flow
* config import/export/copy/rename/delete flow
* success and error dialog sanity check

### Packaging gates

* When package paths or entrypoints change, validate:
  * `python -m build`
  * `scripts/app.spec`
  * launcher references such as `run.py`
  * user-facing startup docs

## Implementation Plan (v1)

### Phase 0 — Pre-move cleanup

* Remove dead UI/packaging imports from backend candidates, especially `src/core/data_comparison.py`
* Deduplicate `HighlightOptimizer` so only one implementation remains
* Decide and document the disposition of `src/config/global_config.py`
* Baseline grep for startup/build/doc references that mention current paths
* Clear `__pycache__` before and after validation

### Phase 1 — Contracts and scaffolding

* Create `src/frontend`, `src/backend`, `src/shared` and backend subpackages with `__init__.py`
* Add shared contracts for `ParameterDocument`, `ParameterRepository`, `ProgressReporter`, and `LogFunc`
* Add import-smoke tests under `tests/`
* Keep runtime behavior unchanged

### Phase 2 — Split `file_utils.py` by symbol

* Move pure helpers to `src/shared`
* Move file preprocessing / JSON / temp-file / workbook-adjacent adapters to `src/backend/infrastructure`
* Move Tkinter/icon helpers to `src/frontend`
* Remove the `file_utils -> excel_header_utils` backward indirection so consumers import the canonical owner directly

### Phase 3 — Frontend-only extraction

* Move `gui_update_manager` and other Tkinter-only runtime helpers into `src/frontend`
* Preserve the current `root.app` initialization order until a safer frontend contract replaces it
* Re-validate start, dialogs, and progress updates

### Phase 4 — Backend domain migration

* Move comparison and Excel-specific domain modules into `src/backend/domain`
* Keep comparison behavior unchanged
* Re-validate compare success path and stop path

### Phase 5 — Application/infrastructure split

* Extract orchestration from `src/gui/main_window.py` into `src/backend/application`
* Split `ParameterManager` into frontend controller responsibilities vs backend repository/persistence responsibilities
* Place `ConfigManager` and related runtime adapters in `src/backend/infrastructure`
* Re-validate config CRUD plus compare flows

### Phase 6 — Entry-point, packaging, and docs alignment

* Move the startup entry module under `src/frontend` if needed
* Update `src/main.py` / `run.py` / `pyproject.toml` / `scripts/app.spec` / build scripts atomically with the path change
* Update user-facing startup docs
* Run build validation and final smoke validation

### Phase 7 — Final cleanup

* Remove obsolete aliases, re-exports, and transitional state that survived earlier phases
* Re-run smoke tests and packaging checks
* Confirm the repo no longer depends on the old `gui/core/utils` boundary semantics

## Decision (ADR-lite)

**Context**: The current codebase already has a nominal GUI/core/utils split, but the real dependency boundary is blurry, especially in `main_window.py`, `parameter_manager.py`, and `gui_update_manager.py`. The user wants a complete migration refactor rather than a small extraction, but does not want the UI to change.

**Decision**: Proceed toward a full frontend/backend reorganization target using direct import-path replacement rather than a temporary compatibility layer, with explicit top-level packages (`src/frontend`, `src/backend`, `src/shared`), a deep backend split (`application`, `domain`, `infrastructure`), and a mixed `src/shared` boundary that only accepts pure helpers and cross-layer contracts, while keeping UI-visible behavior unchanged and using phased validation to control regression risk.

**Consequences**:

* Pros:
  * Cleanest long-term boundary
  * Reduces future coupling and makes backend logic more testable
  * Aligns code organization with the app's actual runtime responsibilities
* Risks:
  * Higher import-path churn and regression surface
  * Harder to validate without a strong automated test suite
  * Each migration phase must leave the app runnable without relying on compatibility shims

## Technical Notes

* Relevant files inspected:
  * `src/gui/main_window.py`
  * `src/gui/parameter_manager.py`
  * `src/core/data_comparison.py`
  * `src/utils/config_manager.py`
  * `src/utils/progress_manager.py`
  * `src/utils/gui_update_manager.py`
  * `docs/开发文档.md`
  * `文件夹结构.md`
* Evidence of current coupling:
  * `src/gui/main_window.py:954` validates paths, auto-saves config, toggles UI state, and spawns a worker thread.
  * `src/gui/main_window.py:1054` collects runtime params, initializes log files, validates files, builds output path, updates `ConfigManager`, and calls core comparison.
  * `src/utils/gui_update_manager.py:1` imports Tkinter and reaches back into `root.app`, so it is infrastructure with UI knowledge rather than pure backend.
  * `src/core/data_comparison.py:20` imports `GUIUpdateManager` symbols even though grep only found the import and no runtime use, which suggests dead coupling.
* Logging constraint:
  * Project guidance prefers callback logging via `log(msg, log_func)`, but current code still has direct `print(...)` inside `src/core/data_comparison.py` and `src/utils/gui_update_manager.py`; any split should avoid spreading that pattern further.
* File-size pressure:
  * `src/gui/main_window.py` = 2175 lines
  * `src/core/data_comparison.py` = 1363 lines
  * `src/gui/parameter_manager.py` = 570 lines
* Existing boundary we should preserve:
  * GUI collects/validates user input
  * Core compares workbooks
  * Utils provide path, config, stop, progress, and logging helpers

### Phase 0 baseline scan findings

* Startup/build path chokepoints confirmed:
  * `run.py` imports `src.main:main`
  * `src/main.py` imports `src.utils.file_utils.set_window_icon` and `src.gui.main_window.DatasetComparatorGUI`
  * `pyproject.toml` pins `dataset-comparator = "src.main:main"`, `dataset-comparator-gui = "src.main:main"`, `entry-point = "src/main.py"`, and `icon = "src/assets/icons/app_icon.ico"`
  * `scripts/app.spec` pins `src/main.py`, `src/config/parameters.json`, and icon candidates under `src/app_icon.ico` and `src/assets/icons/app_icon.ico`
* User-facing docs/build notes that still describe the old layout:
  * `docs/开发文档.md`
  * `文件夹结构.md`
  * `scripts/README_Nuitka.md`
  * `docs/版本更新.md`
* `src/config/global_config.py` currently has no runtime consumers in `src/`; grep only found documentation/spec/PRD references.
* Working disposition for `src/config/global_config.py`:
  * treat it as obsolete dead code, not as an active transitional runtime dependency
  * do not move it into the new package layout unless a real runtime consumer appears later
  * if we remove the tracked file, do it in a phase that also updates docs/spec references and only after explicit confirmation for the deletion step

## Research Notes

### Constraints from our repo/project

* This is a desktop app with callback-based logging and progress, not a request/response service.
* Thread-safe GUI updates are required; background threads must not touch widgets directly.
* Saved JSON config compatibility matters because built-in templates and user configs already exist.
* Large files already exist, so the migration should reduce coupling while keeping the app runnable through each phase.

### Feasible approaches here

**Approach A: Extract an application service from `main_window.py`**

* How it works:
  * Keep Tkinter variables, buttons, dialogs, and listbox operations in `src/gui/`.
  * Extract non-UI orchestration from `start_processing()` / `_processing_thread()` into a backend-facing service module.
  * Pass in plain parameters plus callback adapters for log/progress/stop.
* Pros:
  * Smallest behavioral risk.
  * Directly reduces the biggest hotspot: `src/gui/main_window.py`.
* Cons:
  * Not enough alone for the chosen full migration target.

**Approach B: Split config/runtime orchestration first**

* How it works:
  * Extract config persistence and runtime parameter normalization out of GUI-centric modules first.
  * Create a clearer boundary between `ParameterManager`/JSON persistence and `ConfigManager`/runtime comparison settings.
* Pros:
  * Cleans up a major cross-layer seam.
  * Improves testability for config compatibility.
* Cons:
  * Leaves processing orchestration in `main_window.py` for longer.

**Approach C: Full package-level frontend/backend reorganization** (Selected)

* How it works:
  * Repackage modules around frontend/backend/application boundaries as the target architecture.
  * Preserve UI behavior while migrating responsibilities in phases.
* Pros:
  * Cleanest end-state.
  * Best long-term maintainability if executed carefully.
* Cons:
  * Highest regression risk.
  * Needs explicit delivery strategy and validation checkpoints.

## Expansion Sweep

### Future evolution

* A clean boundary would make later feature work (batch modes, richer config profiles, alternate UIs, or CLI reuse) much easier.
* If we do this well, comparison use-cases can become testable without booting Tkinter.

### Related scenarios

* Config create/import/export/copy/rename/delete flows should stay consistent after the migration, not just the compare button path.
* Progress, stop, success/error dialogs, and log-file handling must remain consistent across all long-running flows.

### Failure & edge cases

* Import-path churn may break startup or packaged builds even if runtime logic is correct.
* Refactor phases must preserve saved-config compatibility and thread-safe UI updates at every checkpoint.
