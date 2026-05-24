import importlib
import sys
import threading
import types

import pytest

from src.backend.domain.processing_control import (
    check_stop,
    check_stop_frequently,
    set_global_stop_flag,
    update_progress,
)


@pytest.fixture(autouse=True)
def reset_global_stop_flag():
    set_global_stop_flag(None)
    yield
    set_global_stop_flag(None)


def test_check_stop_frequently_uses_global_stop_flag() -> None:
    messages = []
    stop_flag = threading.Event()
    stop_flag.set()
    set_global_stop_flag(stop_flag)

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        check_stop_frequently(messages.append)

    assert messages == ["处理已被用户停止"]


def test_check_stop_frequently_prefers_explicit_stop_flag() -> None:
    messages = []
    global_flag = threading.Event()
    global_flag.set()
    explicit_flag = threading.Event()
    set_global_stop_flag(global_flag)

    check_stop_frequently(messages.append, explicit_flag)

    assert messages == []


def test_check_stop_skips_until_counter_interval() -> None:
    messages = []
    stop_flag = threading.Event()
    stop_flag.set()
    set_global_stop_flag(stop_flag)
    counter = [1]

    check_stop(messages.append, check_counter=counter)

    assert counter == [2]
    assert messages == []


def test_check_stop_raises_on_counter_interval() -> None:
    messages = []
    stop_flag = threading.Event()
    stop_flag.set()
    set_global_stop_flag(stop_flag)
    counter = [100]

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        check_stop(messages.append, check_counter=counter)

    assert counter == [101]
    assert messages == ["处理已被用户停止"]


def test_update_progress_delegates_to_callback() -> None:
    updates = []

    update_progress(
        "处理中", 50, progress_func=lambda msg, value: updates.append((msg, value))
    )

    assert updates == [("处理中", 50)]


def test_update_progress_logs_callback_failure(capsys) -> None:
    def fail_progress(_msg, _progress):
        raise RuntimeError("failed")

    update_progress("处理中", 50, progress_func=fail_progress)

    assert capsys.readouterr().out == "进度更新异常: failed\n"


def test_update_progress_propagates_interrupted_error() -> None:
    def stop_progress(_msg, _progress):
        raise InterruptedError("用户停止了操作")

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        update_progress("处理中", 50, progress_func=stop_progress)


def test_read_single_sheet_propagates_interrupted_error(monkeypatch) -> None:
    fake_pandas = types.SimpleNamespace(DataFrame=lambda *args, **kwargs: object())
    fake_openpyxl = types.SimpleNamespace(load_workbook=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)
    sys.modules.pop("src.backend.domain.excel_header_utils", None)
    excel_header_utils = importlib.import_module(
        "src.backend.domain.excel_header_utils"
    )

    closed = []

    class FakeWorksheet:
        def iter_rows(self, *args, **kwargs):
            return iter([("value",)])

    class FakeWorkbook:
        sheetnames = ["Sheet1"]

        def __getitem__(self, _sheet_name):
            return FakeWorksheet()

        def close(self):
            closed.append(True)

    monkeypatch.setattr(
        excel_header_utils,
        "load_workbook",
        lambda *args, **kwargs: FakeWorkbook(),
    )
    stop_flag = threading.Event()
    stop_flag.set()
    set_global_stop_flag(stop_flag)

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        excel_header_utils.read_single_sheet_from_excel(
            "file.xlsx", "Sheet1", 1, 1, lambda _message: None
        )

    assert closed == [True]


def test_file_runtime_propagates_interrupted_error_without_fallback(
    monkeypatch, tmp_path
) -> None:
    fake_appdirs = types.SimpleNamespace(user_data_dir=lambda *args: str(tmp_path))
    fake_pandas = types.SimpleNamespace(read_excel=lambda *args, **kwargs: None)
    fake_openpyxl = types.SimpleNamespace(load_workbook=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "appdirs", fake_appdirs)
    monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)
    sys.modules.pop("src.backend.infrastructure.file_runtime", None)
    file_runtime = importlib.import_module("src.backend.infrastructure.file_runtime")

    source_file = tmp_path / "source.xlsx"
    source_file.write_bytes(b"content")
    fallback_calls = []

    class FakePythonCom:
        def CoInitialize(self):
            pass

        def CoUninitialize(self):
            pass

    class FakeWin32:
        def DispatchEx(self, _name):
            raise InterruptedError("用户停止了操作")

    monkeypatch.setattr(file_runtime, "get_app_temp_dir", lambda: str(tmp_path))
    monkeypatch.setattr(file_runtime, "pythoncom", FakePythonCom())
    monkeypatch.setattr(file_runtime, "win32", FakeWin32())
    monkeypatch.setattr(
        file_runtime,
        "remove_auto_filters_from_xlsx",
        lambda *args, **kwargs: fallback_calls.append(args),
    )

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        file_runtime.check_and_remove_file_protection(
            str(source_file), [], lambda _message: None
        )

    assert fallback_calls == []


