"""后台定时任务：回收站自动清理巡检。

采用 ``threading.Timer`` 循环（与 web_api 的 upload_cleanup_timer 模式一致），
每轮重读 ``config.yaml`` 的 ``interval_minutes`` 作为下一轮间隔。
测试通过 ``DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS=1`` 关闭。
"""

import os
import threading
from typing import Optional

from fastapi import FastAPI
from sqlalchemy.orm import Session

from ...shared.log_utils import log
from ..infrastructure.app_config import get_app_config
from ..infrastructure.database import get_engine
from .recycle_bin_cleanup_service import run_recycle_bin_cleanup

_DISABLE_ENV = "DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS"
_DISABLE_VALUES = {"1", "true", "yes", "on"}


def should_enable_background_jobs() -> bool:
    """读取开关环境变量：值为 1/true/yes/on 时关闭后台任务，缺省开启。"""
    raw = os.environ.get(_DISABLE_ENV, "").strip().lower()
    return raw not in _DISABLE_VALUES


def _run_cleanup_once() -> Optional[dict]:
    """执行一轮回收站清理（自建 Session，不复用请求 scope）。"""
    try:
        session = Session(get_engine())
        try:
            result = run_recycle_bin_cleanup(session)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001 - 后台任务异常只记录不抛出
        log("回收站自动清理失败: {}".format(exc), None)
        return None


def _cleanup_loop(app: FastAPI) -> None:
    """先跑一轮清理，再按当前策略间隔注册下一轮定时器。"""
    try:
        _run_cleanup_once()
    finally:
        if getattr(app.state, "recycle_bin_enabled", False):
            interval = get_app_config().recycle_bin.interval_minutes
            timer = threading.Timer(interval * 60, _cleanup_loop, args=(app,))
            timer.daemon = True
            timer.start()
            app.state.recycle_bin_timer = timer


def start_background_jobs(app: FastAPI) -> None:
    """启动后台巡检（幂等）；被环境变量禁用时不启动。"""
    if not should_enable_background_jobs():
        return
    if getattr(app.state, "recycle_bin_enabled", False):
        return
    app.state.recycle_bin_enabled = True
    _cleanup_loop(app)


def stop_background_jobs(app: FastAPI) -> None:
    """停止后台巡检：置位停用标记并取消当前定时器。"""
    app.state.recycle_bin_enabled = False
    timer = getattr(app.state, "recycle_bin_timer", None)
    if timer is not None:
        timer.cancel()
        app.state.recycle_bin_timer = None
