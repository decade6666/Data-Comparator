import datetime

import pytest

from src.backend.application.comparison_runner import run_comparison


class FakeConfig:
    def __init__(self) -> None:
        self.parameters = None
        self.colors = None

    def update_from_parameters(self, parameters, colors) -> None:
        self.parameters = parameters
        self.colors = colors


def test_run_comparison_validates_paths_and_invokes_domain_processor() -> None:
    created_configs = []
    calls = {}
    logs = []

    def fake_config_factory() -> FakeConfig:
        config = FakeConfig()
        created_configs.append(config)
        return config

    def fake_process(
        old_path,
        new_path,
        output_path,
        log_func,
        config,
        progress_func=None,
        stop_flag=None,
    ):
        calls["old_path"] = old_path
        calls["new_path"] = new_path
        calls["output_path"] = output_path
        calls["config"] = config
        calls["progress_func"] = progress_func
        calls["stop_flag"] = stop_flag
        log_func("处理完成")
        return output_path

    parameters = {
        "old_file_path": "old.xlsx",
        "new_file_path": "new.xlsx",
        "output_directory": "/tmp/out",
        "anchor_row_num": 2,
        "colors": {"highlight_fill": "#FFFFFF"},
    }

    result = run_comparison(
        parameters,
        config_name="A:B",
        log_func=logs.append,
        process_func=fake_process,
        config_factory=fake_config_factory,
        path_exists=lambda path: path in {"old.xlsx", "new.xlsx", "/tmp/out"},
        now=datetime.datetime(2026, 5, 23, 14, 30, 0),
    )

    assert result == "/tmp/out/A-B-比对报告-2026-05-23T14-30-00.xlsx"
    assert calls["old_path"] == "old.xlsx"
    assert calls["new_path"] == "new.xlsx"
    assert calls["output_path"] == result
    assert calls["config"] is created_configs[0]
    assert created_configs[0].parameters is parameters
    assert created_configs[0].colors == {"highlight_fill": "#FFFFFF"}
    assert logs == ["处理完成"]


def test_run_comparison_uses_noop_log_when_callback_is_missing() -> None:
    def fake_process(
        old_path,
        new_path,
        output_path,
        log_func,
        config,
        progress_func=None,
        stop_flag=None,
    ):
        log_func("不会失败")
        return output_path

    result = run_comparison(
        {
            "old_file_path": "old.xlsx",
            "new_file_path": "new.xlsx",
            "output_directory": "/tmp/out",
        },
        process_func=fake_process,
        config_factory=FakeConfig,
        path_exists=lambda path: True,
        now=datetime.datetime(2026, 5, 23, 14, 30, 0),
    )

    assert result == "/tmp/out/web-比对报告-2026-05-23T14-30-00.xlsx"


def test_run_comparison_propagates_path_validation_errors() -> None:
    with pytest.raises(FileNotFoundError, match="输入文件不存在"):
        run_comparison(
            {
                "old_file_path": "old.xlsx",
                "new_file_path": "new.xlsx",
                "output_directory": "/tmp/out",
            },
            config_factory=FakeConfig,
            process_func=lambda *args, **kwargs: "unreachable",
            path_exists=lambda path: path == "/tmp/out",
        )