def test_perform_full_comparison_propagates_interrupted_error(monkeypatch) -> None:
    fake_pandas = types.ModuleType("pandas")

    class FakeInputDataFrame:
        attrs = {
            "sas_file_name": ["id", "value"],
            "sas_name_to_label": {"id": "ID", "value": "Value"},
        }
        columns = ["id", "value"]

    class FakeMergedDataFrame:
        def __init__(self):
            self.attrs = {}
            self.columns = ["id", "value", "id_OLD_", "value_OLD_"]

        def __setitem__(self, _key, _value):
            pass

    fake_pandas.DataFrame = lambda *args, **kwargs: object()
    fake_pandas.merge = lambda *args, **kwargs: FakeMergedDataFrame()

    fake_appdirs = types.ModuleType("appdirs")
    fake_appdirs.user_data_dir = lambda *args: "/tmp"

    fake_openpyxl = types.ModuleType("openpyxl")
    fake_openpyxl.Workbook = object
    fake_openpyxl.load_workbook = lambda *args, **kwargs: None

    fake_styles = types.ModuleType("openpyxl.styles")
    fake_styles.PatternFill = lambda *args, **kwargs: object()
    fake_styles.Font = lambda *args, **kwargs: object()
    fake_styles.Border = lambda *args, **kwargs: object()
    fake_styles.Side = lambda *args, **kwargs: object()
    fake_styles.Alignment = lambda *args, **kwargs: object()

    fake_utils = types.ModuleType("openpyxl.utils")
    fake_utils.get_column_letter = lambda index: str(index)
    fake_dataframe_utils = types.ModuleType("openpyxl.utils.dataframe")
    fake_dataframe_utils.dataframe_to_rows = lambda *args, **kwargs: []

    fake_worksheet_pkg = types.ModuleType("openpyxl.worksheet")
    fake_worksheet = types.ModuleType("openpyxl.worksheet.worksheet")
    fake_worksheet.Worksheet = type("Worksheet", (), {})
    fake_table = types.ModuleType("openpyxl.worksheet.table")
    fake_table.Table = type("Table", (), {})
    fake_table.TableStyleInfo = type("TableStyleInfo", (), {})

    fake_psutil = types.ModuleType("psutil")

    monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
    monkeypatch.setitem(sys.modules, "appdirs", fake_appdirs)
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)
    monkeypatch.setitem(sys.modules, "openpyxl.styles", fake_styles)
    monkeypatch.setitem(sys.modules, "openpyxl.utils", fake_utils)
    monkeypatch.setitem(sys.modules, "openpyxl.utils.dataframe", fake_dataframe_utils)
    monkeypatch.setitem(sys.modules, "openpyxl.worksheet", fake_worksheet_pkg)
    monkeypatch.setitem(sys.modules, "openpyxl.worksheet.worksheet", fake_worksheet)
    monkeypatch.setitem(sys.modules, "openpyxl.worksheet.table", fake_table)
    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)

    for module_name in (
        "src.backend.domain.data_comparison",
        "src.backend.domain.excel_header_utils",
        "src.backend.domain.excel_utils",
        "src.backend.infrastructure.file_runtime",
        "src.backend.infrastructure.config_manager",
    ):
        sys.modules.pop(module_name, None)

    data_comparison = importlib.import_module("src.backend.domain.data_comparison")
    monkeypatch.setattr(
        data_comparison, "create_anchor_by_sas_names", lambda *args: args[0]
    )

    def raise_interrupted(*_args, **_kwargs):
        raise InterruptedError("用户停止了操作")

    monkeypatch.setattr(
        data_comparison, "compare_columns_by_sas_names", raise_interrupted
    )

    class FakeProgressManager:
        def __init__(self):
            self.messages = []

        def safe_log(self, message):
            self.messages.append(message)

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        data_comparison.perform_full_comparison(
            "Sheet1",
            FakeInputDataFrame(),
            FakeInputDataFrame(),
            ["id"],
            types.SimpleNamespace(merge_deleted_data=True),
            FakeProgressManager(),
        )
