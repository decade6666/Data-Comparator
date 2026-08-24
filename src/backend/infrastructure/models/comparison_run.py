from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class ComparisonRun(Base):
    """一次比对任务的历史记录。

    任务结束时由 ``record_job_finished`` 写入，独立于内存 ``JobManager`` 存活：
    即使任务记录已被清扫，用户仍可通过历史记录接口下载报告与日志。
    只存文件 ``basename``（绝不存绝对路径），下载时在用户 results 目录内
    重新拼接并经过 ``is_safe_path`` 校验。

    ``user_id`` 故意不建外键：``database.py`` 开启了 ``PRAGMA foreign_keys=ON``，
    配合 ``UserAdminService.delete_user`` 的 ``session.delete(user)`` 会因引用
    约束抛异常；沿用 ``RecycledConfig.original_owner_id`` 的先例，删除行由
    ``delete_runs_for_user`` 显式执行。
    """

    __tablename__ = "comparison_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    config_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    report_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    log_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    report_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
