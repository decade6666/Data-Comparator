# Research: 补齐数据行后「多列空字符串列名」的下游影响与修复方案对比

- **Query**: 若修复时把数据行右侧补 None 到 `len(sas_field_name)`，DataFrame 会得到多列名为 `""` 的重复列（来自锚点行尾部有样式无值的单元格），下游哪些代码会出错或产生错误输出？
- **Scope**: internal（`src/backend/domain/`）+ /tmp 下 pandas 2.3.3 实验验证
- **Date**: 2026-09-21
- **实验环境**: pandas 2.3.3（与项目 `pyproject.toml` 安装环境一致，已实测 `python3 -c "import pandas"` 输出 2.3.3）

## 结论速览

| 场景 | 结果 | 证据 |
|---|---|---|
| `pd.DataFrame(rows, columns=[...含重复""])` | 正常构造，不报错 | 实验 [1] |
| `df.drop(columns=cols_to_drop, errors="ignore")` | 正常；`cols_to_drop` 来自用户配置，不会包含 `""` | `excel_header_utils.py:193` |
| `name_to_label_map` 字典推导 | 重复 `""` 键互相覆盖，只留最后一个位置对应的 label（元数据错位） | `excel_header_utils.py:198-200`，实验 [2] |
| `sas_name_to_label` 构造 | 同上，`""` 只保留一条映射 | `excel_header_utils.py:218-223`，实验 [3] |
| `create_anchor_by_sas_names` | 不受影响（锚点键来自用户配置，不会是 `""`；`key in df.columns` 对重复列返回 bool） | `data_comparison.py:930-952`，实验 [4] |
| 新增/删除列判定（set 比较） | `""` 进入 `sas_file_name` 集合；新旧文件锚点行宽度不同时产生幻影 `added_cols=['']`/`deleted_cols=['']` → 幻影 `data_changed` + 空 name 表头全部错染高亮 | `data_comparison.py:626-641,858-861`，实验 [5] |
| `pd.merge(on="_ANCHOR", suffixes=("", "_OLD_"))` | 不报错；新侧 `""`×N + 旧侧 `"_OLD_"`×M 共存 | `data_comparison.py:656-662`，实验 [6] |
| `compare_columns_by_sas_names` | **致命**：`merged_df[""]` 返回 DataFrame（多列），`.astype(str).str.strip()` 抛 `AttributeError: 'DataFrame' object has no attribute 'str'` → 整个 Sheet 比对失败 | `data_comparison.py:1040-1057,1086`，实验 [7] |
| 行级判定 `merged_df.loc[row_idx, col]` | **致命**：`""` 多列时返回 Series，`if pd.notna(Series)` 抛 `ValueError: The truth value of a Series is ambiguous` → 被捕获后 Sheet 失败，且错误提示误导为「锚点行可能存在重复列」 | `data_comparison.py:748-765,892-899`，实验 [8]/[A] |
| 删除行合并回写 `merged_df.loc[row_idx, col] = ...` | **致命**：`ValueError: cannot reindex on an axis with duplicate labels` | `data_comparison.py:778-786`，实验 [9] |
| 临时列清理 | `""` 不以 `_ANCHOR`/`DIFF_`/`_OLD_` 开头结尾，不受影响；旧侧空列变 `"_OLD_"` 会被正确丢弃 | `data_comparison.py:822-829`，实验 [10] |
| `reorder_columns_with_update_mark_first` | 不受影响（list.remove/insert + `df[cols]` 对重复列安全） | `dataframe_utils.py:6-16`，实验 [11] |
| `replace_worksheet_headers` | 当前主流程**无任何调用方**（仅 `excel_utils.py:7` 定义），逐 cell 写值，对空串/重复不敏感 | `src/` 全局 grep 仅命中定义处 |
| `apply_highlight_to_worksheet` | `col_name_to_idx` 字典后写覆盖前写 → `""` 高亮定位到**最后一个**空列（错位）；且 `""` 会命中 `add_sas_names`/`del_sas_names` 使所有空 name 表头染色 | `excel_utils.py:123-126,106-112`，实验 [D] |
| `dataframe_to_rows` 写数据 | 按值迭代，与列名无关，安全 | 实验 [C]（openpyxl 实测） |
| 仅有 1 个 `""` 列时 | 全流程可走通（`merged_df[""]` 为 Series） | 实验 [12] |

## 详细查证

### 1. `excel_header_utils.py` 自身（189-234）

- `df.drop(columns=cols_to_drop, errors="ignore")`（`excel_header_utils.py:193`）：`cols_to_drop` 来自 `common_cols`/`sheet_common_cols` 用户配置（`data_comparison.py:376-386` 证实其语义），不会含 `""`，空列不会被误删，也不报错。
- `name_to_label_map = {name: label for ...}`（`excel_header_utils.py:198-200`）：字典推导对重复键 `""` **后者覆盖前者**，多个空列各自的真实 label（若有）全部丢失，只留最后一个；随后 202-206 行按 `df.columns` 重建 label 列表，所有 `""` 列都取到同一个 label（实验 [2] 实测重建结果 `['编号','姓名','年龄','','']`，本例恰好全为空串，无可见错位；若 label 行在空 name 位置有真实文本，则错位可见）。
- `sas_name_to_label`（`excel_header_utils.py:218-223`）：同样按 name 收敛为一条 `"" -> ""` 映射（实验 [3]）。
- 关键点：94-110 行的「锚点行重复告警」**只统计非空名字**（`n.strip()` 过滤，`excel_header_utils.py:95-97`），即现有代码明确允许 `""` 重复列存在——这不是异常路径，是留出的兼容空间。

