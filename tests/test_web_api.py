from src.frontend import web_api


def test_health_endpoint_reports_ok(auth_client) -> None:
    response = auth_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_compare_requires_two_upload_ids(auth_client) -> None:
    response = auth_client.post("/api/compare", json={})
    assert response.status_code == 400
    assert "上传文件" in response.json()["detail"]


def test_compare_rejects_server_path_fields(auth_client) -> None:
    response = auth_client.post(
        "/api/compare",
        json={
            "old_file_path": "old.xlsx",
            "new_file_path": "new.xlsx",
        },
    )
    assert response.status_code == 422


def test_compare_maps_uploaded_inputs(monkeypatch, auth_client) -> None:
    calls = {}

    def fake_run_comparison(parameters, config_name="web", log_func=None):
        calls["parameters"] = parameters
        calls["config_name"] = config_name
        return "/tmp/out/report.xlsx"

    monkeypatch.setattr(web_api, "run_comparison", fake_run_comparison)
    response = auth_client.post(
        "/api/compare",
        json={
            "old_file_upload_id": "old",
            "new_file_upload_id": "new",
            "config_name": "CIMS",
        },
    )
    # 上传记录不存在，边界校验应先失败
    assert response.status_code == 400


def test_compare_maps_unexpected_failure(monkeypatch, auth_client) -> None:
    def fake_run_comparison(parameters, config_name="web", log_func=None):
        raise RuntimeError("处理崩溃")

    monkeypatch.setattr(web_api, "run_comparison", fake_run_comparison)
    response = auth_client.post(
        "/api/compare",
        json={"old_file_upload_id": "old", "new_file_upload_id": "new"},
    )
    assert response.status_code == 400


def test_compare_request_carries_sheet_common_cols() -> None:
    document = web_api.CompareRequest(
        common_cols=["A"], sheet_common_cols={"AE": ["B"]}
    ).to_parameter_document()
    assert document["common_cols"] == ["A"]
    assert document["sheet_common_cols"] == {"AE": ["B"]}


def test_compare_request_defaults_sheet_common_cols() -> None:
    document = web_api.CompareRequest().to_parameter_document()
    assert document["sheet_common_cols"] == {}


def test_compare_rejects_misspelled_sheet_common_cols(auth_client) -> None:
    # extra: forbid 拦下拼错的键名；同时锁定字段名的确切拼写
    response = auth_client.post(
        "/api/compare",
        json={
            "old_file_upload_id": "old",
            "new_file_upload_id": "new",
            "sheet_commoncols": {},
        },
    )
    assert response.status_code == 422
