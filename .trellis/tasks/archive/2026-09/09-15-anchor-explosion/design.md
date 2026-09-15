# Design · 修复比对任务笛卡尔积爆炸与停止无响应

## 关键约束：异常必须绕过两层宽 except

改动的核心难点不是「怎么报错」，而是**让错误能活着到达正确的处理点**。
现有代码有两层会吞掉普通 `Exception` 的处理器：

```
perform_full_comparison            data_comparison.py:608 try
  ├─ :613-618  create_anchor_by_sas_names(new_df / old_df)
  ├─ :656-662  pd.merge(on="_ANCHOR", how="outer")     ← 爆炸点
  ├─ :890      except InterruptedError: raise           ← 既有的「放行」写法
  └─ :892-905  except Exception: 记录日志并 return 空元组 ← ⚠️ 会吞掉锚点错误

process_single_sheet_complete
  ├─ :417-426  调用 perform_full_comparison
  ├─ :436      result.success = True                    ← ⚠️ 空元组也会被判成功
  ├─ :450-451  except InterruptedError: raise
  └─ :452-457  except Exception: success=False + error_message  ← 我们要到达这里
```

若只在 `create_anchor_by_sas_names` 里 `raise ValueError(...)`，它会在 `:892` 被吞掉，
`perform_full_comparison` 返回 `pd.DataFrame(), {}, [], ...`，然后 `:436` 把
`result.success` 置为 `True` —— **表单被静默变成空表**，比现状更难排查。

**结论：必须引入专用异常类，并在 `perform_full_comparison` 里复刻 `:890` 的重抛写法。**

## 方案

### 1. 新增领域异常 `AnchorUnavailableError`

放在 `src/backend/domain/data_comparison.py` 模块级（紧邻 `create_anchor_by_sas_names`）：

```python
class AnchorUnavailableError(Exception):
    """锚点无法构造，继续比对会退化为笛卡尔积，必须快速失败。"""
```

不放进 `processing_control.py` —— 那里的语义是「停止控制」，与此无关。

### 2. `create_anchor_by_sas_names`：4 条兜底路径改抛异常

| 行号 | 现状 | 改为 |
|---|---|---|
| `:923-927` | 无 SASFieldName → `_ANCHOR=""` | `raise AnchorUnavailableError("表单[X]没有 SASFieldName 信息")` |
| `:933-937` | 无 matched_keys → `_ANCHOR=""` | `raise AnchorUnavailableError` 并列出期望 key 与实际 SAS 列数 |
| `:939-947` | matched key 不在 df.columns → `_ANCHOR=""` | `raise AnchorUnavailableError` 并列出缺失列 |
| `:961-965` | 构造异常 → `_ANCHOR=""` | `raise AnchorUnavailableError(...) from e` |

保留 `:955` 的「锚点重复」**告警**不变 —— 锚点重复是合法场景（AC3 要求不误伤）。

错误信息只含表单名、期望 key 名、实际列名，不含单元格内容。

### 3. `perform_full_comparison`：重抛 + 防爆闸

在 `:890` 的 `except InterruptedError: raise` **之后、`:892` 的 `except Exception` 之前**插入：

```python
except AnchorUnavailableError:
    raise
```

顺序很重要：Python 按源码顺序匹配 except 子句，必须排在宽 `except Exception` 前面。

另在 `:656` 的 `pd.merge` **之前**加防爆闸（纵深防御，防止未来出现新的全同锚点路径）：

```python
_guard_anchor_cardinality(new_df, old_df, sheet_name, progress_manager.safe_log)
```

**闸门规则（AC3 要求不误伤合法重复锚点）**：只在「双侧都退化」时拦截 ——
新旧两侧的 `_ANCHOR` **去重后基数均为 1**，且两侧行数乘积超过阈值。
单侧重复、或基数 >1 的正常重复锚点一律放行。

