# Error Handling

> How errors are handled in this project.

---

## Overview

This project has a small HTTP/API error contract in `src/frontend/web_api.py`.
Errors are handled through a mix of:

- validation at API and application boundaries
- return-value based helpers (`True/False`, `None`, error text)
- standard Python exceptions for fatal failures
- a dedicated `InterruptedError` path for user-triggered stop
- log messages plus HTTP errors for user-facing feedback

The codebase currently prefers practical recovery and runtime continuity over a strict exception hierarchy.

---

## Error Types

The project mostly uses built-in exceptions instead of custom classes.

### Current error categories

- `InterruptedError` for cooperative user stop
- `FileNotFoundError` for missing source files
- `ValueError` for invalid sheet/header states or invalid persisted JSON shape
- generic `Exception` catches for cleanup, fallback, or safe reporting

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
The API maps those failures to HTTP responses.

```python
paths = validate_processing_paths(parameters)
```

### 2. Keep API-facing failures informative

`src/frontend/web_api.py` translates application/domain exceptions into `HTTPException` responses
with the original message as detail, so callers see the failing file or sheet name.

### 3. Separate stop from failure

Long-running workflows treat user stop as a normal branch, not as a fatal error.
`InterruptedError` is caught separately in `src/frontend/web_api.py` and mapped to HTTP 409.

```python
except InterruptedError as exc:
    raise HTTPException(status_code=409, detail=str(exc)) from exc
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

- `JsonParameterRepository.load_document()` returns `None` when the config file does not exist
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

### Scenario: Web comparison API boundary

#### 1. Scope / Trigger

- Trigger: The frontend/backend split introduced the FastAPI boundary in `src/frontend/web_api.py` and the framework-agnostic runner in `src/backend/application/comparison_runner.py`.
- Scope: Document the executable contract from HTTP request payload to `ParameterDocument`, path validation, domain processing, and HTTP error mapping.
- This is cross-layer contract depth because API clients, frontend code, application services, and tests must agree on the same fields and failure behavior.

#### 2. Signatures

```python
# src/frontend/web_api.py
GET /health -> {"status": "ok"}
POST /api/compare CompareRequest -> CompareResponse

class CompareRequest(BaseModel):
    old_file_path: str
    new_file_path: str
    output_directory: str
    config_name: str = "web"
    anchor_row_num: int = 1
    header_row_num: int = 1
    anchor_row_content: str = "SASFieldName"
    header_row_content: str = "SASFieldLabel"
    max_workers: Optional[int] = None
    merge_deleted_data: bool = True
    common_cols: List[str] = Field(default_factory=list)
    exclude_sheets: List[str] = Field(default_factory=list)
    default_keys: List[str] = Field(default_factory=list)
    sheet_key_map: Dict[str, List[str]] = Field(default_factory=dict)
    colors: CompareColors = Field(default_factory=CompareColors)

class CompareResponse(BaseModel):
    output_path: str

