"""服务器目录浏览已下线。"""

from fastapi.testclient import TestClient

from src.frontend import web_api


def test_browse_endpoint_removed() -> None:
    response = TestClient(web_api.app).get("/api/browse", params={"path": "/tmp"})
    assert response.status_code == 404
