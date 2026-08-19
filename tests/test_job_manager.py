"""JobManager 单元测试：状态流转、进度/日志归档、取消、并发约束与清理。"""

import datetime
import threading
import time

import pytest

from src.backend.application import job_manager as job_manager_module
from src.backend.application.job_manager import JobManager, JobStatus
from src.shared.contracts import ParameterDocument

MINIMAL_PARAMS: ParameterDocument = {
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


def _install_fake_run_comparison(monkeypatch, fake):
    monkeypatch.setattr(job_manager_module, "run_comparison", fake)


def test_submit_runs_and_completes(monkeypatch) -> None:
    release = threading.Event()

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        release.wait(10)
        progress_func("开始处理表单", 20)
        log_func("开始处理表单 AE")
        progress_func("所有表单处理完成", 100)
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS, config_name="CIMS")

    assert job.status in (JobStatus.PENDING, JobStatus.RUNNING)
    release.set()
    assert _wait_for_terminal(job) == JobStatus.COMPLETED
    snapshot = manager.snapshot(job.job_id)
    assert snapshot["status"] == "completed"
    assert snapshot["output_path"] == "/tmp/out/report.xlsx"
    assert snapshot["progress_percent"] == 100.0
    assert snapshot["progress_message"] == "所有表单处理完成"
    assert snapshot["log_lines"] == ["开始处理表单 AE"]
    assert snapshot["log_cursor"] == 1
    assert not manager.has_active_job()
    manager.stop()


def test_progress_func_writes_partial_updates(monkeypatch) -> None:
    updates = []

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        for percent in (20, 45, 85, 100):
            progress_func(f"进度 {percent}", percent)
            updates.append(percent)
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS)
    _wait_for_terminal(job)

    assert updates == [20, 45, 85, 100]
    snapshot = manager.snapshot(job.job_id)
    assert snapshot["progress_percent"] == 100.0
    assert snapshot["progress_message"] == "进度 100"
    manager.stop()


def test_log_lines_respect_since_cursor(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        log_func("line1")
        log_func("line2")
        log_func("line3")
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS)
    _wait_for_terminal(job)

    lines, cursor = manager.get_log_lines(job.job_id, since=1)
    assert lines == ["line2", "line3"]
    assert cursor == 3

    empty_lines, _ = manager.get_log_lines(job.job_id, since=3)
    assert empty_lines == []
    assert manager.get_log_lines("unknown", since=0) == ([], 0)
    manager.stop()


def test_cancel_sets_stop_flag_and_marks_cancelled(monkeypatch) -> None:
    flag_holder = {}
    started = threading.Event()

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        flag_holder["flag"] = stop_flag
        started.set()
        stop_flag.wait(10)
        raise InterruptedError("用户停止了操作")

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS)
    assert started.wait(10)
    cancelled = manager.cancel_job(job.job_id)

    assert cancelled is not None
    assert flag_holder["flag"].is_set()
    assert _wait_for_terminal(job) == JobStatus.CANCELLED
    assert job.error == "用户停止了操作"
    assert not manager.has_active_job()
    manager.stop()


def test_cancel_terminal_job_is_noop(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS)
    _wait_for_terminal(job)

    assert manager.cancel_job(job.job_id) is not None
    assert manager.cancel_job("unknown") is None
    manager.stop()


def test_concurrent_submit_rejected(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        started.set()
        release.wait(10)
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS)
    assert started.wait(10)
    assert manager.has_active_job()

    with pytest.raises(ValueError, match="已有比对任务正在运行"):
        manager.submit(MINIMAL_PARAMS)

    release.set()
    assert _wait_for_terminal(job) == JobStatus.COMPLETED
    assert not manager.has_active_job()
    manager.stop()


def test_failed_job_records_error(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        raise RuntimeError("保存文件失败")

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS)

    assert _wait_for_terminal(job) == JobStatus.FAILED
    snapshot = manager.snapshot(job.job_id)
    assert snapshot["status"] == "failed"
    assert snapshot["error"] == "比对处理失败: 保存文件失败"
    assert snapshot["output_path"] is None
    manager.stop()


def test_cleanup_removes_expired_jobs(monkeypatch) -> None:
    now_ref = {"value": datetime.datetime(2026, 8, 18, 12, 0, 0)}

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager(retention_minutes=30, now=lambda: now_ref["value"])

    job = manager.submit(MINIMAL_PARAMS)
    _wait_for_terminal(job)

    assert manager.cleanup() == 0
    assert manager.get_job(job.job_id) is not None

    now_ref["value"] += datetime.timedelta(minutes=31)
    assert manager.cleanup() == 1
    assert manager.get_job(job.job_id) is None
    manager.stop()


def test_cleanup_caps_total_jobs(monkeypatch) -> None:
    now_ref = {"value": datetime.datetime(2026, 8, 18, 12, 0, 0)}

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager(max_jobs=2, now=lambda: now_ref["value"])

    job_ids = []
    for _ in range(3):
        job = manager.submit(MINIMAL_PARAMS)
        _wait_for_terminal(job)
        job_ids.append(job.job_id)

    assert manager.cleanup() == 1
    remaining = [manager.get_job(job_id) for job_id in job_ids]
    assert sum(1 for item in remaining if item is not None) == 2
    manager.stop()
