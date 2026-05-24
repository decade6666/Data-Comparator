from src.backend.domain.highlight_optimizer import HighlightOptimizer


class Cell:
    def __init__(self, row, column, value):
        self.row = row
        self.column = column
        self.value = value


class Sheet:
    title = "Sheet1"
    max_column = 3

    def __init__(self, rows=None, columns=None):
        self.rows = rows or {}
        self.columns = columns or {}

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.rows[key]
        return self.columns[key]


def test_get_cell_value_cached_reuses_initial_value() -> None:
    optimizer = HighlightOptimizer()
    cell = Cell(1, 2, " value ")

    assert optimizer.get_cell_value_cached(cell) == "value"
    cell.value = "changed"

    assert optimizer.get_cell_value_cached(cell) == "value"


def test_is_row_empty_cached_tracks_empty_and_non_empty_rows() -> None:
    optimizer = HighlightOptimizer()
    sheet = Sheet(
        rows={
            1: [Cell(1, 1, None), Cell(1, 2, "  ")],
            2: [Cell(2, 1, None), Cell(2, 2, "x")],
        }
    )

    assert optimizer.is_row_empty_cached(sheet, 1)
    assert not optimizer.is_row_empty_cached(sheet, 2)

    sheet.rows = {
        1: [Cell(1, 1, "later")],
        2: [Cell(2, 1, None)],
    }

    assert optimizer.is_row_empty_cached(sheet, 1)
    assert not optimizer.is_row_empty_cached(sheet, 2)


def test_get_cell_value_cached_preserves_falsey_values() -> None:
    optimizer = HighlightOptimizer()

    assert optimizer.get_cell_value_cached(Cell(1, 1, 0)) == "0"
    assert optimizer.get_cell_value_cached(Cell(1, 2, False)) == "False"


def test_batch_get_category_values_uses_cached_cell_values() -> None:
    optimizer = HighlightOptimizer()
    sheet = Sheet(
        columns={"A": [Cell(1, 1, "新增"), Cell(2, 1, " 更新 "), Cell(3, 1, None)]}
    )

    assert optimizer.batch_get_category_values(sheet, "A", 1, 3) == {
        1: "新增",
        2: "更新",
        3: "",
    }


def test_batch_get_category_values_logs_failures(capsys) -> None:
    class FailingSheet:
        def __getitem__(self, key):
            raise RuntimeError(f"missing column: {key}")

    optimizer = HighlightOptimizer()

    assert optimizer.batch_get_category_values(FailingSheet(), "A", 1, 3) == {}
    assert "批量获取更新情况列失败" in capsys.readouterr().out


def test_get_row_status_cached_marks_rows_and_changed_cells() -> None:
    optimizer = HighlightOptimizer()
    sheet = Sheet()

    added_status = optimizer.get_row_status_cached(sheet, 2, "新增", None, {})
    updated_status = optimizer.get_row_status_cached(
        sheet,
        4,
        "更新",
        {2: {"name": True}},
        {"name": 1},
    )

    assert added_status["needs_highlight"] is True
    assert added_status["highlight_cells"] == ["ALL"]
    assert updated_status["needs_highlight"] is True
    assert updated_status["highlight_cells"] == ["name"]
