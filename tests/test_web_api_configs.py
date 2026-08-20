"""配置 CRUD API 测试：用户隔离、内置模板保护与导入导出。"""

import json

from src.backend.infrastructure.parameter_templates import (
    BUILTIN_TEMPLATE_CIMS,
    BUILTIN_TEMPLATE_TM,
)

MINIMAL_DOC = {"anchor_row_num": 1, "common_cols": ["STUDYID"]}


def test_list_configs_includes_builtin_templates(auth_client) -> None:
    response = auth_client.get("/api/configs")
    assert response.status_code == 200
    assert BUILTIN_TEMPLATE_CIMS not in response.json()["configs"]
    assert BUILTIN_TEMPLATE_TM not in response.json()["configs"]
    assert response.json()["builtin_templates"] == [
        BUILTIN_TEMPLATE_CIMS,
        BUILTIN_TEMPLATE_TM,
    ]


def test_save_get_delete_config(auth_client) -> None:
    saved = auth_client.put("/api/configs/我的配置", json=MINIMAL_DOC)
    assert saved.status_code == 200
    assert saved.json() == {"name": "我的配置", "saved": True}
    assert auth_client.get("/api/configs/我的配置").json() == MINIMAL_DOC

    deleted = auth_client.delete("/api/configs/我的配置")
    assert deleted.status_code == 200
    assert auth_client.get("/api/configs/我的配置").status_code == 404


def test_missing_and_builtin_config_errors(auth_client) -> None:
    assert auth_client.get("/api/configs/不存在").status_code == 404
    assert auth_client.delete(f"/api/configs/{BUILTIN_TEMPLATE_TM}").status_code == 400
    assert (
        auth_client.put(
            f"/api/configs/{BUILTIN_TEMPLATE_CIMS}", json=MINIMAL_DOC
        ).status_code
        == 400
    )


def test_copy_config(auth_client) -> None:
    auth_client.put("/api/configs/源配置", json=MINIMAL_DOC)
    response = auth_client.post(
        "/api/configs/源配置/copy", json={"new_name": "备份配置"}
    )
    assert response.status_code == 200
    assert auth_client.get("/api/configs/备份配置").json() == MINIMAL_DOC
    assert (
        auth_client.post(
            "/api/configs/源配置/copy", json={"new_name": "备份配置"}
        ).status_code
        == 409
    )


def test_export_and_import_config(auth_client) -> None:
    auth_client.put("/api/configs/导出配置", json=MINIMAL_DOC)
    exported = auth_client.get("/api/configs/导出配置/export")
    assert exported.status_code == 200
    assert exported.json() == MINIMAL_DOC
    assert "attachment" in exported.headers["content-disposition"]

    content = json.dumps(MINIMAL_DOC, ensure_ascii=False).encode("utf-8")
    imported = auth_client.post(
        "/api/configs/import",
        files={"file": ("导入配置.json", content, "application/json")},
    )
    assert imported.status_code == 200
    assert auth_client.get("/api/configs/导入配置").json() == MINIMAL_DOC


def test_export_strips_file_and_sheet_fields(auth_client) -> None:
    doc = {
        **MINIMAL_DOC,
        "old_file_path": "/data/old.xlsx",
        "new_file_path": "/data/new.xlsx",
        "old_file_upload_id": "upload-old-1",
        "new_file_upload_id": "upload-new-1",
        "old_file_sheets": ["旧表1"],
        "new_file_sheets": ["新表1"],
    }
    auth_client.put("/api/configs/导出配置", json=doc)
    exported = auth_client.get("/api/configs/导出配置/export")

    assert exported.status_code == 200
    body = exported.json()
    for field in (
        "old_file_path",
        "new_file_path",
        "old_file_upload_id",
        "new_file_upload_id",
        "old_file_sheets",
        "new_file_sheets",
    ):
        assert field not in body
    assert body["anchor_row_num"] == MINIMAL_DOC["anchor_row_num"]
    assert body["common_cols"] == MINIMAL_DOC["common_cols"]


def test_import_invalid_json(auth_client) -> None:
    response = auth_client.post(
        "/api/configs/import",
        files={"file": ("bad.json", b"not-json{", "application/json")},
    )
    assert response.status_code == 400
