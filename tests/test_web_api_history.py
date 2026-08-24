"""历史记录 API 测试：列表、详情、下载、归属与错误码。"""

import io
import os
import time

from src.backend.infrastructure import database
from src.backend.infrastructure.database import init_db, session_context
from src.backend.infrastructure.models.comparison_run import ComparisonRun
from src.shared.contracts import ParameterDocument


def _upload(client, name):
    response = client.post(
        "/api/upload",
        files={"file": (name, io.BytesIO(b"xlsx"), "application/octet-stream")},
    )
    assert response.status_code == 201
    return response.json()["upload_id"]


def _create_user(client, username, password):
    return client.post("/api/users", json={"username": username, "password": password})


def _login(client, username, password) -> str:
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seed_run(
    client,
    *,
    user_id=1,
    config_name="项目A",
    report_name="项目A-比对报告-2026-08-23T12-00-00.xlsx",
    log_name="项目A-比对日志-2026-08-23T12-00-00.txt",
    status="completed",
    report_exists=True,
    log_exists=True,
) -> int:
    """直接向 DB 种一条历史行（绕过任务流程，返回 run_id）。"""
    from src.backend.infrastructure.file_runtime import get_user_results_dir

    results_dir = get_user_results_dir(user_id)
    os.makedirs(results_dir, exist_ok=True)
    if report_exists and report_name:
        with open(os.path.join(results_dir, report_name), "wb") as f:
            f.write(b"xlsx")
    if log_exists and log_name:
        with open(os.path.join(results_dir, log_name), "wb") as f:
            f.write(b"log")

    with session_context() as session:
        run = ComparisonRun(
            user_id=user_id,
            job_id="seed%04d" % user_id,
            config_name=config_name,
            status=status,
            report_filename=report_name,
            log_filename=log_name,
            report_size_bytes=(
                os.path.getsize(os.path.join(results_dir, report_name))
                if report_exists and report_name
                else 0
            ),
            parameters_json='{"include_sheets": ["S1"], "ignore_cols": ["x"]}',
            finished_at=__import__("datetime").datetime(2026, 8, 23, 12, 0, 0),
        )
        session.add(run)
        session.commit()
        return run.id


def test_history_empty_for_new_user(auth_client):
    response = auth_client.get("/api/history")
    assert response.status_code == 200
    assert response.json() == []


def test_record_finished_skips_missing_user(auth_client, tmp_path, monkeypatch):
    """回归：用户已被删除后，历史 hook 不得落库，也不得重建用户目录。"""
    import datetime

    from src.backend.application.comparison_history_service import (
        record_job_finished,
    )
    from src.backend.application.job_manager import JobState, JobStatus
    from src.backend.infrastructure.file_runtime import get_user_data_dir

    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    bob_dir = get_user_data_dir(bob_id)
    os.makedirs(bob_dir, exist_ok=True)
    params: ParameterDocument = {
        "old_file_path": "o.xlsx",
        "new_file_path": "n.xlsx",
        "output_directory": "",
    }
    job = JobState(
        job_id="ghost-job",
        status=JobStatus.COMPLETED,
        parameters=params,
        config_name="项目A",
        user_id=bob_id,
        stop_flag=__import__("threading").Event(),
        created_at=datetime.datetime(2026, 8, 23, 12, 0, 0),
    )
    with session_context() as session:
        from src.backend.infrastructure.models.user import User

        session.query(User).filter(User.id == bob_id).delete()
        session.commit()

    record_job_finished(job)
    with session_context() as session:
        assert session.query(ComparisonRun).filter_by(user_id=bob_id).count() == 0


def test_history_lists_and_scopes_to_user(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:
        bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
        bob_token = _login(auth_client, "bob", "bob-pass-123")
        bob_headers = _headers(bob_token)
        alice_id = _create_user(auth_client, "alice", "alice-pass-123").json()["id"]

        rid_bob = _seed_run(auth_client, user_id=bob_id, config_name="项目A")
        _seed_run(auth_client, user_id=alice_id, config_name="项目A")

        # bob 只能看到自己的行
        rows = auth_client.get(
            "/api/history?config_name=项目A", headers=bob_headers
        ).json()
        assert len(rows) == 1
        assert rows[0]["id"] == rid_bob
        # alice 的 id 对 bob 不可见 → 404
        assert (
            auth_client.get(
                f"/api/history/{rid_bob}",
                headers=_headers(_login(auth_client, "alice", "alice-pass-123")),
            ).status_code
            == 404
        )
    finally:
        database._engine = None


def test_history_detail_has_redacted_params(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:
        rid = _seed_run(auth_client, user_id=1, config_name="项目A")
        detail = auth_client.get(f"/api/history/{rid}").json()
        # API 原样回放落库的参数；剥离发生在 record_run（见服务层测试）
        assert detail["parameters"]["include_sheets"] == ["S1"]
        assert "old_file_path" not in detail["parameters"]
    finally:
        database._engine = None


def test_history_report_download(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:
        rid = _seed_run(auth_client, user_id=1, config_name="项目A")
        resp = auth_client.get(f"/api/history/{rid}/report")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument"
        )
        assert "filename" in resp.headers.get("content-disposition", "")
    finally:
        database._engine = None


def test_history_log_download(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:
        rid = _seed_run(auth_client, user_id=1, config_name="项目A")
        resp = auth_client.get(f"/api/history/{rid}/log")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
    finally:
        database._engine = None


def test_history_missing_file_returns_410(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:
        rid = _seed_run(
            auth_client,
            user_id=1,
            config_name="项目A",
            report_exists=False,
        )
        resp = auth_client.get(f"/api/history/{rid}/report")
        assert resp.status_code == 410
    finally:
        database._engine = None


def test_history_failed_run_report_returns_404(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:
        rid = _seed_run(
            auth_client,
            user_id=1,
            config_name="项目A",
            status="failed",
            report_name=None,
            report_exists=False,
        )
        resp = auth_client.get(f"/api/history/{rid}/report")
        assert resp.status_code == 404
    finally:
        database._engine = None


def test_history_requires_auth(auth_client, tmp_path, monkeypatch):
    unauthed = auth_client
    unauthed.headers.pop("Authorization", None)
    assert unauthed.get("/api/history").status_code == 401


def test_history_limit_validation(auth_client):
    assert auth_client.get("/api/history?limit=0").status_code == 422
    assert auth_client.get("/api/history?limit=999").status_code == 422
