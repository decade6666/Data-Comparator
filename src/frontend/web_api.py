import json
import os
import re
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from urllib.parse import unquote

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from ..backend.application.comparison_runner import run_comparison
from ..backend.application.job_manager import JobManager
from ..backend.infrastructure.file_runtime import get_sheet_names
from ..backend.infrastructure.parameter_repository import (
    JsonParameterRepository,
)
from ..backend.infrastructure.parameter_templates import BUILTIN_TEMPLATES
from ..backend.infrastructure.path_security import (
    get_browse_roots,
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

API_TITLE = "Dataset Comparator API"
API_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时安装内置配置模板并启动上传清理定时器，关闭时停止。"""
    _config_repository.ensure_builtin_templates(BUILTIN_TEMPLATES)
    upload_cleanup_timer: Optional[threading.Timer] = None

    def _cleanup_loop() -> None:
        nonlocal upload_cleanup_timer
        try:
            _upload_store.cleanup()
        except Exception:
            # 清理失败不应影响服务主流程
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
    try:
        yield
    finally:
        if upload_cleanup_timer is not None:
            upload_cleanup_timer.cancel()


app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)


class CompareColors(BaseModel):
    highlight_fill: Optional[str] = None
    missing_sheet_tab: Optional[str] = None
    new_sheet_tab: Optional[str] = None


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
    include_sheets: List[str] = Field(default_factory=list)
    ignore_cols: List[str] = Field(default_factory=list)
    sheet_ignore_cols: Dict[str, List[str]] = Field(default_factory=dict)
    sheet_order: List[str] = Field(default_factory=list)
    colors: CompareColors = Field(default_factory=CompareColors)

    def to_parameter_document(self) -> ParameterDocument:
        document: ParameterDocument = {
            "old_file_path": self.old_file_path,
            "new_file_path": self.new_file_path,
            "output_directory": self.output_directory,
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
    """异步比对任务提交请求。

    路径字段与上传字段二选一：提供 ``old_file_upload_id`` / ``new_file_upload_id``
    时走浏览器上传模式，``output_directory`` 可省略（默认输出到临时目录）。
    """

    old_file_path: str = ""
    new_file_path: str = ""
    output_directory: str = ""
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


_job_manager = JobManager()
_upload_store = UploadStore()
_config_repository = JsonParameterRepository()
_UPLOAD_CLEANUP_INTERVAL_SECONDS = 30 * 60


def _max_upload_bytes() -> int:
    raw = os.environ.get("DATASET_COMPARATOR_MAX_UPLOAD_MB", "200").strip()
    try:
        megabytes = max(1, int(raw))
    except ValueError:
        megabytes = 200
    return megabytes * 1024 * 1024


def _resolve_job_input(
    label: str, path_value: str, upload_id: Optional[str]
) -> str:
    if path_value and upload_id:
        raise HTTPException(
            status_code=400,
            detail=f"{label}同时提供了路径和上传文件，请只选择一种方式",
        )
    if upload_id:
        file_path = _upload_store.resolve(upload_id)
        if file_path is None:
            raise HTTPException(
                status_code=400, detail=f"{label}的上传文件不存在或已过期"
            )
        return file_path
    if path_value:
        return path_value
    raise HTTPException(status_code=400, detail=f"请提供{label}的路径或上传文件")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


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
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        message = f"比对处理失败: {exc}"
        _api_log(message)
        raise HTTPException(status_code=500, detail=message) from exc

    return CompareResponse(output_path=output_path)


@app.post("/api/jobs", response_model=JobSubmitResponse, status_code=201)
def submit_job(request: JobSubmitRequest) -> JobSubmitResponse:
    upload_mode = bool(
        request.old_file_upload_id or request.new_file_upload_id
    )
    if not upload_mode and not request.output_directory:
        raise HTTPException(status_code=400, detail="请填写所有必要的路径信息")
    old_path = _resolve_job_input(
        "旧版本文件", request.old_file_path, request.old_file_upload_id
    )
    new_path = _resolve_job_input(
        "新版本文件", request.new_file_path, request.new_file_upload_id
    )
    output_directory = (
        request.output_directory or _upload_store.default_output_dir()
    )
    document = request.to_parameter_document()
    document = {
        **document,
        "old_file_path": old_path,
        "new_file_path": new_path,
        "output_directory": output_directory,
    }
    try:
        job = _job_manager.submit(document, config_name=request.config_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return JobSubmitResponse(job_id=job.job_id, status=job.status.value)


@app.post("/api/upload", response_model=UploadResponse, status_code=201)
def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    try:
        record = _upload_store.save(
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


@app.get("/api/browse", response_model=BrowseResponse)
def browse(path: str, type: str = "all") -> BrowseResponse:
    roots = get_browse_roots()
    safe, message = is_safe_path(path, roots)
    if not safe:
        raise HTTPException(status_code=403, detail=message)
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="目录不存在")
    entries: List[BrowseEntry] = []
    for name in sorted(os.listdir(path)):
        full_path = os.path.join(path, name)
        is_directory = os.path.isdir(full_path)
        if is_directory:
            if type in ("directories", "all"):
                entries.append(
                    BrowseEntry(name=name, path=full_path, is_directory=True)
                )
            continue
        if type == "directories":
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in (".xlsx", ".xls"):
            continue
        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = None
        entries.append(
            BrowseEntry(
                name=name, path=full_path, is_directory=False, size=size
            )
        )
    parent_path = None
    if entries or os.path.isdir(path):
        resolved = os.path.abspath(path)
        for root in roots:
            root_real = os.path.abspath(root)
            if resolved != root_real and resolved.startswith(
                root_real + os.sep
            ):
                parent_path = os.path.dirname(resolved)
                break
    return BrowseResponse(
        current_path=os.path.abspath(path),
        parent_path=parent_path,
        entries=entries,
    )


@app.get("/api/sheets")
def get_sheets(
    file_path: Optional[str] = None, upload_id: Optional[str] = None
) -> Dict[str, List[str]]:
    if upload_id:
        resolved = _upload_store.resolve(upload_id)
        if resolved is None:
            raise HTTPException(status_code=400, detail="上传文件不存在或已过期")
    elif file_path:
        resolved = file_path
        if not os.path.isfile(resolved):
            raise HTTPException(status_code=404, detail="文件不存在")
    else:
        raise HTTPException(
            status_code=400, detail="请提供 file_path 或 upload_id"
        )
    sheets = get_sheet_names(resolved, _api_log)
    return {"sheets": sheets}


@app.get("/api/configs")
def list_configs() -> Dict[str, List[str]]:
    return {
        "configs": _config_repository.list_configurations(),
        "builtin_templates": list(BUILTIN_TEMPLATES.keys()),
    }


@app.get("/api/configs/{name}")
def get_config(name: str) -> Dict[str, Any]:
    document = _config_repository.load_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    return dict(document)


@app.put("/api/configs/{name}")
def save_config(name: str, document: Dict[str, Any]) -> Dict[str, Any]:
    if name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能覆盖内置模板")
    _config_repository.save_document(name, cast(ParameterDocument, document))
    return {"name": name, "saved": True}


@app.delete("/api/configs/{name}")
def delete_config(name: str) -> Dict[str, Any]:
    if name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能删除内置模板")
    if not _config_repository.delete_document(name):
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"name": name, "deleted": True}


class CopyConfigRequest(BaseModel):
    new_name: str


@app.post("/api/configs/{name}/copy")
def copy_config(name: str, request: CopyConfigRequest) -> Dict[str, Any]:
    if request.new_name in BUILTIN_TEMPLATES:
        raise HTTPException(status_code=400, detail="不能覆盖内置模板")
    document = _config_repository.load_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    if _config_repository.load_document(request.new_name) is not None:
        raise HTTPException(status_code=409, detail="目标配置已存在")
    _config_repository.save_document(request.new_name, document)
    return {"name": request.new_name, "copied": True}


@app.get("/api/configs/{name}/export")
def export_config(name: str) -> FileResponse:
    document = _config_repository.load_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="配置不存在")
    return FileResponse(
        _write_config_json_to_temp(name, document),
        filename=f"{name}.json",
        media_type="application/json",
    )


def _write_config_json_to_temp(
    name: str, document: ParameterDocument
) -> str:
    import tempfile

    content = json.dumps(document, ensure_ascii=False, indent=4)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".json", delete=False
    )
    handle.write(content)
    handle.close()
    return handle.name


@app.post("/api/configs/import")
async def import_config(file: UploadFile = File(...)) -> Dict[str, Any]:
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
    _config_repository.save_document(name, cast(ParameterDocument, document))
    return {"name": name, "imported": True}


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, since: int = 0) -> JobStatusResponse:
    snapshot = _job_manager.snapshot(job_id, since=max(0, since))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JobStatusResponse(**snapshot)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> Dict[str, str]:
    job = _job_manager.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status.value in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail="任务已结束，无法取消")
    return {"job_id": job_id, "status": "cancelling"}


@app.get("/api/jobs/{job_id}/download")
def download_job_result(job_id: str) -> FileResponse:
    job = _job_manager.get_job(job_id)
    if job is None:
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