# src/backend/application/comparison_runner.py
def run_comparison(
    parameters: ParameterDocument,
    config_name: str = "web",
    log_func: Optional[LogFunc] = None,
    progress_func: Optional[Callable[[str, Optional[int]], None]] = None,
    stop_flag=None,
    process_func: Optional[ProcessFunc] = None,
    config_factory: ConfigFactory = _default_config_factory,
    path_exists: Callable[[str], bool] = os.path.exists,
    make_dirs: Callable[..., None] = os.makedirs,
    now: Optional[datetime.datetime] = None,
) -> str: ...
```

#### 3. Contracts

Request fields:

| Field | Type | Required | Default | Boundary behavior |
|-------|------|----------|---------|-------------------|
| `old_file_path` | `str` | Yes | none | Must be present and point to an existing source file before processing starts. |
| `new_file_path` | `str` | Yes | none | Must be present and point to an existing source file before processing starts. |
| `output_directory` | `str` | Yes | none | Created by the application layer if it does not already exist. |
| `config_name` | `str` | No | `"web"` | Used only to build the report filename; invalid filename characters are sanitized. |
| `anchor_row_num` | `int` | No | `1` | Passed through to runtime config. |
| `header_row_num` | `int` | No | `1` | Passed through to runtime config. |
| `anchor_row_content` | `str` | No | `"SASFieldName"` | Passed through to runtime config. |
| `header_row_content` | `str` | No | `"SASFieldLabel"` | Passed through to runtime config. |
| `max_workers` | `int \| null` | No | `null` | Omitted from `ParameterDocument` when `null`; otherwise passed through. |
| `merge_deleted_data` | `bool` | No | `true` | Passed through to runtime config. |
| `common_cols` | `List[str]` | No | `[]` | Copied into a new list before entering the backend runner. |
| `exclude_sheets` | `List[str]` | No | `[]` | Copied into a new list before entering the backend runner. |
| `default_keys` | `List[str]` | No | `[]` | Copied into a new list before entering the backend runner. |
| `sheet_key_map` | `Dict[str, List[str]]` | No | `{}` | Copied into a new dict before entering the backend runner. |
| `colors.highlight_fill` | `str \| null` | No | `null` | Included in `ParameterDocument.colors` only when not `null`. |
| `colors.missing_sheet_tab` | `str \| null` | No | `null` | Included in `ParameterDocument.colors` only when not `null`. |
| `colors.new_sheet_tab` | `str \| null` | No | `null` | Included in `ParameterDocument.colors` only when not `null`. |

Response fields:

| Field | Type | Behavior |
|-------|------|----------|
| `output_path` | `str` | Full generated report path returned by the domain processor. |

Environment keys:

- No environment variables are part of this API contract.
- Server startup concerns such as host, port, and reload mode belong to process configuration, not request payloads.

#### 4. Validation & Error Matrix

| Condition | Raised by | HTTP status | Response detail |
|-----------|-----------|-------------|-----------------|
| Missing required JSON field or invalid JSON type | FastAPI/Pydantic | `422` | Pydantic validation body |
| Any required path is blank after model parsing | `validate_processing_paths(...)` | `400` | `"请填写所有必要的路径信息"` |
| `old_file_path` or `new_file_path` does not exist | `validate_processing_paths(...)` | `404` | `"输入文件不存在"` |
| `output_directory` does not exist and cannot be created | `validate_processing_paths(...)` | `500` | `"创建输出目录失败: ..."` |
| Domain validation failure such as invalid workbook/header state | backend domain code | `400` | Original `ValueError` message |
| User-triggered cooperative stop | stop-control helpers | `409` | Original `InterruptedError` message |
| Filesystem/runtime processing failure | application/domain/infrastructure | `500` | Original `OSError` or `RuntimeError` message |
| Unexpected failure | API boundary | `500` | `"比对处理失败: <original error>"`; also logged through `_api_log(...)` |

#### 5. Good/Base/Bad Cases

Good case:

```json
{
  "old_file_path": "old.xlsx",
  "new_file_path": "new.xlsx",
  "output_directory": "/tmp/out",
  "config_name": "CIMS",
  "anchor_row_num": 2,
  "header_row_num": 3,
  "common_cols": ["更新时间"],
  "exclude_sheets": ["说明"],
  "default_keys": ["USUBJID"],
  "sheet_key_map": {"AE": ["USUBJID", "AESEQ"]},
  "colors": {"highlight_fill": "#FFFFFF"}
}
```

Base case:

```json
{
  "old_file_path": "old.xlsx",
  "new_file_path": "new.xlsx",
  "output_directory": "/tmp/out"
}
```

Bad cases:

```json
{}
```

```json
{
  "old_file_path": "missing.xlsx",
  "new_file_path": "new.xlsx",
  "output_directory": "/tmp/out"
}
```

#### 6. Tests Required

- API smoke: `tests/test_web_api.py::test_health_endpoint_reports_ok` asserts `GET /health` returns `200` and `{"status": "ok"}`.
- API translation: `tests/test_web_api.py::test_compare_endpoint_runs_synchronous_comparison` asserts request fields become `ParameterDocument`, optional colors are preserved, and `config_name` is passed separately.
- API validation: `tests/test_web_api.py::test_compare_endpoint_requires_paths` asserts missing required payload fields return `422`.
- API error mapping: `tests/test_web_api.py::test_compare_endpoint_maps_missing_input_to_404` asserts missing inputs return `404` with the original detail.
- Unexpected failure logging: `tests/test_web_api.py::test_compare_endpoint_logs_unexpected_failure` asserts generic failures are logged and prefixed.
- Application validation: `tests/test_processing_service.py` asserts missing paths, missing input files, output directory creation, immutable path application, and sanitized output names.
- Runner orchestration: `tests/test_comparison_runner.py` asserts `run_comparison(...)` validates paths, creates config, passes callbacks, preserves colors, and returns the generated output path.
- When changing this contract, add focused tests for any changed `400`, `409`, or `500` branch before editing implementation.

#### 7. Wrong vs Correct

##### Wrong

```python
@app.post("/api/compare")
def compare(request: CompareRequest) -> dict:
    try:
        output_path = process_edc_multithreaded(**request.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"output_path": output_path}
