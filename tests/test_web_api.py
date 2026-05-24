from fastapi.testclient import TestClient

from src.frontend import web_api


def test_health_endpoint_reports_ok() -> None:
    client = TestClient(web_api.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_compare_endpoint_runs_synchronous_comparison(monkeypatch) -> None:
    calls = {}

    def fake_run_comparison(parameters, config_name="web", log_func=None):
        calls["parameters"] = parameters
        calls["config_name"] = config_name
        log_func("开始处理")
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(web_api, "run_comparison", fake_run_comparison)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/compare",
        json={
            "old_file_path": "old.xlsx",
            "new_file_path": "new.xlsx",
            "output_directory": "/tmp/out",
            "config_name": "CIMS",
            "anchor_row_num": 2,
            "header_row_num": 3,
            "common_cols": ["更新时间"],
            "exclude_sheets": ["说明"],
            "default_keys": ["USUBJID"],
            "sheet_key_map": {"AE": ["USUBJID", "AESEQ"]},
            "colors": {"highlight_fill": "#FFFFFF"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"output_path": "/tmp/out/report.xlsx"}
    assert calls["config_name"] == "CIMS"
    assert calls["parameters"]["old_file_path"] == "old.xlsx"
    assert calls["parameters"]["anchor_row_num"] == 2
    assert calls["parameters"]["sheet_key_map"] == {"AE": ["USUBJID", "AESEQ"]}
    assert calls["parameters"]["colors"] == {"highlight_fill": "#FFFFFF"}


def test_compare_endpoint_maps_missing_input_to_404(monkeypatch) -> None:
    def fake_run_comparison(parameters, config_name="web", log_func=None):
        raise FileNotFoundError("输入文件不存在")

    monkeypatch.setattr(web_api, "run_comparison", fake_run_comparison)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/compare",
        json={
            "old_file_path": "old.xlsx",
            "new_file_path": "new.xlsx",
            "output_directory": "/tmp/out",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "输入文件不存在"}


def test_compare_endpoint_logs_unexpected_failure(monkeypatch) -> None:
    messages = []

    def fake_run_comparison(parameters, config_name="web", log_func=None):
        raise Exception("处理崩溃")

    monkeypatch.setattr(web_api, "run_comparison", fake_run_comparison)
    monkeypatch.setattr(web_api, "_api_log", messages.append)
    client = TestClient(web_api.app)

    response = client.post(
        "/api/compare",
        json={
            "old_file_path": "old.xlsx",
            "new_file_path": "new.xlsx",
            "output_directory": "/tmp/out",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "比对处理失败: 处理崩溃"}
    assert messages == ["比对处理失败: 处理崩溃"]


def test_compare_endpoint_requires_paths() -> None:
    client = TestClient(web_api.app)

    response = client.post("/api/compare", json={})

    assert response.status_code == 422
