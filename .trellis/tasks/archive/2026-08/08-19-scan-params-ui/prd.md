# 表单扫描自动化与参数合并前端重构（子任务）

## Goal

重构比对参数界面：上传后自动扫描表单并显示扫描进度，表单类参数改为只勾选，修复「表单顺序」弹窗缺陷，合并「比对表单」「忽略字段」「锚点」三组参数，参数卡片标题加悬停说明。后端比对语义完全不变。

## Requirements

- R2.1 上传后自动扫描：`CompareForm.vue` 监听 `PathSelector` 已 emit 的 `uploaded` 事件（`PathSelector.vue:21`），上传成功即调 `GET /api/sheets?upload_id=…`；新增 `composables/useSheets.js`（oldSheets/newSheets/allSheets 并集、scanStatus、scanProgress）；旧文件扫描完成 scanProgress +5，新文件再 +5（0→5→10）；`ProgressPanel.vue` 增加「扫描文件中…」状态与扫描进度显示；删除 `ParameterEditDialog.vue` 手动扫描按钮与 `discoverSheets()`。
- R2.2 表单类参数只能勾选：删除 `sheetlist` 类型弹窗的文本框输入路径；未上传文件时显示「请先上传文件」提示，不提供手输兜底。
- R2.3 「指定表单」「排除表单」合并为「比对表单」：`CompareForm.vue` CARDS 中 `exclude_sheets`+`include_sheets` 合成一张卡片；弹窗 = 扫描到表单的复选框列表，默认全选，扫描完成后自动取消勾选配置 `exclude_sheets` 中的项；保存映射 `include_sheets`=勾选项、`exclude_sheets`=未勾选项 ∪（原 `exclude_sheets` 中本次未扫描到的项）；无扫描结果时两者保持原值。
- R2.4 「表单顺序」弹窗修复：用 `vuedraggable`（已在 `package.json:16-18`）渲染可拖拽列表；内容 = 比对表单勾选后的结果（R2.3 输出），而非全部扫描结果或空白；修复 `openDialog()` 对 `type:'order'` 不初始化（`ParameterEditDialog.vue:57-68`）与 `save()` 对 order 走 `textToValue()` 清空 `sheet_order`（`:104-117`）两个缺陷；保存值 = 拖拽后的顺序数组。
- R2.5 「忽略比对字段」+「表单忽略字段」合并为「忽略字段」：双列表格（表单可选 + 字段）；只填字段 → `ignore_cols`，表单+字段 → `sheet_ignore_cols[表单]`；加载已有配置反向拆行。
- R2.6 「默认锚点」+「自定义锚点」合并为「锚点」：交互与 R2.5 一致，映射 `default_keys` / `sheet_key_map`。
- R2.7 悬停说明：`ParameterCard.vue` 标题包 `el-tooltip`；新增 `constants/parameterDescriptions.js` 作为唯一文案源（内容取自 `App.vue:151-165` 帮助文案）；帮助弹窗改引用同一常量。
- R2.8 卡片收敛：8 张 → 5 张（排除字段 / 比对表单 / 忽略字段 / 锚点 / 表单顺序）。

## Acceptance Criteria

- [ ] 上传旧/新文件后自动扫描，进度条显示「扫描文件中…」，0→5→10；无手动扫描按钮。
- [ ] 表单类弹窗只有复选框，无输入框；未上传时提示先上传文件。
- [ ] 「比对表单」默认全选；模板排除项（如 CIMS 的 `exclude_sheets`）自动取消勾选；保存/重载勾选状态保持；换文件后模板排除项仍保留在排除列表。
- [ ] 「表单顺序」弹窗显示可拖拽列表且内容 = 勾选后的表单；拖动保存后输出报告 Sheet 顺序一致；不再空白、不再清空已存顺序。
- [ ] 「忽略字段」「锚点」填单参数/双参数保存后，配置 JSON 分别正确落在 `ignore_cols`/`sheet_ignore_cols`、`default_keys`/`sheet_key_map`。
- [ ] 5 张卡片标题悬停显示说明，帮助弹窗与悬停文案一致（同一数据源）。
- [ ] 现有比对行为不回归（`tests/test_compare_scope_and_order.py` 补 include+order 合并回归用例）。

## Out of Scope

- 后端任何参数语义变更（映射由前端组装，后端字段不变）。
- 登录/用户隔离（子任务 auth-isolation 负责；本任务依赖其 `useApi.js` 鉴权头落地）。

## Key Decisions

- 表单扫描数据源统一为并集（与后端 `data_comparison.py:1259-1261` 口径一致）。
- 合并参数在后端保持双字段，前端双向映射；避免后端契约变更风险。
- 帮助文案单一来源，防止悬停与帮助弹窗漂移。

## Risks

- `CompareForm.vue`/`ParameterEditDialog.vue` 是多个需求的汇合点，改动集中，需逐条验收。
- `sheet_order` 清空缺陷属于数据丢失类 bug，修复必须加回归断言（保存后值非空且顺序保留）。
- 依赖 auth-isolation 的 `useApi.js` 鉴权头；若其未落地，本地开发可用 mock 登录态先行。
