# pandas 上游如何处理 reset_dimensions() 后的参差行

> 调研人：Opus（主会话，非子代理）
> 结论强度：已在本机 pandas 2.3.3 / openpyxl 3.1.5 源码与运行时双重验证

## 为什么要查这个

我们的 `read_single_sheet_from_excel` 调用 `ws.reset_dimensions()`（`src/backend/domain/excel_header_utils.py:45-46`）后行宽不齐，
导致锚点行宽于数据行时 `pd.DataFrame(data_rows, columns=sas_field_name)` 抛 ValueError。

`08-23-fix-empty-read-and-project-state` 的 PRD 引入 `reset_dimensions()` 时，理由是
「`read_only` 工作表的 `reset_dimensions()` 是 pandas `OpenpyxlReader` 对只读工作表的标准做法」。
那句话只对了一半：pandas 确实这么做，但 **pandas 紧接着做了两步善后，而我们只抄了前半句**。

## 上游实现（pandas 2.3.3，`pandas/io/excel/_openpyxl.py`）

```python
def get_sheet_data(self, sheet, file_rows_needed=None):
    if self.book.read_only:
        sheet.reset_dimensions()

    data = []
    last_row_with_data = -1
    for row_number, row in enumerate(sheet.rows):
        converted_row = [self._convert_cell(cell) for cell in row]
        while converted_row and converted_row[-1] == "":
            # trim trailing empty elements      <-- 第 1 步
            converted_row.pop()
        if converted_row:
            last_row_with_data = row_number
        data.append(converted_row)
        ...
    data = data[: last_row_with_data + 1]

    if len(data) > 0:
        # extend rows to max width               <-- 第 2 步
        max_width = max(len(data_row) for data_row in data)
        if min(len(data_row) for data_row in data) < max_width:
            empty_cell = [""]
            data = [
                data_row + (max_width - len(data_row)) * empty_cell
                for data_row in data
            ]
    return data
```

**第 1 步：逐行裁掉尾部空值。** 这一步直接消灭「有样式、无值」的尾部单元格 —— 正是我们锚点行 22 宽而数据行 16 宽的成因。
**第 2 步：把所有行补齐到全局最大宽度。** 这一步保证 DataFrame 构造不会因行宽不齐而失败。

pandas 明确知道 `reset_dimensions()` 会产生参差行，所以把这两步写死在读取路径里。我们缺的就是这两步。

## 机制佐证（openpyxl 3.1.5 侧）

- `ReadOnlyWorksheet.iter_rows`：`max_col = max_col or self.max_column`。
- `reset_dimensions()` 把 `_max_column` 置 `None`，而 `max_column` 属性**不会自动重算**
  （`calculate_dimension()` 不带 `force=True` 直接抛 `ValueError("Worksheet is unsized")`，`iter_rows` 没有调它）。
- 于是 `_cells_by_row` 传 `max_col=None` → `_get_row` 落到 `max_col = max_col or row[-1]['column']` → **每行按自己最后一个单元格定宽**。

本机实测（dimension 声明正确的 4 行 3 列工作簿，仅第 1、2 行 D/E/F 加底色不填值）：

```
dimension 声明 : A1:F4
reset_dimensions 后逐行宽度 : [6, 6, 3, 3]
```

## 对本任务方案选型的结论

采用 pandas 同款两步法（**先逐行裁尾、再全局补齐**），顺序不可颠倒。理由：

| 场景 | 两步法的结果 | 是否满足需求 |
|---|---|---|
| 锚点行尾部是「有样式无值」单元格（本次线上故障） | 裁尾后锚点行宽度回落到真实宽度，与数据行一致 | ✅ R1.2、R1.3 |
| 锚点行尾部是**真实声明但无数据**的 SAS 字段名（非空字符串） | 不被裁掉，数据行补齐到锚点宽度 | ✅ R1.4（已声明 schema 不丢失） |
| 数据行宽于锚点行（现状已支持） | 全局最大宽度取数据宽度，锚点行补 `Unnamed_i`（现有 `:168-183` 逻辑） | ✅ R1.1 不回归 |

### 与本项目的两点差异（实现时必须处理，不能照抄）

1. **空值表示不同**：pandas `_convert_cell` 把空单元格转成 `""`，所以它的裁尾谓词是 `== ""`；
   我们的 `_normalize_value`（`excel_header_utils.py:58-69`）对空单元格返回 `None`。
   裁尾谓词必须写成「`None` 或 `strip()` 后为空的字符串」，只判 `== ""` 会漏掉 `None`。
2. **空行终止语义不同**：pandas 读完全部行再裁掉尾部空行；我们在遇到第一个空行时 `break`（`:127-134`）。
   这是既有语义，本次**不改**。需确认裁尾不会改变该判定 —— 已核对：
   现状 `all(v is None or 空串 for v in row_values)` 对全空行为 `True`；裁尾后该行长度为 0，`all([])` 同样为 `True`，
   `break` 行为一致，无回归。

### 补齐用什么填充值

pandas 用 `""`。我们应当用 `None` —— 与 `_normalize_value` 对空单元格的返回值保持一致，
且 `None` 进入 DataFrame 后为 `NaN`，与现状「短行以 NaN 补齐」的既有测试预期
（`tests/test_excel_header_utils.py:137` `pd.isna(...) or == ""`）兼容。

## 参考

- `pandas/io/excel/_openpyxl.py::OpenpyxlReader.get_sheet_data`（pandas 2.3.3）
- `openpyxl/worksheet/_read_only.py::ReadOnlyWorksheet.iter_rows` / `_cells_by_row` / `_get_row`（openpyxl 3.1.5）
- `src/backend/domain/excel_header_utils.py:45-46`、`:58-69`、`:117-136`、`:168-183`、`:187`
- 复现脚本：`/tmp/repro_wide_anchor.py`
