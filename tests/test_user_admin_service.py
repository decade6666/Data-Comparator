# -*- coding: utf-8 -*-
"""用户管理服务单元测试（管理员建号/改密/停用/保留管理员校验）。"""

import os

import pytest

from src.backend.infrastructure import database
from src.backend.infrastructure.database import init_db, session_context
from src.backend.infrastructure.models.user import User


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path))
    database._engine = None
    init_db()
    yield tmp_path
    database._engine = None


def _create_admin(session, username="admin", password="admin-pass-123"):
    from src.backend.application.auth_service import hash_password

    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_admin=True,
        auth_version=1,
    )
    session.add(user)
    session.flush()
    return user


def test_create_user_and_list(db) -> None:
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        _create_admin(session)
        created = UserAdminService.create_user(session, "bob", "bob-pass-123")
        assert created.is_admin is False
        assert created.id > 0

    with session_context() as session:
        infos = UserAdminService.list_users(session)
        usernames = {info.username for info in infos}
        assert usernames == {"admin", "bob"}
        bob = next(i for i in infos if i.username == "bob")
        assert bob.has_password is True
        assert bob.is_admin is False


def test_create_user_duplicate_rejected(db) -> None:
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        _create_admin(session)
        UserAdminService.create_user(session, "bob", "bob-pass-123")
        with pytest.raises(ValueError, match="用户名已存在"):
            UserAdminService.create_user(session, "bob", "other-pass-123")


def test_create_user_blank_or_reserved_rejected(db) -> None:
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        _create_admin(session)
        with pytest.raises(ValueError, match="用户名不能为空"):
            UserAdminService.create_user(session, "   ", "bob-pass-123")


def test_rename_user_ok(db) -> None:
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        _create_admin(session)
        bob = UserAdminService.create_user(session, "bob", "bob-pass-123")
        renamed = UserAdminService.rename_user(session, bob.id, "bob2")
        assert renamed is bob
        session.refresh(bob)
        assert bob.username == "bob2"


def test_rename_user_blank_or_reserved_rejected(db, monkeypatch) -> None:
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        _create_admin(session)
        bob = UserAdminService.create_user(session, "bob", "bob-pass-123")
        with pytest.raises(ValueError, match="用户名不能为空"):
            UserAdminService.rename_user(session, bob.id, "   ")
        with pytest.raises(ValueError, match="保留管理员账号"):
            UserAdminService.rename_user(session, bob.id, "admin")
        with pytest.raises(ValueError, match="用户不存在"):
            UserAdminService.rename_user(session, 9999, "nobody")


def test_reset_password_bumps_auth_version(db) -> None:
    from src.backend.application.auth_service import verify_password
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        _create_admin(session)
        bob = UserAdminService.create_user(session, "bob", "bob-pass-123")
        old_version = bob.auth_version
        UserAdminService.reset_password(session, bob.id, "new-pass-456")
        session.refresh(bob)
        assert bob.auth_version == old_version + 1
        assert verify_password("new-pass-456", bob.hashed_password)
        assert not verify_password("bob-pass-123", bob.hashed_password)


def test_reset_password_unknown_user_raises(db) -> None:
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        with pytest.raises(ValueError, match="用户不存在"):
            UserAdminService.reset_password(session, 9999, "new-pass-456")


def test_delete_user_removes_row(db, monkeypatch) -> None:
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    from sqlalchemy import select

    from src.backend.application.user_admin_service import UserAdminService
    from src.backend.infrastructure.models.user import User

    with session_context() as session:
        _create_admin(session)
        bob = UserAdminService.create_user(session, "bob", "bob-pass-123")
        bob_id = bob.id

    with session_context() as session:
        UserAdminService.delete_user(session, bob_id)

    with session_context() as session:
        assert session.get(User, bob_id) is None
        assert session.scalar(select(User).where(User.username == "bob")) is None


def test_delete_user_rejects_reserved_admin_and_unknown(db, monkeypatch) -> None:
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    from src.backend.application.user_admin_service import UserAdminService

    with session_context() as session:
        admin = _create_admin(session)
        with pytest.raises(ValueError, match="保留管理员账号"):
            UserAdminService.delete_user(session, admin.id)
        with pytest.raises(ValueError, match="用户不存在"):
            UserAdminService.delete_user(session, 9999)


def test_is_reserved_admin_username(db, monkeypatch) -> None:
    monkeypatch.setenv("DATASET_COMPARATOR_ADMIN_USERNAME", "admin")
    from src.backend.application.user_admin_service import (
        is_reserved_admin_username,
    )

    assert is_reserved_admin_username("admin")
    assert not is_reserved_admin_username("other")


def test_get_app_data_dir_and_user_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATASET_COMPARATOR_DATA_DIR", str(tmp_path))
    from src.backend.infrastructure.file_runtime import (
        get_app_data_dir,
        get_user_data_dir,
    )

    assert get_app_data_dir() == str(tmp_path)
    user_dir = get_user_data_dir(42)
    assert user_dir == os.path.join(str(tmp_path), "users", "42")
    assert os.path.isdir(user_dir)
