"""比对历史记录 API。

独立于内存 ``JobManager`` 的持久化历史：服务重启后记录仍在，
报告/日志从 ``users/<id>/results`` 按行内 basename 解析下载。
所有端点只允许访问当前用户自己的记录（跨用户一律 404，不泄露存在性）。
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ...backend.application.comparison_history_service import (
    get_run,
    list_runs,
    run_to_detail,
    run_to_summary,
)
from ...backend.infrastructure.database import get_engine
from ...backend.infrastructure.file_runtime import get_user_results_dir
from ...backend.infrastructure.models.comparison_run import ComparisonRun
from ...backend.infrastructure.models.user import User
from ...backend.infrastructure.path_security import is_safe_path
from ..dependencies import get_current_user

router = APIRouter(prefix="/history", tags=["history"])

_REPORT_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _results_session() -> Session:
    """自建 Session（只读查询，FastAPI 依赖生成器不适用于脚本式 router）。"""
    return Session(get_engine())


def _resolve_history_file(
    user_id: int,
    filename: Optional[str],
    kind: str,
) -> str:
    """在用户自己的 results 目录内解析文件路径（basename + 白名单双重防护）。"""
    if not filename:
        raise HTTPException(
            status_code=404,
            detail="该记录{}".format(
                "没有比对报告" if kind == "report" else "没有日志"
            ),
        )
    results_dir = get_user_results_dir(user_id)
    candidate = os.path.join(results_dir, os.path.basename(filename))
    safe, message = is_safe_path(candidate, [results_dir])
    if not safe:
        raise HTTPException(status_code=400, detail=message)
    if not os.path.isfile(candidate):
        raise HTTPException(status_code=410, detail="结果文件已被清理")
    return candidate


def _load_owned_run(session: Session, run_id: int, user_id: int) -> ComparisonRun:
    """取属于当前用户的记录；不存在或属于他人一律 404。"""
    run = get_run(session, user_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return run


@router.get("", response_model=List[Dict[str, Any]])
def get_history(
    config_name: Optional[str] = Query(None, max_length=500),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    session = _results_session()
    try:
        runs = list_runs(session, current_user.id, config_name=config_name, limit=limit)
        return [
            run_to_summary(run, get_user_results_dir(current_user.id)) for run in runs
        ]
    finally:
        session.close()


@router.get("/{run_id}", response_model=Dict[str, Any])
def get_history_detail(
    run_id: int,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    session = _results_session()
    try:
        run = _load_owned_run(session, run_id, current_user.id)
        return run_to_detail(run, get_user_results_dir(current_user.id))
    finally:
        session.close()


@router.get("/{run_id}/report")
def download_history_report(
    run_id: int,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    session = _results_session()
    try:
        run = _load_owned_run(session, run_id, current_user.id)
        if not run.report_filename:
            raise HTTPException(status_code=404, detail="该记录没有比对报告")
        path = _resolve_history_file(
            current_user.id, run.report_filename, kind="report"
        )
        return FileResponse(
            path,
            filename=os.path.basename(path),
            media_type=_REPORT_MEDIA_TYPE,
        )
    finally:
        session.close()


@router.get("/{run_id}/log")
def download_history_log(
    run_id: int,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    session = _results_session()
    try:
        run = _load_owned_run(session, run_id, current_user.id)
        if not run.log_filename:
            raise HTTPException(status_code=404, detail="该记录没有日志")
        path = _resolve_history_file(current_user.id, run.log_filename, kind="log")
        return FileResponse(
            path,
            filename=os.path.basename(path),
            media_type="text/plain; charset=utf-8",
        )
    finally:
        session.close()
