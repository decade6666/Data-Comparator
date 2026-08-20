"""认证服务：密码哈希与 JWT 签发/解码。

密钥来自环境变量 ``DATASET_COMPARATOR_SECRET_KEY``，缺失时拒绝服务启动
（不提供默认值，避免部署出默认密钥）。
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

SECRET_KEY_ENV = "DATASET_COMPARATOR_SECRET_KEY"
TOKEN_EXPIRE_MINUTES_ENV = "DATASET_COMPARATOR_TOKEN_EXPIRE_MINUTES"
DEFAULT_TOKEN_EXPIRE_MINUTES = 120
_MIN_PASSWORD_LENGTH = 8

_PASSWORD_CONTEXT = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@dataclass(frozen=True)
class TokenIdentity:
    """JWT 身份载荷。"""

    user_id: int
    username: str
    auth_version: int


def get_secret_key() -> str:
    secret = os.environ.get(SECRET_KEY_ENV, "").strip()
    if not secret:
        raise RuntimeError(
            f"缺少必需环境变量 {SECRET_KEY_ENV}，拒绝启动：请设置用于 JWT 签名的密钥"
        )
    return secret


def get_token_expire_minutes() -> int:
    raw = os.environ.get(TOKEN_EXPIRE_MINUTES_ENV, "").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_TOKEN_EXPIRE_MINUTES


def validate_password_policy(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"密码长度不能少于 {_MIN_PASSWORD_LENGTH} 个字符")


def hash_password(password: str) -> str:
    validate_password_policy(password)
    return _PASSWORD_CONTEXT.hash(password)


def has_usable_password_hash(hashed: Optional[str]) -> bool:
    if not hashed:
        return False
    try:
        handler = _PASSWORD_CONTEXT.identify(hashed, resolve=True)
    except ValueError:
        return False
    if handler is None:
        return False
    try:
        handler.from_string(hashed)
    except (TypeError, ValueError):
        return False
    return True


def verify_password(password: str, hashed: Optional[str]) -> bool:
    if not has_usable_password_hash(hashed):
        return False
    try:
        return _PASSWORD_CONTEXT.verify(password, hashed)
    except (UnknownHashError, ValueError):
        return False


def change_own_password(
    current_password: str, new_password: str, hashed: Optional[str]
) -> str:
    """校验当前密码并生成新哈希；失败抛 ValueError。"""
    if not verify_password(current_password, hashed):
        raise ValueError("当前密码错误")
    if new_password == current_password:
        raise ValueError("新密码不能与当前密码相同")
    validate_password_policy(new_password)
    return hash_password(new_password)


def create_access_token(user_id: int, username: str, auth_version: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=get_token_expire_minutes())
    return jwt.encode(
        {
            "sub": str(user_id),
            "username": username,
            "ver": auth_version,
            "exp": expire,
        },
        get_secret_key(),
        algorithm="HS256",
    )


def decode_token(token: str) -> TokenIdentity:
    """解码 JWT；payload 非法或密钥不符抛 jwt.PyJWTError。"""
    payload = jwt.decode(token, get_secret_key(), algorithms=["HS256"])
    try:
        return TokenIdentity(
            user_id=int(payload["sub"]),
            username=str(payload["username"]),
            auth_version=int(payload["ver"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise jwt.InvalidTokenError("invalid token payload") from exc
