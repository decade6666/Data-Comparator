import json
import os
import re
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from urllib.parse import unquote

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..backend.application.background_jobs import (
    start_background_jobs,
    stop_background_jobs,
)
from ..backend.application.comparison_runner import run_comparison
from ..backend.application.job_manager import get_job_manager
from ..backend.application.recycle_bin_service import RecycleBinService
from ..backend.application.user_admin_service import get_bootstrap_admin_credentials
from ..backend.infrastructure.database import get_session, init_db, session_context
from ..backend.infrastructure.file_runtime import get_sheet_names
from ..backend.infrastructure.models.user import User
from ..backend.infrastructure.parameter_repository import (
    JsonParameterRepository,
)
from ..backend.infrastructure.parameter_templates import BUILTIN_TEMPLATES
from ..backend.infrastructure.path_security import (
    is_safe_path,
    validate_asset_raw_path,
)
from ..backend.infrastructure.upload_store import (
    UploadRejectedError,
    UploadStore,
    UploadTooLargeError,
)
from ..shared.contracts import ParameterColors, ParameterDocument
from ..shared.log_utils import log
from .dependencies import get_current_user, require_admin
from .routers import admin as admin_router
from .routers import auth as auth_router
from .routers import users as users_router

API_TITLE = "Dataset Comparator API"
API_VERSION = "1.1.0"

_UPLOAD_CLEANUP_INTERVAL_SECONDS = 30 * 60
_CONFIGS_SUBDIR = "configs"
_UPLOADS_SUBDIR = "uploads"
_RESULTS_SUBDIR = "results"


def _user_config_dir(user_id: int) -> str:
    from ..backend.infrastructure.file_runtime import get_user_data_dir

    return os.path.join(get_user_data_dir(user_id), _CONFIGS_SUBDIR)


def _user_uploads_dir(user_id: int) -> str:
    from ..backend.infrastructure.file_runtime import get_user_data_dir

    return os.path.join(get_user_data_dir(user_id), _UPLOADS_SUBDIR)


def _user_results_dir(user_id: int) -> str:
    from ..backend.infrastructure.file_runtime import get_user_data_dir

    return os.path.join(get_user_data_dir(user_id), _RESULTS_SUBDIR)


def _repository_for(user_id: int) -> JsonParameterRepository:
    from ..backend.infrastructure.file_runtime import get_user_data_dir

    def base_dir_getter() -> str:
        return get_user_data_dir(user_id)

    return JsonParameterRepository(base_dir_getter=base_dir_getter)


def _upload_store_for(user_id: int) -> UploadStore:
    def config_dir_getter() -> str:
        return _user_config_dir(user_id)

    return UploadStore(
        base_dir=_user_uploads_dir(user_id),
        config_dir_getter=config_dir_getter,
    )


