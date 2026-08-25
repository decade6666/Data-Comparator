# Design：排除字段 per-sheet 化与表单可搜索下拉

## 边界与契约

新增配置键 `sheet_common_cols: Dict[str, List[str]]`，贯穿链路：

```
ParameterDocument (contracts.py)
  → CompareRequest / to_parameter_document (web_api.py, 逐字段手写拷贝!)
  → ConfigManager.sheet_common_cols (config_manager.py)
  → process_single_sheet_complete 解析 effective_cols_to_drop (data_comparison.py)
  → read_single_sheet_from_excel(cols_to_drop=...) (excel_header_utils.py, 签名不动)
```

前端数据层：`emptyConfig()` + `buildParameters()`（useConfig.js）双补，否则 `applyDocument` 遍历不到 / payload 不带出。

## 语义

- **整体替换**：`if sheet_name in config.sheet_common_cols`（成员判断，非真值判断——`{"AE": []}` 必须表示「AE 什么都不删」）。
- 丢弃发生在**读取期**（`df.drop`），早于锚点解析与差异比对；`process_missing_sheet` / `process_new_sheet` 收到已 drop 的 DataFrame，无需改动。
- 老配置缺键 → `{}` → 全部走全局分支，输出逐字节不变。

## 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 编辑器形态 | 复用 fields/anchors 的 dict 表格 | 用户拍板「完全复用现有表格」 |
| 生效语义 | 整体替换 | 用户拍板，与既有 sheet_ignore_cols / sheet_key_map 约定一致 |
| 表单列输入 | `el-select filterable + allow-create + clearable + default-first-option` | filterable 是 allow-create 生效前提（EP 源码 useSelect.mjs:118）；clearable 保证能改回全局 |
| 比对表单 | `el-select multiple filterable`，不开 allow-create | 多选造名会污染 include/exclude 推导 |
| 候选来源 | `allSheets ∪ 当前已选/本行值` | 保证未扫描到手输的表单名不丢失、可重选 |
| 卡片 key | 保持 `common_cols` 不改名 | `App.vue:39` 直读常量无兜底，改名漏改渲染 `undefined` |
| 数据驱动 | CARDS 加 `globalKey`/`perSheetKey`，cardValue/saveEditedValue 塌缩为 `if (card.globalKey)` | 避免两张 `type:'fields'` 卡片串写（最高风险点） |
| 分隔线 | `.parameter-card + .parameter-card { border-top: color-mix(border 55%, transparent) }` | 相邻兄弟天然 N-1 条线；混 transparent 适配两种背景（panel-body 与历史详情对话框）；`--color-border` 暗色自动跟随 |
| STRIP 元组 | `_EXPORT_STRIP_FIELDS` / `_STRIP_PARAMETER_FIELDS` **不加**新键 | 它们只剥离路径/上传 id，误加 = 导出丢配置 / 历史详情不可见 |

## 兼容性

- 老配置 JSON 无新键：后端 `{}` 回退全局；前端 `|| {}` 渲染只出全局标签。
- 老前端 bundle 不传新键：Pydantic `default_factory=dict` 补 `{}`，无需版本协商。
- 前端 `applyDocument` 缺键不重置的既有缺陷（跨配置残值污染）本次修复为 `key in doc ? doc[key] : defaults[key]`，爆炸半径已核（config_name 被后续覆盖、其余回默认更正确）。

## 回滚

- 阶段 A（契约）/ 阶段 B（行为）各自合入后单独可回滚且行为零变化（新键未用 / 缺键回退）。
- 前端新键字段随后端回滚时会被 `extra: forbid` 拦成 422——回滚顺序必须后端先行回滚再回滚前端。

## 测试要点

- 后端：3 条行为用例（全局/替换/空列表清空）+ ConfigManager 回退 + 契约用例（to_parameter_document 直测、422 锁定拼写、导出与历史不剥离、模板双声明）。
- 前端：ParameterEditDialog（往返/候选集/allow-create/null 安全/sheets 保存回归）、CompareForm（不串写回归 ×2 + 双 patch）、useConfig（emptyConfig/buildParameters/applyDocument 残值修复）、HistoryRunDetail 扩展。
- el-dialog stub 需渲染双插槽并 onMounted emit('open')；select 用 vm.$emit 驱动。
