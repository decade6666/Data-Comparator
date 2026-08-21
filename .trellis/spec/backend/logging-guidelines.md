# Logging Guidelines

> How logging is done in this project.

---

## Overview

This project does **not** use Python's standard `logging` package today.
The current logging mechanism is lightweight and callback-based:

- `src/shared/log_utils.py::log(msg, log_func)` prints to stdout
- the same helper forwards the message to an optional callback
- Web/API code may leave messages on stdout, or route them into a callback

This means logs are plain text, not structured JSON.
If you add new logging, match the current callback style unless the whole app is intentionally migrated.

### Project-level exemption for `print()`

General Python guidance treats `print()` in business code as a smell and recommends the `logging` module instead.
This project deliberately keeps `print()` inside `src/shared/log_utils.py::log()` for these reasons:

- the Linux Web/API entry can use stdout when no callback is provided
- the same helper still routes the message into callbacks, so the call site stays single-source
- the helper handles `UnicodeEncodeError` explicitly to keep Windows consoles working

Rules for new code:

- Do **not** introduce `print(...)` in `src/backend/`, `src/frontend/`, or other business modules — go through `log(msg, log_func)` instead
- The allowed console-printing path is `src/shared/log_utils.py`; do not duplicate that pattern elsewhere
- If the project later adopts the stdlib `logging` module, this exemption should be removed at the same time as `log_utils.py` is migrated

---

## Log Levels

There is no enforced logging enum in the shared helper.
Instead, the codebase uses plain-text conventions from the caller.

### Current practical levels

- `INFO` for normal progress and lifecycle messages
- `ERROR` for failures that block the workflow or a user action
- `SUCCESS` for completion messages
- plain text markers or prefixes when existing call sites need user-friendly emphasis

### Real examples

From `src/frontend/web_api.py`:

```python
def _api_log(message: str) -> None:
    log(message, None)
```

From `src/backend/infrastructure/file_runtime.py`:

```python
log_func(f"所有验证引擎都失败，但文件可能仍可修复")
log_func(f"ℹ️ 非 OOXML 包（.xls 等），跳过筛选器清理: {str(exc)}")
```

---

## Structured Logging

Logging is currently **unstructured plain text**.
There is no standard schema, but useful messages usually include the business context directly in the string.

### Include these details when available

- file path or file role (`old`, `new`, `output`)
- sheet name
- operation stage (`validate`, `read`, `save`, `cleanup`, `stop`)
- cleanup outcome (rewritten, skipped, or failed)
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
log_func(
    "✅ 已清除筛选器：工作表 "
    f"{result.sheet_autofilters_removed} 处、表格 "
    f"{result.table_autofilters_removed} 处，恢复隐藏行 "
    f"{result.hidden_rows_restored} 行"
)
```

### Current transport pattern

- background code logs through a callback (`log_func`)
- thread-safe progress code exposes `safe_log(...)`
- the caller decides whether messages go to the screen, a file, or both

---

## What to Log

Log these events consistently:

- start/stop of a comparison run
- path validation failures
- file validation results
- sheet-level skip/new/missing/update decisions
- cleanup outcomes, especially skipped non-OOXML inputs and recovery failures that may affect the next run
- output-file and log-file locations

### Real examples in the codebase

- `src/backend/domain/data_comparison.py` logs skipped, new, missing, and empty-sheet branches
- `src/backend/infrastructure/file_runtime.py` logs validation results and byte-level cleanup outcomes
- `src/frontend/web_api.py` logs unexpected comparison failures through `_api_log(...)`

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

- Writing directly with `print(...)` in new business logic instead of using `log(..., log_func)`
- Logging a failure without naming the file or sheet involved
- Logging inside tight loops at a granularity that hurts performance
- Emitting success messages before the output workbook is actually saved
- Swallowing an exception silently during cleanup without at least one log line
- Swallowing `InterruptedError` in a broad exception handler and logging it as a normal failure
