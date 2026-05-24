import importlib.util

import pytest

from src.shared import LogFunc, ParameterDocument, ParameterRepository, ProgressReporter


def test_phase1_packages_import() -> None:
    import src.backend
    import src.backend.application
    import src.backend.domain
    import src.backend.infrastructure
    import src.frontend
    import src.shared

    assert src.backend is not None
    assert src.backend.application is not None
    assert src.backend.domain is not None
    assert src.backend.infrastructure is not None
    assert src.frontend is not None
    assert src.shared is not None


def test_shared_contracts_import() -> None:
    assert LogFunc is not None
    assert ParameterDocument.__name__ == "ParameterDocument"
    assert ParameterRepository.__name__ == "ParameterRepository"
    assert ProgressReporter.__name__ == "ProgressReporter"


def test_phase2_module_imports() -> None:
    from src.backend.domain.dataframe_utils import (
        reorder_columns_with_update_mark_first,
    )
    from src.backend.domain.highlight_optimizer import HighlightOptimizer
    from src.backend.domain.processing_control import check_stop_frequently
    from src.backend.domain.sheet_process_result import SheetProcessResult
    from src.frontend.window_utils import set_window_icon
    from src.shared.log_utils import log
    from src.shared.resource_utils import get_resource_path

    assert log is not None
    assert reorder_columns_with_update_mark_first is not None
    assert check_stop_frequently is not None
    assert HighlightOptimizer is not None
    assert SheetProcessResult is not None
    assert set_window_icon is not None
    assert get_resource_path is not None

    if importlib.util.find_spec("openpyxl") is not None:
        from src.backend.infrastructure.config_manager import ConfigManager

        assert ConfigManager is not None

    from src.backend.infrastructure.progress_manager import ThreadSafeProgressManager

    assert ThreadSafeProgressManager is not None

    if importlib.util.find_spec("tkinter") is None:
        pytest.skip("tkinter is not available in this test environment")

    from src.frontend.gui_update_manager import GUIUpdateManager, GUIUpdateType

    assert GUIUpdateManager is not None
    assert GUIUpdateType is not None
