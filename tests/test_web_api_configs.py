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


def test_rename_config(auth_client) -> None:
    auth_client.put("/api/configs/源配置", json=MINIMAL_DOC)
    response = auth_client.post(
        "/api/configs/源配置/rename", json={"new_name": "改名配置"}
    )
    assert response.status_code == 200
    assert response.json() == {"name": "改名配置", "renamed": True}
    assert auth_client.get("/api/configs/改名配置").json() == MINIMAL_DOC
    assert auth_client.get("/api/configs/源配置").status_code == 404


def test_rename_config_errors(auth_client) -> None:
    auth_client.put("/api/configs/源配置", json=MINIMAL_DOC)
    auth_client.put("/api/configs/目标配置", json=MINIMAL_DOC)
    assert (
        auth_client.post(
            "/api/configs/源配置/rename", json={"new_name": "目标配置"}
        ).status_code
        == 409
    )
    assert (
        auth_client.post(
            "/api/configs/不存在/rename", json={"new_name": "新配置"}
        ).status_code
        == 404
    )
    assert (
        auth_client.post(
            f"/api/configs/源配置/rename",
            json={"new_name": BUILTIN_TEMPLATE_TM},
        ).status_code
        == 400
    )
    assert (
        auth_client.post(
            f"/api/configs/{BUILTIN_TEMPLATE_CIMS}/rename",
            json={"new_name": "新配置"},
        ).status_code
        == 400
    )
    assert (
        auth_client.post(
            "/api/configs/源配置/rename", json={"new_name": ""}
        ).status_code
        == 422
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


def test_rename_migrates_history_and_copy_does_not(
    auth_client, tmp_path, monkeypatch
) -> None:
    """改名后历史行跟随新项目名；复制不迁移（副本无历史）。"""
    from src.backend.infrastructure import database
    from src.backend.infrastructure.database import init_db, session_context
    from src.backend.infrastructure.models.comparison_run import ComparisonRun

    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    try:
        auth_client.put("/api/configs/旧项目", json={"anchor_row_num": 2})
        with session_context() as session:
            session.add(
                ComparisonRun(
                    user_id=1,
                    job_id="r1",
                    config_name="旧项目",
                    status="completed",
                    report_filename=None,
                    log_filename=None,
                    report_size_bytes=0,
                    parameters_json="{}",
                    finished_at=__import__("datetime").datetime(2026, 8, 23, 12, 0, 0),
                )
            )
            session.commit()

        resp = auth_client.post(
            "/api/configs/旧项目/rename", json={"new_name": "新项目"}
        )
        assert resp.status_code == 200

        with session_context() as session:
            rows = session.query(ComparisonRun).filter_by(user_id=1).all()
            assert all(r.config_name == "新项目" for r in rows)

        # 复制不迁移：新建「旧项目」副本不产生新历史
        auth_client.put("/api/configs/旧项目", json={"anchor_row_num": 2})
        auth_client.post("/api/configs/旧项目/copy", json={"new_name": "副本项目"})
        with session_context() as session:
            rows = session.query(ComparisonRun).filter_by(user_id=1).all()
            assert len(rows) == 1
            assert rows[0].config_name == "新项目"
    finally:
        database._engine = None
