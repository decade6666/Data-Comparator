"""上传端点测试：扩展名白名单、大小限制与用户隔离。"""

import io


def test_upload_xlsx_returns_upload_id(auth_client) -> None:
    content = b"PK\x03\x04data"
    response = auth_client.post(
        "/api/upload",
        files={"file": ("old.xlsx", io.BytesIO(content), "application/octet-stream")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "old.xlsx"
    assert body["size"] == len(content)

    status = auth_client.get(f"/api/uploads/{body['upload_id']}")
    assert status.json()["exists"] is True


def test_upload_xls_is_accepted(auth_client) -> None:
    response = auth_client.post(
        "/api/upload",
        files={"file": ("data.xls", io.BytesIO(b"legacy"), "application/octet-stream")},
    )
    assert response.status_code == 201


def test_upload_invalid_extension_returns_400(auth_client) -> None:
    response = auth_client.post(
        "/api/upload",
        files={"file": ("evil.txt", io.BytesIO(b"x"), "text/plain")},
    )
    assert response.status_code == 400
    assert "仅支持" in response.json()["detail"]


def test_missing_upload_status_returns_exists_false(auth_client) -> None:
    response = auth_client.get("/api/uploads/missing-upload")
    assert response.status_code == 200
    assert response.json() == {
        "upload_id": "missing-upload",
        "exists": False,
    }


def test_upload_size_limit_returns_413(auth_client, monkeypatch) -> None:
    monkeypatch.setenv("DATASET_COMPARATOR_MAX_UPLOAD_MB", "1")
    response = auth_client.post(
        "/api/upload",
        files={
            "file": (
                "big.xlsx",
                io.BytesIO(b"x" * (1024 * 1024 + 10)),
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 413
