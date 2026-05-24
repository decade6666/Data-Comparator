from typing import Any, Callable, List, Optional

from ...shared.contracts import LogFunc
from ...shared.log_utils import log

_global_stop_flag: Optional[Any] = None


def set_global_stop_flag(stop_flag: Optional[Any]) -> None:
    global _global_stop_flag
    _global_stop_flag = stop_flag


def check_stop_frequently(
    log_func: Optional[LogFunc], stop_flag: Optional[Any] = None
) -> None:
    current_flag = stop_flag or _global_stop_flag
    if current_flag and current_flag.is_set():
        log("处理已被用户停止", log_func)
        raise InterruptedError("用户停止了操作")


def check_stop(
    log_func: Optional[LogFunc],
    stop_flag: Optional[Any] = None,
    check_counter: Optional[List[int]] = None,
) -> None:
    current_flag = stop_flag or _global_stop_flag

    if check_counter is not None:
        if check_counter[0] % 100 != 0:
            check_counter[0] += 1
            return
        check_counter[0] += 1

    if current_flag and current_flag.is_set():
        log("处理已被用户停止", log_func)
        raise InterruptedError("用户停止了操作")


def update_progress(
    msg: str,
    progress: Optional[int] = None,
    progress_func: Optional[Callable[[str, Optional[int]], None]] = None,
) -> None:
    if not progress_func:
        return

    try:
        progress_func(msg, progress)
    except InterruptedError:
        raise
    except Exception as exc:
        # 出错时通过共享日志助手回退到 stdout，避免在业务模块中直接使用 print
        log(f"进度更新异常: {str(exc)}", None)
