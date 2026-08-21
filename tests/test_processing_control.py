import importlib
import sys
import threading
import types

import pytest

from src.backend.domain.processing_control import (
    check_stop,
    check_stop_frequently,
    update_progress,
)


def test_check_stop_frequently_raises_on_set_flag() -> None:
    messages = []
    stop_flag = threading.Event()
    stop_flag.set()

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        check_stop_frequently(messages.append, stop_flag)

    assert messages == ["处理已被用户停止"]


def test_check_stop_frequently_passes_on_unset_flag() -> None:
    messages = []

    check_stop_frequently(messages.append, threading.Event())

    assert messages == []


def test_check_stop_skips_until_counter_interval() -> None:
    messages = []
    stop_flag = threading.Event()
    stop_flag.set()
    counter = [1]

    check_stop(messages.append, stop_flag, check_counter=counter)

    assert counter == [2]
    assert messages == []


def test_check_stop_raises_on_counter_interval() -> None:
    messages = []
    stop_flag = threading.Event()
    stop_flag.set()
    counter = [100]

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        check_stop(messages.append, stop_flag, check_counter=counter)

    assert counter == [101]
    assert messages == ["处理已被用户停止"]


def test_update_progress_delegates_to_callback() -> None:
    updates = []

    update_progress(
        "处理中",
        50,
        progress_func=lambda msg, value: updates.append((msg, value)),
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
    fake_pandas = types.SimpleNamespace(
        DataFrame=lambda *args, **kwargs: object(),
    )
    fake_openpyxl = types.SimpleNamespace(
        load_workbook=lambda *args, **kwargs: None,
    )
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

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        excel_header_utils.read_single_sheet_from_excel(
            "file.xlsx",
            "Sheet1",
            1,
            1,
            lambda _message: None,
            stop_flag=stop_flag,
        )

    assert closed == [True]


def test_read_single_sheet_passes_unset_flag(monkeypatch) -> None:
    """未触发停止标志时，显式传入的 stop_flag 不应抛异常。"""
    fake_pandas = types.SimpleNamespace(
        DataFrame=lambda *args, **kwargs: object(),
    )
    fake_openpyxl = types.SimpleNamespace(
        load_workbook=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "pandas", fake_pandas)
    monkeypatch.setitem(sys.modules, "openpyxl", fake_openpyxl)
    sys.modules.pop("src.backend.domain.excel_header_utils", None)
    excel_header_utils = importlib.import_module(
        "src.backend.domain.excel_header_utils"
    )

    monkeypatch.setattr(
        excel_header_utils,
        "load_workbook",
        lambda *args, **kwargs: types.SimpleNamespace(
            sheetnames=["Sheet1"],
            __getitem__=lambda self, name: None,
            close=lambda: None,
        ),
    )

    excel_header_utils.read_single_sheet_from_excel(
        "file.xlsx",
        "Sheet1",
        1,
        1,
        lambda _message: None,
        stop_flag=threading.Event(),
    )


def test_file_runtime_propagates_interrupted_error_without_fallback(
    monkeypatch, tmp_path
) -> None:
    from src.backend.infrastructure import file_runtime

    source_file = tmp_path / "source.xlsx"
    source_file.write_bytes(b"content")
    messages = []

    def stop_during_cleanup(*_args, **_kwargs):
        raise InterruptedError("用户停止了操作")

    monkeypatch.setattr(file_runtime, "remove_filters", stop_during_cleanup)

    with pytest.raises(InterruptedError, match="用户停止了操作"):
        file_runtime.check_and_remove_file_protection(
            str(source_file), [], messages.append, work_dir=str(tmp_path)
        )

    assert not any("回退" in message or "备用" in message for message in messages)
    assert list(tmp_path.glob("source_nofilter_*.xlsx")) == []


def test_file_runtime_skips_non_ooxml_input_on_copy(
    monkeypatch,
    tmp_path,
) -> None:
    from src.backend.infrastructure import file_runtime

    source_file = tmp_path / "legacy.xls"
    source_file.write_bytes(b"legacy workbook")
    messages = []

    result = file_runtime.check_and_remove_file_protection(
        str(source_file), [], messages.append, work_dir=str(tmp_path)
    )

    assert result[:2] == (False, False)
    assert result[3] is None
    copied_path = result[2]
    assert copied_path != str(source_file)
    with open(copied_path, "rb") as copied_file:
        assert copied_file.read() == source_file.read_bytes()
    assert any("非 OOXML 包" in message for message in messages)


def test_perform_full_comparison_propagates_interrupted_error(
    monkeypatch,
) -> None:
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
    monkeypatch.setitem(
        sys.modules,
        "openpyxl.utils.dataframe",
        fake_dataframe_utils,
    )
    monkeypatch.setitem(sys.modules, "openpyxl.worksheet", fake_worksheet_pkg)
    monkeypatch.setitem(
        sys.modules,
        "openpyxl.worksheet.worksheet",
        fake_worksheet,
    )
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

    data_comparison = importlib.import_module(
        "src.backend.domain.data_comparison",
    )
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
