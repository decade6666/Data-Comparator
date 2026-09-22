# Design: 修复锚点行宽于数据行导致整表读取失败并误判为缺失表单

## 设计总纲

两个缺陷、两层修复，互相独立、可分别验证：

| 层 | 缺陷 | 修复 | 文件 |
|---|---|---|---|
| L1 读取层 | 行宽不齐导致 `pd.DataFrame` 抛 ValueError | 抄 pandas 上游两步法：先逐行裁尾、再全局补齐 | `excel_header_utils.py` |
| L2 错误语义层 | 读失败被吞成 `None`，与「表单不存在」同义 → 误判为缺失表单 | 读失败改抛领域异常，落入既有失败路径；失败清单写进报告 | `excel_header_utils.py`、`data_comparison.py` |

L1 修完后，本次线上的 4 个表单就能正常比对。L2 是止血之外的「防下一次」——因为掉进同一个 `except → None` 坑的失败原因不止一种（见下）。

---

## L1：双向列宽对齐（R1）

### 现状缺陷

`excel_header_utils.py:168-183` 只有单向补齐：

```python
if data_rows:
    actual_num_cols = max(len(row) for row in data_rows)
    if len(sas_field_name) < actual_num_cols:      # 只有「列名窄于数据」这一侧
        sas_field_name.extend([f"Unnamed_{i}" ...])
    if len(sas_field_label) < actual_num_cols:
        sas_field_label.extend([f"Unnamed_{i}" ...])
```

注释写「进行填充或截断」，实际无截断分支。反方向直接落到 `:187` 抛 ValueError。

### 方案：照搬 pandas `OpenpyxlReader.get_sheet_data` 的两步法

依据见 `research/pandas-upstream-ragged-row-handling.md`。pandas 在 `reset_dimensions()` 后做了两步善后，
`08-23` 那次只抄了「调用 reset_dimensions」，漏了善后。

**第 1 步 — 逐行裁掉尾部空值**，作用于表头行与数据行：

```python
def _trim_trailing_empty(values: List[Any]) -> List[Any]:
    end = len(values)
    while end > 0 and _is_blank(values[end - 1]):
        end -= 1
    return values[:end]

def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
```

> **不能照抄 pandas 的谓词。** pandas 的 `_convert_cell` 把空单元格转成 `""`，所以它用 `converted_row[-1] == ""`；
> 本项目 `_normalize_value`（`:58-69`）对空单元格返回 `None`。只判 `== ""` 会漏掉全部 `None`，等于没裁。

**第 2 步 — 全局补齐到统一宽度**，替换现有 `:168-183`：

```python
widths = [len(sas_field_name), len(sas_field_label)]
widths += [len(row) for row in data_rows]
target_width = max(widths) if widths else 0

# 列名侧：沿用既有 Unnamed_i 命名，不改语义
if len(sas_field_name) < target_width:
    sas_field_name.extend(f"Unnamed_{i}" for i in range(len(sas_field_name), target_width))
if len(sas_field_label) < target_width:
    sas_field_label.extend(f"Unnamed_{i}" for i in range(len(sas_field_label), target_width))

# 数据侧：新增。补 None（不是 ""），与 _normalize_value 对空单元格的返回值一致
data_rows = [
    row if len(row) == target_width else row + [None] * (target_width - len(row))
    for row in data_rows
]
```

补齐值用 `None` 而非 pandas 的 `""`：进 DataFrame 后为 `NaN`，与既有测试
`tests/test_excel_header_utils.py:137`（`pd.isna(...) or == ""`）的预期兼容。

> **注意：裁尾对三类行各自独立进行**（锚点行按自己的尾部空值裁、表头行按自己的裁、每条数据行按自己的裁），
> 不是「两行同位置都为空才裁」的联合条件。这一点很关键：当锚点行某尾部位置为空、而表头行同位置有文本时，
> 锚点行被裁短、表头行未裁 → `target_width` 取表头宽度 → 锚点行该位置由第 2 步补成 `Unnamed_i`，
> 而不是留下 `""`。联合条件反而会把 `""` 留下来。

**第 3 步 — 消灭残留的空列名**（新增，依据 `research/dup-empty-columns-downstream-impact.md`）：

```python
sas_field_name = [
    name if (isinstance(name, str) and name.strip()) else f"Unnamed_{i}"
    for i, name in enumerate(sas_field_name)
]
```

