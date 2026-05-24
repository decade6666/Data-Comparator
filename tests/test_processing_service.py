import datetime

import pytest

from src.backend.application.processing_service import (
    ProcessingPaths,
    apply_processing_paths,
    build_output_path,
    resolve_log_directory,
    sanitize_output_name,
    validate_processing_paths,
)


def test_sanitize_output_name_replaces_invalid_characters() -> None:
    assert sanitize_output_name(' a:b/c*?"<>| ') == "a-b-c"


def test_validate_processing_paths_requires_all_paths() -> None:
    with pytest.raises(ValueError, match="请填写所有必要的路径信息"):
        validate_processing_paths({"old_file_path": "a", "new_file_path": ""})


def test_validate_processing_paths_requires_existing_input_files() -> None:
    with pytest.raises(FileNotFoundError, match="输入文件不存在"):
        validate_processing_paths(
            {
                "old_file_path": "old.xlsx",
                "new_file_path": "new.xlsx",
                "output_directory": "out",
            },
            path_exists=lambda path: path == "out",
        )


def test_validate_processing_paths_creates_output_directory_when_missing() -> None:
    created = []

    def fake_exists(path: str) -> bool:
        return path in {"old.xlsx", "new.xlsx"}

    def fake_makedirs(path: str) -> None:
        created.append(path)

    result = validate_processing_paths(
        {
            "old_file_path": "old.xlsx",
            "new_file_path": "new.xlsx",
            "output_directory": "out",
        },
        path_exists=fake_exists,
        make_dirs=fake_makedirs,
    )

    assert result == ProcessingPaths("old.xlsx", "new.xlsx", "out")
    assert created == ["out"]


def test_apply_processing_paths_returns_new_mapping() -> None:
    original = {
        "old_file_path": "old0.xlsx",
        "new_file_path": "new0.xlsx",
        "output_directory": "out0",
        "anchor_row_num": 2,
    }

    updated = apply_processing_paths(
        original,
        ProcessingPaths("old.xlsx", "new.xlsx", "out"),
    )

    assert updated is not original
    assert updated["old_file_path"] == "old.xlsx"
    assert updated["anchor_row_num"] == 2
    assert original["old_file_path"] == "old0.xlsx"


def test_resolve_log_directory_falls_back_to_temp_dir() -> None:
    assert resolve_log_directory("", lambda: "/tmp/app") == "/tmp/app"


def test_build_output_path_uses_sanitized_config_name() -> None:
    output = build_output_path(
        "A:B",
        "/tmp/out",
        now=datetime.datetime(2026, 5, 23, 14, 30, 0),
    )

    assert output == "/tmp/out/A-B-比对报告-2026-05-23T14-30-00.xlsx"
