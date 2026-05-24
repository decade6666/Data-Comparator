# Database Guidelines

> Persistence patterns and conventions for this project.

---

## Overview

This project does **not** use a database, ORM, migration framework, or SQL query layer.
The real persistence model today is:

- Excel workbooks as the primary data source and output format
- JSON config files under the user's AppData-backed temp directory
- Temporary workbook copies under the app temp directory

Do not document or implement database conventions that do not exist in the repository.
If the project later becomes a service with real persistence, this file should be rewritten.

---

## Query Patterns

Since there is no database, the equivalent of "query patterns" is file-reading strategy.

### Preferred access patterns

- Read as narrowly as possible
- Prefer per-sheet reads over loading an entire workbook into pandas at once
- Prefer lightweight validation before expensive processing
- Copy the input workbook before mutating anything related to filters/protection

### Real patterns in the codebase

- `src/backend/domain/excel_header_utils.py` reads one sheet with `load_workbook(..., read_only=True, data_only=True)`
- `src/backend/infrastructure/file_runtime.py::validate_excel_file` reads only one row for fast validation
- `src/backend/infrastructure/file_runtime.py::check_and_remove_file_protection` creates a temp copy before workbook cleanup

### Examples

```python
# src/backend/domain/excel_header_utils.py
wb = load_workbook(file_path, read_only=True, data_only=True)
ws = wb[sheet_name]
```

```python
# src/backend/infrastructure/file_runtime.py
test_df = pd.read_excel(file_path, sheet_name=0, nrows=1, engine=engine)
```

```python
# src/backend/infrastructure/file_runtime.py
shutil.copy2(file_path, new_file_path)
```

---

## Migrations

Traditional schema migrations do not exist here.
The closest equivalent is config-schema evolution for saved JSON parameter files.

### Current pattern for config evolution

- Keep persisted config files as JSON
- Backfill missing keys instead of failing hard on older files
- Protect built-in templates from in-place overwrite
- Keep runtime config translation in `src/backend/infrastructure/config_manager.py`
- Keep JSON persistence in `src/backend/infrastructure/parameter_repository.py`

### Real examples

`src/gui/parameter_manager.py::_ensure_parameter_structure` adds missing keys to older configs:

```python
for key, default_value in default_structure.items():
    if key not in self.parameters:
        self.parameters[key] = default_value
```

`src/gui/parameter_manager.py` also protects built-in templates from overwrite/delete:

```python
if config_name in (BUILTIN_TEMPLATE_CIMS, BUILTIN_TEMPLATE_TM):
    return False
```

### Practical rule

If you add a new persisted parameter:

1. add the key to the default structure
2. add it to built-in template definitions if it belongs there
3. keep old config files loadable by backfilling the new key
4. update `src/shared/contracts.py` if the key is part of the cross-layer parameter document
5. update `ConfigManager.update_from_parameters(...)` if the key affects runtime behavior

---

## Naming Conventions

Because persistence is JSON/file-based rather than SQL-based, naming conventions apply to config keys and temp files.

### Config keys

- Use `snake_case`
- Match Python field names where practical
- Keep nested color settings under `colors`

Examples:

- `old_file_path`
- `new_file_path`
- `output_directory`
- `default_keys`
- `sheet_key_map`
- `merge_deleted_data`

### Temp files

- Derived temp copies use the original filename plus `_nofilter_` and a timestamp
- Temp files live under `get_app_temp_dir()` rather than next to the source file

Example:

```python
new_file_name = f"{original_filename}_nofilter_{timestamp}{ext}"
```

---

## Common Mistakes

- Assuming there is a DB layer and trying to introduce repository/ORM abstractions that the app does not need
- Reading the whole workbook when only one sheet or a header slice is needed
- Mutating the original source workbook instead of working on a temp copy
- Adding new config keys without backfilling older saved JSON files
- Treating built-in templates as editable runtime state
- Reintroducing `src/config/global_config.py` as a runtime owner for defaults
