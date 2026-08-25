# PRD：排除字段 per-sheet 化与表单可搜索下拉

## 背景

「排除字段」（`common_cols`）是「比对参数」里唯一还用纯文本域（每行一个值）编辑的字段类参数，与「忽略字段」「锚点」的表格式编辑器不一致；且它只有一份全局配置，无法针对单个表单单独指定「只在 AE 表排除某字段」。

「表单选择」相关 UI 现状：

- 「比对表单」（include/exclude）是平铺 checkbox 列表，不能搜索；
- 「忽略字段」「锚点」表格中的「表单」列是自由文本输入，拼错表单名静默不生效（与扫描结果完全脱钩）。

参数卡片之间没有视觉分隔，5 张卡片挤在一起。

## 目标

1. 「排除字段」编辑器与「忽略字段/锚点」完全一致：点 `+` 加行，每行「表单（可选）+ 逗号分隔字段 + 删除」。
2. 新增 per-sheet 排除字段配置 `sheet_common_cols`，语义与既有 `sheet_ignore_cols` / `sheet_key_map` 一致（**整体替换**：某表单一旦配置完全覆盖全局）。
3. 「表单」列与「比对表单」都改为可搜索下拉，候选来自已上传文件的扫描结果，同时保留自由输入能力。
4. 参数卡片之间加浅色分隔线，暗色模式自动适配。

## 非目标

- 不改变「表单顺序」（保持拖拽排序）。
- 不改变「忽略字段」「锚点」的数据结构与存储键。
- 不改变 `common_cols` 的语义本身（读取期物理删列）。
- 不做配置项字段校验（`PUT /api/configs/{name}` 仍为裸 dict 透传，沿用现状）。

## 需求约束

- 前端向后端提交任务时 `CompareRequest` 为 `extra: forbid`，新键必须后端先声明，否则提交即 422。
- 老配置 JSON 没有 `sheet_common_cols` 键时必须回退全局行为，输出与改造前一致。
- 前端 `applyDocument` 只遍历 `emptyConfig()` 的键，新键必须同时补 `emptyConfig()` 与 `buildParameters()`，否则加载/保存静默丢失。

## 验收标准

1. 「排除字段」卡片点击编辑后出现与「忽略字段」相同的表格编辑器；全局行与指定表单行均可添加、删除。
2. 配置 `common_cols=["UPDATETIME"]` + `sheet_common_cols={"AE":["AEMODIFY"]}` 时：AE 表输出无 `AEMODIFY` 但保留 `UPDATETIME`；DM 表无 `UPDATETIME`（回退全局）。
3. `sheet_common_cols={"AE":[]}` 时：AE 表什么都不删（全局排除失效）；其他表仍按全局排除。
4. 老配置无 `sheet_common_cols` 键时行为与改造前逐字节一致。
5. 表格「表单」列下拉可搜索、可输入新值回车创建、可清空（清空=全局）；「比对表单」为可搜索多选下拉，未扫描文件时保留「请先上传…」提示。
6. 参数卡片之间有浅色分隔线，最后一张卡片无下边框；暗色模式下可见。
7. 历史详情只读展示中「排除字段」正确显示全局与 per-sheet 条目；老历史快照无该键时只显示全局标签。
8. 后端覆盖率不下降；前端新增对 ParameterEditDialog / CompareForm / useConfig 的单元测试。

## 验收测试用例（后端）

| 用例 | 断言 |
|---|---|
| `test_global_common_cols_drops_columns` | 全局 `common_cols` 生效，AE/DM 表头均无该列 |
| `test_sheet_common_cols_replaces_global` | AE 用 per-sheet 替换（`UPDATETIME` 仍在）；DM 回退全局 |
| `test_sheet_common_cols_empty_list_disables_global` | `{"AE": []}` 清空 AE 的全局排除；DM 不受影响 |
| `test_config_manager_defaults_sheet_common_cols` | `ConfigManager` 默认 `{}`；老参数回退 `{}` |
| 契约用例 | `to_parameter_document` 带出该键；拼错键名 422；导出/历史快照不剥离该键；两个内置模板均声明该键 |
