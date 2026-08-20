# -*- coding: utf-8 -*-
"""管理员配置操作 API 测试：列表/批量复制/批量转移/批量删除/回收站。"""

DOC_WITH_UPLOADS = {
    "anchor_row_num": 5,
    "old_file_upload_id": "up-old-1",
    "new_file_upload_id": "up-new-1",
    "old_file_path": "/data/old.xlsx",
    "new_file_path": "/data/new.xlsx",
}


def _create_user(client, username, password):
    return client.post("/api/users", json={"username": username, "password": password})


def _login(client, username, password) -> str:
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_admin_lists_user_configs(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    auth_client.put(
        "/api/configs/我的配置", json={"anchor_row_num": 5}, headers=_headers(bob_token)
    )

    body = auth_client.get(f"/api/admin/users/{bob_id}/configs")
    assert body.status_code == 200
    assert body.json() == {"configs": ["我的配置"]}
    # 内置模板不出现
    assert "TM" not in body.json()["configs"]

    assert auth_client.get("/api/admin/users/9999/configs").status_code == 404


def test_batch_copy_clears_upload_fields_and_appends_suffix(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    carol_id = _create_user(auth_client, "carol", "carol-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    auth_client.put(
        "/api/configs/源配置", json=DOC_WITH_UPLOADS, headers=_headers(bob_token)
    )

    response = auth_client.post(
        "/api/admin/configs/batch-copy",
        json={
            "config_names": ["源配置"],
            "source_user_id": bob_id,
            "target_user_id": carol_id,
        },
    )
    assert response.status_code == 200
    assert response.json() == [
        {"config_name": "源配置", "new_name": "源配置", "status": "success"}
    ]

    # 目标用户看到的配置已清空 upload 字段
    carol_token = _login(auth_client, "carol", "carol-pass-123")
    copied = auth_client.get(
        "/api/configs/源配置", headers=_headers(carol_token)
    ).json()
    for field in (
        "old_file_upload_id",
        "new_file_upload_id",
        "old_file_path",
        "new_file_path",
    ):
        assert field not in copied
    assert copied["anchor_row_num"] == 5

    # 再次复制 → 重名后缀 (副本)
    response = auth_client.post(
        "/api/admin/configs/batch-copy",
        json={
            "config_names": ["源配置"],
            "source_user_id": bob_id,
            "target_user_id": carol_id,
        },
    )
    assert response.json()[0]["new_name"] == "源配置 (副本)"

    # 源配置仍在 bob 名下
    assert auth_client.get("/api/configs", headers=_headers(bob_token)).json()[
        "configs"
    ] == ["源配置"]


def test_batch_copy_missing_source_reports_failed_item(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    carol_id = _create_user(auth_client, "carol", "carol-pass-123").json()["id"]

    response = auth_client.post(
        "/api/admin/configs/batch-copy",
        json={
            "config_names": ["不存在的配置"],
            "source_user_id": bob_id,
            "target_user_id": carol_id,
        },
    )
    assert response.status_code == 200
    assert response.json() == [
        {"config_name": "不存在的配置", "status": "failed", "error": "源配置不存在"}
    ]


def test_batch_copy_unknown_user_returns_404(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]

    # 源用户不存在 → 404
    response = auth_client.post(
        "/api/admin/configs/batch-copy",
        json={
            "config_names": ["源配置"],
            "source_user_id": 9999,
            "target_user_id": bob_id,
        },
    )
    assert response.status_code == 404

    # 目标用户不存在 → 404，且不产生孤儿配置目录
    response = auth_client.post(
        "/api/admin/configs/batch-copy",
        json={
            "config_names": ["源配置"],
            "source_user_id": bob_id,
            "target_user_id": 8888,
        },
    )
    assert response.status_code == 404


def test_batch_move_unknown_user_returns_404(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]

    response = auth_client.post(
        "/api/admin/configs/batch-move",
        json={
            "config_names": ["源配置"],
            "source_user_id": bob_id,
            "target_user_id": 8888,
        },
    )
    assert response.status_code == 404


def test_batch_move_moves_file_and_removes_source(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    carol_id = _create_user(auth_client, "carol", "carol-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    auth_client.put(
        "/api/configs/搬移配置", json=DOC_WITH_UPLOADS, headers=_headers(bob_token)
    )

    response = auth_client.post(
        "/api/admin/configs/batch-move",
        json={
            "config_names": ["搬移配置"],
            "source_user_id": bob_id,
            "target_user_id": carol_id,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success", "moved": 1}

    # 源用户不再拥有
    assert (
        auth_client.get("/api/configs", headers=_headers(bob_token)).json()["configs"]
        == []
    )
    # 目标用户拥有且 upload 字段已清空
    carol_token = _login(auth_client, "carol", "carol-pass-123")
    moved = auth_client.get(
        "/api/configs/搬移配置", headers=_headers(carol_token)
    ).json()
    assert moved["anchor_row_num"] == 5
    assert "old_file_upload_id" not in moved


def test_batch_move_all_fail_returns_400(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    carol_id = _create_user(auth_client, "carol", "carol-pass-123").json()["id"]
    response = auth_client.post(
        "/api/admin/configs/batch-move",
        json={
            "config_names": ["不存在的配置"],
            "source_user_id": bob_id,
            "target_user_id": carol_id,
        },
    )
    assert response.status_code == 400
    assert "全部配置转移失败" in response.json()["detail"]


def test_batch_delete_goes_to_recycle_bin(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    auth_client.put(
        "/api/configs/待删配置", json={"anchor_row_num": 1}, headers=_headers(bob_token)
    )

    response = auth_client.post(
        "/api/admin/configs/batch-delete",
        json={"config_names": ["待删配置", "不存在的配置"], "user_id": bob_id},
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": 1}

    # 用户侧 404
    assert (
        auth_client.get(
            "/api/configs/待删配置", headers=_headers(bob_token)
        ).status_code
        == 404
    )
    # 回收站列表含 owner 信息
    entries = auth_client.get("/api/admin/recycle-bin").json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["original_owner_username"] == "bob"
    assert entry["original_config_name"] == "待删配置"
    assert entry["estimated_size_bytes"] > 0
    assert entry["deleted_by_user_deletion"] is False
    assert "deleted_at" in entry


def test_restore_and_hard_delete_recycle_bin(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    auth_client.put(
        "/api/configs/恢复配置", json=DOC_WITH_UPLOADS, headers=_headers(bob_token)
    )
    auth_client.delete("/api/configs/恢复配置", headers=_headers(bob_token))
    recycled_id = auth_client.get("/api/admin/recycle-bin").json()[0]["id"]

    # 原 owner 仍存在 → 无需 target_user_id
    response = auth_client.post(
        f"/api/admin/recycle-bin/{recycled_id}/restore", json={}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["restored_to_user_id"] == bob_id
    assert body["config_name"] == "恢复配置"

    # 恢复后用户可见且 upload 字段清空
    restored = auth_client.get(
        "/api/configs/恢复配置", headers=_headers(bob_token)
    ).json()
    assert restored["anchor_row_num"] == 5
    assert "old_file_upload_id" not in restored

    # 再删一次 → 彻底删除
    auth_client.delete("/api/configs/恢复配置", headers=_headers(bob_token))
    recycled_id = auth_client.get("/api/admin/recycle-bin").json()[0]["id"]
    assert (
        auth_client.delete(f"/api/admin/recycle-bin/{recycled_id}").status_code == 204
    )
    assert auth_client.get("/api/admin/recycle-bin").json() == []
    # 不存在条目 → 404
    assert (
        auth_client.delete(f"/api/admin/recycle-bin/{recycled_id}").status_code == 404
    )


def test_restore_orphan_requires_target_user(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    carol_id = _create_user(auth_client, "carol", "carol-pass-123").json()["id"]
    bob_token = _login(auth_client, "bob", "bob-pass-123")
    auth_client.put(
        "/api/configs/孤儿配置", json={"anchor_row_num": 1}, headers=_headers(bob_token)
    )

    # 删除用户 bob → 配置入回收站（孤儿）
    assert auth_client.delete(f"/api/users/{bob_id}").status_code == 204
    recycled_id = auth_client.get("/api/admin/recycle-bin").json()[0]["id"]

    # 无 target → 400
    response = auth_client.post(
        f"/api/admin/recycle-bin/{recycled_id}/restore", json={}
    )
    assert response.status_code == 400
    assert "指定目标用户" in response.json()["detail"]

    # 指定目标 → 恢复到 carol
    response = auth_client.post(
        f"/api/admin/recycle-bin/{recycled_id}/restore",
        json={"target_user_id": carol_id},
    )
    assert response.status_code == 200
    assert response.json()["restored_to_user_id"] == carol_id

    carol_token = _login(auth_client, "carol", "carol-pass-123")
    assert (
        auth_client.get(
            "/api/configs/孤儿配置", headers=_headers(carol_token)
        ).status_code
        == 200
    )


def test_non_admin_forbidden(auth_client) -> None:
    _create_user(auth_client, "bob", "bob-pass-123")
    bob_token = _login(auth_client, "bob", "bob-pass-123")

    assert (
        auth_client.get(
            "/api/admin/recycle-bin", headers=_headers(bob_token)
        ).status_code
        == 403
    )
    assert (
        auth_client.get(
            "/api/admin/recycle-bin/cleanup-policy", headers=_headers(bob_token)
        ).status_code
        == 403
    )
    assert (
        auth_client.post(
            "/api/admin/configs/batch-copy",
            json={
                "config_names": ["x"],
                "source_user_id": 1,
                "target_user_id": 2,
            },
            headers=_headers(bob_token),
        ).status_code
        == 403
    )


def test_batch_ops_reject_unsafe_names(auth_client) -> None:
    bob_id = _create_user(auth_client, "bob", "bob-pass-123").json()["id"]
    carol_id = _create_user(auth_client, "carol", "carol-pass-123").json()["id"]

    response = auth_client.post(
        "/api/admin/configs/batch-copy",
        json={
            "config_names": ["../escape"],
            "source_user_id": bob_id,
            "target_user_id": carol_id,
        },
    )
    assert response.status_code == 200
    assert response.json()[0]["status"] == "failed"
