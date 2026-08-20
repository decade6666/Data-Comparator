# -*- coding: utf-8 -*-
"""用户硬删除测试：配置入回收站/任务取消/目录清理/token 失效。"""

import os
import threading
import time

from src.backend.application.job_manager import JobStatus

MINIMAL_PARAMS = {
    "old_file_path": "/data/old.xlsx",
    "new_file_path": "/data/new.xlsx",
    "output_directory": "/data/output",
}


def _create_user(client, username, password):
    return client.post("/api/users", json={"username": username, "password": password})


def _login(client, username, password) -> str:
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_delete_user_recycles_configs_and_removes_dir(auth_client, tmp_path) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    bob_headers = _headers(bob_token)
    auth_client.put(
        "/api/configs/配置A", json={"anchor_row_num": 1}, headers=bob_headers
    )
    auth_client.put(
        "/api/configs/配置B", json={"anchor_row_num": 2}, headers=bob_headers
    )

    response = auth_client.delete(f"/api/users/{bob_id}")
    assert response.status_code == 204

    # User 行删除
    users = auth_client.get("/api/users").json()
    assert all(user["id"] != bob_id for user in users)
    # 已删除用户的 token 立即失效
    assert auth_client.get("/api/configs", headers=bob_headers).status_code == 401

    # 用户数据目录被删除（不重建）
    assert not os.path.exists(os.path.join(str(tmp_path), "users", str(bob_id)))

    # 全部配置入回收站且标记因用户删除
    entries = auth_client.get("/api/admin/recycle-bin").json()
    names = {entry["original_config_name"] for entry in entries}
    assert names == {"配置A", "配置B"}
    assert all(entry["deleted_by_user_deletion"] is True for entry in entries)
    assert all(entry["original_owner_username"] == "bob" for entry in entries)


def test_delete_user_cancels_running_job(auth_client, monkeypatch) -> None:
    from src.backend.application import job_manager as job_manager_module
    from src.frontend import web_api

    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
    ):
        if stop_flag is not None:
            stop_flag.wait(10)
        if stop_flag is not None and stop_flag.is_set():
            raise InterruptedError("用户停止了操作")
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(job_manager_module, "run_comparison", fake_run_comparison)
    job = web_api._job_manager.submit(MINIMAL_PARAMS, config_name="web", user_id=bob_id)
    deadline = time.monotonic() + 10
    while job.status != JobStatus.RUNNING and time.monotonic() < deadline:
        time.sleep(0.01)
    assert job.status == JobStatus.RUNNING

    # 删除用户 → 运行中任务被取消并等待结束
    assert auth_client.delete(f"/api/users/{bob_id}").status_code == 204
    assert job.status == JobStatus.CANCELLED
    # 任务不被其他用户可见（归属校验）
    assert web_api._job_manager.snapshot(job.job_id, user_id=999) is None


def test_delete_user_unknown_id_404(auth_client) -> None:
    assert auth_client.delete("/api/users/9999").status_code == 404


def test_delete_self_rejected(auth_client) -> None:
    users = auth_client.get("/api/users").json()
    admin = next(user for user in users if user["username"] == "admin")
    response = auth_client.delete(f"/api/users/{admin['id']}")
    assert response.status_code == 400
    assert "不能删除自己" in response.json()["detail"]


def test_delete_reserved_admin_rejected_at_service_level(tmp_path, monkeypatch) -> None:
    import pytest

    from src.backend.infrastructure import database
    from src.backend.infrastructure.database import init_db, session_context
    from src.backend.infrastructure.models.user import User

    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    database._engine = None
    init_db()
    try:
        from src.backend.application.user_admin_service import UserAdminService

        with session_context() as session:
            admin = User(username="admin", is_admin=True)
            session.add(admin)
            session.flush()
            with pytest.raises(ValueError, match="保留管理员账号"):
                UserAdminService.delete_user(session, admin.id)
    finally:
        database._engine = None


def test_deleted_user_login_rejected(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    assert auth_client.delete(f"/api/users/{bob_id}").status_code == 204
    login = auth_client.post(
        "/api/auth/login", json={"username": "bob", "password": "bob-pass-123"}
    )
    assert login.status_code == 401


def test_delete_user_with_pending_extra_config_single_failure_ok(
    auth_client, tmp_path
) -> None:
    """配置文件损坏时删除流程不中断（跳过坏文件，其余照常入站）。"""
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    bob_headers = _headers(bob_token)
    auth_client.put(
        "/api/configs/好配置", json={"anchor_row_num": 1}, headers=bob_headers
    )
    # 手工造一个损坏的 JSON 文件
    bad_dir = os.path.join(str(tmp_path), "users", str(bob_id), "configs")
    os.makedirs(bad_dir, exist_ok=True)
    with open(os.path.join(bad_dir, "坏配置.json"), "w", encoding="utf-8") as file:
        file.write("{not-valid-json")

    assert auth_client.delete(f"/api/users/{bob_id}").status_code == 204
    entries = auth_client.get("/api/admin/recycle-bin").json()
    assert {entry["original_config_name"] for entry in entries} == {"好配置"}
