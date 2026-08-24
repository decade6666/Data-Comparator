"""任务 API 测试：提交、轮询、取消与用户归属。"""

import io
import os
import threading
import time

from src.frontend import web_api


def _upload(client, name):
    response = client.post(
        "/api/upload",
        files={"file": (name, io.BytesIO(b"xlsx"), "application/octet-stream")},
    )
    assert response.status_code == 201
    return response.json()["upload_id"]


def _submit(client):
    return client.post(
        "/api/jobs",
        json={
            "old_file_upload_id": _upload(client, "old.xlsx"),
            "new_file_upload_id": _upload(client, "new.xlsx"),
        },
    )


def _poll(client, job_id, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in ("completed", "failed", "cancelled"):
            return body
        time.sleep(0.02)
    raise AssertionError("任务未结束")


def test_submit_job_returns_status(monkeypatch, auth_client):
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
        log_func("开始处理")
        progress_func("处理中", 50)
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(
        "src.backend.application.job_manager.run_comparison", fake_run_comparison
    )
    response = _submit(auth_client)
    assert response.status_code == 201
    release.set()
    body = _poll(auth_client, response.json()["job_id"])
    assert body["status"] == "completed"
    assert body["progress_percent"] == 50.0
    assert body["log_lines"] == ["开始处理"]


def test_submit_path_fields_rejected(auth_client):
    response = auth_client.post(
        "/api/jobs",
        json={"old_file_path": "old.xlsx", "new_file_path": "new.xlsx"},
    )
    assert response.status_code == 422


def test_unknown_upload_returns_400(auth_client):
    response = auth_client.post(
        "/api/jobs",
        json={"old_file_upload_id": "old", "new_file_upload_id": "new"},
    )
    assert response.status_code == 400


def test_cancel_running_job(monkeypatch, auth_client):
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
        started.set()
        stop_flag.wait(10)
        raise InterruptedError("用户停止了操作")

    monkeypatch.setattr(
        "src.backend.application.job_manager.run_comparison", fake_run_comparison
    )
    response = _submit(auth_client)
    job_id = response.json()["job_id"]
    assert started.wait(10)
    cancelled = auth_client.post(f"/api/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    body = _poll(auth_client, job_id)
    assert body["status"] == "cancelled"


def test_unknown_job_returns_404(auth_client):
    assert auth_client.get("/api/jobs/unknown").status_code == 404
    assert auth_client.post("/api/jobs/unknown/cancel").status_code == 404


def test_completed_job_persists_history_and_log(tmp_path, monkeypatch, auth_client):
    """端到端：真实任务完成后，comparison_run 有记录且日志文件生成。"""
    from src.backend.infrastructure import database
    from src.backend.infrastructure.database import init_db, session_context
    from src.backend.infrastructure.file_runtime import get_user_results_dir
    from src.backend.infrastructure.models.comparison_run import ComparisonRun

    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:

        def fake(
            parameters,
            config_name="web",
            log_func=None,
            progress_func=None,
            stop_flag=None,
            work_dir=None,
            now=None,
        ):
            log_func("✅ 比对开始")
            log_func("✅ 比对完成")
            return "/tmp/out/report.xlsx"

        monkeypatch.setattr("src.backend.application.job_manager.run_comparison", fake)
        resp = _submit(auth_client)
        assert resp.status_code == 201
        job_id = resp.json()["job_id"]
        _poll(auth_client, job_id)

        # hook 在任务状态置为终态之后才落库，轮询等两拍避免竞态
        rows = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with session_context() as session:
                rows = session.query(ComparisonRun).filter_by(user_id=1).all()
                if rows:
                    break
            time.sleep(0.02)

        with session_context() as session:
            rows = session.query(ComparisonRun).filter_by(user_id=1).all()
            assert len(rows) == 1
            row = rows[0]
            assert row.status == "completed"
            assert row.job_id == job_id
            # 日志文件写到 results 目录（fake 的 output_path 是 /tmp/out，但
            # 日志按 parameters.output_directory 落盘，即用户自己的 results 目录）
            results_dir = get_user_results_dir(1)
            assert row.log_filename is not None
            assert os.path.isfile(os.path.join(results_dir, row.log_filename or ""))
        log_response = auth_client.get(f"/api/jobs/{job_id}/log")
        assert log_response.status_code == 200
        assert log_response.headers["content-type"].startswith("text/plain")
    finally:
        database._engine = None