理由：笛卡尔积爆炸的充分条件就是双侧同时塌缩成单一键值；只有一侧塌缩时
外连接的行数是 N+M 量级而非 N×M，不构成爆炸。阈值取一个明显异常的值
（如乘积 > 1_000_000），避免拦下小表的合理场景。

### 4. `apply_highlight_to_worksheet`：提取 + 停止检查

`src/backend/domain/excel_utils.py`：

```python
def apply_highlight_to_worksheet(ws, config, sheet_type=None, diff_info=None,
                                 add_sas_names=[], del_sas_names=[],
                                 sas_file_names=[], log_func=None,
                                 stop_flag=None):          # ← 新增，默认 None 保持兼容
```

- 在 `:134` 的行循环**之前**构建一次 `diff_keys`（`diff_info` 为空则为 `{}`），
  循环体内 `:156-158` 改为直接引用。纯等价变换。
- 循环内复用既有原语 `processing_control.check_stop`（带 `check_counter` 节流，
  见 `processing_control.py`，`test_processing_control.py:34-56` 已覆盖其节流语义），
  避免每行都做一次 Event 查询的开销。

调用点 `data_comparison.py:1473-1482` 补 `stop_flag=stop_flag`。

## 失败表单的下游行为（AC2）

`AnchorUnavailableError` 从 `perform_full_comparison` 抛出后：
1. `process_single_sheet_complete:452` 的 `except Exception` 接住 →
   `success=False` + `error_message`，**正常 return**（不抛）。
2. 写入循环 `:1412-1416` 命中既有的 `if not result.success:` 分支，记日志并 `continue`。
3. 其余表单照常写入，任务最终 `completed`。

**无需新增任何管道** —— 完全复用既有失败路径。

> 对根计划的一处修正：修复后该任务**不是**「以失败收尾」，而是**成功完成**，
> 报告只含 10 个锚点有效的表单，日志里有 48 条明确的锚点失败记录。这比整体失败更好：
> 用户拿到部分结果 + 可操作的诊断信息。

## 兼容性

- `AnchorUnavailableError` 继承 `Exception`，不影响 `InterruptedError` 传播链。
- `apply_highlight_to_worksheet` 新参数有默认值，既有调用方无需改动。
- `test_processing_control.py:301-303` monkeypatch 了 `create_anchor_by_sas_names`
  为 `lambda *args: args[0]`，绕过真实实现 → **不受影响**。
- 行为变化（预期且符合 PRD）：以前锚点失效的表单会产出笛卡尔积垃圾数据，
  现在会被跳过。这是修复目的本身，不是回归。

### 已知行为差异（已评估，接受）

`diff_keys` 从循环内提到循环外，带来一个理论上的时序差异：当 `diff_info` 非空
**且键无法 `int()` 转换** 时——

| | 旧行为 | 新行为 |
|---|---|---|
| 有「更新」行 | 循环内第一条更新行抛 `ValueError` | 循环前抛 `ValueError` |
| 无「更新」行 | 不抛（分支从未进入） | 抛 `ValueError` |

已实测确认。评估结论：**接受**。
1. `diff_info` 的键来自 `perform_full_comparison` 里 dift DataFrame 的 `row["row"]`，
   始终是 pandas 行索引（int / np.int64），生产路径不可能出现不可转换的键。
2. 即使出现，异常会被写入循环的 `data_comparison.py:1532` `except Exception` 接住，
   记录「写入最终文件时异常」并跳过该表单，属于安全降级。
3. 为「兼容」而吞掉畸形 diff 数据会违反项目 CLAUDE.md 的「不要静默吞错」。


## 风险

| 风险 | 处置 |
|---|---|
| 某些用户依赖「锚点失效也出数据」的现状 | 现状产出的是笛卡尔积垃圾（N×M 行），无实用价值；日志会明确说明跳过原因 |
| 防爆闸误伤 | 规则收紧到「双侧基数均为 1 且乘积超阈值」，并加单测覆盖正常重复锚点 |
| 停止检查拖慢高亮 | 用带 `check_counter` 节流的 `check_stop`，不是每行 `check_stop_frequently` |