### 2. `data_comparison.py`

- `create_anchor_by_sas_names`（`data_comparison.py:908-967`）：锚点键来自 `config.sheet_key_map`/`default_keys`（`data_comparison.py:366-371`），不会是 `""`；930 行 `set(sas_names)` 与 940 行 `key not in df.columns` 对重复列均返回 bool，不抛错；952 行 `df[matched_keys]` 按 list 取列，与其他位置的重复列无关（实验 [4]）。空列只是随行数据一起被 merge，本身无害。
- `compare_columns_by_sas_names`（`data_comparison.py:970-...`）：
  - 993 行 `col.endswith("_OLD_")` 会把旧侧空列变成的 `"_OLD_"` 纳入，998 行还原出 `original_col=""`；999 行 `"" in all_columns` 为 True → `""` 进入比对列表（非锚点、非忽略列，1006-1013 行拦不住它）。
  - 1047/1086 行 `merged_df[col]`：当合并后 `""` 列 ≥2 时返回 **DataFrame**，1050 行 `.astype(str).str.strip()` 抛 `AttributeError`（实验 [7]）。该异常上抛到 `perform_full_comparison` 的 except（`data_comparison.py:892-905`），整个 Sheet 返回失败结果。
- `perform_full_comparison`：
  - 无 reindex/align 类操作，但 656-662 行 `pd.merge` 在双方各带重复空列时**不报错**（实验 [6]），产物是新侧 `""`×N + 旧侧 `"_OLD_"`×M。
  - 626-641 行用 **set** 比较 `sas_file_name`：`""` 参与集合运算。仅一侧锚点行更宽时，`""` 落入 `added_cols`/`deleted_cols`（实验 [5]）；858-861 行非空 `added_cols` 直接把 `change_type` 强制为 `data_changed` —— 纯宽度差异制造幻影变更；`""` 再经 `apply_highlight_to_worksheet`（`excel_utils.py:106-112`）让所有空 name 表头染上新增/删除色。
  - 748-765 行行级判定：`merged_df.loc[row_idx, ""]` 在 `""` 多列时返回 Series，`if pd.notna(Series) and ...` 抛 ambiguous ValueError（实验 [8]/[A]）；错误文案被 895-899 行特意翻译成「锚点行可能存在重复列……」，说明该失败模式已在项目预期内，但目前靠 broad except 兜底成 Sheet 失败。
  - 778-786 行删除行合并回写 `merged_df.loc[row_idx, col_name] = ...`：重复标签下抛 `cannot reindex on an axis with duplicate labels`（实验 [9]）。
- `reorder_columns_with_update_mark_first`（`dataframe_utils.py:6-16`）：`"更新情况（标记）" in df.columns`、`list.remove/insert`、`df[cols]` 均对重复列安全，且有 try/except 兜底（实验 [11]）。

### 3. `excel_utils.py`

- `replace_worksheet_headers`（`excel_utils.py:7-57`）：逐 cell 写 `new_headers` 值，长度不齐时补/截空串（20-38 行），对空串与重名完全不敏感；且 grep 证实**当前 `src/` 主流程没有任何调用方**，与本问题无关。
- `apply_highlight_to_worksheet`（`excel_utils.py:60-176`）：123-126 行 `col_name_to_idx[col_name] = col_idx` 字典后写覆盖前写，重复 `""` 只剩最后一个索引（实验 [D] 实测取 idx=3 而非第一个空列 idx=2）→「更新」单元格高亮会打到**最后一个**空列上；106-112 行 `current_sas_name in add/del_sas_names` 会让所有 `""` 表头一起染色。不崩溃，但输出错。

### 4. 其他假设列名唯一的位置

全仓 grep `set_index|to_dict|pd.concat|groupby|pivot|value_counts|drop_duplicates|merge(` 仅命中 `data_comparison.py:656` 的 `pd.merge` 与 842 行 `reset_index`；`dataframe_to_rows`（`data_comparison.py:1454`）按值迭代安全（实验 [C]）。**真正的单列访问点**为：

- `data_comparison.py:1047,1086`（`merged_df[col]`，比对列）→ 崩溃点一；
- `data_comparison.py:751,762,784`（`.loc[row_idx, col]`）→ 崩溃点二/三；
- `data_comparison.py:200,240,318,352,813-815,849`（`df["更新情况（标记）"]`）→ 该列名由代码生成且唯一，不受影响；
- `data_comparison.py:952`（`df[matched_keys]`，list 取列）→ 安全。

## 方案对比（结论性判断）

### 方案 A：裁掉锚点行与表头行同位置都为空的尾部条目，再补齐数据行

