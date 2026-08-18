"""后台比对任务管理器。

维护异步比对任务的完整生命周期（pending -> running -> completed/failed/cancelled），
把领域层已经支持但此前未被 Web 层使用的 progress_func / log_func / stop_flag
参数接入任务状态，供前端轮询进度、查看日志和取消任务。

并发约束：由于 ``domain/processing_control.py`` 中的 ``_global_stop_flag`` 是进程级
全局状态（``data_comparison.process_edc_multithreaded`` 每次运行都会覆写它），
并发运行多个比对任务会互相覆盖停止标志，因此本管理器强制同一时间最多运行一个
任务（单任务串行）。
"""

import datetime
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from ...shared.contracts import ParameterDocument
from .comparison_runner import run_comparison

DEFAULT_RETENTION_MINUTES = 30
DEFAULT_MAX_JOBS = 20
DEFAULT_SWEEP_INTERVAL_SECONDS = 300


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL_STATUSES = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)


@dataclass
class JobState:
    """单个比对任务的运行状态，所有可变字段在 lock 保护下读写。"""

    job_id: str
    status: JobStatus
    parameters: ParameterDocument
    config_name: str
    stop_flag: threading.Event
    created_at: datetime.datetime
    progress_percent: Optional[float] = None
    progress_message: Optional[str] = None
    log_lines: List[str] = field(default_factory=list)
    output_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    finished_at: Optional[datetime.datetime] = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class JobManager:
    """单任务串行的比对任务注册表。"""

    def __init__(
        self,
        retention_minutes: int = DEFAULT_RETENTION_MINUTES,
        max_jobs: int = DEFAULT_MAX_JOBS,
        sweep_interval_seconds: int = DEFAULT_SWEEP_INTERVAL_SECONDS,
        now: Callable[[], datetime.datetime] = datetime.datetime.now,
    ) -> None:
        self._retention_minutes = retention_minutes
        self._max_jobs = max_jobs
        self._sweep_interval_seconds = sweep_interval_seconds
        self._now = now
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobState] = {}
        self._active_job_id: Optional[str] = None
        self._sweep_timer: Optional[threading.Timer] = None

    def has_active_job(self) -> bool:
        with self._lock:
            return self._active_job_id is not None

    def submit(
        self, parameters: ParameterDocument, config_name: str = "web"
    ) -> JobState:
        """登记任务并在后台线程执行；已有任务运行中时抛 ``ValueError``。"""
        with self._lock:
            if self._active_job_id is not None:
                raise ValueError("已有比对任务正在运行，请等待完成或取消后再提交")
            job = JobState(
                job_id=uuid.uuid4().hex[:16],
                status=JobStatus.PENDING,
                parameters=parameters,
                config_name=config_name,
                stop_flag=threading.Event(),
                created_at=self._now(),
            )
            self._jobs[job.job_id] = job
            self._active_job_id = job.job_id
        self._ensure_sweep_timer()
        thread = threading.Thread(
            target=self._run_thread,
            args=(job.job_id,),
            daemon=True,
            name="compare-job-{}".format(job.job_id),
        )
        thread.start()
        return job

    def get_job(self, job_id: str) -> Optional[JobState]:
        return self._jobs.get(job_id)

    def snapshot(self, job_id: str, since: int = 0) -> Optional[dict]:
        """返回供 HTTP 响应使用的任务状态快照（含 since 之后的新日志行）。"""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        with job.lock:
            return {
                "job_id": job.job_id,
                "status": job.status.value,
                "progress_percent": job.progress_percent,
                "progress_message": job.progress_message,
                "log_lines": list(job.log_lines[since:]),
                "log_cursor": len(job.log_lines),
                "output_path": job.output_path,
                "error": job.error,
            }

    def cancel_job(self, job_id: str) -> Optional[JobState]:
        """请求停止任务；返回任务状态，已结束任务不做任何操作。"""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        with job.lock:
            if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
                return job
        job.stop_flag.set()
        return job

    def get_log_lines(
        self, job_id: str, since: int = 0
    ) -> Tuple[List[str], int]:
        job = self._jobs.get(job_id)
        if job is None:
            return [], 0
        with job.lock:
            return list(job.log_lines[since:]), len(job.log_lines)

    def cleanup(self, now: Optional[datetime.datetime] = None) -> int:
        """淘汰超过保留期的已结束任务，并控制任务总数上限。"""
        current = now or self._now()
        removed = 0
        with self._lock:
            deadline = current - datetime.timedelta(
                minutes=self._retention_minutes
            )
            for job in list(self._jobs.values()):
                if (
                    job.status in _TERMINAL_STATUSES
                    and job.finished_at is not None
                    and job.finished_at <= deadline
                ):
                    del self._jobs[job.job_id]
                    removed += 1
            remaining_terminal = [
                job
                for job in self._jobs.values()
                if job.status in _TERMINAL_STATUSES
            ]
            excess = len(self._jobs) - self._max_jobs
            if excess > 0:
                for job in sorted(
                    remaining_terminal,
                    key=lambda j: j.finished_at or current,
                ):
                    if excess <= 0:
                        break
                    del self._jobs[job.job_id]
                    excess -= 1
                    removed += 1
        return removed

    def stop(self) -> None:
        """停止清扫定时器（应用关闭时调用）。"""
        with self._lock:
            if self._sweep_timer is not None:
                self._sweep_timer.cancel()
                self._sweep_timer = None

    def _ensure_sweep_timer(self) -> None:
        with self._lock:
            if self._sweep_timer is None:
                timer = threading.Timer(
                    self._sweep_interval_seconds, self._sweep_loop
                )
                timer.daemon = True
                timer.start()
                self._sweep_timer = timer

    def _sweep_loop(self) -> None:
        try:
            self.cleanup()
        except Exception:
            # 清扫失败不应影响服务主流程
            pass
        with self._lock:
            if self._jobs:
                timer = threading.Timer(
                    self._sweep_interval_seconds, self._sweep_loop
                )
                timer.daemon = True
                timer.start()
                self._sweep_timer = timer
            else:
                self._sweep_timer = None

    def _run_thread(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        with job.lock:
            job.status = JobStatus.RUNNING
            job.started_at = self._now()

        def job_progress_func(
            message: str, percent: Optional[int] = None
        ) -> None:
            with job.lock:
                if percent is not None:
                    job.progress_percent = float(percent)
                if message:
                    job.progress_message = message

        def job_log_func(message: str) -> None:
            # 领域层通过 shared.log() 输出时已经打印过一次，这里只负责归档，
            # 避免与既有 stdout 行为叠加成重复输出。
            with job.lock:
                job.log_lines.append(message)

        try:
            output_path = run_comparison(
                job.parameters,
                config_name=job.config_name,
                log_func=job_log_func,
                progress_func=job_progress_func,
                stop_flag=job.stop_flag,
            )
        except InterruptedError as exc:
            self._finish(job, JobStatus.CANCELLED, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - 失败信息要落到任务状态
            self._finish(job, JobStatus.FAILED, error="比对处理失败: {}".format(exc))
        else:
            with job.lock:
                job.status = JobStatus.COMPLETED
                job.output_path = output_path
                job.finished_at = self._now()
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def _finish(self, job: JobState, status: JobStatus, error: str) -> None:
        with job.lock:
            job.status = status
            job.error = error
            job.finished_at = self._now()
