"""后台比对任务管理器。

维护异步比对任务的完整生命周期（pending -> running -> completed/failed/cancelled），
把领域层已经支持但此前未被 Web 层使用的 progress_func / log_func / stop_flag
参数接入任务状态，供前端轮询进度、查看日志和取消任务。

并发约束：每用户至多 1 个运行中任务；跨用户并发受全局信号量
``DATASET_COMPARATOR_MAX_CONCURRENT_JOBS``（默认 2）限制，超限任务在
pending 排队等待。
"""

import datetime
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from ...shared.contracts import ParameterDocument
from ...shared.log_utils import log
from ..infrastructure.file_runtime import get_user_data_dir
from .comparison_runner import run_comparison
from .processing_service import build_log_path, write_log_file

DEFAULT_RETENTION_MINUTES = 30
DEFAULT_MAX_JOBS = 20
DEFAULT_SWEEP_INTERVAL_SECONDS = 300
DEFAULT_MAX_CONCURRENT_JOBS = 2


def get_max_concurrent_jobs() -> int:
    raw = os.environ.get("DATASET_COMPARATOR_MAX_CONCURRENT_JOBS", "").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_MAX_CONCURRENT_JOBS


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TERMINAL_STATUSES = frozenset(
    {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
)

JobFinishedHook = Callable[["JobState"], None]


@dataclass
class JobState:
    """单个比对任务的运行状态，所有可变字段在 lock 保护下读写。"""

    job_id: str
    status: JobStatus
    parameters: ParameterDocument
    config_name: str
    user_id: int
    stop_flag: threading.Event
    created_at: datetime.datetime
    progress_percent: Optional[float] = None
    progress_message: Optional[str] = None
    log_lines: List[str] = field(default_factory=list)
    output_path: Optional[str] = None
    log_path: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    finished_at: Optional[datetime.datetime] = None
    finalized_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)


