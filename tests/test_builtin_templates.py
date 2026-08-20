# -*- coding: utf-8 -*-
"""内置模板全局只读：模板不落盘、可直接读取、不可覆盖/删除。"""

from src.backend.infrastructure.parameter_templates import BUILTIN_TEMPLATES


def test_builtin_templates_are_not_written_by_ensure(tmp_path) -> None:
    """ensure_builtin_templates 不应把模板写入用户配置目录。"""
    from src.backend.infrastructure.parameter_repository import (
        JsonParameterRepository,
    )

    repo = JsonParameterRepository(base_dir_getter=lambda: str(tmp_path))
    repo.ensure_builtin_templates(BUILTIN_TEMPLATES)

    names = repo.list_configurations()
    assert names == []


def test_builtin_template_document_matches_constant(tmp_path) -> None:
    """按名字读取模板时，应返回 BUILTIN_TEMPLATES 常量而非落盘文件。"""
    from src.backend.infrastructure.parameter_repository import (
        JsonParameterRepository,
    )

    repo = JsonParameterRepository(base_dir_getter=lambda: str(tmp_path))
    template_name = next(iter(BUILTIN_TEMPLATES))
    document = repo.load_document(template_name)
    assert document == BUILTIN_TEMPLATES[template_name]
