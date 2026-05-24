import sys
from typing import Optional

from .contracts import LogFunc


def log(msg: str, log_func: Optional[LogFunc]) -> None:
    """通用日志转发函数。"""
    try:
        print(msg)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(msg.encode("utf-8", "replace").decode(encoding, "replace"))
    if log_func:
        log_func(msg)
