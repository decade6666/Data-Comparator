import threading
from typing import Callable, Optional

from ...shared.contracts import LogFunc


class ThreadSafeProgressManager:
    """线程安全地更新比对进度和日志。"""

    def __init__(
        self,
        total_sheets: int,
        progress_func: Optional[Callable[[Optional[str], float], None]],
        log_func: Optional[LogFunc],
    ) -> None:
        self.total_sheets = total_sheets
        self.progress_func = progress_func
        self.log_func = log_func
        self.completed_sheets_count = 0
        self.lock = threading.Lock()

    def update_sheet_progress(
        self,
        sheet_name: str,
        status: str = "处理中",
        is_final_update: bool = False,
    ) -> None:
        with self.lock:
            if is_final_update:
                self.completed_sheets_count += 1

            progress = (
                30 + (self.completed_sheets_count / self.total_sheets) * 50
                if self.total_sheets > 0
                else 30
            )
            display_message = (
                f"已完成表单 [{self.completed_sheets_count}/"
                f"{self.total_sheets}]: {sheet_name}"
                if is_final_update
                else None
            )

            if self.progress_func:
                try:
                    self.progress_func(display_message, progress)
                except Exception as exc:
                    if self.log_func:
                        self.log_func(f"进度更新失败: {str(exc)}")

    def safe_log(self, message: str) -> None:
        with self.lock:
            if self.log_func:
                self.log_func(message)
