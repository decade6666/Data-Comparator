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


@pytest.fixture(autouse=True)
def _isolate_output_dir(tmp_path, monkeypatch):
    """日志落盘按 output_directory 写文件，指向 tmp_path 避免污染真实目录。"""
    monkeypatch.setitem(MINIMAL_PARAMS, "output_directory", str(tmp_path))


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
        work_dir=None,
        now=None,
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
        work_dir=None,
        now=None,
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
        work_dir=None,
        now=None,
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
        work_dir=None,
        now=None,
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
        work_dir=None,
        now=None,
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
        work_dir=None,
        now=None,
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
        work_dir=None,
        now=None,
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
    assert job.log_lines[-1] == "比对处理失败: 保存文件失败"
    assert job.log_path is not None
    manager.stop()


def test_cleanup_removes_expired_jobs(monkeypatch) -> None:
    now_ref = {"value": datetime.datetime(2026, 8, 18, 12, 0, 0)}

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
        now=None,
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
        work_dir=None,
        now=None,
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


def test_on_finished_hook_fires_once_for_completed(monkeypatch) -> None:
    calls = []

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
        now=None,
    ):
        log_func("line1")
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager(on_finished=lambda job: calls.append(job))

    job = manager.submit(MINIMAL_PARAMS)
    _wait_for_terminal(job)

    assert len(calls) == 1
    assert calls[0].job_id == job.job_id
    assert calls[0].status is JobStatus.COMPLETED
    assert calls[0].log_path is not None
    assert calls[0].output_path == "/tmp/out/report.xlsx"
    manager.stop()


def test_on_finished_hook_fires_for_failed(monkeypatch) -> None:
    calls = []

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
        now=None,
    ):
        log_func("出错了")
        raise RuntimeError("保存文件失败")

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager(on_finished=lambda job: calls.append(job))

    job = manager.submit(MINIMAL_PARAMS)
    _wait_for_terminal(job)

    assert len(calls) == 1
    assert calls[0].status is JobStatus.FAILED
    assert calls[0].output_path is None
    assert calls[0].log_path is not None
    manager.stop()


def test_raising_hook_does_not_change_terminal_status(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
        now=None,
    ):
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)

    def boom(_job):
        raise RuntimeError("落库失败")

    manager = JobManager(on_finished=boom)

    job = manager.submit(MINIMAL_PARAMS)
    assert _wait_for_terminal(job) == JobStatus.COMPLETED
    assert not manager.has_active_job()
    manager.stop()


def test_no_log_file_when_log_lines_empty(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
        now=None,
    ):
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, fake_run_comparison)
    manager = JobManager()

    job = manager.submit(MINIMAL_PARAMS)
    _wait_for_terminal(job)

    assert job.log_path is None
    manager.stop()


def test_cancelled_queued_job_releases_user_active(monkeypatch) -> None:
    """回归：排队中（受信号量阻塞、尚未运行）被取消的任务必须释放
    _user_active，否则该用户被永久 409 拒绝提交。

    排队只发生在跨用户场景：同用户第二个任务在 submit 即被拒，
    跨用户任务才在全局信号量上等待。时序必须是确定性的：
    queued 在 first 释放信号量后才真正运行，因此先释放 first，
    再等两者终结，最后验证用户 2 能再次提交。
    """
    holder = threading.Event()
    first_started = threading.Event()

    def first_run(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
        now=None,
    ):
        first_started.set()
        holder.wait(10)
        return "/tmp/out/report.xlsx"

    _install_fake_run_comparison(monkeypatch, first_run)
    finished = []
    manager = JobManager(
        max_concurrent_jobs=1,
        on_finished=lambda job: finished.append((job.job_id, job.status)),
    )

    first = manager.submit(MINIMAL_PARAMS, user_id=1)
    assert first_started.wait(10)
    queued = manager.submit(MINIMAL_PARAMS, user_id=2)
    assert manager.has_active_job()

    manager.cancel_job(queued.job_id)

    # 释放第一个任务：信号量归还后 queued 才运行并立即以 cancelled 收尾
    holder.set()
    _wait_for_terminal(first)
    _wait_for_terminal(queued)
    assert queued.status is JobStatus.CANCELLED
    assert not manager.has_active_job()
    assert (queued.job_id, JobStatus.CANCELLED) in finished

    # 关键断言：排队被取消后，用户 2 应立即能再次提交（泄漏时会被拒绝）
    retry = manager.submit(MINIMAL_PARAMS, user_id=2)
    _wait_for_terminal(retry)
    manager.stop()
