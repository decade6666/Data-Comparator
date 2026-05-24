# Directory Structure

> How backend-adjacent code is organized in this project.

---

## Overview

This repository is now oriented toward Linux Web/API runtime, with the legacy desktop GUI still present.
In this project, "backend" means the non-UI application logic that reads Excel files,
compares datasets, writes reports, manages runtime configuration, and coordinates worker threads.

The current separation is:

- `src/gui/` for legacy Tkinter windows, dialogs, parameter panels, and user interaction
- `src/frontend/` for FastAPI Web API boundaries and frontend runtime helpers such as window resources and GUI update queues
- `src/backend/application/` for application orchestration services such as comparison running, path validation, and output-path generation
- `src/backend/domain/` for Excel reading, comparison, write-back, highlighting, and stop-control domain logic
- `src/backend/infrastructure/` for runtime configuration, progress coordination, temp files, preprocessing, and JSON parameter persistence
- `src/shared/` for cross-layer contracts and pure helpers
- `scripts/` for packaging and release tooling

The current HTTP boundary is the thin FastAPI module `src/frontend/web_api.py`.
Do not add framework-specific routing inside `src/backend/domain/` or `src/backend/infrastructure/`.

`src/config/` is a deprecated legacy package with no runtime configuration ownership.
Do not add new global defaults there; use `ConfigManager`, built-in templates, or saved JSON config paths instead.

---

## Directory Layout

```text
src/
├── main_web.py                     # Linux Web/API entry used by package scripts
├── main.py                         # Legacy GUI app entry
├── app_icon.ico                    # Primary icon path used by build scripts
├── assets/
│   └── icons/
│       └── app_icon.ico            # Compatibility fallback icon path
├── backend/
│   ├── application/
│   │   ├── comparison_runner.py    # Framework-agnostic comparison application service
│   │   └── processing_service.py   # Path validation and output-path setup
│   ├── domain/
│   │   ├── data_comparison.py      # Main comparison pipeline and sheet workflow
│   │   ├── dataframe_utils.py      # DataFrame ordering helpers
│   │   ├── excel_header_utils.py   # Sheet reading and SAS header extraction
│   │   ├── excel_utils.py          # Workbook write-back and highlight helpers
│   │   ├── highlight_optimizer.py  # Cell/row caches for Excel highlight passes
│   │   ├── highlight_utils.py      # Highlight exports for domain callers
│   │   ├── processing_control.py   # Cooperative stop and progress callbacks
│   │   └── sheet_process_result.py # Per-sheet result container
│   ├── infrastructure/
│   │   ├── config_manager.py       # Runtime config object
│   │   ├── file_runtime.py         # File/path/resource/temp-file helpers
│   │   ├── parameter_repository.py # JSON parameter persistence
│   │   └── progress_manager.py     # Thread-safe progress/log coordinator
│   └── __init__.py
├── frontend/
│   ├── web_api.py                  # FastAPI request/response boundary
│   ├── gui_update_manager.py       # Cross-thread GUI update queue
│   └── window_utils.py             # Window icon/resource helpers
├── gui/
│   ├── main_window.py              # Main window and event orchestration
│   ├── parameter_manager.py        # Saved parameter/config management UI
│   ├── components/                 # Reusable UI widgets
│   └── dialogs/                    # Error/help dialogs
└── shared/
    ├── contracts.py                # Cross-layer typing contracts
    ├── log_utils.py                # Console + callback logging helper
    └── resource_utils.py           # Packaged-resource path helper
```

### Asset duplication note

`app_icon.ico` exists at two paths on purpose:

- `src/app_icon.ico` is the primary location preferred by `scripts/app.spec` and Nuitka build scripts
- `src/assets/icons/app_icon.ico` is the compatibility fallback referenced by `pyproject.toml [tool.pyinstaller]` and the runtime resource search order in `src/frontend/window_utils.py`

Keep both in sync if the icon is ever updated.

Related non-source folders:

- `docs/` stores user/developer documentation
- `scripts/` stores PyInstaller/Nuitka build helpers
- `tests/` stores pytest coverage for backend/application/domain/infrastructure/shared behavior
- `.trellis/spec/backend/` stores project conventions for future AI sessions

---

## Module Organization

### Put logic by responsibility, not by framework layer names

- Put Excel comparison workflow in `src/backend/domain/`
- Put path validation, output-path generation, and framework-agnostic comparison orchestration in `src/backend/application/`
- Put runtime adapters such as temp files, config translation, progress, and JSON persistence in `src/backend/infrastructure/`
- Put FastAPI request/response boundaries, GUI update queues, and window resource helpers in `src/frontend/`
- Put pure cross-layer contracts and resource/logging helpers in `src/shared/`
- Keep Tkinter widgets, dialogs, and `messagebox` calls inside `src/gui/`
- Keep packaging-only logic inside `scripts/`

### Current delegation pattern

1. Web API or legacy GUI collects parameters and starts user actions
2. Application services validate paths, translate parameters, and build output/log locations
3. Infrastructure translates runtime config and coordinates progress/file preprocessing
4. Domain code executes the comparison pipeline and workbook write-back
5. Shared helpers provide typing contracts, resource lookup, and callback logging

### Placement rules

- Do not put workbook comparison rules in `src/gui/`
- Do not import Tkinter widgets into `src/backend/domain/` or `src/backend/infrastructure/`
- Do not create long-term compatibility shims for old `src.core` or `src.utils` imports
- Do not create temporary runtime artifacts under the repo root; use `get_app_temp_dir()`
- Do not move build-only logic into `src/`

---

## Naming Conventions

- Python modules use `snake_case`, for example `data_comparison.py` and `parameter_manager.py`
- Coordinator classes commonly use the `*Manager` suffix, for example:
  - `ConfigManager`
  - `GUIUpdateManager`
  - `ThreadSafeProgressManager`
- Helper modules are named after the domain they operate on:
  - `file_runtime.py`
  - `excel_header_utils.py`
  - `highlight_optimizer.py`
- Entry points stay shallow:
  - Web/API package entry: `src/main_web.py`
  - legacy GUI package entry: `src/main.py`
  - legacy repo entry: `run.py`

---

## Examples

### Example 1: GUI orchestrates, backend domain executes

`src/gui/main_window.py` starts a worker thread, but the actual comparison is delegated to `process_edc_multithreaded(...)` in `src/backend/domain/data_comparison.py`.

```python
result_output_path = process_edc_multithreaded(
    old_path=final_old_path,
    new_path=final_new_path,
    output_path=output_path,
    config=self.config_manager,
    log_func=self.log_message,
    progress_func=self.update_progress,
    stop_flag=self.stop_flag,
)
```

### Example 2: Runtime config is translated outside the GUI

`src/gui/parameter_manager.py` persists raw JSON-like parameters, while `src/backend/infrastructure/config_manager.py` converts them into runtime fields and `PatternFill` objects.

```python
self.anchor_row_num = parameters.get("anchor_row_num", 1)
self.max_workers = parameters.get("max_workers", self.max_workers)
self.highlight_fill = self._create_fill(colors.get("highlight_fill"))
```

### Example 3: Infrastructure helpers own temp workbook copies

`src/backend/infrastructure/file_runtime.py` owns temp-path, protection-removal, and workbook-preprocessing helpers instead of spreading them across GUI or domain modules.

```python
new_file_name = f"{original_filename}_nofilter_{timestamp}{ext}"
new_file_path = os.path.join(temp_app_dir, new_file_name)
```
