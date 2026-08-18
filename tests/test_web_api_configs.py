"""配置 CRUD API 测试：列表、加载、保存、删除、复制、导入、导出与内置模板保护。"""

import json

from fastapi.testclient import TestClient

from src.frontend import web_api
from src.backend.infrastructure.parameter_repository import (
    JsonParameterRepository,
)
from src.backend.infrastructure.parameter_templates import (
    BUILTIN_TEMPLATE_CIMS,
    BUILTIN_TEMPLATE_TM,
)

MINIMAL_DOC = {
    "old_file_path": "",
    "new_file_path": "",
    "output_directory": "",
}


def _install_fresh_repo(monkeypatch, tmp_path) -> JsonParameterRepository:
    repo = JsonParameterRepository(base_dir_getter=lambda: str(tmp_path))
    repo.ensure_config_directory()
    monkeypatch.setattr(web_api, "_config_repository", repo)
    return repo


def test_list_configs_includes_builtin_templates(
    monkeypatch, tmp_path
) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.get("/api/configs")

    assert response.status_code == 200
    body = response.json()
    assert body["configs"] == []
    assert body["builtin_templates"] == [
        BUILTIN_TEMPLATE_CIMS,
        BUILTIN_TEMPLATE_TM,
    ]


def test_get_config_returns_document(monkeypatch, tmp_path) -> None:
    repo = _install_fresh_repo(monkeypatch, tmp_path)
    repo.save_document("我的配置", MINIMAL_DOC)
    client = TestClient(web_api.app)

    response = client.get("/api/configs/我的配置")

    assert response.status_code == 200
    assert response.json() == MINIMAL_DOC


def test_get_missing_config_returns_404(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.get("/api/configs/不存在")

    assert response.status_code == 404


def test_save_config_persists_document(monkeypatch, tmp_path) -> None:
    repo = _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.put("/api/configs/CIMS对比", json=MINIMAL_DOC)

    assert response.status_code == 200
    assert response.json() == {"name": "CIMS对比", "saved": True}
    assert repo.load_document("CIMS对比") == MINIMAL_DOC


def test_save_builtin_template_returns_400(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.put(
        f"/api/configs/{BUILTIN_TEMPLATE_CIMS}", json=MINIMAL_DOC
    )

    assert response.status_code == 400
    assert "内置模板" in response.json()["detail"]


def test_delete_config_removes_document(monkeypatch, tmp_path) -> None:
    repo = _install_fresh_repo(monkeypatch, tmp_path)
    repo.save_document("待删除", MINIMAL_DOC)
    client = TestClient(web_api.app)

    response = client.delete("/api/configs/待删除")

    assert response.status_code == 200
    assert response.json() == {"name": "待删除", "deleted": True}
    assert repo.load_document("待删除") is None


def test_delete_missing_config_returns_404(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.delete("/api/configs/不存在")

    assert response.status_code == 404


def test_delete_builtin_template_returns_400(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.delete(f"/api/configs/{BUILTIN_TEMPLATE_TM}")

    assert response.status_code == 400


def test_copy_config_creates_new_document(monkeypatch, tmp_path) -> None:
    repo = _install_fresh_repo(monkeypatch, tmp_path)
    repo.save_document("源配置", MINIMAL_DOC)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/configs/源配置/copy", json={"new_name": "备份配置"}
    )

    assert response.status_code == 200
    assert repo.load_document("备份配置") == MINIMAL_DOC


def test_copy_missing_source_returns_404(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.post("/api/configs/不存在/copy", json={"new_name": "新配置"})

    assert response.status_code == 404


def test_copy_existing_target_returns_409(monkeypatch, tmp_path) -> None:
    repo = _install_fresh_repo(monkeypatch, tmp_path)
    repo.save_document("源配置", MINIMAL_DOC)
    repo.save_document("目标配置", MINIMAL_DOC)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/configs/源配置/copy", json={"new_name": "目标配置"}
    )

    assert response.status_code == 409


def test_export_config_returns_json_file(monkeypatch, tmp_path) -> None:
    repo = _install_fresh_repo(monkeypatch, tmp_path)
    repo.save_document("导出配置", MINIMAL_DOC)
    client = TestClient(web_api.app)

    response = client.get("/api/configs/导出配置/export")

    assert response.status_code == 200
    assert response.json() == MINIMAL_DOC
    assert "attachment" in response.headers.get("content-disposition", "")
    assert ".json" in response.headers.get("content-disposition", "")


def test_export_missing_config_returns_404(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.get("/api/configs/不存在/export")

    assert response.status_code == 404


def test_import_config_from_json_upload(monkeypatch, tmp_path) -> None:
    repo = _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)
    content = json.dumps(MINIMAL_DOC, ensure_ascii=False).encode("utf-8")

    response = client.post(
        "/api/configs/import",
        files={"file": ("导入配置.json", content, "application/json")},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "导入配置"
    assert repo.load_document("导入配置") == MINIMAL_DOC


def test_import_invalid_json_returns_400(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/configs/import",
        files={"file": ("bad.json", b"not-json{", "application/json")},
    )

    assert response.status_code == 400
    assert "JSON" in response.json()["detail"]


def test_import_non_object_json_returns_400(monkeypatch, tmp_path) -> None:
    _install_fresh_repo(monkeypatch, tmp_path)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/configs/import",
        files={"file": ("list.json", b"[1,2,3]", "application/json")},
    )

    assert response.status_code == 400
    assert "配置对象" in response.json()["detail"]
