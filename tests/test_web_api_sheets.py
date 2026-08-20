"""上传文件后读取 Sheet 名称。"""

import io

import openpyxl


def _make_xlsx() -> bytes:
    wb = openpyxl.Workbook()
    wb.active.title = "AE"
    wb.create_sheet("DM")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _upload(client):
    response = client.post(
        "/api/upload",
        files={"file": ("data.xlsx", _make_xlsx(), "application/octet-stream")},
    )
    assert response.status_code == 201
    return response.json()["upload_id"]


def test_get_sheets_via_upload_id(auth_client) -> None:
    upload_id = _upload(auth_client)
    response = auth_client.get("/api/sheets", params={"upload_id": upload_id})
    assert response.status_code == 200
    assert set(response.json()["sheets"]) == {"AE", "DM"}


def test_get_sheets_unknown_upload_returns_400(auth_client) -> None:
    response = auth_client.get("/api/sheets", params={"upload_id": "unknown"})
    assert response.status_code == 400


def test_get_sheets_requires_upload_id(auth_client) -> None:
    response = auth_client.get("/api/sheets")
    assert response.status_code == 422
