"""认证路由：登录与自助改密。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...backend.application.auth_service import (
    change_own_password,
    create_access_token,
    verify_password,
)
from ...backend.application.user_admin_service import (
    is_reserved_admin_username,
)
from ...backend.infrastructure.database import get_session
from ...backend.infrastructure.models.user import User
from ..dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("用户名不能为空")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError("密码不能为空")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SelfPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    model_config = {"extra": "forbid"}


def _build_login_error(user: Optional[User]) -> HTTPException:
    if user and not user.is_active:
        return HTTPException(status_code=401, detail="账号已停用")
    return HTTPException(status_code=401, detail="用户名或密码错误")


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, session: Session = Depends(get_session)):
    """账号密码登录。"""
    user = session.scalar(select(User).where(User.username == data.username))
    if not user and is_reserved_admin_username(data.username):
        user = session.scalar(
            select(User).where(User.username == data.username).order_by(User.id)
        )
    if not user or not verify_password(data.password, user.hashed_password):
        raise _build_login_error(user)
    return TokenResponse(
        access_token=create_access_token(user.id, user.username, user.auth_version)
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
    }


@router.put("/me/password", status_code=204)
def change_my_password(
    data: SelfPasswordChangeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """普通用户自助修改自己的密码。"""
    if current_user.is_admin:
        raise HTTPException(status_code=403, detail="管理员不能使用普通用户自助改密")
    try:
        user = session.get(User, current_user.id)
        if user is None:
            raise ValueError("用户不存在")
        user.hashed_password = change_own_password(
            data.current_password, data.new_password, user.hashed_password
        )
        user.auth_version += 1
        session.flush()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