只规范化 **name**，不动 `sas_field_label`（label 允许为空，它只用于展示与 `attrs`，不参与列访问）。
`Unnamed_{i}` 必须用**绝对下标**，否则两个空洞会拿到同一个名字，重名问题原地复发。

### 为什么必须有第 3 步：空列名不是无害的

第 1 步的裁尾只能消灭**尾部**空列名，消灭不了锚点行**中段**的空洞（两个真实列名之间夹一个空单元格）。
中段空洞是既有缺陷（不是本次改动引入），但 `research/dup-empty-columns-downstream-impact.md` 的
12 组 pandas 2.3.3 实测证明它危害明确，且本任务的验收标准 AC3 已承诺「`df.columns` 不含空字符串列名且无重复」：

| 空列名数量 | 后果 | 位置 |
|---|---|---|
| ≥2 个 | **硬崩溃**：`merged_df[""]` 返回 DataFrame → `.astype(str).str.strip()` 抛 `AttributeError` | `data_comparison.py:1047,1086` |
| ≥2 个 | **硬崩溃**：`.loc[row_idx, ""]` 返回 Series → `if pd.notna(Series)` 抛 ambiguous `ValueError` | `data_comparison.py:751,762` |
| ≥2 个 | **硬崩溃**：`.loc[...] = ...` 抛 `cannot reindex on an axis with duplicate labels` | `data_comparison.py:778-786` |
| **哪怕只有 1 个** | **静默错误输出**：新旧锚点行宽度不同时 `""` 落入 `added_cols`/`deleted_cols`（set 比较，`:626-641`），`:858-861` 强制 `change_type=data_changed` → 幻影变更 | `data_comparison.py:626-641,858-861` |
| **哪怕只有 1 个** | **静默错误输出**：`col_name_to_idx` 后写覆盖前写 → 高亮打到最后一个空列；所有空 name 表头被染新增/删除色 | `excel_utils.py:106-112,123-126` |

注意 `data_comparison.py:895-899` 把 ambiguous `ValueError` 特意翻译成「锚点行可能存在重复列」的提示 ——
说明这个失败模式项目早已遇到过，但一直靠 broad except 兜底成「Sheet 失败」，没有根治。
第 3 步顺手根治它，代价只是低频空洞场景可能出现 `Unnamed_i` 幻影增删，与现有 `Unnamed_i` 补名行为一致。

被否决的替代方案（同一份 research，均有实验佐证）：

- **截断列名到数据宽度**：三重后果，均有实验佐证。①丢失真实声明的 SAS 字段名（静默删除）；
  ②新旧文件不对称截断 → 成批幻影删除列；③若锚点键落在被截断区，`create_anchor_by_sas_names`
  整体置空锚点（`data_comparison.py:940-946`），merge 退化为同键笛卡尔积（实测 2×2 → 4 行）——
  数据量大时是灾难级后果。**不可取**。
- **只做裁尾、不做第 3 步**：对本次线上故障够用，但中段空洞的三个硬崩溃点仍在，且违反 AC3。

### 为什么这个顺序能同时满足 R1.3 和 R1.4

| 锚点行尾部的性质 | 裁尾是否生效 | 结果 | 需求 |
|---|---|---|---|
| 有样式、无值（本次线上故障，22 vs 16） | ✅ 裁掉 | 锚点宽度回落到真实宽度，与数据一致 | R1.3 不产生空列名 |
| 真实声明的 SAS 字段名、但无数据 | ❌ 不裁（非空） | 数据行补 `None` 到锚点宽度，字段保留 | R1.4 已声明 schema 不丢失 |
| 数据行反而更宽（现状） | — | `target_width` 取数据宽度，列名补 `Unnamed_i`（原逻辑） | R1.1 不回归 |

**顺序不可颠倒。** 先补后裁会先造出一批空列名再去裁，等于没解决；且中途可能产生重名空列污染
`name_to_label_map`（`:198-200` 的字典推导，重名互相覆盖）。

### 不改的部分

- **不回退 `reset_dimensions()`**（`:45-46`）。回退会让 `08-23` 的「成片均为空」缺陷复发。
- **不改空行终止语义**（`:127-134`）。已核对无回归：现状对全空行 `all(...)` 为 `True`；
  裁尾后该行长度为 0，`all([])` 同样为 `True`，`break` 行为一致。
- **不改锚点重复列名检查**（`:94-110`）。该检查在读到锚点行后立即执行，**位置在裁尾/补齐/规范化之前**，
  且只统计 `non_empty_names`，因此第 1～3 步都不会改变它的判定结果。顺序不要调整。

