"""用户管理服务（管理员专用）。"""

import json
import os
import shutil
from dataclasses import dataclass
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...shared.log_utils import log
from ..infrastructure.file_runtime import get_app_data_dir
from ..infrastructure.models.user import User
from .auth_service import hash_password
from .recycle_bin_service import RecycleBinService

ADMIN_USERNAME_ENV = "DATASET_COMPARATOR_ADMIN_USERNAME"
ADMIN_PASSWORD_ENV = "DATASET_COMPARATOR_ADMIN_PASSWORD"


@dataclass(frozen=True)
class UserInfo:
    id: int
    username: str
    has_password: bool
    is_admin: bool
    is_active: bool


def get_bootstrap_admin_credentials() -> tuple:
    """返回初始管理员配置，缺一返回 (None, None)。"""
    username = os.environ.get(ADMIN_USERNAME_ENV, "").strip()
    password = os.environ.get(ADMIN_PASSWORD_ENV, "")
    if not username or not password:
        return None, None
    return username, password


def is_reserved_admin_username(username: str) -> bool:
    return username.strip() == os.environ.get(ADMIN_USERNAME_ENV, "").strip()


def get_user_configs_paths(user_id: int) -> List[str]:
    """返回用户配置 JSON 文件路径列表（目录不存在返回空，不创建目录）。"""
    configs_dir = os.path.join(get_app_data_dir(), "users", str(user_id), "configs")
    if not os.path.isdir(configs_dir):
        return []
    return [
        os.path.join(configs_dir, name)
        for name in sorted(os.listdir(configs_dir))
        if name.endswith(".json")
    ]


class UserAdminService:
    """管理员用户管理服务。"""

    @staticmethod
    def list_users(session: Session) -> List[UserInfo]:
        rows = session.execute(select(User).order_by(User.id)).scalars().all()
        return [
            UserInfo(
                id=user.id,
                username=user.username,
                has_password=bool(user.hashed_password),
                is_admin=user.is_admin,
                is_active=user.is_active,
            )
            for user in rows
        ]

    @staticmethod
    def create_user(session: Session, username: str, password: str) -> User:
        username = username.strip()
        if not username:
            raise ValueError("用户名不能为空")
        if is_reserved_admin_username(username):
            raise ValueError("该用户名为保留管理员账号，不允许手动创建")
        existing = session.scalar(select(User).where(User.username == username))
        if existing:
            raise ValueError("用户名已存在")
        user = User(
            username=username,
            hashed_password=hash_password(password),
            is_admin=False,
        )
        session.add(user)
        session.flush()
        return user

    @staticmethod
    def rename_user(session: Session, user_id: int, new_username: str) -> User:
        new_username = new_username.strip()
        if not new_username:
            raise ValueError("用户名不能为空")
        if is_reserved_admin_username(new_username):
            raise ValueError("该用户名为保留管理员账号，不允许修改")
        user = session.get(User, user_id)
        if user is None:
            raise ValueError("用户不存在")
        existing = session.scalar(select(User).where(User.username == new_username))
        if existing is not None and existing.id != user_id:
            raise ValueError("用户名已存在")
        user.username = new_username
        session.flush()
        return user

    @staticmethod
    def reset_password(session: Session, user_id: int, password: str) -> User:
        """重置指定用户密码，并使旧 token 立即失效。"""
        user = session.get(User, user_id)
        if user is None:
            raise ValueError("用户不存在")
        user.hashed_password = hash_password(password)
        user.auth_version += 1
        session.flush()
        return user

    @staticmethod
    def delete_user(session: Session, user_id: int, job_manager=None) -> None:
        """硬删除用户：取消任务 → 配置入回收站 → 删用户目录 → 删 User 行。

        不能删除自己由 API 层校验（需要 current_user）；保留管理员账号在此拒绝。
        job_manager 可为 None（服务级调用跳过任务取消）。
        """
        user = session.get(User, user_id)
        if user is None:
            raise ValueError("用户不存在")
        if is_reserved_admin_username(user.username):
            raise ValueError("保留管理员账号不允许删除")
        if job_manager is not None:
            job_manager.cancel_all_for_user(user_id)
        for config_path in get_user_configs_paths(user_id):
            config_name = os.path.splitext(os.path.basename(config_path))[0]
            try:
                with open(config_path, "r", encoding="utf-8") as file:
                    document = json.load(file)
                if not isinstance(document, dict):
                    continue
                RecycleBinService.recycle_config(
                    session,
                    owner_id=user_id,
                    owner_username=user.username,
                    config_name=config_name,
                    config_path=config_path,
                    config_document=document,
                    deleted_by_user_deletion=True,
                )
            except Exception as exc:  # noqa: BLE001 - 单条失败不阻断用户删除
                log("回收配置 {} 失败: {}".format(config_name, exc), None)
                continue
        shutil.rmtree(
            os.path.join(get_app_data_dir(), "users", str(user_id)),
            ignore_errors=True,
        )
        session.delete(user)
        session.flush()
