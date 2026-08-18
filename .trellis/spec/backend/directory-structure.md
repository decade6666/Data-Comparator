# Directory Structure

> How backend-adjacent code is organized in this project.

---

## Overview

This repository is a Linux Web/API runtime.
In this project, "backend" means the non-UI application logic that reads Excel files,
compares datasets, writes reports, manages runtime configuration, and coordinates worker threads.

The current separation is:

- `src/frontend/` for the FastAPI Web API boundary (`web_api.py`)
- `src/backend/application/` for application orchestration services such as comparison running, path validation, and output-path generation
- `src/backend/domain/` for Excel reading, comparison, write-back, highlighting, and stop-control domain logic
- `src/backend/infrastructure/` for runtime configuration, progress coordination, temp files, preprocessing, and JSON parameter persistence
- `src/shared/` for cross-layer contracts and pure helpers
- `tests/` for the pytest suite

The current HTTP boundary is the thin FastAPI module `src/frontend/web_api.py`.
Do not add framework-specific routing inside `src/backend/domain/` or `src/backend/infrastructure/`.

---

## Directory Layout

```text
src/
├── main_web.py                     # Linux Web/API entry used by package scripts
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
│   │   ├── parameter_templates.py  # Built-in config templates (protected)
│   │   └── progress_manager.py     # Thread-safe progress/log coordinator
│   └── __init__.py
├── frontend/
│   └── web_api.py                  # FastAPI request/response boundary
└── shared/
    ├── contracts.py                # Cross-layer typing contracts
    └── log_utils.py                # Console + callback logging helper
```

Related non-source folders:

- `docs/` stores user/developer documentation
- `tests/` stores pytest coverage for backend/application/domain/infrastructure/shared behavior
- `.trellis/spec/backend/` stores project conventions for future AI sessions

---

## Module Organization

### Put logic by responsibility, not by framework layer names

- Put Excel comparison workflow in `src/backend/domain/`
- Put path validation, output-path generation, and framework-agnostic comparison orchestration in `src/backend/application/`
- Put runtime adapters such as temp files, config translation, progress, and JSON persistence in `src/backend/infrastructure/`
- Put FastAPI request/response boundaries in `src/frontend/`
- Put pure cross-layer contracts and logging helpers in `src/shared/`

### Current delegation pattern

1. Web API collects parameters and starts user actions
2. Application services validate paths, translate parameters, and build output/log locations
3. Infrastructure translates runtime config and coordinates progress/file preprocessing
4. Domain code executes the comparison pipeline and workbook write-back
5. Shared helpers provide typing contracts and callback logging

### Placement rules

- Do not import FastAPI routing into `src/backend/domain/` or `src/backend/infrastructure/`
- Do not create long-term compatibility shims for old `src.core` or `src.utils` imports
- Do not create temporary runtime artifacts under the repo root; use `get_app_temp_dir()`

---

## Naming Conventions

- Python modules use `snake_case`, for example `data_comparison.py` and `parameter_repository.py`
- Coordinator classes commonly use the `*Manager` suffix, for example:
  - `ConfigManager`
  - `ThreadSafeProgressManager`
- Helper modules are named after the domain they operate on:
  - `file_runtime.py`
  - `excel_header_utils.py`
  - `highlight_optimizer.py`
- Entry points stay shallow:
  - Web/API package entry: `src/main_web.py`

---

## Examples

### Example 1: Web API orchestrates, backend domain executes

`src/frontend/web_api.py` maps the request to a `ParameterDocument` and calls the application runner,
which delegates the actual comparison to `process_edc_multithreaded(...)` in `src/backend/domain/data_comparison.py`.

```python
output_path = run_comparison(
    request.to_parameter_document(),
    config_name=request.config_name,
    log_func=_api_log,
)
```

### Example 2: Runtime config is translated by ConfigManager

`src/backend/infrastructure/parameter_repository.py` persists raw JSON-like parameters, while
`src/backend/infrastructure/config_manager.py` converts them into runtime fields and `PatternFill` objects.

```python
self.anchor_row_num = parameters.get("anchor_row_num", 1)
self.max_workers = parameters.get("max_workers", self.max_workers)
self.highlight_fill = self._create_fill(colors.get("highlight_fill"))
```

### Example 3: Infrastructure helpers own temp workbook copies

`src/backend/infrastructure/file_runtime.py` owns temp-path, protection-removal, and workbook-preprocessing helpers instead of spreading them across application or domain modules.

```python
new_file_name = f"{original_filename}_nofilter_{timestamp}{ext}"
new_file_path = os.path.join(temp_app_dir, new_file_name)
```
