"""配置 CRUD API 测试：用户隔离、内置模板保护与导入导出。"""

import json
import time

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


def test_rename_rejected_while_job_unfinalized(
    auth_client, tmp_path, monkeypatch
) -> None:
    """回归：项目存在未收尾任务（终态但 hook 未完成）时改名必须 409，
    且项目文件与历史保持原样。收尾完成后改名成功并迁移历史。"""
    import threading

    from src.backend.application import job_manager as job_manager_module
    from src.backend.application.comparison_history_service import (
        record_job_finished,
    )
    from src.backend.infrastructure import database
    from src.backend.infrastructure.database import init_db, session_context
    from src.backend.infrastructure.models.comparison_run import ComparisonRun
    from src.frontend import web_api

    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    database._engine = None
    init_db()
    auth_client.put("/api/configs/旧项目", json={"anchor_row_num": 2})

    release = threading.Event()
    hook_started = threading.Event()

    def fake_run_comparison(
        parameters,
        config_name="web",
        log_func=None,
        progress_func=None,
        stop_flag=None,
        work_dir=None,
        now=None,
    ):
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(job_manager_module, "run_comparison", fake_run_comparison)
    web_api._job_manager.set_finished_hook(
        lambda job: (
            hook_started.set(),
            release.wait(10),
        )
    )
    job = web_api._job_manager.submit(
        {"old_file_path": "o.xlsx", "new_file_path": "n.xlsx"},
        config_name="旧项目",
        user_id=1,
    )
    deadline = time.monotonic() + 10
    while job.status.value != "completed" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert hook_started.wait(10)
    assert not job.finalized_event.is_set()
    assert web_api._job_manager.get_job(job.job_id) is not None

    # 阻塞窗口内改名 → 409
    response = auth_client.post(
        "/api/configs/旧项目/rename", json={"new_name": "新项目"}
    )
    assert response.status_code == 409
    assert "正在收尾" in response.json()["detail"]
    assert auth_client.get("/api/configs/旧项目").status_code == 200
    assert auth_client.get("/api/configs/新项目").status_code == 404

    # 收尾完成后改名成功并迁移历史
    release.set()
    deadline = time.monotonic() + 10
    while not job.finalized_event.is_set() and time.monotonic() < deadline:
        time.sleep(0.01)
    # 收尾完成后改名成功并迁移历史
    assert (
        auth_client.post(
            "/api/configs/旧项目/rename", json={"new_name": "新项目"}
        ).status_code
        == 200
    )
    with session_context() as session:
        rows = session.query(ComparisonRun).filter_by(user_id=1).all()
        assert all(r.config_name == "新项目" for r in rows)
    # 恢复生产 hook：清成 None 会让后续依赖历史落库的测试（test_web_api_jobs）
    # 拿不到历史行。
    web_api._job_manager.set_finished_hook(record_job_finished)


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
