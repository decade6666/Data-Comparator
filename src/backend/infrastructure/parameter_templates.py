# -*- coding: utf-8 -*-
"""内置配置模板（原 GUI ParameterManager 内置模板，迁移保留）。

模板为纯数据常量，供 JsonParameterRepository.ensure_builtin_templates 使用。
"""

from typing import Dict

from ...shared.contracts import ParameterDocument

BUILTIN_TEMPLATE_CIMS = "【模板】CIMS数据集"
BUILTIN_TEMPLATE_TM = "【模板】TM数据集"

BUILTIN_TEMPLATES: Dict[str, ParameterDocument] = {
    BUILTIN_TEMPLATE_CIMS: {
        "old_file_path": "",
        "new_file_path": "",
        "output_directory": "",
        "anchor_row_num": 1,
        "header_row_num": 2,
        "merge_deleted_data": True,
        "common_cols": [
            "STUDYID",
            "RANDID",
            "SUBINI",
            "SUBSTA",
            "FORMNO",
            "FORMSTA",
            "STA_DEC",
            "SDVSTA",
            "DMRSTA",
            "MR_STA",
            "TOPIC",
        ],
        "sheet_common_cols": {},
        "exclude_sheets": [
            "系统变量",
            "数据范围",
            "eCRF表单",
            "CPH_FT--Header & Footer",
            "eCRF备注日志",
        ],
        "default_keys": ["SUBJID", "VISITNUM", "FORMSEQ", "TOPICSEQ"],
        "sheet_key_map": {},
        "include_sheets": [],
        "ignore_cols": [],
        "sheet_ignore_cols": {},
        "sheet_order": [],
        "colors": {
            "highlight_fill": "#FFE5E5",
            "missing_sheet_tab": "#DC143C",
            "new_sheet_tab": "#00FF00",
        },
    },
    BUILTIN_TEMPLATE_TM: {
        "old_file_path": "",
        "new_file_path": "",
        "output_directory": "",
        "anchor_row_num": 2,
        "header_row_num": 1,
        "merge_deleted_data": True,
        "common_cols": ["PSTUDYNM", "PSTUDYID", "GROUPID", "ISDEL", "CRFVER"],
        "sheet_common_cols": {},
        "exclude_sheets": ["Code_List", "DOMAIN_NAME"],
        "default_keys": [
            "SUBJID",
            "VISTOID",
            "VISTREP",
            "FORMOID",
            "FORMREP",
            "RECREP",
        ],
        "sheet_key_map": {},
        "include_sheets": [],
        "ignore_cols": [],
        "sheet_ignore_cols": {},
        "sheet_order": [],
        "colors": {
            "highlight_fill": "#FFE5E5",
            "missing_sheet_tab": "#DC143C",
            "new_sheet_tab": "#00FF00",
        },
    },
}
