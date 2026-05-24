import json

import pytest

from src.backend.infrastructure.parameter_repository import JsonParameterRepository


def test_repository_saves_and_loads_document(tmp_path) -> None:
    repository = JsonParameterRepository(base_dir_getter=lambda: str(tmp_path))
    repository.ensure_config_directory()

    document = {
        "old_file_path": "old.xlsx",
        "new_file_path": "new.xlsx",
        "output_directory": "out",
    }

    repository.save_document("sample", document)

    loaded = repository.load_document("sample")

    assert loaded == document
    assert repository.get_config_path("sample").endswith("sample.json")


def test_repository_lists_and_deletes_documents(tmp_path) -> None:
    repository = JsonParameterRepository(base_dir_getter=lambda: str(tmp_path))
    repository.ensure_config_directory()
    repository.save_document("b", {"output_directory": "b"})
    repository.save_document("a", {"output_directory": "a"})

    assert repository.list_configurations() == ["a", "b"]
    assert repository.delete_document("a") is True
    assert repository.delete_document("missing") is False
    assert repository.list_configurations() == ["b"]


def test_repository_creates_missing_builtin_templates(tmp_path) -> None:
    repository = JsonParameterRepository(base_dir_getter=lambda: str(tmp_path))

    repository.ensure_builtin_templates(
        {
            "tpl": {
                "old_file_path": "",
                "new_file_path": "",
                "output_directory": "",
            }
        }
    )

    assert repository.list_configurations() == ["tpl"]
    assert repository.load_document("tpl") is not None


def test_repository_rejects_non_object_document(tmp_path) -> None:
    repository = JsonParameterRepository(base_dir_getter=lambda: str(tmp_path))
    repository.ensure_config_directory()

    with open(repository.get_config_path("broken"), "w", encoding="utf-8") as file:
        json.dump(["not", "a", "document"], file)

    with pytest.raises(ValueError, match="配置文件格式无效"):
        repository.load_document("broken")
