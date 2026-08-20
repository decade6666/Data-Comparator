"""回收站服务：配置软删入站、恢复、彻底删除。

与 UserAdminService 一致的静态方法风格，全部显式接收
``session: Session`` 与文件系统路径参数，便于测试与复用。
"""

import json
import os
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..infrastructure.models.recycled_config import RecycledConfig
from ..infrastructure.models.user import User

UPLOAD_FIELDS = (
    "old_file_upload_id",
    "new_file_upload_id",
    "old_file_path",
    "new_file_path",
)


def _is_safe_config_name(name: str) -> bool:
    return bool(name) and os.sep not in name and "/" not in name and ".." not in name


def _resolve_restore_name(configs_dir: str, original_name: str) -> str:
    """目标目录重名时生成 原名 (恢复) / (恢复2) / (恢复3)…。"""
    existing = set()
    if os.path.isdir(configs_dir):
        existing = {
            os.path.splitext(name)[0]
            for name in os.listdir(configs_dir)
            if name.endswith(".json")
        }
    if original_name not in existing:
        return original_name
    candidate = f"{original_name} (恢复)"
    if candidate not in existing:
        return candidate
    index = 2
    while f"{original_name} (恢复{index})" in existing:
        index += 1
    return f"{original_name} (恢复{index})"


class RecycleBinService:
    """回收站 CRUD。"""

    @staticmethod
    def recycle_config(
        session: Session,
        owner_id: int,
        owner_username: str,
        config_name: str,
        config_path: str,
        config_document: dict,
        deleted_by_user_deletion: bool = False,
    ) -> RecycledConfig:
        """把配置软删入回收站：插行（JSON 全文）并删除磁盘文件。"""
        if not _is_safe_config_name(config_name):
            raise ValueError("配置名不合法")
        size = os.path.getsize(config_path) if os.path.isfile(config_path) else 0
        entry = RecycledConfig(
            original_owner_id=owner_id,
            original_owner_username=owner_username,
            original_config_name=config_name,
            config_document=json.dumps(config_document, ensure_ascii=False),
            estimated_size_bytes=size,
            deleted_at=datetime.now(),
            deleted_by_user_deletion=deleted_by_user_deletion,
        )
        session.add(entry)
        if os.path.isfile(config_path):
            os.remove(config_path)
        session.flush()
        return entry

    @staticmethod
    def list_recycled(session: Session) -> List[RecycledConfig]:
        """按删除时间倒序返回全部回收站条目。"""
        return list(
            session.execute(
                select(RecycledConfig).order_by(
                    RecycledConfig.deleted_at.desc(), RecycledConfig.id.desc()
                )
            ).scalars()
        )

    @staticmethod
    def restore_config(
        session: Session,
        recycled_id: int,
        *,
        target_user_id: Optional[int],
        configs_dir: str,
    ) -> dict:
        """恢复回收站条目到目标用户目录，返回 {"restored_to_user_id", "config_name"}。

        target_user_id 为空时恢复给原 owner；原 owner 已删除且未指定目标时抛
        ``ValueError``。恢复时清空 upload 相关字段。
        """
        entry = session.get(RecycledConfig, recycled_id)
        if entry is None:
            raise ValueError("回收站条目不存在")
        if target_user_id is None:
            if entry.original_owner_id is None:
                raise ValueError("原用户已删除，请指定目标用户")
            owner = session.get(User, entry.original_owner_id)
            if owner is None:
                raise ValueError("原用户已删除，请指定目标用户")
            target_user_id = entry.original_owner_id
        if not _is_safe_config_name(entry.original_config_name):
            raise ValueError("配置名不合法")
        document = json.loads(entry.config_document)
        if not isinstance(document, dict):
            raise ValueError("回收站配置内容无效")
        for field in UPLOAD_FIELDS:
            document.pop(field, None)
        target_name = _resolve_restore_name(configs_dir, entry.original_config_name)
        os.makedirs(configs_dir, exist_ok=True)
        with open(
            os.path.join(configs_dir, f"{target_name}.json"), "w", encoding="utf-8"
        ) as file:
            json.dump(document, file, ensure_ascii=False, indent=4)
        session.delete(entry)
        session.flush()
        return {"restored_to_user_id": target_user_id, "config_name": target_name}

    @staticmethod
    def hard_delete_config(session: Session, recycled_id: int) -> None:
        """彻底删除回收站条目。"""
        entry = session.get(RecycledConfig, recycled_id)
        if entry is None:
            raise ValueError("回收站条目不存在")
        session.delete(entry)
        session.flush()

    @staticmethod
    def purge_all(session: Session) -> int:
        """清空回收站（后台清理兜底），返回删除数量。"""
        rows = list(session.scalars(select(RecycledConfig)).all())
        count = len(rows)
        for row in rows:
            session.delete(row)
        session.flush()
        return count
