# -*- coding: utf-8 -*-
"""回收站清理引擎测试：年龄规则/容量规则/min_retain_hours/竞态重查。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from src.backend.infrastructure import database
from src.backend.infrastructure.app_config import (
    RecycleBinAgeRule,
    RecycleBinConfig,
    RecycleBinSizeRule,
)
from src.backend.infrastructure.database import init_db, session_context
from src.backend.infrastructure.models.recycled_config import RecycledConfig

NOW = datetime(2026, 8, 19, 12, 0, 0)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path))
    database._engine = None
    init_db()
    yield tmp_path
    database._engine = None


def _insert_config(session, *, name="cfg", size=100, deleted_at=None, username="bob"):
    entry = RecycledConfig(
        original_owner_id=1,
        original_owner_username=username,
        original_config_name=name,
        config_document="{}",
        estimated_size_bytes=size,
        deleted_at=deleted_at or NOW,
    )
    session.add(entry)
    session.flush()
    return entry


def _age_policy(days=30, enabled=True, interval=60, retain=24) -> RecycleBinConfig:
    return RecycleBinConfig(
        interval_minutes=interval,
        min_retain_hours=retain,
        age=RecycleBinAgeRule(enabled=enabled, value=days, unit="day"),
        size=RecycleBinSizeRule(enabled=False, value=500, unit="MB"),
    )


def _size_policy(
    value=1, unit="MB", enabled=True, retain=24, interval=60
) -> RecycleBinConfig:
    return RecycleBinConfig(
        interval_minutes=interval,
        min_retain_hours=retain,
        age=RecycleBinAgeRule(enabled=False, value=30, unit="day"),
        size=RecycleBinSizeRule(enabled=enabled, value=value, unit=unit),
    )


def test_age_rule_selects_items_older_than_cutoff(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        build_cleanup_plan,
    )

    with session_context() as session:
        old = _insert_config(session, name="old", deleted_at=NOW - timedelta(days=100))
        recent = _insert_config(
            session, name="recent", deleted_at=NOW - timedelta(days=1)
        )
        old_id = old.id
        recent_id = recent.id

    with session_context() as session:
        plan = build_cleanup_plan(session, policy=_age_policy(days=30), now=NOW)

    assert plan.age_ids == [old_id]
    assert recent_id not in plan.age_ids
    assert plan.all_target_ids() == [old_id]
    assert plan.matched_rules_for(old_id) == ["age"]


def test_age_rule_disabled_is_noop(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        build_cleanup_plan,
    )

    with session_context() as session:
        _insert_config(session, name="old", deleted_at=NOW - timedelta(days=1000))

    with session_context() as session:
        plan = build_cleanup_plan(
            session, policy=_age_policy(days=30, enabled=False), now=NOW
        )

    assert plan.age_ids == []
    assert plan.size_ids == []
    assert plan.would_converge is True


def test_size_rule_fifo_until_under_limit(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        build_cleanup_plan,
    )

    # 1MB 上限；三条各 700KB，FIFO 删两条后剩余 700KB <= 1MB
    with session_context() as session:
        oldest = _insert_config(
            session, name="a", size=700_000, deleted_at=NOW - timedelta(hours=50)
        )
        middle = _insert_config(
            session, name="b", size=700_000, deleted_at=NOW - timedelta(hours=49)
        )
        newest = _insert_config(
            session, name="c", size=700_000, deleted_at=NOW - timedelta(hours=48)
        )
        oldest_id = oldest.id
        middle_id = middle.id
        newest_id = newest.id

    with session_context() as session:
        plan = build_cleanup_plan(
            session, policy=_size_policy(value=1, unit="MB"), now=NOW
        )

    assert plan.size_ids == [oldest_id, middle_id]
    assert newest_id not in plan.size_ids
    assert plan.total_bytes_after == 700_000
    assert plan.would_converge is True


def test_size_rule_under_limit_is_noop(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        build_cleanup_plan,
    )

    with session_context() as session:
        _insert_config(session, name="a", size=10_000)

    with session_context() as session:
        plan = build_cleanup_plan(
            session, policy=_size_policy(value=1, unit="MB"), now=NOW
        )

    assert plan.size_ids == []
    assert plan.total_bytes_before == 10_000
    assert plan.total_bytes_after == 10_000


def test_age_applies_first_then_size_on_remaining(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        build_cleanup_plan,
    )

    policy = RecycleBinConfig(
        interval_minutes=60,
        min_retain_hours=24,
        age=RecycleBinAgeRule(enabled=True, value=30, unit="day"),
        size=RecycleBinSizeRule(enabled=True, value=1, unit="MB"),
    )
    with session_context() as session:
        old = _insert_config(
            session, name="old", size=800_000, deleted_at=NOW - timedelta(days=100)
        )
        mid = _insert_config(
            session, name="mid", size=800_000, deleted_at=NOW - timedelta(days=1)
        )
        new = _insert_config(
            session, name="new", size=800_000, deleted_at=NOW - timedelta(hours=1)
        )
        old_id = old.id
        mid_id = mid.id

    with session_context() as session:
        plan = build_cleanup_plan(session, policy=policy, now=NOW)

    assert plan.age_ids == [old_id]
    # 容量在剩余集合 (mid, new) 上算：删 mid 后剩 new 800KB <= 1MB
    assert plan.size_ids == [mid_id]
    assert plan.all_target_ids() == [old_id, mid_id]
    assert plan.total_bytes_before == 2_400_000
    # 不双重扣减：total_after 只扣 size 命中
    assert plan.total_bytes_after == 800_000
    assert plan.matched_rules_for(old_id) == ["age"]
    assert plan.matched_rules_for(mid_id) == ["size"]


def test_min_retain_hours_protects_recent_items(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        build_cleanup_plan,
    )

    with session_context() as session:
        _insert_config(
            session, name="a", size=700_000, deleted_at=NOW - timedelta(hours=1)
        )
        _insert_config(
            session, name="b", size=700_000, deleted_at=NOW - timedelta(hours=2)
        )
        _insert_config(
            session, name="c", size=700_000, deleted_at=NOW - timedelta(minutes=30)
        )

    with session_context() as session:
        plan = build_cleanup_plan(session, policy=_size_policy(retain=24), now=NOW)

    assert plan.size_ids == []
    assert plan.would_converge is False


def test_min_retain_protects_only_recent_but_oldest_purged(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        build_cleanup_plan,
    )

    with session_context() as session:
        old_enough = _insert_config(
            session, name="a", size=700_000, deleted_at=NOW - timedelta(days=2)
        )
        recent = _insert_config(
            session, name="b", size=700_000, deleted_at=NOW - timedelta(hours=1)
        )
        _insert_config(
            session, name="c", size=700_000, deleted_at=NOW - timedelta(minutes=30)
        )
        old_enough_id = old_enough.id
        recent_id = recent.id

    with session_context() as session:
        plan = build_cleanup_plan(session, policy=_size_policy(retain=24), now=NOW)

    # 删掉 a 后总量 1.4MB 仍超限，但剩余都在保留期内 → 停，不收敛
    assert plan.size_ids == [old_enough_id]
    assert plan.would_converge is False
    assert recent_id not in plan.size_ids


def test_run_cleanup_deletes_planned_rows(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        run_recycle_bin_cleanup,
    )

    with session_context() as session:
        _insert_config(
            session, name="old", size=800_000, deleted_at=NOW - timedelta(days=100)
        )
        _insert_config(
            session, name="mid", size=800_000, deleted_at=NOW - timedelta(days=1)
        )
        _insert_config(
            session, name="new", size=800_000, deleted_at=NOW - timedelta(hours=1)
        )

    policy = RecycleBinConfig(
        interval_minutes=60,
        min_retain_hours=24,
        age=RecycleBinAgeRule(enabled=True, value=30, unit="day"),
        size=RecycleBinSizeRule(enabled=True, value=1, unit="MB"),
    )
    with session_context() as session:
        result = run_recycle_bin_cleanup(session, policy=policy, now=NOW)

    assert result["purged_count"] == 2
    assert result["freed_bytes"] == 1_600_000
    with session_context() as session:
        remaining = list(session.scalars(select(RecycledConfig)).all())
        assert len(remaining) == 1
        assert remaining[0].original_config_name == "new"


def test_run_cleanup_skips_rows_deleted_after_plan(db, monkeypatch) -> None:
    """计划生成后条目被并发删除时逐条重查并跳过。"""
    from src.backend.application import recycle_bin_cleanup_service as svc

    with session_context() as session:
        first = _insert_config(session, name="a", size=100)
        second = _insert_config(session, name="b", size=200)
        first_id = first.id
        second_id = second.id

    class FakePlan:
        def all_target_ids(self) -> list:
            return [first_id, 999999, second_id]

    monkeypatch.setattr(svc, "build_cleanup_plan", lambda *a, **k: FakePlan())

    with session_context() as session:
        result = svc.run_recycle_bin_cleanup(session)

    assert result["purged_count"] == 2
    assert result["freed_bytes"] == 300
    with session_context() as session:
        assert list(session.scalars(select(RecycledConfig)).all()) == []


def test_run_cleanup_second_pass_is_empty(db) -> None:
    from src.backend.application.recycle_bin_cleanup_service import (
        run_recycle_bin_cleanup,
    )

    with session_context() as session:
        _insert_config(
            session, name="a", size=700_000, deleted_at=NOW - timedelta(days=2)
        )
        _insert_config(
            session, name="b", size=700_000, deleted_at=NOW - timedelta(days=1)
        )

    with session_context() as session:
        result = run_recycle_bin_cleanup(session, policy=_size_policy(), now=NOW)
        assert result["purged_count"] == 1
        assert result["freed_bytes"] == 700_000
        # 第一轮后剩余总量已 <= 上限，第二轮不再命中
        result = run_recycle_bin_cleanup(session, policy=_size_policy(), now=NOW)
        assert result["purged_count"] == 0
        assert result["freed_bytes"] == 0
