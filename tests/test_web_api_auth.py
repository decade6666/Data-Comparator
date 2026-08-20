# -*- coding: utf-8 -*-
"""认证与用户隔离的 Web API 集成测试。"""

import pytest
from fastapi.testclient import TestClient

from src.backend.infrastructure import database
from src.backend.infrastructure.database import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATASET_COMPARATOR_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_PASSWORD", "admin-pass-123")
    database._engine = None
    init_db()

    from src.frontend import web_api

    with TestClient(web_api.app) as c:
        yield c
    database._engine = None


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, username, password):
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


def _create_user(client, admin_token, username, password):
    return client.post(
        "/api/users",
        json={"username": username, "password": password},
        headers=_auth_headers(admin_token),
    )


def test_login_ok_and_protected_endpoint_requires_auth(client) -> None:
    assert _login(client, "admin", "wrong-pass").status_code == 401

    ok = _login(client, "admin", "admin-pass-123")
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    assert token

    assert client.get("/api/configs").status_code == 401
    assert client.get("/api/configs", headers=_auth_headers(token)).status_code == 200


def test_admin_creates_user_and_self_password_change(client) -> None:
    admin_token = _login(client, "admin", "admin-pass-123").json()["access_token"]

    created = _create_user(client, admin_token, "bob", "bob-pass-123")
    assert created.status_code == 201

    bob_token = _login(client, "bob", "bob-pass-123").json()["access_token"]
    change = client.put(
        "/api/auth/me/password",
        json={"current_password": "bob-pass-123", "new_password": "new-pass-456"},
        headers=_auth_headers(bob_token),
    )
    assert change.status_code == 204
    # 改密后旧 token 失效
    assert (
        client.get("/api/configs", headers=_auth_headers(bob_token)).status_code == 401
    )
    assert _login(client, "bob", "new-pass-456").status_code == 200


def test_non_admin_cannot_access_user_admin(client) -> None:
    admin_token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    _create_user(client, admin_token, "bob", "bob-pass-123")
    bob_token = _login(client, "bob", "bob-pass-123").json()["access_token"]

    assert client.get("/api/users", headers=_auth_headers(bob_token)).status_code == 403
    assert (
        client.post(
            "/api/users",
            json={"username": "carol", "password": "carol-pass-123"},
            headers=_auth_headers(bob_token),
        ).status_code
        == 403
    )


def test_admin_renames_user_and_old_token_invalidated(client) -> None:
    admin_token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    created = _create_user(client, admin_token, "bob", "bob-pass-123")
    bob_id = created.json()["id"]
    bob_token = _login(client, "bob", "bob-pass-123").json()["access_token"]

    rename = client.put(
        f"/api/users/{bob_id}",
        json={"username": "bob2"},
        headers=_auth_headers(admin_token),
    )
    assert rename.status_code == 204

    users = client.get("/api/users", headers=_auth_headers(admin_token)).json()
    usernames = [u["username"] for u in users]
    assert "bob2" in usernames
    assert "bob" not in usernames

    # 改名后旧 token 因 username 不匹配立即失效
    assert (
        client.get("/api/configs", headers=_auth_headers(bob_token)).status_code == 401
    )
    assert _login(client, "bob2", "bob-pass-123").status_code == 200


def test_rename_user_conflicts(client) -> None:
    admin_token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    bob_id = _create_user(client, admin_token, "bob", "bob-pass-123").json()["id"]
    _create_user(client, admin_token, "carol", "carol-pass-123")

    # 重名 → 400
    resp = client.put(
        f"/api/users/{bob_id}",
        json={"username": "carol"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 400
    assert "用户名已存在" in resp.json()["detail"]
    # 改为保留管理员名 → 400
    resp = client.put(
        f"/api/users/{bob_id}",
        json={"username": "admin"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 400
    assert "保留管理员账号" in resp.json()["detail"]
    # 不存在 id → 404
    resp = client.put(
        "/api/users/9999",
        json={"username": "nobody"},
        headers=_auth_headers(admin_token),
    )
    assert resp.status_code == 404


def test_users_isolated_configs(client) -> None:
    admin_token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    _create_user(client, admin_token, "bob", "bob-pass-123")
    bob_token = _login(client, "bob", "bob-pass-123").json()["access_token"]

    client.put(
        "/api/configs/mine",
        json={"anchor_row_num": 5},
        headers=_auth_headers(bob_token),
    )
    # 管理员看不到 bob 的配置
    admin_configs = client.get(
        "/api/configs", headers=_auth_headers(admin_token)
    ).json()
    assert "mine" not in admin_configs["configs"]
    # bob 自己能看到
    body = client.get("/api/configs", headers=_auth_headers(bob_token)).json()
    assert body["configs"] == ["mine"]


def test_compare_requires_upload_or_422(client, monkeypatch) -> None:
    token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    headers = _auth_headers(token)

    # 旧路径字段已下线：无 upload_id 时返回明确的 400
    assert client.post("/api/compare", json={}, headers=headers).status_code == 400
    assert (
        client.post(
            "/api/compare",
            json={
                "old_file_path": "old.xlsx",
                "new_file_path": "new.xlsx",
                "output_directory": "/tmp/out",
            },
            headers=headers,
        ).status_code
        == 422
    )
    # 缺 upload 详情 → 400
    assert (
        client.post(
            "/api/compare",
            json={"output_directory": "/tmp/out"},
            headers=headers,
        ).status_code
        == 400
    )


def test_browse_endpoint_removed(client) -> None:
    token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    response = client.get(
        "/api/browse", params={"path": "/tmp"}, headers=_auth_headers(token)
    )
    assert response.status_code == 404


def test_admin_list_users_without_engine_collision(client) -> None:
    admin_token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    body = client.get("/api/users", headers=_auth_headers(admin_token))
    assert body.status_code == 200
    usernames = [u["username"] for u in body.json()]
    assert "admin" in usernames


def test_protected_response_has_refreshed_token_header(client) -> None:
    """受保护端点必须在响应中下发 X-Refreshed-Token，且新 token 可通过认证。"""
    admin_token = _login(client, "admin", "admin-pass-123").json()["access_token"]
    response = client.get("/api/configs", headers=_auth_headers(admin_token))
    assert response.status_code == 200
    refreshed = response.headers.get("X-Refreshed-Token")
    assert refreshed
    # 新 token 可正常通过认证
    assert (
        client.get("/api/configs", headers=_auth_headers(refreshed)).status_code == 200
    )


def test_openapi_has_no_response_query_param(client) -> None:
    """get_current_user 的 Response 注入不得泄漏为 OpenAPI 查询参数。"""
    spec = client.get("/openapi.json").json()
    params = spec["paths"]["/api/configs"]["get"].get("parameters", [])
    assert all(p["name"] != "response" for p in params)
