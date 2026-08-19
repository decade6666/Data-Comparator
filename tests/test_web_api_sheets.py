"""Sheet 名称发现端点测试。"""

import io

from fastapi.testclient import TestClient

from src.frontend import web_api
from src.backend.infrastructure.upload_store import UploadStore


def _make_xlsx() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "AE"
    wb.create_sheet("DM")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_get_sheets_returns_sheet_names(tmp_path, monkeypatch) -> None:
    file_path = tmp_path / "data.xlsx"
    file_path.write_bytes(_make_xlsx())
    client = TestClient(web_api.app)

    response = client.get("/api/sheets", params={"file_path": str(file_path)})

    assert response.status_code == 200
    assert set(response.json()["sheets"]) == {"AE", "DM"}


def test_get_sheets_missing_file_returns_404(tmp_path) -> None:
    client = TestClient(web_api.app)

    response = client.get(
        "/api/sheets", params={"file_path": str(tmp_path / "nope.xlsx")}
    )

    assert response.status_code == 404


def test_get_sheets_via_upload_id(monkeypatch, tmp_path) -> None:
    store = UploadStore(base_dir=str(tmp_path))
    record = store.save("data.xlsx", io.BytesIO(_make_xlsx()), max_bytes=10**6)
    monkeypatch.setattr(web_api, "_upload_store", store)
    client = TestClient(web_api.app)

    response = client.get(
        "/api/sheets", params={"upload_id": record.upload_id}
    )

    assert response.status_code == 200
    assert set(response.json()["sheets"]) == {"AE", "DM"}


def test_get_sheets_unknown_upload_returns_400(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        web_api, "_upload_store", UploadStore(base_dir=str(tmp_path))
    )
    client = TestClient(web_api.app)

    response = client.get("/api/sheets", params={"upload_id": "unknown"})

    assert response.status_code == 400


def test_get_sheets_without_input_returns_400() -> None:
    client = TestClient(web_api.app)

    response = client.get("/api/sheets")

    assert response.status_code == 400
