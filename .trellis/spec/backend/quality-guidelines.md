# Quality Guidelines

> Code quality standards for backend-adjacent development in this project.

---

## Overview

This repository is now oriented toward Linux Web/API runtime, with the legacy desktop GUI still present.
Quality problems usually come from mixing API/UI boundaries with workbook logic, mutating original files, or introducing thread-unsafe updates.

The current toolchain and documented reality are:

- formatting/tooling declared in `pyproject.toml`: `black`, `isort`, `flake8`, `pytest`
- automated pytest coverage exists under `tests/` for backend application, domain, infrastructure, shared helpers, and import smoke behavior
- manual GUI validation is still required for desktop-only flows such as start, stop, dialogs, and packaged-window behavior
- some legacy broad `except Exception` blocks remain around cleanup/UI safety; do not spread that pattern into core business logic

Document the current state honestly when changing this area.

---

## Tooling Baseline (from `pyproject.toml`)

These are the **exact** settings AI sessions and contributors must respect. Do not silently change them.

### Python and dependencies

- `requires-python = ">=3.8"` — code must stay compatible with Python 3.8
- Core runtime deps: `pandas>=1.3.0,<3.0.0`, `numpy>=1.20.0,<2.0.0`, `openpyxl>=3.0.0,<4.0.0`, `fastapi>=0.110.0,<1.0.0`, `pydantic>=2.0.0,<3.0.0`, `uvicorn>=0.27.0,<1.0.0`, `ttkbootstrap>=1.10.0`, `appdirs>=1.4.0`, plus `pywin32>=305` on Windows
- Optional `[project.optional-dependencies] dev` group: `pytest>=6.0.0`, `black>=21.0.0`, `flake8>=3.9.0`, `isort>=5.0.0`

### Formatting

```toml
[tool.black]
line-length = 88
target-version = ['py38']
```

```toml
[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88
known_first_party = ["src"]
```

Practical rules:

- Always run `black` and `isort` before committing Python changes
- Do not change `line-length` per file or per PR — keep it at 88 project-wide
- Imports from `src.*` are first-party; do not mix them with third-party blocks
- Keep type annotations compatible with Python 3.8, using `typing.List`, `typing.Dict`, and `typing.Optional` where needed

