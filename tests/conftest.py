import os

os.environ.setdefault("DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS", "1")

import time  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.backend.infrastructure import database  # noqa: E402
from src.frontend import web_api  # noqa: E402


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setenv("DATASET_COMPARATOR_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_PASSWORD", "admin-pass-123")
    database._engine = None
    with TestClient(web_api.app) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-pass-123"},
        )
        response.raise_for_status()
        client.headers.update(
            {"Authorization": f"Bearer {response.json()['access_token']}"}
        )
        yield client
    database._engine = None


@pytest.fixture(autouse=True)
def cleanup_job_manager():
    yield
    deadline = time.monotonic() + 10
    while web_api._job_manager.has_active_job() and time.monotonic() < deadline:
        time.sleep(0.02)
    web_api._job_manager.stop()
