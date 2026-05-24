from typing import Any, Dict, Optional, Set, Tuple

from ...shared.log_utils import log


class HighlightOptimizer:
    """高亮标记优化器，提供缓存和批量处理功能。"""

    def __init__(self) -> None:
        self.cell_value_cache: Dict[Tuple[int, int], str] = {}
        self.row_status_cache: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.empty_rows_cache: Set[int] = set()
        self.non_empty_rows_cache: Set[int] = set()

    def clear_cache(self) -> None:
        self.cell_value_cache.clear()
        self.row_status_cache.clear()
        self.empty_rows_cache.clear()
        self.non_empty_rows_cache.clear()

    def get_cell_value_cached(self, cell: Any) -> str:
        cell_key = (cell.row, cell.column)
        if cell_key not in self.cell_value_cache:
            value = cell.value
            self.cell_value_cache[cell_key] = (
                str(value).strip() if value is not None else ""
            )
        return self.cell_value_cache[cell_key]

    def is_row_empty_cached(
        self,
        sheet: Any,
        row_idx: int,
        start_col: int = 1,
        end_col: Optional[int] = None,
    ) -> bool:
        if row_idx in self.empty_rows_cache:
            return True
        if row_idx in self.non_empty_rows_cache:
            return False

        if end_col is None:
            end_col = sheet.max_column

        is_empty = True
        row = sheet[row_idx]
        for col_idx in range(start_col - 1, min(end_col, len(row))):
            if col_idx < len(row):
                cell = row[col_idx]
                if cell and cell.value is not None and str(cell.value).strip():
                    is_empty = False
                    break

        if is_empty:
            self.empty_rows_cache.add(row_idx)
        else:
            self.non_empty_rows_cache.add(row_idx)

        return is_empty

    def batch_get_category_values(
        self,
        sheet: Any,
        category_col_letter: str,
        start_row: int,
        end_row: int,
    ) -> Dict[int, str]:
        category_values = {}
        try:
            category_column = sheet[category_col_letter]
            for row_idx in range(start_row, min(end_row + 1, len(category_column) + 1)):
                if row_idx - 1 < len(category_column):
                    cell = category_column[row_idx - 1]
                    if cell:
                        category_values[row_idx] = self.get_cell_value_cached(cell)
        except Exception as exc:
            log(f"批量获取更新情况列失败: {str(exc)}", None)
        return category_values

    def get_row_status_cached(
        self,
        sheet: Any,
        row_idx: int,
        category_value: str,
        diff_info: Optional[Dict[int, Dict[str, Any]]],
        col_name_to_idx: Dict[str, int],
    ) -> Dict[str, Any]:
        cache_key = (sheet.title, row_idx)
        if cache_key in self.row_status_cache:
            return self.row_status_cache[cache_key]

        status: Dict[str, Any] = {
            "category": category_value,
            "needs_highlight": False,
            "highlight_cells": [],
            "is_empty": False,
        }

        if category_value in ["新增", "删除", "更新"]:
            status["needs_highlight"] = True

            if category_value in ["新增", "删除"]:
                status["highlight_cells"] = ["ALL"]
            elif category_value == "更新":
                data_row_idx = row_idx - 2
                if diff_info and data_row_idx in diff_info:
                    status["highlight_cells"] = list(diff_info[data_row_idx].keys())

        self.row_status_cache[cache_key] = status
        return status