### Testing

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
]
```

Practical rules:

- New test files must live under `tests/` and follow `test_*.py`
- `--strict-markers` is on: any new marker must be registered in `[tool.pytest.ini_options]` before use
- Use `@pytest.mark.slow` for expensive Excel/IO tests and `@pytest.mark.integration` for end-to-end flows
- Prefer `python3 -m pytest tests -q` in this repository so the top-level `src` package resolves consistently

---

## Forbidden Patterns

### Do not add new UI-thread violations

Background threads must not update Tkinter widgets directly.
Route UI changes through `GUIUpdateManager` in `src/frontend/gui_update_manager.py` or through thread-safe callbacks owned by the GUI layer.

### Do not mutate the user's original workbook when preprocessing

The current project copies input files to AppData temp storage before removing protection or filters.
New preprocessing code should preserve that behavior through `src/backend/infrastructure/file_runtime.py`.

### Do not move workbook rules into GUI handlers

`src/gui/main_window.py` may collect input and orchestrate user actions, but workbook comparison rules belong in `src/backend/domain/`.
Path validation and output-path setup belong in `src/backend/application/`, while temp files, config translation, progress coordination, and JSON persistence belong in `src/backend/infrastructure/`.

### Do not reintroduce legacy boundary shims

The old `src/core/` and `src/utils/` packages are not compatibility boundaries anymore.
Use direct imports from the current packages instead of adding long-term forwarding modules.

### Do not expand silent cleanup catches into core business logic

The codebase contains broad catches for best-effort cleanup and GUI shutdown.
Do not copy that pattern into new comparison or persistence logic unless the branch is truly non-critical and logged.
Always preserve `InterruptedError` as a separate user-stop path.

### Do not assume built-in templates are editable state

Built-in configs are treated as protected templates and must not be overwritten in place.

---

## Required Patterns

### Validate external input at the boundary

Examples already in the codebase:

- verify required paths before processing
- verify file existence before launching work
- validate workbook readability before comparison
- backfill missing config keys when reading saved JSON

### Keep the current separation of concerns

- GUI widgets, dialogs, and message boxes in `src/gui/`
- Web API boundaries and frontend runtime helpers in `src/frontend/`
- framework-agnostic application orchestration in `src/backend/application/`
- workbook reading, comparison, write-back, highlighting, and stop-control logic in `src/backend/domain/`
- runtime adapters such as config, progress, temp files, preprocessing, and JSON persistence in `src/backend/infrastructure/`
- pure cross-layer contracts and helpers in `src/shared/`
- packaging-only logic in `scripts/`

### Use cooperative stop checks in long-running flows

Long loops and per-sheet work should call stop helpers from `src/backend/domain/processing_control.py`, such as `check_stop_frequently(...)`.
Do not swallow `InterruptedError` inside broad exception handlers.

### Prefer narrow reads and staged processing

Read only what is needed first:

- one sheet instead of the entire workbook
- one header slice before a full data pass
- one validation row before expensive processing

### Preserve compatibility for saved configs

When adding a persisted parameter, update the default structure and template definitions so old JSON files still load.
Keep raw persisted documents compatible with `src/shared/contracts.py` and runtime translation in `ConfigManager`.

---

## Testing Requirements

### Current repository reality

- `pytest` is declared in `pyproject.toml`
- pytest discovery is configured under `[tool.pytest.ini_options]`
- committed tests live under `tests/` and cover the extracted backend/application/domain/infrastructure/shared seams
- API smoke can validate the Linux Web runtime through `/health`
- Legacy GUI smoke still depends on local desktop prerequisites: Tkinter, `ttkbootstrap`, and a display server

### What to do today

For documentation-only changes, acceptable validation is:

- check the modified Markdown paths
- confirm examples point to real files
- inspect the diff manually
- run a legacy-reference scan when changing architecture docs

For code changes in backend logic, the preferred direction is:

1. add or update pytest tests under `tests/`
2. cover file validation, config compatibility, stop propagation, or comparison edge cases where practical
3. run focused tests first, then `python3 -m pytest tests -q`
4. manually test the API or GUI flow for start/stop/success/failure when the environment supports it

### High-value manual scenarios

- missing input path
- unreadable or corrupted workbook
- duplicated anchor row names
- stop during long-running processing
- config save/load on custom and built-in templates
- temp-copy cleanup and output file generation

---

## Code Review Checklist

- Is the change in the correct layer (`gui`, `frontend`, `backend/application`, `backend/domain`, `backend/infrastructure`, `shared`, or `scripts`)?
- Does workbook preprocessing still operate on a temp copy, not the original source file?
- Are long-running operations using stop checks and thread-safe GUI update paths?
- Does user-facing failure handling both log the issue and restore/unlock the UI?
- If config persistence changed, are old JSON files still loadable?
- Are new module/file names consistent with the current `snake_case` style?
- If manual validation was used instead of automated tests, is that limitation stated clearly?

---

## Examples

### Example 1: Thread-safe progress updates

`src/backend/infrastructure/progress_manager.py` uses a lock and callbacks instead of touching GUI widgets directly.

```python
with self.lock:
    if self.progress_func:
        self.progress_func(display_message, progress)
```

### Example 2: GUI updates are marshalled back to the main thread

`src/frontend/gui_update_manager.py` uses a queue and `root.after(...)` to process background updates safely.

```python
self.update_queue.put(message)
self.root.after(self.update_interval, self.process_updates)
```

### Example 3: Config compatibility is preserved on load

`src/gui/parameter_manager.py` fills in missing keys instead of assuming all saved files already match the latest schema.

```python
for key, default_value in default_structure.items():
    if key not in self.parameters:
        self.parameters[key] = default_value
```