- 能消除的：尾部 `""` 列全部消失 → 崩溃点一/二/三、幻影 `added_cols=['']`、`name_to_label_map` 收敛、高亮错位，全部消失（对照上表逐项）。数据行在尾部这些位置的值本来就只可能是 None（数据行比锚点行窄才有本 bug），裁掉不丢任何真实数据。
- 残留缺口 1：**锚点行空、但表头行（label 行）同位置非空**的尾部条目，按「都为空」的裁剪条件会被保留 → 列名仍为 `""`；若 ≥2 个此类位置，崩溃点一/二仍在。真实文件中 label 行比锚点行长且恰好落在锚点空位的情况（未验证是否出现）。
- 残留缺口 2：锚点行**中段**的空洞（两个真实列名之间夹空单元格）不是尾部条目，方案 A 不管；≥2 个中段空洞同样复现崩溃。是否真实存在（未验证）。
- 结论：对已确认的「尾部有样式无值」场景**足够**；但按字面条件不是 100% 闭环。

### 方案 B：列名直接截断到数据宽度

会丢失的东西（按严重度）：

1. **真实声明的 SAS 字段名被静默删除**：任务背景已确认锚点行尾部可能是「真实声明但无数据」的非空字段名。截断后这些列不进 `attrs["sas_file_name"]`、不出现在报告里，且无任何告警。
2. **新旧不对称制造幻影差异**：若旧文件该处数据更宽（或锚点行不宽），旧保留了这些名字而新被截断 → `data_comparison.py:626-641` 集合差产生成批幻影 `deleted_cols` → `change_type="data_changed"`、整列染删除色、（`merge_deleted_data` 默认 True 时）触发 778-786 行合并回写。
3. **末日场景：锚点键被截掉**：若配置的锚点列恰好位于数据宽度之外的尾部 → `data_comparison.py:940` 判 `missing_keys` → 946 行 `_ANCHOR` 整体置 `""` → 两文件所有行锚点同为空串，`pd.merge(on="_ANCHOR", how="outer")` 按同键做笛卡尔积（实验 [B] 实测 2 行×2 行 → 4 行；真实数据量下是行数乘积级的内存与垃圾差异爆炸）。
4. **按 Sheet 数据行数不一致**：168 行截断仅发生在 `if data_rows:` 有数据时，空数据 Sheet 不截断，同一文件读两遍（新旧各一次）行为都可能不同。

结论：B 不可取。

### 方案 C：沿用现有 `Unnamed_i` 约定给空列名补名

- 项目已有该约定：无锚点行时 `Unnamed_{i}`（`excel_header_utils.py:158-160`）、锚点行比数据行窄时按**绝对位置**补 `Unnamed_{i}`（`excel_header_utils.py:170-176`，`range(len(sas_field_name), actual_num_cols)`）。给 `""` 位置按同样规则补名（如 `Unnamed_{i}`，i 取该列绝对下标）完全贴合现有代码习惯。
- 效果：列名唯一 → 崩溃点一/二/三、字典收敛、高亮错位全部消失，且同时覆盖 A 的两个残留缺口（label 非空的尾部、中段空洞）。
- 代价：补出来的 `Unnamed_i` 会参与 626-641 行集合比较。新旧文件空洞位置/数量不同时产生 `Unnamed_20` 级别的幻影增删列与幻影 `data_changed`——比 `""` 的幻影**更显眼**（名字各不相同，无法互相抵消），可能把纯宽度差异放大成可见告警。A 的尾部裁剪没有这个副作用（两边尾部同位空条目都被裁掉，集合相等）。

### 推荐

**A 为主 + C 为兜底（A+C 组合）**：

1. 先按方案 A 裁掉「锚点名与表头名在同一位置都为空」的**尾部**条目——消除最常见的宽度差噪声且无幻影副作用；
2. 再对仍剩余的 `""` 列名（label 非空的尾部位、中段空洞）套用方案 C 的 `Unnamed_{i}`（绝对下标）补名——保证列名唯一这一硬性下游约束（`compare_columns_by_sas_names` 与 `.loc` 的单列访问是硬崩溃点），代价只是低频空洞场景可能出现 `Unnamed_i` 幻影增删，且与现有 `Unnamed_i` 行为一致、可接受；
3. 明确放弃方案 B（真实字段名丢失 + 幻影差异 + 锚点失效笛卡尔合并，均已在代码路径与实验中证实）。

## Caveats / 未验证

- 「锚点行中段空洞」「label 行比锚点行长且覆盖锚点空位」在真实 CRF 文件中是否出现：未验证（无样本文件）。
- openpyxl 只读模式 `reset_dimensions()` 后行宽推断与 `iter_rows(values_only=True)` 每行实际返回宽度的具体表现：未在本次调研中实验（属修复实现层，不影响本结论；任务背景已确认 187 行 `ValueError` 现象）。
- pandas < 2.x 对重复列 merge 的行为可能与 2.3.3 不同：未验证，项目锁定环境为 2.3.3。
- 实验脚本位于 `/tmp/exp_dup_cols.py`、`/tmp/exp_extra.py`（仓库外，未污染工作区）。
