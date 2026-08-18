"""目录浏览端点测试：白名单围栏、条目过滤与路径不存在处理。"""

import os

import pytest
from fastapi.testclient import TestClient

from src.frontend import web_api


@pytest.fixture()
def browse_root(tmp_path, monkeypatch):
    root = tmp_path / "browse_root"
    root.mkdir()
    (root / "sub").mkdir()
    (root / "data.xlsx").write_bytes(b"PK")
    (root / "data.xls").write_bytes(b"legacy")
    (root / "notes.txt").write_text("ignore me")
    monkeypatch.setenv("DATASET_COMPARATOR_BROWSE_ROOTS", str(root))
    return str(root)


def test_browse_valid_directory_returns_entries(browse_root) -> None:
    client = TestClient(web_api.app)

    response = client.get("/api/browse", params={"path": browse_root})

    assert response.status_code == 200
    body = response.json()
    assert body["current_path"] == browse_root
    names = [entry["name"] for entry in body["entries"]]
    assert "sub" in names
    assert "data.xlsx" in names
    assert "data.xls" in names
    assert "notes.txt" not in names
    file_entry = next(e for e in body["entries"] if e["name"] == "data.xlsx")
    assert file_entry["is_directory"] is False
    assert file_entry["size"] == 2
    dir_entry = next(e for e in body["entries"] if e["name"] == "sub")
    assert dir_entry["is_directory"] is True


def test_browse_directories_only(browse_root) -> None:
    client = TestClient(web_api.app)

    response = client.get(
        "/api/browse", params={"path": browse_root, "type": "directories"}
    )

    assert response.status_code == 200
    names = [entry["name"] for entry in response.json()["entries"]]
    assert names == ["sub"]


def test_browse_parent_path_inside_root(browse_root) -> None:
    client = TestClient(web_api.app)

    sub_path = os.path.join(browse_root, "sub")
    response = client.get("/api/browse", params={"path": sub_path})

    assert response.status_code == 200
    body = response.json()
    assert body["parent_path"] == browse_root


def test_browse_root_has_no_parent(browse_root) -> None:
    client = TestClient(web_api.app)

    response = client.get("/api/browse", params={"path": browse_root})

    assert response.json()["parent_path"] is None


def test_browse_outside_allowed_root_returns_403(
    tmp_path, monkeypatch
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("DATASET_COMPARATOR_BROWSE_ROOTS", str(allowed))
    client = TestClient(web_api.app)

    response = client.get("/api/browse", params={"path": str(outside)})

    assert response.status_code == 403


def test_browse_traversal_returns_403(browse_root) -> None:
    client = TestClient(web_api.app)
    traversal = os.path.join(browse_root, "..", "..", "etc")

    response = client.get("/api/browse", params={"path": traversal})

    assert response.status_code == 403


def test_browse_nonexistent_returns_404(browse_root) -> None:
    client = TestClient(web_api.app)

    response = client.get(
        "/api/browse", params={"path": os.path.join(browse_root, "missing")}
    )

    assert response.status_code == 404