class JobManager:
    """单任务串行的比对任务注册表。"""

    def __init__(
        self,
        retention_minutes: int = DEFAULT_RETENTION_MINUTES,
        max_jobs: int = DEFAULT_MAX_JOBS,
        sweep_interval_seconds: int = DEFAULT_SWEEP_INTERVAL_SECONDS,
        now: Callable[[], datetime.datetime] = datetime.datetime.now,
        max_concurrent_jobs: Optional[int] = None,
        on_finished: Optional["JobFinishedHook"] = None,
    ) -> None:
        self._retention_minutes = retention_minutes
        self._max_jobs = max_jobs
        self._sweep_interval_seconds = sweep_interval_seconds
        self._now = now
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobState] = {}
        self._user_active: Dict[int, str] = {}
        self._sweep_timer: Optional[threading.Timer] = None
        if max_concurrent_jobs is None:
            max_concurrent_jobs = get_max_concurrent_jobs()
        self._max_concurrent_jobs = max(1, max_concurrent_jobs)
        self._semaphore = threading.Semaphore(self._max_concurrent_jobs)
        self._finished_hook = on_finished

    def has_active_job(self) -> bool:
        with self._lock:
            return bool(self._user_active)

    def submit(
        self, parameters: ParameterDocument, config_name: str = "web", user_id: int = 0
    ) -> JobState:
        """登记任务并在后台线程执行。

        同一用户已有运行中任务时抛 ``ValueError``；跨用户并发受全局信号量
        限制，超限任务保持 pending 排队。
        """
        with self._lock:
            active_job_id = self._user_active.get(user_id)
            if active_job_id:
                active_job = self._jobs.get(active_job_id)
                # 终态任务在 finalize 清理映射前存在一个很短的窗口；
                # 必须等历史 hook 完成，避免硬删用户与落库并发。
                if active_job is None or (
                    active_job.status in _TERMINAL_STATUSES
                    and active_job.finalized_event.is_set()
                ):
                    del self._user_active[user_id]
                else:
                    raise ValueError("已有比对任务正在运行，请等待完成或取消后再提交")
            job = JobState(
                job_id=uuid.uuid4().hex[:16],
                status=JobStatus.PENDING,
                parameters=parameters,
                config_name=config_name,
                user_id=user_id,
                stop_flag=threading.Event(),
                created_at=self._now(),
            )
            self._jobs[job.job_id] = job
            self._user_active[user_id] = job.job_id
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

    def _job_belongs_to(self, job: JobState, user_id: Optional[int]) -> bool:
        """归属校验：未提供 user_id 视为管理员/内部访问放行。"""
        return user_id is None or job.user_id == user_id

    def snapshot(
        self, job_id: str, since: int = 0, user_id: Optional[int] = None
    ) -> Optional[dict]:
        """返回供 HTTP 响应使用的任务状态快照（含 since 之后的新日志行）。"""
        job = self._jobs.get(job_id)
        if job is None or not self._job_belongs_to(job, user_id):
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

    def cancel_all_for_user(self, user_id: int, timeout: float = 10.0) -> int:
        """取消指定用户所有非终态任务并等待其结束，返回取消数量。

        用户硬删除前调用；等待时间超过 ``timeout`` 时放弃等待（删除流程继续）。
        """
        with self._lock:
            targets = [
                job
                for job in self._jobs.values()
                if job.user_id == user_id
                and job.status in (JobStatus.PENDING, JobStatus.RUNNING)
            ]
        for job in targets:
            with job.lock:
                if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                    job.stop_flag.set()
        deadline = time.monotonic() + timeout
        for job in targets:
            while time.monotonic() < deadline:
                with job.lock:
                    terminal = job.status in _TERMINAL_STATUSES
                if terminal and job.finalized_event.is_set():
                    break
                time.sleep(0.02)
        return len(targets)

    def cancel_job(
        self, job_id: str, user_id: Optional[int] = None
    ) -> Optional[JobState]:
        """请求停止任务；返回任务状态，已结束任务不做任何操作。"""
        job = self._jobs.get(job_id)
        if job is None or not self._job_belongs_to(job, user_id):
            return None
        with job.lock:
            if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
                return job
        job.stop_flag.set()
        return job

    def get_log_lines(
        self, job_id: str, since: int = 0, user_id: Optional[int] = None
    ) -> Tuple[List[str], int]:
        job = self._jobs.get(job_id)
        if job is None or not self._job_belongs_to(job, user_id):
            return [], 0
        with job.lock:
            return list(job.log_lines[since:]), len(job.log_lines)

    def cleanup(self, now: Optional[datetime.datetime] = None) -> int:
        """淘汰超过保留期的已结束任务，并控制任务总数上限。"""
        current = now or self._now()
        removed = 0
        with self._lock:
            deadline = current - datetime.timedelta(minutes=self._retention_minutes)
            for job in list(self._jobs.values()):
                if (
                    job.status in _TERMINAL_STATUSES
                    and job.finished_at is not None
                    and job.finished_at <= deadline
                ):
                    del self._jobs[job.job_id]
                    removed += 1
            remaining_terminal = [
                job for job in self._jobs.values() if job.status in _TERMINAL_STATUSES
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
                timer = threading.Timer(self._sweep_interval_seconds, self._sweep_loop)
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
                timer = threading.Timer(self._sweep_interval_seconds, self._sweep_loop)
                timer.daemon = True
                timer.start()
                self._sweep_timer = timer
            else:
                self._sweep_timer = None

    def _run_thread(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        acquired = self._semaphore.acquire(timeout=None)
        try:
            if not acquired:
                return
            self._run_with_semaphore(job_id)
        finally:
            self._semaphore.release()

    def set_finished_hook(self, hook: Optional[JobFinishedHook]) -> None:
        """注册任务结束回调（历史记录落库等），在任务锁外触发。"""
        self._finished_hook = hook

    def _run_with_semaphore(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        run_started = self._now()
        work_dir: Optional[str] = None
        try:
            if job.stop_flag.is_set():
                # 排队期间被取消：无日志、无产出文件，直接以 cancelled 收尾。
                self._finish(job, JobStatus.CANCELLED, error="用户停止了操作")
            else:
                with job.lock:
                    job.status = JobStatus.RUNNING
                    job.started_at = run_started
                work_dir = os.path.join(
                    get_user_data_dir(job.user_id), "temp", job.job_id
                )
                os.makedirs(work_dir, exist_ok=True)
                output_path = run_comparison(
                    job.parameters,
                    config_name=job.config_name,
                    log_func=self._build_log_func(job),
                    progress_func=self._build_progress_func(job),
                    stop_flag=job.stop_flag,
                    work_dir=work_dir,
                    now=run_started,
                )
                with job.lock:
                    job.status = JobStatus.COMPLETED
                    job.output_path = output_path
                    job.finished_at = self._now()
        except InterruptedError as exc:
            self._finish(job, JobStatus.CANCELLED, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - 失败信息要落到任务状态
            self._finish(job, JobStatus.FAILED, error="比对处理失败: {}".format(exc))
        finally:
            self._finalize_job(job, job_id, run_started, work_dir)

    def _build_progress_func(self, job: JobState) -> Callable[..., None]:
        def job_progress_func(message: str, percent: Optional[int] = None) -> None:
            with job.lock:
                if percent is not None:
                    job.progress_percent = float(percent)
                if message:
                    job.progress_message = message

        return job_progress_func

    def _build_log_func(self, job: JobState) -> Callable[[str], None]:
        def job_log_func(message: str) -> None:
            # 领域层通过 shared.log() 输出时已经打印过一次，这里只负责归档，
            # 避免与既有 stdout 行为叠加成重复输出。
            with job.lock:
                job.log_lines.append(message)

        return job_log_func

    def _finalize_job(
        self,
        job: JobState,
        job_id: str,
        run_started: datetime.datetime,
        work_dir: Optional[str],
    ) -> None:
        self._persist_job_log(job, run_started)
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        # 必须在 finally 清理完成后触发：排队取消也要进入历史记录。
        self._notify_finished(job)
        job.finalized_event.set()
        with self._lock:
            if self._user_active.get(job.user_id) == job_id:
                del self._user_active[job.user_id]

    def _persist_job_log(self, job: JobState, run_started: datetime.datetime) -> None:
        with job.lock:
            if job.status not in _TERMINAL_STATUSES:
                return
            lines = list(job.log_lines)
            output_directory = job.parameters.get("output_directory", "")
        try:
            log_path = write_log_file(
                build_log_path(job.config_name, output_directory, now=run_started),
                lines,
            )
        except Exception as exc:  # noqa: BLE001 - 日志失败不得阻断任务清理
            log("写入日志文件失败: {}".format(exc), None)
            log_path = None
        with job.lock:
            job.log_path = log_path

    def _finish(self, job: JobState, status: JobStatus, error: str) -> None:
        with job.lock:
            job.status = status
            job.error = error
            job.finished_at = self._now()
            if error and (not job.log_lines or job.log_lines[-1] != error):
                # 即使路径校验在领域日志初始化前失败，落盘日志也要包含可诊断信息。
                job.log_lines.append(error)

    def _notify_finished(self, job: JobState) -> None:
        """任务锁外触发结束回调；记录失败不改变任务状态，仅记日志。"""
        hook = self._finished_hook
        if hook is None:
            return
        try:
            hook(job)
        except Exception as exc:  # noqa: BLE001 - 历史记录失败不得翻转任务状态
            log("记录比对历史失败: {}".format(exc), None)


_instance_lock = threading.Lock()
_instance: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """模块级 JobManager 单例（web_api 与 users 路由共用）。"""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = JobManager()
        return _instance
