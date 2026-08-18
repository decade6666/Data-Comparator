"""任务生命周期 API 测试：提交、轮询、取消与下载。"""

import threading
import time

import pytest
from fastapi.testclient import TestClient

from src.frontend import web_api

RUN_COMPARISON_TARGET = "src.backend.application.job_manager.run_comparison"

VALID_PATHS = {
    "old_file_path": "/data/old.xlsx",
    "new_file_path": "/data/new.xlsx",
    "output_directory": "/data/output",
}


@pytest.fixture(autouse=True)
def _stop_job_manager_after_test():
    yield
    # 等待后台任务自然结束，避免失败用例遗留的活动任务污染后续测试
    deadline = time.monotonic() + 15
    while (
        web_api._job_manager.has_active_job()
        and time.monotonic() < deadline
    ):
        time.sleep(0.02)
    web_api._job_manager.stop()


def _poll_job(client: TestClient, job_id: str, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in ("completed", "failed", "cancelled"):
            return body
        time.sleep(0.02)
    raise AssertionError(f"任务 {job_id} 未在 {timeout}s 内结束")


def test_submit_job_returns_201_with_job_id(monkeypatch) -> None:
    release = threading.Event()

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        release.wait(10)
        log_func("开始处理")
        progress_func("处理中", 50)
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    response = client.post("/api/jobs", json=VALID_PATHS)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] in ("pending", "running")
    job_id = body["job_id"]
    release.set()

    status = _poll_job(client, job_id)
    assert status["status"] == "completed"
    assert status["output_path"] == "/tmp/out/report.xlsx"
    assert status["progress_percent"] == 50.0
    assert status["log_lines"] == ["开始处理"]


def test_job_status_log_cursor_pagination(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        log_func("line1")
        log_func("line2")
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    job_id = client.post("/api/jobs", json=VALID_PATHS).json()["job_id"]
    status = _poll_job(client, job_id)
    cursor = status["log_cursor"]
    assert cursor == 2

    second = client.get(f"/api/jobs/{job_id}?since={cursor}").json()
    assert second["log_lines"] == []
    assert second["log_cursor"] == 2


def test_submit_missing_paths_returns_400() -> None:
    client = TestClient(web_api.app)

    response = client.post(
        "/api/jobs",
        json={
            "old_file_path": "",
            "new_file_path": "",
            "output_directory": "",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "请填写所有必要的路径信息"}


def test_submit_while_active_returns_409(monkeypatch) -> None:
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

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    first = client.post("/api/jobs", json=VALID_PATHS)
    assert first.status_code == 201
    assert started.wait(10)

    second = client.post("/api/jobs", json=VALID_PATHS)

    assert second.status_code == 409
    release.set()
    _poll_job(client, first.json()["job_id"])


def test_submit_job_with_upload_ids_resolves_paths(
    monkeypatch, tmp_path
) -> None:
    import io

    from src.backend.infrastructure.upload_store import UploadStore

    received = {}

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        received["parameters"] = parameters
        return "/tmp/out/report.xlsx"

    store = UploadStore(base_dir=str(tmp_path))
    old_record = store.save("old.xlsx", io.BytesIO(b"old"), max_bytes=10**6)
    new_record = store.save("new.xlsx", io.BytesIO(b"new"), max_bytes=10**6)
    monkeypatch.setattr(web_api, "_upload_store", store)
    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/jobs",
        json={
            "old_file_upload_id": old_record.upload_id,
            "new_file_upload_id": new_record.upload_id,
            "config_name": "web",
        },
    )

    assert response.status_code == 201
    _poll_job(client, response.json()["job_id"])
    assert received["parameters"]["old_file_path"] == old_record.file_path
    assert received["parameters"]["new_file_path"] == new_record.file_path
    assert (
        received["parameters"]["output_directory"]
        == store.default_output_dir()
    )


def test_submit_job_with_unknown_upload_returns_400(
    tmp_path, monkeypatch
) -> None:
    from src.backend.infrastructure.upload_store import UploadStore

    monkeypatch.setattr(
        web_api, "_upload_store", UploadStore(base_dir=str(tmp_path))
    )
    client = TestClient(web_api.app)

    response = client.post(
        "/api/jobs",
        json={
            "old_file_upload_id": "unknown",
            "new_file_upload_id": "unknown",
        },
    )

    assert response.status_code == 400


def test_submit_job_with_path_and_upload_returns_400(
    monkeypatch, tmp_path
) -> None:
    import io

    from src.backend.infrastructure.upload_store import UploadStore

    store = UploadStore(base_dir=str(tmp_path))
    record = store.save("old.xlsx", io.BytesIO(b"old"), max_bytes=10**6)
    monkeypatch.setattr(web_api, "_upload_store", store)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/jobs",
        json={
            "old_file_path": "/data/old.xlsx",
            "old_file_upload_id": record.upload_id,
            "new_file_path": "/data/new.xlsx",
            "output_directory": "/data/output",
        },
    )

    assert response.status_code == 400
    assert "只选择一种方式" in response.json()["detail"]


def test_get_job_status_unknown_returns_404() -> None:
    client = TestClient(web_api.app)

    assert client.get("/api/jobs/unknown").status_code == 404


def test_cancel_running_job_returns_cancelling(monkeypatch) -> None:
    started = threading.Event()

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        started.set()
        stop_flag.wait(10)
        raise InterruptedError("用户停止了操作")

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    job_id = client.post("/api/jobs", json=VALID_PATHS).json()["job_id"]
    assert started.wait(10)

    response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json() == {"job_id": job_id, "status": "cancelling"}

    status = _poll_job(client, job_id)
    assert status["status"] == "cancelled"
    assert status["error"] == "用户停止了操作"


def test_cancel_completed_job_returns_409(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    job_id = client.post("/api/jobs", json=VALID_PATHS).json()["job_id"]
    _poll_job(client, job_id)

    response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 409
    assert response.json() == {"detail": "任务已结束，无法取消"}


def test_failed_job_reports_error(monkeypatch) -> None:
    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        raise RuntimeError("保存文件失败")

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    job_id = client.post("/api/jobs", json=VALID_PATHS).json()["job_id"]

    status = _poll_job(client, job_id)
    assert status["status"] == "failed"
    assert status["error"] == "比对处理失败: 保存文件失败"


def test_download_completed_job_returns_file(monkeypatch, tmp_path) -> None:
    output_file = tmp_path / "报告.xlsx"
    output_file.write_bytes(b"PK\x03\x04fake-xlsx-content")

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
    ):
        return str(output_file)

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    job_id = client.post("/api/jobs", json=VALID_PATHS).json()["job_id"]
    _poll_job(client, job_id)

    response = client.get(f"/api/jobs/{job_id}/download")

    assert response.status_code == 200
    assert response.content == b"PK\x03\x04fake-xlsx-content"
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats"
    )


def test_download_running_job_returns_404(monkeypatch) -> None:
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

    monkeypatch.setattr(RUN_COMPARISON_TARGET, fake_run_comparison)
    client = TestClient(web_api.app)

    job_id = client.post("/api/jobs", json=VALID_PATHS).json()["job_id"]
    assert started.wait(10)

    assert client.get(f"/api/jobs/{job_id}/download").status_code == 404
    release.set()
    _poll_job(client, job_id)


def test_download_unknown_job_returns_404() -> None:
    client = TestClient(web_api.app)

    assert client.get("/api/jobs/unknown/download").status_code == 404
