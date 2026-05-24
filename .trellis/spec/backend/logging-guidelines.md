# Logging Guidelines

> How logging is done in this project.

---

## Overview

This project does **not** use Python's standard `logging` package today.
The current logging mechanism is lightweight and callback-based:

- `src/shared/log_utils.py::log(msg, log_func)` prints to stdout
- the same helper forwards the message to an optional callback
- Web/API code may leave messages on stdout, while GUI code decides how to display or persist callback output

This means logs are plain text, not structured JSON.
If you add new logging, match the current callback style unless the whole app is intentionally migrated.

### Project-level exemption for `print()`

General Python guidance treats `print()` in business code as a smell and recommends the `logging` module instead.
This project deliberately keeps `print()` inside `src/shared/log_utils.py::log()` for these reasons:

- the Linux Web/API entry and packaged GUI can both use stdout when no callback is provided
- the same helper still routes the message into callbacks, so the call site stays single-source
- the helper handles `UnicodeEncodeError` explicitly to keep Windows consoles working

Rules for new code:

- Do **not** introduce `print(...)` in `src/backend/`, `src/gui/`, `src/frontend/`, or other business modules — go through `log(msg, log_func)` or a GUI-aware callback instead
- The allowed console-printing path is `src/shared/log_utils.py`; do not duplicate that pattern elsewhere
- If the project later adopts the stdlib `logging` module, this exemption should be removed at the same time as `log_utils.py` is migrated

---

## Log Levels

There is no enforced logging enum in the shared helper.
Instead, the codebase uses plain-text conventions from the caller.

### Current practical levels

- `INFO` for normal progress and lifecycle messages
- `ERROR` for failures that block the workflow or a user action
- `SUCCESS` for completion messages in the GUI layer
- plain text markers or prefixes when existing call sites need user-friendly emphasis

### Real examples

From `src/gui/main_window.py`:

```python
self.log_message("输入文件不存在", "ERROR")
self.log_message(f"配置 '{self.parameter_manager.current_config_name}' 已保存", "INFO")
self.log_message(f"比对结果已保存至: {result_output_path}", "SUCCESS")
```

From `src/backend/infrastructure/file_runtime.py`:

```python
log_func(f"所有验证引擎都失败，但文件可能仍可修复")
log_func(f"备用筛选器清除失败: {str(fallback_e)}")
```

---

## Structured Logging

Logging is currently **unstructured plain text**.
There is no standard schema, but useful messages usually include the business context directly in the string.

### Include these details when available

- file path or file role (`old`, `new`, `output`)
- sheet name
- operation stage (`validate`, `read`, `save`, `cleanup`, `stop`)
- fallback branch taken
- exception text when the action actually failed

### Good project-native examples

```python
log_func(f"读取Sheet [{sheet_name}] 失败: {str(e)}")
```

```python
self.log_message(f"旧版本数据集: {final_old_path}")
self.log_message(f"输出目录: {output_path}")
```

```python
log_func(f"主要预处理失败: {str(e)}，尝试回退方法")
```

### Current transport pattern

- background code logs through a callback (`log_func`)
- thread-safe progress code exposes `safe_log(...)`
- GUI decides whether messages go to the screen, a file, or both

---

## What to Log

Log these events consistently:

- start/stop of a comparison run
- path validation failures
- file validation results
- sheet-level skip/new/missing/update decisions
- fallback paths, especially preprocessing fallbacks
- output-file and log-file locations
- cleanup or recovery failures that may affect the next run

### Real examples in the codebase

- `src/backend/domain/data_comparison.py` logs skipped, new, missing, and empty-sheet branches
- `src/backend/infrastructure/file_runtime.py` logs validation failures and fallback cleanup behavior
- `src/gui/main_window.py` logs save/start/stop/success/fatal-error lifecycle events

---

## What NOT to Log

- full workbook contents or large DataFrame dumps
- sensitive local filesystem details unless they are needed to fix the issue
- noisy per-cell logs inside hot loops
- duplicate GUI + worker messages that say the same thing with no extra context
- secrets or credentials if the project later introduces them

Because comparisons operate on user-supplied or server-local workbook paths, file paths are commonly logged today.
That is acceptable when needed for diagnosis, but avoid logging more data than the user needs to act on a failure.

---

## Common Mistakes

- Writing directly with `print(...)` in new business logic instead of using `log(..., log_func)` or a GUI-aware callback
- Logging a failure without naming the file or sheet involved
- Logging inside tight loops at a granularity that hurts performance
- Emitting success messages before the output workbook is actually saved
- Swallowing an exception silently during fallback/cleanup without at least one log line
- Swallowing `InterruptedError` in a broad exception handler and logging it as a normal failure