---

## L2：区分读失败与表单不存在（R2、R3）

### 现状缺陷

`read_single_sheet_from_excel` 的返回值 `None` 承载了两种互斥语义：

| 情形 | 位置 | 返回 |
|---|---|---|
| 表单确实不存在 | `:37-39` 显式检查 `sheet_name not in wb.sheetnames` | `None` |
| 读取失败（任意异常） | `:246-253` broad `except Exception` | `None` |

调用方 `data_comparison.py:155-156` 无法区分 → `:207-231` 走缺失分支 →
`process_missing_sheet`（`:467`）把旧表**每一行**标记「删除」→ `result.success = True` → 任务终态 ✅。

掉进这个坑的失败原因至少有两种，说明这不是孤例：

1. 本次：行宽不齐（L1 已修根因）。
2. `08-24-sheet-read-failure-sentinel` 记录的：锚点行重复列名 → `:110` 主动 `raise ValueError`。

### 方案：改抛领域异常，落入既有失败路径

**否决的方案**：烂尾任务 `08-24` 提议的 `READ_FAILED = object()` 哨兵。
哨兵值需要在每个分支前插入判定（`:155-156` 归一化、`:173/:178/:207` 三个分支、`df.empty` 判定），
穿透面大、易漏判，且与 `DataFrame.empty` 的交互需要额外小心（该任务自己的 Risks 就点了这条）。

**采纳的方案**：新增领域异常，由**既有**的 `except Exception` 接住。

```python
# excel_header_utils.py 模块级
class SheetReadError(Exception):
    """读取单个 Sheet 失败。与「Sheet 不存在」（返回 None）区分。"""
```

`:246-253` 改为：

```python
except Exception as e:
    # 关闭 workbook 的清理逻辑保持不变
    raise SheetReadError(f"读取Sheet [{sheet_name}] 失败: {e}") from e
```

- `:37-39` 的「不存在 → `None`」**保持不变**。
- `:239-245` 的 `except InterruptedError: raise` **保持不变**，且位置在前，不会被新分支截胡（R4）。
- `❌ 读取Sheet [...] 失败` 的日志由上游统一打，读取层不再自己打（避免一条失败打两行）。

### 为什么不用改调用方的分支逻辑

`process_single_sheet_complete` 的 try 覆盖了两次读取调用（`:136-153`），其异常出口已经齐备：

```python
except InterruptedError:
    raise                                            # :450-451  停止语义优先，不受影响
except Exception as e:
    error_msg = f"处理Sheet [{sheet_name}] 时出错: {str(e)}"
    log_func(f"❌ {error_msg}")                       # :452-457  统一失败日志
    result.success = False
    result.error_message = error_msg
    return result
finally:
    progress_manager.update_sheet_progress(
        sheet_name, "完成" if result.success else "失败", is_final_update=True
    )                                                # :458-462  进度已自动置「失败」
```

聚合层也已有「部分失败、整体继续」的先例：

```python
if not result.success:
    log_func(f"⚠️ 表单 [{sheet_name}] 处理失败: {result.error_message}")   # :1412-1416
    continue
```

**所以 L2 的核心改动只有「`return None` → `raise SheetReadError`」一行语义变更**，
其余全部复用既有惯例。`SheetProcessResult.error_message` 字段已存在（`sheet_process_result.py:13`），无需新增。

### R3：失败可见性（日志醒目汇总）

**用户决策（2026-09-21）**：采用日志汇总方案，**报告结构完全不变**。
曾评估过的「报告新增『读取失败表单』工作表」方案已被否决，见下方「明确不做的可见性增强」。

在聚合循环中收集失败清单，保存前打一条醒目的多行汇总：

```python
# 聚合循环外初始化
failed_sheets: List[Tuple[str, str]] = []

# 聚合循环内（:1412-1416 处）
if not result.success:
    log_func(f"⚠️ 表单 [{sheet_name}] 处理失败: {result.error_message}")
    failed_sheets.append((sheet_name, result.error_message or "未知原因"))
    continue
```

```python
# 保存前（"所有表单处理完成，开始保存最终文件..." 之后、创建「比对结果汇总」之前）
if failed_sheets:
    log_func(f"⚠️ 共 {len(failed_sheets)} 个表单处理失败:")
    for name, reason in failed_sheets:
        log_func(f"   {name}: {reason}")
```

