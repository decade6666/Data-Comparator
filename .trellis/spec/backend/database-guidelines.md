# Database Guidelines

> Persistence patterns and conventions for this project.

---

## Overview

The project uses **SQLite + SQLAlchemy 2.x** as its metadata database, alongside the pre-existing file-based persistence:

| Layer | What it persists | Location |
|-------|------------------|----------|
| SQLite DB (SQLAlchemy) | Users, recycled (deleted) configs | `<appdata>/dataset_comparator.db` |
| JSON config files | Per-user comparison configs (incl. built-in templates) | `<appdata>/users/<uid>/configs/*.json` |
| Uploaded workbooks | Temporary Excel uploads | `<appdata>/users/<uid>/uploads/` |
| Output reports | Generated Excel comparison reports | `<appdata>/users/<uid>/results/` |
| App config YAML | Recycle-bin cleanup policy | `<appdata>/config.yaml` |

The DB stores **metadata only** (accounts, recycle bin). Excel content and comparison configs remain file-based.

---

## ORM & Session Patterns

### Engine (process-level singleton)

`src/backend/infrastructure/database.py`:

```python
# sqlite:///<appdata>/dataset_comparator.db, check_same_thread=False
# PRAGMA foreign_keys=ON, journal_mode=WAL, busy_timeout=5000, synchronous=NORMAL
get_engine()  # lazy singleton
init_db()     # Base.metadata.create_all(get_engine()) — idempotent, no migration framework
get_db_path() -> str
```

### Session dependencies

```python
# FastAPI write dependency: auto-commit on success, rollback on exception
get_session() -> Iterator[Session]      # yield -> commit -> close

# FastAPI read-only dependency: no commit
read_session() -> Iterator[Session]

# Non-FastAPI code (background jobs, tests)
session_context() -> Iterator[Session]  # same behavior as get_session
```

- **Never** reuse a request-scoped Session in background threads; background jobs create their own `Session(get_engine())`.
- Tests pin the DB to a temp dir via `db_path_for_testing(tmp_path)` and call `init_db()` before queries (the engine is lazy).

### Models

All models live in `src/backend/infrastructure/models/` and are re-exported from `models/__init__.py` (`Base` plus each model). Registering a new model means adding the file plus the `__init__.py` import; `create_all(checkfirst=True)` picks it up on next startup.

Current tables:

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `user` | Auth accounts | `username` (unique), `hashed_password`, `is_admin`, `is_active`, `auth_version`, `created_at` |
| `recycled_config` | Deleted configs awaiting restore/hard-delete | `original_owner_id` (nullable), `original_owner_username` (snapshot), `original_config_name`, `config_document` (JSON text), `estimated_size_bytes`, `deleted_at`, `deleted_by_user_deletion` |

Note: `deleted_at` stores naive local time (`DateTime(timezone=True)` is declarative only; SQLite returns naive datetimes) — keep comparisons consistent within the same process.

### No migration framework

Schema evolves via `create_all(checkfirst=True)` only. Do **not** add Alembic or hand-written migration scripts; adding columns/tables requires no migration step, renaming/removing columns requires manual handling for existing DBs.

---

## Query Patterns

- Use `select()` / `session.get(Model, id)` / `session.execute(select(func.sum(...), func.count(...)))` for aggregates (see recycle-bin policy totals).
- SQLite is single-writer: keep write transactions short, one business unit per transaction, commit via `get_session` lifecycle.
- Cleanup jobs must re-check row existence before deleting (race between preview/plan and execution): re-`session.get()` before `session.delete()`.

---

## Migrations / Schema Evolution

Config-schema evolution for saved JSON parameter files (pre-existing pattern):

1. add the key to the default structure
2. add it to built-in template definitions if it belongs there
3. keep old config files loadable by backfilling the new key
4. update `src/shared/contracts.py` if the key is part of the cross-layer parameter document
5. update `ConfigManager.update_from_parameters(...)` if the key affects runtime behavior

---

## Naming Conventions

- Tables: `snake_case`, singular (`user`, `recycled_config`)
- Columns: `snake_case`, nullable foreign references explicitly `Optional[int]`
- Config keys (JSON): `snake_case`, match Python field names where practical, keep nested color settings under `colors`
- App config YAML (`config.yaml`): pydantic `BaseModel` in `src/backend/infrastructure/app_config.py`, loaded via `get_app_config()` (`@lru_cache`) and written atomically via `update_app_config(updates)` (lock + temp file + `os.replace` + `cache_clear`)

---

## Common Mistakes

- Assuming there is **no** database — the file predates the SQLite layer and is now wrong; see Overview.
- Reusing a request-scoped Session in a background thread (Timer jobs): create a fresh `Session(get_engine())`.
- Adding a model but forgetting the `models/__init__.py` import (silent import-time surprise).
- Adding Alembic / hand migration scripts — the project uses idempotent `create_all`.
- Deleting a user's config row and directory before cancelling their running jobs — cancel first, then recycle, then `rmtree` the user dir, then delete the `User` row.
- Reading the whole workbook when only one sheet or a header slice is needed
- Mutating the original source workbook instead of working on a temp copy
- Adding new config keys without backfilling older saved JSON files
- Treating built-in templates as editable runtime state
- Reintroducing `src/config/global_config.py` as a runtime owner for defaults
