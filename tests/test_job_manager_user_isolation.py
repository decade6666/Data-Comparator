# -*- coding: utf-8 -*-
"""JobManager 多用户并发与归属校验测试。"""

import threading
import time

import pytest

from src.backend.application import job_manager as job_manager_module
from src.backend.application.job_manager import JobManager, JobStatus

MINIMAL_PARAMS = {
    "old_file_path": "/data/old.xlsx",
    "new_file_path": "/data/new.xlsx",
    "output_directory": "/data/output",
}


def _wait_for_terminal(job, timeout: float = 10.0) -> JobStatus:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if job.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            return job.status
        time.sleep(0.01)
    raise AssertionError(f"任务未在 {timeout}s 内结束，当前状态: {job.status}")


def _blocking_fake(release, started=None, interrupted=False):
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
    ):
        if started is not None:
            started.set()
        release.wait(10)
        if interrupted:
            raise InterruptedError("用户停止了操作")
        return "/tmp/out/report.xlsx"

    return fake_run_comparison


def test_job_records_user_id(monkeypatch) -> None:
    release = threading.Event()
    monkeypatch.setattr(job_manager_module, "run_comparison", _blocking_fake(release))
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS, config_name="web", user_id=42)
    assert job.user_id == 42
    release.set()
    _wait_for_terminal(job)
    manager.stop()


def test_same_user_second_job_rejected(monkeypatch) -> None:
    release = threading.Event()
    started = threading.Event()
    monkeypatch.setattr(
        job_manager_module, "run_comparison", _blocking_fake(release, started)
    )
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS, user_id=1)
    assert started.wait(10)

    with pytest.raises(ValueError, match="已有比对任务正在运行"):
        manager.submit(MINIMAL_PARAMS, user_id=1)

    release.set()
    _wait_for_terminal(job)
    manager.stop()


def test_different_users_run_concurrently(monkeypatch) -> None:
    release = threading.Event()
    started = threading.Event()
    monkeypatch.setattr(
        job_manager_module, "run_comparison", _blocking_fake(release, started)
    )
    manager = JobManager()

    job_a = manager.submit(MINIMAL_PARAMS, user_id=1)
    assert started.wait(10)

    job_b = manager.submit(MINIMAL_PARAMS, user_id=2)
    assert job_b.status in (JobStatus.PENDING, JobStatus.RUNNING)

    release.set()
    assert _wait_for_terminal(job_a) == JobStatus.COMPLETED
    assert _wait_for_terminal(job_b) == JobStatus.COMPLETED
    assert not manager.has_active_job()
    manager.stop()


def test_cancel_requires_owner(monkeypatch) -> None:
    release = threading.Event()
    started = threading.Event()
    monkeypatch.setattr(
        job_manager_module,
        "run_comparison",
        _blocking_fake(release, started, interrupted=True),
    )
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS, user_id=1)
    assert started.wait(10)

    # 他人取消 → 404 语义（返回 None），不触碰 stop_flag
    assert manager.cancel_job(job.job_id, user_id=2) is None
    assert not job.stop_flag.is_set()

    # 本人取消 → stop_flag 置位，领域层随即抛 InterruptedError → cancelled
    assert manager.cancel_job(job.job_id, user_id=1) is not None
    assert job.stop_flag.is_set()
    release.set()
    assert _wait_for_terminal(job) == JobStatus.CANCELLED
    manager.stop()


def test_snapshot_requires_owner(monkeypatch) -> None:
    release = threading.Event()
    monkeypatch.setattr(job_manager_module, "run_comparison", _blocking_fake(release))
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS, user_id=7)
    assert manager.snapshot(job.job_id, user_id=7) is not None
    assert manager.snapshot(job.job_id, user_id=8) is None
    assert manager.get_log_lines(job.job_id, since=0, user_id=8) == ([], 0)
    release.set()
    _wait_for_terminal(job)
    manager.stop()


def test_global_semaphore_queues_third_job(monkeypatch) -> None:
    release = threading.Event()
    started = threading.Event()
    monkeypatch.setattr(
        job_manager_module, "run_comparison", _blocking_fake(release, started)
    )
    manager = JobManager(max_concurrent_jobs=2)

    job_a = manager.submit(MINIMAL_PARAMS, user_id=1)
    assert started.wait(10)
    job_b = manager.submit(MINIMAL_PARAMS, user_id=2)
    started.clear()

    # 第三个不同用户提交：进入 pending 排队而非报错
    job_c = manager.submit(MINIMAL_PARAMS, user_id=3)
    assert job_c.status == JobStatus.PENDING

    release.set()
    assert _wait_for_terminal(job_a) == JobStatus.COMPLETED
    assert _wait_for_terminal(job_b) == JobStatus.COMPLETED
    assert _wait_for_terminal(job_c) == JobStatus.COMPLETED
    manager.stop()
