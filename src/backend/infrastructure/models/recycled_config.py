from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class RecycledConfig(Base):
    """回收站中的配置条目。

    配置被删除（普通用户软删或用户整体删除）时入站：磁盘 JSON 删除，
    内容全文存入 ``config_document``，供管理员恢复或彻底删除。
    """

    __tablename__ = "recycled_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    original_owner_username: Mapped[str] = mapped_column(String(100), nullable=False)
    original_config_name: Mapped[str] = mapped_column(String(500), nullable=False)
    config_document: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_size_bytes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_by_user_deletion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
