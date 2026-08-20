# -*- coding: utf-8 -*-
"""回收站服务单元测试：入站/恢复/彻底删除/重名后缀。"""

import json
import os

import pytest
from sqlalchemy import select

from src.backend.infrastructure import database
from src.backend.infrastructure.database import init_db, session_context


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path))
    database._engine = None
    init_db()
    yield tmp_path
    database._engine = None


def _create_user(session, username="bob", password="bob-pass-123"):
    from src.backend.application.auth_service import hash_password
    from src.backend.infrastructure.models.user import User

    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_admin=False,
    )
    session.add(user)
    session.flush()
    return user


def _write_config(db_path, user_id, name, document) -> str:
    configs_dir = os.path.join(str(db_path), "users", str(user_id), "configs")
    os.makedirs(configs_dir, exist_ok=True)
    config_path = os.path.join(configs_dir, f"{name}.json")
    with open(config_path, "w", encoding="utf-8") as file:
        json.dump(document, file, ensure_ascii=False)
    return config_path


def test_recycle_config_inserts_row_and_deletes_file(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService
    from src.backend.infrastructure.models.recycled_config import RecycledConfig

    document = {
        "anchor_row_num": 5,
        "old_file_upload_id": "up-1",
        "new_file_upload_id": "up-2",
    }
    config_path = _write_config(db, 1, "我的配置", document)

    with session_context() as session:
        entry = RecycleBinService.recycle_config(
            session,
            owner_id=1,
            owner_username="bob",
            config_name="我的配置",
            config_path=config_path,
            config_document=document,
            deleted_by_user_deletion=False,
        )
        assert entry.id > 0

    assert not os.path.exists(config_path)
    with session_context() as session:
        rows = list(session.scalars(select(RecycledConfig)).all())
        assert len(rows) == 1
        row = rows[0]
        assert row.original_owner_id == 1
        assert row.original_owner_username == "bob"
        assert row.original_config_name == "我的配置"
        assert row.estimated_size_bytes > 0
        assert row.deleted_by_user_deletion is False
        assert json.loads(row.config_document) == document


def test_recycle_config_rejects_unsafe_name(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService

    with session_context() as session:
        with pytest.raises(ValueError, match="配置名不合法"):
            RecycleBinService.recycle_config(
                session,
                owner_id=1,
                owner_username="bob",
                config_name="../escape",
                config_path="/nonexistent",
                config_document={},
            )


def test_restore_to_original_owner(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService
    from src.backend.infrastructure.models.recycled_config import RecycledConfig

    document = {
        "anchor_row_num": 5,
        "old_file_upload_id": "up-1",
        "new_file_upload_id": "up-2",
        "old_file_path": "/data/old.xlsx",
        "new_file_path": "/data/new.xlsx",
    }
    with session_context() as session:
        bob = _create_user(session)
        bob_id = bob.id
        config_path = _write_config(db, bob_id, "我的配置", document)
        entry = RecycleBinService.recycle_config(
            session,
            owner_id=bob_id,
            owner_username="bob",
            config_name="我的配置",
            config_path=config_path,
            config_document=document,
        )
        recycled_id = entry.id
        configs_dir = os.path.join(str(db), "users", str(bob_id), "configs")

    with session_context() as session:
        result = RecycleBinService.restore_config(
            session, recycled_id, target_user_id=None, configs_dir=configs_dir
        )

    assert result == {"restored_to_user_id": bob_id, "config_name": "我的配置"}
    restored_path = os.path.join(configs_dir, "我的配置.json")
    with open(restored_path, "r", encoding="utf-8") as file:
        restored = json.load(file)
    assert restored["anchor_row_num"] == 5
    for field in (
        "old_file_upload_id",
        "new_file_upload_id",
        "old_file_path",
        "new_file_path",
    ):
        assert field not in restored
    with session_context() as session:
        assert session.get(RecycledConfig, recycled_id) is None


def test_restore_name_conflict_appends_suffix(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService

    with session_context() as session:
        bob = _create_user(session)
        bob_id = bob.id
        configs_dir = os.path.join(str(db), "users", str(bob_id), "configs")
        config_path = _write_config(db, bob_id, "我的配置", {"anchor_row_num": 9})
        entry = RecycleBinService.recycle_config(
            session,
            owner_id=bob_id,
            owner_username="bob",
            config_name="我的配置",
            config_path=config_path,
            config_document={"anchor_row_num": 9},
        )
        recycled_id = entry.id

    # 入站后目标目录出现同名与 (恢复) 后缀名，模拟恢复时的重名冲突
    os.makedirs(configs_dir, exist_ok=True)
    for name in ("我的配置.json", "我的配置 (恢复).json"):
        with open(os.path.join(configs_dir, name), "w", encoding="utf-8") as f:
            json.dump({"anchor_row_num": 1}, f)

    with session_context() as session:
        result = RecycleBinService.restore_config(
            session, recycled_id, target_user_id=None, configs_dir=configs_dir
        )

    assert result["config_name"] == "我的配置 (恢复2)"
    assert os.path.isfile(os.path.join(configs_dir, "我的配置 (恢复2).json"))


def test_restore_orphan_without_target_raises(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService

    with session_context() as session:
        config_path = _write_config(db, 42, "孤儿配置", {"anchor_row_num": 1})
        entry = RecycleBinService.recycle_config(
            session,
            owner_id=42,
            owner_username="ghost",
            config_name="孤儿配置",
            config_path=config_path,
            config_document={"anchor_row_num": 1},
        )
        recycled_id = entry.id

    with session_context() as session:
        with pytest.raises(ValueError, match="原用户已删除"):
            RecycleBinService.restore_config(
                session,
                recycled_id,
                target_user_id=None,
                configs_dir=str(db),
            )


def test_restore_orphan_with_target_user(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService
    from src.backend.infrastructure.models.recycled_config import RecycledConfig

    with session_context() as session:
        carol = _create_user(session, username="carol", password="carol-pass-123")
        carol_id = carol.id
        config_path = _write_config(db, 42, "孤儿配置", {"anchor_row_num": 3})
        entry = RecycleBinService.recycle_config(
            session,
            owner_id=42,
            owner_username="ghost",
            config_name="孤儿配置",
            config_path=config_path,
            config_document={"anchor_row_num": 3},
        )
        recycled_id = entry.id
        configs_dir = os.path.join(str(db), "users", str(carol_id), "configs")

    with session_context() as session:
        result = RecycleBinService.restore_config(
            session,
            recycled_id,
            target_user_id=carol_id,
            configs_dir=configs_dir,
        )

    assert result["restored_to_user_id"] == carol_id
    assert os.path.isfile(os.path.join(configs_dir, "孤儿配置.json"))
    with session_context() as session:
        assert session.get(RecycledConfig, recycled_id) is None


def test_hard_delete_removes_row(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService
    from src.backend.infrastructure.models.recycled_config import RecycledConfig

    with session_context() as session:
        config_path = _write_config(db, 1, "待删配置", {"anchor_row_num": 1})
        entry = RecycleBinService.recycle_config(
            session,
            owner_id=1,
            owner_username="bob",
            config_name="待删配置",
            config_path=config_path,
            config_document={"anchor_row_num": 1},
        )
        recycled_id = entry.id
        assert recycled_id > 0

    with session_context() as session:
        RecycleBinService.hard_delete_config(session, recycled_id)
        with pytest.raises(ValueError, match="回收站条目不存在"):
            RecycleBinService.hard_delete_config(session, recycled_id)

    with session_context() as session:
        assert session.get(RecycledConfig, recycled_id) is None


def test_purge_all_clears_rows(db) -> None:
    from src.backend.application.recycle_bin_service import RecycleBinService
    from src.backend.infrastructure.models.recycled_config import RecycledConfig

    with session_context() as session:
        for index in range(3):
            config_path = _write_config(db, 1, f"配置{index}", {"i": index})
            RecycleBinService.recycle_config(
                session,
                owner_id=1,
                owner_username="bob",
                config_name=f"配置{index}",
                config_path=config_path,
                config_document={"i": index},
            )

    with session_context() as session:
        assert RecycleBinService.purge_all(session) == 3
        assert list(session.scalars(select(RecycledConfig)).all()) == []
