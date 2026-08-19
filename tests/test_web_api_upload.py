"""上传端点测试：扩展名白名单、大小限制与上传记录返回。"""

import io

from fastapi.testclient import TestClient

from src.frontend import web_api
from src.backend.infrastructure.upload_store import UploadStore


def test_upload_xlsx_returns_upload_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        web_api, "_upload_store", UploadStore(base_dir=str(tmp_path))
    )
    client = TestClient(web_api.app)

    response = client.post(
        "/api/upload",
        files={
            "file": (
                "old.xlsx",
                io.BytesIO(b"PK\x03\x04data"),
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "old.xlsx"
    assert body["size"] == len(b"PK\x03\x04data")
    upload_id = body["upload_id"]
    assert web_api._upload_store.resolve(upload_id) is not None


def test_upload_xls_is_accepted(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        web_api, "_upload_store", UploadStore(base_dir=str(tmp_path))
    )
    client = TestClient(web_api.app)

    response = client.post(
        "/api/upload",
        files={
            "file": (
                "data.xls",
                io.BytesIO(b"legacy"),
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 201


def test_upload_invalid_extension_returns_400(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        web_api, "_upload_store", UploadStore(base_dir=str(tmp_path))
    )
    client = TestClient(web_api.app)

    response = client.post(
        "/api/upload",
        files={"file": ("evil.txt", io.BytesIO(b"x"), "text/plain")},
    )

    assert response.status_code == 400
    assert "仅支持" in response.json()["detail"]


def test_upload_exceeds_size_returns_413(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        web_api, "_upload_store", UploadStore(base_dir=str(tmp_path))
    )
    monkeypatch.setenv("DATASET_COMPARATOR_MAX_UPLOAD_MB", "1")
    client = TestClient(web_api.app)

    response = client.post(
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
    assert "超过限制" in response.json()["detail"]
