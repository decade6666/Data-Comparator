# Error Handling

> How errors are handled in this project.

---

## Overview

This project has a small HTTP/API error contract in `src/frontend/web_api.py`, while the legacy GUI still handles desktop-facing errors.
Errors are handled through a mix of:

- validation at API, GUI, and application boundaries
- return-value based helpers (`True/False`, `None`, error text)
- standard Python exceptions for fatal failures
- a dedicated `InterruptedError` path for user-triggered stop
- log messages plus HTTP errors or Tkinter dialogs for user-facing feedback

The codebase currently prefers practical recovery and runtime continuity over a strict exception hierarchy.

---

## Error Types

The project mostly uses built-in exceptions instead of custom classes.

### Current error categories

- `InterruptedError` for cooperative user stop
- `FileNotFoundError` for missing source files
- `ValueError` for invalid sheet/header states or invalid persisted JSON shape
- generic `Exception` catches for cleanup, fallback, or GUI-safe reporting

### Real examples

`src/backend/domain/processing_control.py` raises `InterruptedError` when the stop flag is set:

```python
if current_flag and current_flag.is_set():
    log("处理已被用户停止", log_func)
    raise InterruptedError("用户停止了操作")
```

`src/backend/application/processing_service.py` validates missing source files before processing begins:

```python
if not os.path.exists(old_path) or not os.path.exists(new_path):
    raise FileNotFoundError("输入文件不存在")
```

`src/backend/domain/excel_header_utils.py` raises `ValueError` when anchor-row names are duplicated:

```python
if len(non_empty_names) != len(set(non_empty_names)):
    raise ValueError(msg)
```

---

## Error Handling Patterns

### 1. Validate early at the application boundary

Before processing starts, `src/backend/application/processing_service.py` validates required paths,
input-file existence, and output-directory creation.
The API maps those failures to HTTP responses, while the GUI logs them and shows the user-facing dialog.

```python
paths = validate_processing_paths(old_path, new_path, output_dir)
```

### 2. Keep GUI-facing failures user friendly

`src/gui/main_window.py` is responsible for restoring UI state and showing Tkinter dialogs.
Backend modules should raise or return enough context for the GUI to present a clear message.

```python
self.log_message(f"处理过程中出现错误：{error_msg}", "ERROR")
self._force_unlock_ui()
```

### 3. Separate stop from failure

Long-running workflows treat user stop as a normal branch, not as a fatal error.
`InterruptedError` is caught separately in `src/gui/main_window.py::_processing_thread`.

```python
except InterruptedError:
    self.update_progress("操作已停止", 0)
    self.log_message("操作已被用户停止", "INFO")
```

Broad exception handlers in backend/domain or backend/infrastructure code must re-raise `InterruptedError` before handling generic failures.

```python
except InterruptedError:
    raise
except Exception as exc:
    log_func(f"处理失败: {str(exc)}")
```

### 4. Use fallback paths for recoverable preprocessing

`src/backend/infrastructure/file_runtime.py` tries the Windows automation path first when clearing filters, then falls back to a workbook-level cleanup path.
The fallback is logged instead of silently ignored.

```python
except Exception as exc:
    log_func(f"主要预处理失败: {str(exc)}，尝试回退方法")
    try:
        remove_auto_filters_from_xlsx(...)
    except Exception as fallback_exc:
        log_func(f"备用筛选器清除失败: {str(fallback_exc)}")
```

### 5. Return `None`/`False` for utility-level recoverable cases

The codebase often uses sentinel return values instead of custom exceptions when the caller can continue.
Examples:

- `ParameterManager.load_config()` returns `False` on failure
- `read_single_sheet_from_excel()` returns `None` when a sheet is missing or unreadable
- `validate_excel_file()` returns `(False, error_text)`

---

## API Error Responses

`src/frontend/web_api.py` is the current HTTP boundary.
It keeps the API contract thin by translating application/domain exceptions into `HTTPException` responses:

- `GET /health` returns `200` with `{"status": "ok"}`
- `POST /api/compare` returns `200` with `{"output_path": "..."}` on success
- `FileNotFoundError` maps to `404`
- `ValueError` maps to `400`
- `InterruptedError` maps to `409`
- `OSError` and `RuntimeError` map to `500`
- unexpected exceptions map to `500` with a generic comparison-failure prefix

The legacy GUI still uses dialog-based feedback for desktop-only flows:

- `messagebox.showerror(...)` for blocking failures
- `messagebox.showwarning(...)` for invalid or risky user choices
- `messagebox.showinfo(...)` for stop/completion guidance
- `show_file_error_dialog(...)` for richer file-repair instructions

Example from `src/gui/main_window.py`:

```python
self.log_message(f"处理过程中出现错误：{error_msg}", "ERROR")
self._force_unlock_ui()
self.root.after(0, lambda msg=error_msg: self._show_message_then_unlock("error", "错误", f"处理过程中出现错误：\n{msg}"))
```

---

## Common Mistakes

- Catching `Exception` and doing nothing in core logic where the failure matters
- Treating user stop and actual failure as the same path
- Updating Tkinter widgets directly from a worker thread instead of routing through the GUI update manager
- Forgetting to unlock/restore the UI after failures in background processing
- Adding a new persisted config field without a compatibility backfill path
- Returning vague error text when the code can include the failing sheet/file name
- Reintroducing old `src.core` or `src.utils` exception examples in new docs or imports
