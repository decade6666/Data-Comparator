"""SQLite 数据库 Session 管理。

单用户服务：引擎进程级单例，SQLite WAL 模式 + busy_timeout 提升并发读写能力。
"""

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from .file_runtime import get_app_data_dir
from .models import Base

_engine = None


def get_db_path() -> str:
    return os.path.join(get_app_data_dir(), "dataset_comparator.db")


def get_engine():
    global _engine
    if _engine is None:
        engine = create_engine(
            f"sqlite:///{get_db_path()}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_conn, _connection_record) -> None:
            dbapi_conn.execute("PRAGMA foreign_keys = ON")
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA busy_timeout=5000")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")

        _engine = engine
    return _engine


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI 写 Session 依赖，自动提交/回滚并关闭。"""
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_context() -> Iterator[Session]:
    """非 FastAPI 代码使用的 Session 上下文。"""
    yield from get_session()


def read_session() -> Iterator[Session]:
    """FastAPI 只读 Session 依赖。"""
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()


def db_path_for_testing(tmp_path: str) -> None:
    """测试专用：把数据库路径固定到临时目录（避免污染真实用户数据目录）。"""
    global _engine
    _engine = None
    os.environ["DATASET_COMPARATOR_DATA_DIR"] = str(tmp_path)
    get_engine()