def _max_upload_bytes() -> int:
    raw = os.environ.get("DATASET_COMPARATOR_MAX_UPLOAD_MB", "200").strip()
    try:
        megabytes = max(1, int(raw))
    except ValueError:
        megabytes = 200
    return megabytes * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库与初始管理员，迁移旧全局配置，启动上传清理定时器。"""
    from ..backend.application.auth_service import get_secret_key

    get_secret_key()
    init_db()
    _bootstrap_admin()

    _migrate_legacy_global_configs()

    upload_cleanup_timer: Optional[threading.Timer] = None

    def _cleanup_loop() -> None:
        nonlocal upload_cleanup_timer
        try:
            users_root = os.path.join(_app_data_dir(), "users")
            if os.path.isdir(users_root):
                for user_name in os.listdir(users_root):
                    uploads_dir = os.path.join(users_root, user_name, _UPLOADS_SUBDIR)
                    if os.path.isdir(uploads_dir):
                        _upload_store_for(int(user_name)).cleanup()
        except Exception:
            pass
        upload_cleanup_timer = threading.Timer(
            _UPLOAD_CLEANUP_INTERVAL_SECONDS, _cleanup_loop
        )
        upload_cleanup_timer.daemon = True
        upload_cleanup_timer.start()

    upload_cleanup_timer = threading.Timer(
        _UPLOAD_CLEANUP_INTERVAL_SECONDS, _cleanup_loop
    )
    upload_cleanup_timer.daemon = True
    upload_cleanup_timer.start()
    start_background_jobs(app)
    try:
        yield
    finally:
        if upload_cleanup_timer is not None:
            upload_cleanup_timer.cancel()
        stop_background_jobs(app)


def _app_data_dir() -> str:
    from ..backend.infrastructure.file_runtime import get_app_data_dir

    return get_app_data_dir()


def _bootstrap_admin() -> None:
    """按环境变量创建初始管理员；缺失配置时打印指引并拒绝创建。"""
    from sqlalchemy import select

    username, password = get_bootstrap_admin_credentials()
    if not username:
        log(
            "未配置初始管理员（DATASET_COMPARATOR_ADMIN_USERNAME/PASSWORD），"
            "请设置后再启动。",
            None,
        )
        return
    with session_context() as session:
        existing = session.scalar(select(User).where(User.username == username))
        if existing is not None:
            return
        from ..backend.application.auth_service import hash_password

        admin = User(
            username=username,
            hashed_password=hash_password(password),
            is_admin=True,
            auth_version=1,
        )
        session.add(admin)
        session.flush()
        log(f"已创建初始管理员: {username}", None)


def _migrate_legacy_global_configs() -> None:
    """把旧版全局 temp/configs 迁移到初始管理员名下（仅一次）。"""
    from sqlalchemy import select

    from ..backend.infrastructure.file_runtime import get_app_temp_dir

    legacy_dir = os.path.join(get_app_temp_dir(), _CONFIGS_SUBDIR)
    marker = os.path.join(_app_data_dir(), ".legacy_configs_migrated")
    if os.path.exists(marker) or not os.path.isdir(legacy_dir):
        return
    username, _ = get_bootstrap_admin_credentials()
    if not username:
        return
    with session_context() as session:
        admin = session.scalar(select(User).where(User.username == username))
        if admin is None:
            return
        target_dir = _user_config_dir(admin.id)
        os.makedirs(target_dir, exist_ok=True)
        for name in os.listdir(legacy_dir):
            if not name.endswith(".json"):
                continue
            config_name = name[:-5]
            if config_name in BUILTIN_TEMPLATES:
                continue
            source = os.path.join(legacy_dir, name)
            target = os.path.join(target_dir, name)
            if not os.path.exists(target):
                shutil.copy2(source, target)
        log(f"已迁移旧全局配置到初始管理员 {username}（{admin.id}）", None)
        Path(marker).touch()


app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)
app.include_router(auth_router.router, prefix="/api")
app.include_router(users_router.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")

_job_manager = get_job_manager()


class CompareColors(BaseModel):
    highlight_fill: Optional[str] = None
    missing_sheet_tab: Optional[str] = None
    new_sheet_tab: Optional[str] = None


class CompareRequest(BaseModel):
    old_file_upload_id: Optional[str] = None
    new_file_upload_id: Optional[str] = None
    output_directory: str = ""
    config_name: str = "web"

    model_config = {"extra": "forbid"}
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
    include_sheets: List[str] = Field(default_factory=list)
    ignore_cols: List[str] = Field(default_factory=list)
    sheet_ignore_cols: Dict[str, List[str]] = Field(default_factory=dict)
    sheet_order: List[str] = Field(default_factory=list)
    colors: CompareColors = Field(default_factory=CompareColors)

    def to_parameter_document(self) -> ParameterDocument:
        document: ParameterDocument = {
            "old_file_path": "",
            "new_file_path": "",
            "output_directory": "",
            "anchor_row_num": self.anchor_row_num,
            "header_row_num": self.header_row_num,
            "anchor_row_content": self.anchor_row_content,
            "header_row_content": self.header_row_content,
            "merge_deleted_data": self.merge_deleted_data,
            "common_cols": list(self.common_cols),
            "exclude_sheets": list(self.exclude_sheets),
            "default_keys": list(self.default_keys),
            "sheet_key_map": dict(self.sheet_key_map),
            "include_sheets": list(self.include_sheets),
            "ignore_cols": list(self.ignore_cols),
            "sheet_ignore_cols": dict(self.sheet_ignore_cols),
            "sheet_order": list(self.sheet_order),
        }
        if self.max_workers is not None:
            document = {**document, "max_workers": self.max_workers}

        colors: ParameterColors = {}
        if self.colors.highlight_fill is not None:
            colors = {**colors, "highlight_fill": self.colors.highlight_fill}
        if self.colors.missing_sheet_tab is not None:
            colors = {
                **colors,
                "missing_sheet_tab": self.colors.missing_sheet_tab,
            }
        if self.colors.new_sheet_tab is not None:
            colors = {**colors, "new_sheet_tab": self.colors.new_sheet_tab}
        if colors:
            document = {**document, "colors": colors}

        return document


class CompareResponse(BaseModel):
    output_path: str


class JobSubmitRequest(CompareRequest):
    """异步比对任务提交请求：只接受上传模式，路径字段已下线。"""

    old_file_upload_id: Optional[str] = None
    new_file_upload_id: Optional[str] = None


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_percent: Optional[float] = None
    progress_message: Optional[str] = None
    log_lines: List[str] = Field(default_factory=list)
    log_cursor: int = 0
    output_path: Optional[str] = None
    error: Optional[str] = None


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    size: int


class BrowseEntry(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: Optional[int] = None


class BrowseResponse(BaseModel):
    current_path: str
    parent_path: Optional[str] = None
    entries: List[BrowseEntry] = Field(default_factory=list)


def _api_log(message: str) -> None:
    log(message, None)


def _resolve_upload(label: str, upload_id: Optional[str], user_id: int) -> str:
    if not upload_id:
        raise HTTPException(status_code=400, detail=f"请提供{label}的上传文件")
    file_path = _upload_store_for(user_id).resolve(upload_id)
    if file_path is None:
        raise HTTPException(status_code=400, detail=f"{label}的上传文件不存在或已过期")
    return file_path


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/compare", response_model=CompareResponse)
def compare(
    request: CompareRequest,
    current_user: User = Depends(get_current_user),
) -> CompareResponse:
    old_path = _resolve_upload(
        "旧版本文件", request.old_file_upload_id, current_user.id
    )
    new_path = _resolve_upload(
        "新版本文件", request.new_file_upload_id, current_user.id
    )
    document = request.to_parameter_document()
    document = {
        **document,
        "old_file_path": old_path,
        "new_file_path": new_path,
        "output_directory": _user_results_dir(current_user.id),
    }
    try:
        output_path = run_comparison(
            document,
            config_name=request.config_name,
            log_func=_api_log,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except InterruptedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        message = f"比对处理失败: {exc}"
        _api_log(message)
        raise HTTPException(status_code=500, detail=message) from exc

    return CompareResponse(output_path=output_path)


@app.post("/api/jobs", response_model=JobSubmitResponse, status_code=201)
def submit_job(
    request: JobSubmitRequest,
    current_user: User = Depends(get_current_user),
) -> JobSubmitResponse:
    old_path = _resolve_upload(
        "旧版本文件", request.old_file_upload_id, current_user.id
    )
    new_path = _resolve_upload(
        "新版本文件", request.new_file_upload_id, current_user.id
    )
    output_directory = _user_results_dir(current_user.id)
    document = request.to_parameter_document()
    document = {
        **document,
        "old_file_path": old_path,
        "new_file_path": new_path,
        "output_directory": output_directory,
    }
    try:
        job = _job_manager.submit(
            document, config_name=request.config_name, user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JobSubmitResponse(job_id=job.job_id, status=job.status.value)


@app.post("/api/upload", response_model=UploadResponse, status_code=201)
def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    try:
        record = _upload_store_for(current_user.id).save(
            file.filename or "upload.xlsx", file.file, _max_upload_bytes()
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UploadRejectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadResponse(
        upload_id=record.upload_id,
        filename=record.original_name,
        size=record.size,
    )


@app.get("/api/uploads/{upload_id}")
def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """返回上传文件是否仍可用于恢复后的配置。"""
    record = _upload_store_for(current_user.id).get(upload_id)
    if record is None:
        return {"upload_id": upload_id, "exists": False}
    return {
        "upload_id": upload_id,
        "exists": True,
        "filename": record.original_name,
        "size": record.size,
    }


@app.get("/api/sheets")
def get_sheets(
    upload_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, List[str]]:
    resolved = _upload_store_for(current_user.id).resolve(upload_id)
    if resolved is None:
        raise HTTPException(status_code=400, detail="上传文件不存在或已过期")
    sheets = get_sheet_names(resolved, _api_log)
    return {"sheets": sheets}


@app.get("/api/configs")
def list_configs(
    current_user: User = Depends(get_current_user),
) -> Dict[str, List[str]]:
    return {
        "configs": _repository_for(current_user.id).list_configurations(),
        "builtin_templates": list(BUILTIN_TEMPLATES.keys()),
    }


@app.get("/api/configs/{name}")
def get_config(
    name: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    document = _repository_for(current_user.id).load_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    return dict(document)


@app.put("/api/configs/{name}")
def save_config(
    name: str,
    document: Dict[str, Any],
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能覆盖内置模板")
    _repository_for(current_user.id).save_document(
        name, cast(ParameterDocument, document)
    )
    return {"name": name, "saved": True}


@app.delete("/api/configs/{name}")
def delete_config(
    name: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    if name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能删除内置模板")
    repository = _repository_for(current_user.id)
    document = repository.load_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    try:
        RecycleBinService.recycle_config(
            session,
            owner_id=current_user.id,
            owner_username=current_user.username,
            config_name=name,
            config_path=repository.get_config_path(name),
            config_document=dict(document),
            deleted_by_user_deletion=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"name": name, "recycled": True, "deleted": True}


class CopyConfigRequest(BaseModel):
    new_name: str


@app.post("/api/configs/{name}/copy")
def copy_config(
    name: str,
    request: CopyConfigRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    repository = _repository_for(current_user.id)
    if request.new_name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能覆盖内置模板")
    document = repository.load_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    if repository.load_document(request.new_name) is not None:
        raise HTTPException(status_code=409, detail="目标配置已存在")
    repository.save_document(request.new_name, document)
    return {"name": request.new_name, "copied": True}


@app.get("/api/configs/{name}/export")
def export_config(
    name: str,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    document = _repository_for(current_user.id).load_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    return FileResponse(
        _write_config_json_to_temp(name, document),
        filename=f"{name}.json",
        media_type="application/json",
    )


def _write_config_json_to_temp(name: str, document: ParameterDocument) -> str:
    import tempfile

    content = json.dumps(document, ensure_ascii=False, indent=4)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".json", delete=False
    )
    handle.write(content)
    handle.close()
    return handle.name


@app.post("/api/configs/import")
async def import_config(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    raw = await file.read()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="导入文件不是合法的 JSON") from exc
    if not isinstance(document, dict):
        raise HTTPException(status_code=400, detail="导入的 JSON 必须是配置对象")
    name = file.filename or "导入配置"
    if name.endswith(".json"):
        name = name[:-5]
    if name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能覆盖内置模板")
    _repository_for(current_user.id).save_document(
        name, cast(ParameterDocument, document)
    )
    return {"name": name, "imported": True}


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    since: int = 0,
    current_user: User = Depends(get_current_user),
) -> JobStatusResponse:
    snapshot = _job_manager.snapshot(
        job_id, since=max(0, since), user_id=current_user.id
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JobStatusResponse(**snapshot)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    job = _job_manager.cancel_job(job_id, user_id=current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status.value in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail="任务已结束，无法取消")
    return {"job_id": job_id, "status": "cancelling"}


@app.get("/api/jobs/{job_id}/download")
def download_job_result(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    job = _job_manager.get_job(job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    with job.lock:
        output_path = job.output_path
        status = job.status.value
    if status != "completed" or not output_path:
        raise HTTPException(status_code=404, detail="任务尚未完成")
    if not os.path.isfile(output_path):
        raise HTTPException(status_code=410, detail="结果文件已被清理")
    return FileResponse(
        output_path,
        filename=os.path.basename(output_path),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )


# ——— 前端静态资源服务 ———

_STATIC_DIR_ENV = "DATASET_COMPARATOR_STATIC_DIR"
_static_dir = os.environ.get(
    _STATIC_DIR_ENV,
    str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"),
)
_assets_dir = Path(_static_dir) / "assets"
_WINDOWS_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


def _iter_asset_path_variants(filepath: str):
    """遍历原始路径及其有限次 URL 解码结果，用于拒绝危险输入。"""
    current = filepath
    seen = set()
    for _ in range(3):
        if current in seen:
            break
        seen.add(current)
        yield current
        decoded = unquote(current)
        if decoded == current:
            break
        current = decoded


@app.get("/assets/{filepath:path}", include_in_schema=False)
async def serve_asset(filepath: str) -> Response:
    """提供静态资源，no-cache 头确保浏览器验证资源是否最新（Vite hash 命名）。"""
    safe, message = validate_asset_raw_path(filepath)
    if not safe:
        return Response(status_code=400, content=message)
    asset_path = Path(os.path.normpath(_assets_dir / filepath)).resolve()
    safe, message = is_safe_path(str(asset_path), [str(_assets_dir)])
    if not safe:
        return Response(status_code=400, content=message)
    if not asset_path.is_file():
        return Response(status_code=404)
    return FileResponse(
        str(asset_path),
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/", include_in_schema=False)
def index() -> Response:
    index_file = Path(_static_dir) / "index.html"
    if index_file.exists():
        return FileResponse(
            str(index_file),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return Response(
        content="前端尚未构建，请在 frontend/ 目录执行 npm run build",
        status_code=404,
    )
