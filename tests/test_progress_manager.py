from concurrent.futures import ThreadPoolExecutor

from src.backend.infrastructure.progress_manager import ThreadSafeProgressManager


def test_progress_manager_reports_final_progress() -> None:
    updates = []
    manager = ThreadSafeProgressManager(
        total_sheets=2,
        progress_func=lambda message, progress: updates.append((message, progress)),
        log_func=None,
    )

    manager.update_sheet_progress("Sheet1", is_final_update=True)

    assert updates == [("已完成表单 [1/2]: Sheet1", 55.0)]
    assert manager.completed_sheets_count == 1


def test_progress_manager_logs_progress_callback_failure() -> None:
    logs = []

    def fail_progress(message, progress):
        raise RuntimeError("boom")

    manager = ThreadSafeProgressManager(
        total_sheets=1,
        progress_func=fail_progress,
        log_func=logs.append,
    )

    manager.update_sheet_progress("Sheet1", is_final_update=True)

    assert logs == ["进度更新失败: boom"]


def test_progress_manager_reports_non_final_progress_without_completion() -> None:
    updates = []
    manager = ThreadSafeProgressManager(
        total_sheets=2,
        progress_func=lambda message, progress: updates.append((message, progress)),
        log_func=None,
    )

    manager.update_sheet_progress("Sheet1")

    assert updates == [(None, 30.0)]
    assert manager.completed_sheets_count == 0


def test_progress_manager_reports_base_progress_when_total_sheets_zero() -> None:
    updates = []
    manager = ThreadSafeProgressManager(
        total_sheets=0,
        progress_func=lambda message, progress: updates.append((message, progress)),
        log_func=None,
    )

    manager.update_sheet_progress("Sheet1")

    assert updates == [(None, 30)]
    assert manager.completed_sheets_count == 0


def test_progress_manager_counts_concurrent_final_updates() -> None:
    updates = []
    manager = ThreadSafeProgressManager(
        total_sheets=5,
        progress_func=lambda message, progress: updates.append((message, progress)),
        log_func=None,
    )

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(
            executor.map(
                lambda index: manager.update_sheet_progress(
                    f"Sheet{index}", is_final_update=True
                ),
                range(5),
            )
        )

    assert manager.completed_sheets_count == 5
    assert len(updates) == 5
    assert sorted(progress for _, progress in updates) == [40.0, 50.0, 60.0, 70.0, 80.0]


def test_progress_manager_safe_log_delegates_to_log_func() -> None:
    logs = []
    manager = ThreadSafeProgressManager(
        total_sheets=0,
        progress_func=None,
        log_func=logs.append,
    )

    manager.safe_log("message")

    assert logs == ["message"]
