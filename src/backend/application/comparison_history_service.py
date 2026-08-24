"""比对历史记录服务。

负责把 JobManager 结束的任务持久化到 ``comparison_run`` 表，并对外提供
列表/详情查询与按用户删除。Session 由各方法自建（与 ``background_jobs``
的巡检模式一致），绝不复用请求作用域 session——任务线程活得比请求久。

只存文件 ``basename`` 且剥离绝对路径与 upload id：API 响应不泄露服务器
文件系统布局，也不会带着已过期的上传引用。
"""

import json
import os
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...shared.log_utils import log
from ..infrastructure.database import get_engine
from ..infrastructure.models.comparison_run import ComparisonRun
from .job_manager import JobState, JobStatus

#: 落库前从参数快照中剥离的字段：绝对服务器路径与已过期上传引用。
_STRIP_PARAMETER_FIELDS = (
    "old_file_path",
    "new_file_path",
    "old_file_upload_id",
    "new_file_upload_id",
    "output_directory",
)


def redact_parameters(parameters: Mapping[str, Any]) -> Dict[str, Any]:
    """返回剥离敏感字段后的参数快照（不就地修改原对象）。"""
    return {
        key: value
        for key, value in parameters.items()
        if key not in _STRIP_PARAMETER_FIELDS
    }


def _get_file_size(path: Optional[str]) -> int:
    if not path:
        return 0
    try:
        return os.path.getsize(path) if os.path.isfile(path) else 0
    except OSError:
        return 0


def record_run(
    session: Session,
    job: JobState,
) -> ComparisonRun:
    """把一次任务终结持久化为历史记录行。

    任务线程在 ``_notify_finished`` 中调用；只有终结状态（completed /
    failed / cancelled）才会走到这里。
    """
    status = job.status.value if isinstance(job.status, JobStatus) else str(job.status)
    parameters = redact_parameters(job.parameters)
    run = ComparisonRun(
        user_id=job.user_id,
        job_id=job.job_id,
        config_name=job.config_name,
        status=status,
        report_filename=(
            os.path.basename(job.output_path) if job.output_path else None
        ),
        log_filename=os.path.basename(job.log_path) if job.log_path else None,
        report_size_bytes=_get_file_size(job.output_path),
        parameters_json=json.dumps(parameters, ensure_ascii=False),
        error=job.error,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
    session.add(run)
    session.flush()
    return run


def record_job_finished(job: JobState) -> None:
    """``JobManager`` 结束回调入口：自建 Session 落库，异常只记录不抛出。"""
    try:
        session = Session(get_engine())
        try:
            record_run(session, job)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - 历史记录失败不得翻任务状态
        log("记录比对历史失败: {}".format(exc), None)


def list_runs(
    session: Session,
    user_id: int,
    config_name: Optional[str] = None,
    limit: int = 20,
) -> List[ComparisonRun]:
    """按用户（且可选项目名）倒序列出历史记录。"""
    query = select(ComparisonRun).where(ComparisonRun.user_id == user_id)
    if config_name:
        query = query.where(ComparisonRun.config_name == config_name)
    query = query.order_by(ComparisonRun.finished_at.desc()).limit(limit)
    return list(session.scalars(query))


def get_run(
    session: Session,
    user_id: int,
    run_id: int,
) -> Optional[ComparisonRun]:
    """按 id 取历史记录；仅返回属于 ``user_id`` 的行（跨用户视为不存在）。"""
    return session.scalars(
        select(ComparisonRun).where(
            ComparisonRun.id == run_id,
            ComparisonRun.user_id == user_id,
        )
    ).first()


def delete_runs_for_user(
    session: Session,
    user_id: int,
) -> int:
    """硬删用户前清空其历史行（磁盘文件已随用户目录一起删除）。"""
    ids = session.scalars(
        select(ComparisonRun.id).where(ComparisonRun.user_id == user_id)
    ).all()
    session.query(ComparisonRun).filter(ComparisonRun.user_id == user_id).delete()
    return len(ids)


def run_to_summary(run: ComparisonRun, results_dir: str) -> Dict[str, Any]:
    """历史行 → 列表摘要（不含参数；``*_available`` 实测文件存在性）。"""
    report_filename = (
        os.path.basename(run.report_filename) if run.report_filename else None
    )
    log_filename = os.path.basename(run.log_filename) if run.log_filename else None
    report_path = (
        os.path.join(results_dir, report_filename) if report_filename else None
    )
    log_path = os.path.join(results_dir, log_filename) if log_filename else None
    return {
        "id": run.id,
        "job_id": run.job_id,
        "config_name": run.config_name,
        "status": run.status,
        "report_filename": report_filename,
        "report_available": bool(report_path and os.path.isfile(report_path)),
        "report_size_bytes": run.report_size_bytes,
        "log_filename": log_filename,
        "log_available": bool(log_path and os.path.isfile(log_path)),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error": run.error,
    }


def run_to_detail(run: ComparisonRun, results_dir: str) -> Dict[str, Any]:
    """历史行 → 详情（列表摘要 + 参数快照，供展开行懒加载）。"""
    try:
        parameters: Dict[str, Any] = json.loads(run.parameters_json or "{}")
    except ValueError:
        parameters = {}
        log("历史记录 {} 的参数 JSON 解析失败".format(run.id), None)
    return {
        **run_to_summary(run, results_dir),
        "parameters": parameters,
    }


def migrate_config_name(
    session: Session,
    user_id: int,
    old_name: str,
    new_name: str,
) -> int:
    """项目改名后，把历史行的 ``config_name`` 一并迁移（复制不迁移）。"""
    count = (
        session.query(ComparisonRun)
        .filter(
            ComparisonRun.user_id == user_id,
            ComparisonRun.config_name == old_name,
        )
        .update({ComparisonRun.config_name: new_name})
    )
    return int(count or 0)
