# -*- coding: utf-8 -*-
"""认证服务单元测试：密码哈希、JWT 签发/解码、密钥缺失快速失败。"""

import pytest


def test_hash_and_verify_password() -> None:
    from src.backend.application.auth_service import (
        hash_password,
        verify_password,
    )

    hashed = hash_password("correct-horse-123")
    assert hashed != "correct-horse-123"
    assert verify_password("correct-horse-123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hash_password_rejects_short_password() -> None:
    from src.backend.application.auth_service import hash_password

    with pytest.raises(ValueError, match="密码长度不能少于 8"):
        hash_password("short")


def test_verify_password_false_for_none_or_empty() -> None:
    from src.backend.application.auth_service import verify_password

    assert not verify_password("anything", None)
    assert not verify_password("anything", "")


def test_token_roundtrip(monkeypatch) -> None:
    from src.backend.application.auth_service import (
        TokenIdentity,
        create_access_token,
        decode_token,
    )

    monkeypatch.setenv("DATASET_COMPARATOR_SECRET_KEY", "test-secret")
    token = create_access_token(7, "alice", 3)
    identity = decode_token(token)
    assert identity == TokenIdentity(user_id=7, username="alice", auth_version=3)


def test_token_rejects_wrong_secret(monkeypatch) -> None:
    import jwt as pyjwt

    from src.backend.application.auth_service import (
        create_access_token,
        decode_token,
    )

    monkeypatch.setenv("DATASET_COMPARATOR_SECRET_KEY", "secret-a")
    token = create_access_token(7, "alice", 3)
    monkeypatch.setenv("DATASET_COMPARATOR_SECRET_KEY", "secret-b")
    with pytest.raises(pyjwt.PyJWTError):
        decode_token(token)


def test_get_secret_key_missing_raises(monkeypatch) -> None:
    from src.backend.application.auth_service import get_secret_key

    monkeypatch.delenv("DATASET_COMPARATOR_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DATASET_COMPARATOR_SECRET_KEY"):
        get_secret_key()


def test_get_token_expire_minutes_defaults(monkeypatch) -> None:
    from src.backend.application.auth_service import get_token_expire_minutes

    monkeypatch.delenv("DATASET_COMPARATOR_TOKEN_EXPIRE_MINUTES", raising=False)
    assert get_token_expire_minutes() == 120
    monkeypatch.setenv("DATASET_COMPARATOR_TOKEN_EXPIRE_MINUTES", "30")
    assert get_token_expire_minutes() == 30
    monkeypatch.setenv("DATASET_COMPARATOR_TOKEN_EXPIRE_MINUTES", "abc")
    assert get_token_expire_minutes() == 120


def test_validate_password_policy() -> None:
    from src.backend.application.auth_service import validate_password_policy

    validate_password_policy("12345678")
    with pytest.raises(ValueError, match="密码长度不能少于 8"):
        validate_password_policy("1234567")