失败表单在报告中**直接缺席**（聚合循环 `continue` 跳过写入），不再被误标为整表「删除」——
这本身就是相对现状的核心改善：宁可少一张表，也不能给出一张内容错误的表。

**为什么不需要碰保存前的工作表插入逻辑**：本方案不新增任何工作表，
因此 `.trellis/spec/backend/excel-data-guidelines.md` 的「汇总表必须固定第一张 / `worksheets[1:]` 假设」约束
与本次改动无关，`_sheets.sort()`（`:1575`/`:1584`）与汇总表创建（`:1590`）一行都不用动。

### 明确不做的可见性增强

- **不在报告中新增「读取失败表单」工作表**（用户决策）。
  技术上已验证可行且安全（该表无 `更新情况（标记）` 列 → 汇总循环三项计数为 0 → 被 `:1627` 跳过，不污染汇总），
  但会给报告多引入一种结构形态。留档备查：若日后日志汇总被证明仍不够显眼，这是现成的升级路径。
- **不新增任务终态「部分失败」**。`job_manager.py:384-391` 只有 completed/failed/cancelled 三态，
  新增需同步前端状态映射，改动面超出本任务（R5）。
- **不新增 sheet 进度状态串**。`update_sheet_progress` 的 status 目前无任何消费者
  （`progress_manager.py:22-49` 函数体不读它），前端也无 sheet 状态枚举 —— 加了零成本也零效果。
  注意 `finally`（`:458-462`）本就会把失败表单的进度置为「失败」，无需改动。
- **不让读失败终止整份比对**。会因个别坏表废掉整份报告，与既有「单表失败、整体继续」的产品语义相悖
  （聚合层 `:1412-1416` 已有该先例）。

> **残留风险（已知并接受）**：任务终态仍为 `completed`，用户若不看日志仍可能忽略失败。
> 相比现状的改善是：失败表单不再以「整表删除」的错误形态出现在报告里。

---

## 兼容性与回滚

| 维度 | 影响 |
|---|---|
| 配置契约 | 无变更。不碰 `contracts.py` / Web API 请求模型 / 配置仓库 |
| API 契约 | 无变更。`run_comparison` 签名与返回不变，异常映射不变 |
| 报告结构 | **无变更**。不新增工作表；失败表单在报告中缺席（而非错标为「删除」） |
| 停止语义 | 不变。`InterruptedError` 两处分支均在新逻辑之前，优先级不变 |
| 回滚 | 两层独立提交，可单独 `git revert`。L1 回滚即恢复现状崩溃；L2 回滚即恢复 `None` 语义 |

## 风险

- **`SheetReadError` 会被 `except Exception` 接住是有意为之**，但也意味着它无法穿透到应用层。
  这符合「单表失败、整体继续」的语义；若将来需要任务级失败，需另设通道，不要改这里。
- **`data_comparison.py` 是 1691 行的复杂核心文件**。本次只碰三处：聚合循环内加 3 行收集、
  保存前加失败表写入、不动比对算法与分支结构。
- **L1 的裁尾会改变 `sas_field_label` 的长度**，进而影响 `df.attrs["sas_file_label"]`（`:213-215` 有 `[:len(df.columns)]` 截断保护）。
  需在测试中断言 label 与 name 长度一致。
- **第 3 步的 `Unnamed_{i}` 理论上可能与真实列名撞名**（源文件真有一列就叫 `Unnamed_3`）。
  该暴露面在现有补名逻辑（`:170-183`）中已经存在，本次不新增防护，仅记录。
- **第 3 步会改变中段空洞表单的既有行为**：这类表单的列名从 `""` 变为 `Unnamed_i`。
  变化方向是从「崩溃或幻影差异」变为「与现有 `Unnamed_i` 一致的可寻址列」，属修复而非回归；
  但若有既存报告依赖 `""` 列名，会看到差异。已确认无此类依赖（`""` 无法被用户配置引用）。

## 参考

- `research/pandas-upstream-ragged-row-handling.md`（L1 依据）
- `research/read-failure-surfacing.md`（L2 依据）
- `.trellis/spec/backend/excel-data-guidelines.md`（汇总表位置约束）
- `.trellis/spec/backend/error-handling.md`（异常惯例：内置异常优先、`InterruptedError` 独立通道）
- 被本任务吸收的烂尾规划：`git show fix/sheet-read-failure-sentinel:.trellis/tasks/08-24-sheet-read-failure-sentinel/prd.md`