```

##### Correct

```python
@app.post("/api/compare", response_model=CompareResponse)
def compare(request: CompareRequest) -> CompareResponse:
    try:
        output_path = run_comparison(
            request.to_parameter_document(),
            config_name=request.config_name,
            log_func=_api_log,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InterruptedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CompareResponse(output_path=output_path)
```

### Scenario: Auth & admin API boundary

#### 1. Scope / Trigger

- Trigger: User isolation & authentication (task `08-19-auth-isolation`) introduced JWT auth, per-user data isolation, admin user management, config batch operations, and the recycle bin — a new HTTP contract family in `src/frontend/routers/` (`auth.py`, `users.py`, `admin.py`) plus `src/frontend/dependencies.py`.
- Scope: Document auth/ownership/validation error semantics so frontend and tests agree.

#### 2. Signatures

```python
# src/frontend/dependencies.py
get_current_user  # Bearer token -> User; 401 on missing/invalid/expired token
require_admin     # Depends(get_current_user); 403 for non-admin

# src/frontend/routers/auth.py
POST /api/auth/login                       {"username","password"} -> {"token","user"}
PUT  /api/auth/me/password                 {"password"} -> 204   (self-service)

# src/frontend/routers/users.py  (all require_admin)
GET    /api/users                          -> [{"id","username","has_password","is_admin","is_active"}]
POST   /api/users                          {"username","password"} -> 201
PUT    /api/users/{user_id}                {"username"} -> 204   (rename)
PUT    /api/users/{user_id}/password       {"password"} -> 204
DELETE /api/users/{user_id}                -> 204 (hard delete)

# src/frontend/routers/admin.py  (all require_admin)
GET    /api/admin/users/{user_id}/configs                          -> {"configs":[names]}
POST   /api/admin/configs/batch-copy       {config_names,source_user_id,target_user_id} -> per-item results
POST   /api/admin/configs/batch-move       {config_names,source_user_id,target_user_id} -> {"status","moved"}
POST   /api/admin/configs/batch-delete     {config_names,user_id} -> {"deleted"}
GET    /api/admin/recycle-bin                                       -> [entries]
POST   /api/admin/recycle-bin/{id}/restore {target_user_id?}        -> restored entry
DELETE /api/admin/recycle-bin/{id}                                   -> 204 (hard delete)
GET    /api/admin/recycle-bin/cleanup-policy                        -> policy + totals
PUT    /api/admin/recycle-bin/cleanup-policy                        -> policy (persisted)
POST   /api/admin/recycle-bin/cleanup/preview                       -> items to delete
```

#### 3. Contracts

- Auth: `Authorization: Bearer <JWT>` on all endpoints except `/health`, `/api/auth/login`, and static assets. Token carries `sub/username/ver/exp`; changing password bumps `auth_version` and invalidates old tokens; renaming a user invalidates tokens via username mismatch. Responses may include `X-Refreshed-Token` for sliding renewal.
- Ownership: job/config/upload access checks return **404** (not 403) for non-owned resources to prevent enumeration.
- Batch operations: copy/move/restore strip `old_file_upload_id`/`new_file_upload_id`/`old_file_path`/`new_file_path` (target user must re-upload); duplicate names get ` (副本)`/` (恢复)` + numeric suffix.
- Recycle bin: config soft-delete (user delete) stores JSON content + owner snapshot + size; restore to the original owner when they still exist, otherwise a `target_user_id` is required; `deleted_by_user_deletion` distinguishes the two paths.
- Config names: rejected if empty, contain `/`, `\`, `..`, or match a built-in template name (all `config_name`-accepting endpoints, including URL-encoded variants).

#### 4. Validation & Error Matrix

| Condition | Raised by | HTTP status | Response detail |
|-----------|-----------|-------------|-----------------|
| Missing/invalid/expired token | `get_current_user` | `401` | auth error |
| Non-admin accessing admin/users endpoints | `require_admin` | `403` | permission error |
| Wrong login password / inactive user | login | `401` | `"用户名或密码错误"` / account error |
| Rename to blank/duplicate username; reserved admin username | `UserAdminService.rename_user` | `400` | message |
| Deleting yourself | `users.delete_user` | `400` | `"不能删除自己"` |
| Delete/reset/rename nonexistent user | service `ValueError` | `404` | `"用户不存在"` |
| Batch copy/move to nonexistent source/target user | `_require_user` | `404` | `"用户不存在"` |
| Restore with no target when original owner deleted; nonexistent target | restore | `400` | message |
| Config name invalid (empty/`/`/`\`/`..`/builtin) | `_validate_config_name` | `400` | `"配置名不合法"` / `"不能操作内置模板"` |
| Cleanup policy value out of range / bad unit | `_validate_policy_update` | `400` | message |
| Recycle entry not found | `RecycleBinService` `ValueError` | `404` | message |

#### 5. Good/Base/Bad Cases

Good: admin logs in, copies a config to another user, restores a deleted user's config to a chosen target.
Base: normal user deletes their own config -> it lands in the recycle bin (soft delete).
Bad: non-owner accesses another user's job id -> 404, not 403 (no enumeration).

#### 6. Tests Required

- `tests/test_web_api_auth.py` (login/token/permission), `tests/test_auth_service.py`, `tests/test_user_admin_service.py`, `tests/test_admin_config_ops.py` (batch ops, ownership, strip-upload), `tests/test_recycle_bin_service.py`, `tests/test_recycle_bin_cleanup.py`, `tests/test_recycle_bin_policy_api.py`, `tests/test_user_delete_with_recycle.py` (delete flow ordering), `tests/test_job_manager_user_isolation.py`, `tests/test_builtin_templates.py`.

#### 7. Wrong vs Correct

##### Wrong

```python
# Missing config name validation — enables path traversal:
@app.delete("/configs/{name}")
def delete_config(name): ...   # "..%2F.." -> deletes outside configs dir
```

##### Correct

```python
# Validate at the boundary before touching the filesystem:
def _validate_config_name(name: str) -> None:
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "配置名不合法")
    if name in BUILTIN_TEMPLATES:
        raise HTTPException(400, "不能操作内置模板")
```

---

## Common Mistakes

- Catching `Exception` and doing nothing in core logic where the failure matters
- Treating user stop and actual failure as the same path
- Adding a new persisted config field without a compatibility backfill path
- Returning vague error text when the code can include the failing sheet/file name
- Reintroducing old `src.core` or `src.utils` exception examples in new docs or imports
- Returning 403 for non-owned resources — use 404 so resource existence stays hidden from other users
- Skipping `config_name` path-traversal validation on any endpoint that accepts a config name
- Deleting a user's config dir before cancelling their running jobs / before recycling configs
