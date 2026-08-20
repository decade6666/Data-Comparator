# -*- coding: utf-8 -*-
"""回收站清理策略 API 测试：GET/PUT round-trip、非法输入、预览、后台开关。"""

import pytest
from fastapi.testclient import TestClient

from src.backend.infrastructure import database

DEFAULT_POLICY = {
    "interval_minutes": 60,
    "min_retain_hours": 24,
    "age": {"enabled": False, "value": 30, "unit": "day"},
    "size": {"enabled": False, "value": 500, "unit": "MB"},
}


def _put_policy(auth_client, **overrides) -> dict:
    payload = {
        "interval_minutes": 60,
        "min_retain_hours": 24,
        "age": {"enabled": False, "value": 30, "unit": "day"},
        "size": {"enabled": False, "value": 500, "unit": "MB"},
    }
    payload.update(overrides)
    return payload


def test_get_default_cleanup_policy(auth_client) -> None:
    response = auth_client.get("/api/admin/recycle-bin/cleanup-policy")
    assert response.status_code == 200
    body = response.json()
    for key, value in DEFAULT_POLICY.items():
        assert body[key] == value
    assert body["total_estimated_size_bytes"] == 0
    assert body["recycled_config_count"] == 0


def test_put_policy_round_trip(auth_client) -> None:
    payload = _put_policy(
        auth_client,
        interval_minutes=30,
        min_retain_hours=12,
        age={"enabled": True, "value": 60, "unit": "day"},
        size={"enabled": True, "value": 2, "unit": "GB"},
    )
    response = auth_client.put("/api/admin/recycle-bin/cleanup-policy", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["interval_minutes"] == 30
    assert body["min_retain_hours"] == 12
    assert body["age"] == {"enabled": True, "value": 60, "unit": "day"}
    assert body["size"] == {"enabled": True, "value": 2, "unit": "GB"}

    again = auth_client.get("/api/admin/recycle-bin/cleanup-policy").json()
    assert again["age"] == {"enabled": True, "value": 60, "unit": "day"}
    assert again["interval_minutes"] == 30


def test_put_policy_invalid_values_rejected(auth_client) -> None:
    cases = [
        {"age": {"enabled": True, "value": 0, "unit": "day"}},
        {"size": {"enabled": True, "value": -1, "unit": "MB"}},
        {"age": {"enabled": True, "value": 30, "unit": "TB"}},
        {"size": {"enabled": True, "value": 500, "unit": "KB"}},
        {"interval_minutes": 0},
        {"interval_minutes": 2000},
        {"min_retain_hours": -1},
    ]
    for overrides in cases:
        response = auth_client.put(
            "/api/admin/recycle-bin/cleanup-policy",
            json=_put_policy(auth_client, **overrides),
        )
        assert response.status_code == 400, overrides


def test_put_policy_unknown_extra_field_rejected(auth_client) -> None:
    payload = _put_policy(auth_client)
    payload["unknown"] = True
    response = auth_client.put("/api/admin/recycle-bin/cleanup-policy", json=payload)
    assert response.status_code == 422


def test_preview_does_not_delete(auth_client) -> None:
    # 造一条过期配置入回收站
    auth_client.put("/api/configs/旧配置", json={"anchor_row_num": 1})
    auth_client.delete("/api/configs/旧配置")
    auth_client.put(
        "/api/admin/recycle-bin/cleanup-policy",
        json=_put_policy(
            auth_client,
            age={"enabled": True, "value": 1, "unit": "day"},
        ),
    )

    response = auth_client.post("/api/admin/recycle-bin/cleanup/preview")
    assert response.status_code == 200
    items = response.json()
    # 刚删除的配置在保留期内（min_retain_hours=24），不命中任何规则
    assert all(item["matched_rules"] == [] for item in items)

    # preview 不删除任何条目
    body = auth_client.get("/api/admin/recycle-bin/cleanup-policy").json()
    assert body["recycled_config_count"] == 1


def test_preview_matches_age_rule(auth_client) -> None:
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from src.backend.infrastructure.database import session_context
    from src.backend.infrastructure.models.recycled_config import RecycledConfig

    auth_client.put("/api/configs/旧配置", json={"anchor_row_num": 1})
    auth_client.delete("/api/configs/旧配置")

    # 把删除时间改到 3 天前，使年龄规则命中
    with session_context() as session:
        row = session.scalars(select(RecycledConfig)).one()
        row.deleted_at = datetime.now() - timedelta(days=3)

    auth_client.put(
        "/api/admin/recycle-bin/cleanup-policy",
        json=_put_policy(
            auth_client,
            min_retain_hours=0,
            age={"enabled": True, "value": 1, "unit": "day"},
        ),
    )
    response = auth_client.post("/api/admin/recycle-bin/cleanup/preview")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["original_config_name"] == "旧配置"
    assert items[0]["matched_rules"] == ["age"]
    assert items[0]["owner_username"] == "admin"


def test_background_jobs_disabled_by_default_env(monkeypatch) -> None:
    from src.backend.application.background_jobs import should_enable_background_jobs

    monkeypatch.setenv("DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS", "1")
    assert should_enable_background_jobs() is False
    monkeypatch.setenv("DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS", "true")
    assert should_enable_background_jobs() is False
    monkeypatch.setenv("DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS", "on")
    assert should_enable_background_jobs() is False


def test_background_jobs_enabled_when_env_missing(monkeypatch) -> None:
    from src.backend.application.background_jobs import should_enable_background_jobs

    monkeypatch.delenv("DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS")
    assert should_enable_background_jobs() is True


def test_background_jobs_lifespan_start_stop(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATASET_COMPARATOR_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_PASSWORD", "admin-pass-123")
    monkeypatch.delenv("DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS")
    database._engine = None

    from src.frontend import web_api

    assert getattr(web_api.app.state, "recycle_bin_enabled", False) is False
    with TestClient(web_api.app) as client:
        assert client.get("/health").status_code == 200
        assert getattr(web_api.app.state, "recycle_bin_enabled", False) is True
        assert getattr(web_api.app.state, "recycle_bin_timer", None) is not None
    assert getattr(web_api.app.state, "recycle_bin_enabled", False) is False
    database._engine = None
