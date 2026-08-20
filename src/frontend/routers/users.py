"""用户管理路由（管理员专用）。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...backend.application.job_manager import get_job_manager
from ...backend.application.user_admin_service import UserAdminService
from ...backend.infrastructure.database import get_session
from ...backend.infrastructure.models.user import User
from ..dependencies import require_admin

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    username: str
    password: str

    model_config = {"extra": "forbid"}


class UserPasswordRequest(BaseModel):
    password: str

    model_config = {"extra": "forbid"}


class UserRenameRequest(BaseModel):
    username: str

    model_config = {"extra": "forbid"}


@router.get("")
def list_users(
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    infos = UserAdminService.list_users(session)
    return [
        {
            "id": info.id,
            "username": info.username,
            "has_password": info.has_password,
            "is_admin": info.is_admin,
            "is_active": info.is_active,
        }
        for info in infos
    ]


@router.post("", status_code=201)
def create_user(
    data: UserCreateRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    try:
        user = UserAdminService.create_user(session, data.username, data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
    }


@router.put("/{user_id}", status_code=204)
def rename_user(
    user_id: int,
    data: UserRenameRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    try:
        UserAdminService.rename_user(session, user_id, data.username)
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if detail == "用户不存在" else 400, detail=detail
        )


@router.put("/{user_id}/password", status_code=204)
def reset_user_password(
    user_id: int,
    data: UserPasswordRequest,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
):
    try:
        UserAdminService.reset_password(session, user_id, data.password)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> None:
    """硬删除用户：取消任务 → 配置入回收站 → 删目录 → 删 User 行。"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    try:
        UserAdminService.delete_user(session, user_id, job_manager=get_job_manager())
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=404 if detail == "用户不存在" else 400, detail=detail
        )
