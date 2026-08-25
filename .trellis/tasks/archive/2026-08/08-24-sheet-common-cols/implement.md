# Implement：排除字段 per-sheet 化与表单可搜索下拉

执行顺序（后端先行，`CompareRequest` 为 `extra: forbid`）：

```
A 后端契约 → B 后端行为 → C 前端数据层 → D 前端 UI → E 样式 → F 测试与文档
```

## A 后端契约

- [ ] `src/shared/contracts.py:26` `ParameterDocument` 加 `sheet_common_cols: Dict[str, List[str]]`
- [ ] `src/frontend/web_api.py:249` `CompareRequest` 加 `sheet_common_cols = Field(default_factory=dict)`
- [ ] `src/frontend/web_api.py:269` `to_parameter_document()` 加 `"sheet_common_cols": dict(self.sheet_common_cols)`
- [ ] `src/backend/infrastructure/config_manager.py:16/:46` `__init__` 与 `update_from_parameters` 双补
- [ ] `src/backend/infrastructure/parameter_templates.py` CIMS / TM 两模板补 `"sheet_common_cols": {}`
- [ ] 不动 `_EXPORT_STRIP_FIELDS` / `_STRIP_PARAMETER_FIELDS`

## B 后端行为（data_comparison.py）

- [ ] `process_single_sheet_complete` :116 后插 per-sheet 解析（成员判断 `if sheet_name in`，照抄 :359-372 范式）
- [ ] :121-138 两次 `read_single_sheet_from_excel` 第 6/7 位置实参改关键字 `cols_to_drop=` / `stop_flag=`（必须成对改）
- [ ] 锚点列冲突告警：`effective_cols_to_drop` 与 `key_cols` 交集非空时打 `⚠️` 日志

## C 前端数据层（useConfig.js）

- [ ] `emptyConfig()` 加 `sheet_common_cols: {}`
- [ ] `buildParameters()` 加 `sheet_common_cols: config.sheet_common_cols`
- [ ] `applyDocument` 缺键重置修复：`config[key] = key in doc ? cloneValue(doc[key]) : defaults[key]`

## D 前端 UI

- [ ] `CompareForm.vue`：CARDS 加 `globalKey`/`perSheetKey`（common_cols 改 `type:'fields'`），`cardValue`/`saveEditedValue` 塌缩为 `if (card.globalKey)` —— 与 CARDS 同一次提交
- [ ] `ParameterEditDialog.vue`：dict 表格表单列换 `el-select filterable clearable allow-create default-first-option`，候选 `sheetOptionsFor(row) = allSheets ∪ 本行值`
- [ ] `ParameterEditDialog.vue`：比对表单换多选 `el-select`（collapse-tags 三件套，不开 allow-create），降级提示改 `v-if="!sheetNames.length"`，上方加全选/清空按钮
- [ ] `ParameterEditDialog.vue`：`rowsToValue` 用 `String(row.sheet || '').trim()`；删除 `toggleSheet` 与 textarea 死代码
- [ ] `ParameterEditDialog.vue`：样式 `.dict-row > .el-select, .dict-row > .el-input { min-width: 0 }`、`.sheet-select { width: 100% }`
- [ ] `HistoryRunDetail.vue:38-43`：排除字段卡片改 `{ global, perSheet }` 形态
- [ ] `constants/parameterDescriptions.js:2`：更新 common_cols 文案

## E 样式

- [ ] `main.css` `.parameter-card + .parameter-card` 分隔线 + `:last-child` 去 margin

## F 测试

- [ ] 后端 `test_compare_scope_and_order.py`：4 条用例（全局/替换/空列表/ConfigManager 回退）+ `_headers` 助手
- [ ] 后端 `test_web_api.py`：`to_parameter_document` 直测 + 拼错键 422
- [ ] 后端 `test_web_api_configs.py`：MINIMAL_DOC 扩展 + 导出断言
- [ ] 后端 `test_comparison_history_service.py`：redact 保留该键
- [ ] 后端 `test_builtin_templates.py`：双模板声明断言
- [ ] 前端 `ParameterEditDialog.spec.js`（新建）
- [ ] 前端 `CompareForm.spec.js`（新建）
- [ ] 前端 `useConfig.sheetCommonCols.spec.js`（新建）
- [ ] 前端 `HistoryRunDetail.spec.js`（扩展）

## G 文档

- [ ] README.md 配置表（补 common_cols + sheet_common_cols 两行）
- [ ] docs/使用手册.md、docs/开发文档.md JSON 示例
- [ ] src/shared/CLAUDE.md、根 CLAUDE.md（AI 使用指引 + Changelog）
- [ ] .trellis/spec/backend/excel-data-guidelines.md（common_cols 小节）

## 验证命令

```bash
python3 -m pytest -v --tb=short --strict-markers
python3 -m pytest --cov=src --cov-report=term-missing   # 覆盖率不下降
cd frontend && npm run test && npm run build
```

## 评审门

- [ ] 后端改动经 code-reviewer 复查（per-sheet 语义、关键字化调用）
- [ ] 前端 CompareForm 串写回归用例通过
- [ ] 手工 E2E（上传 → 编辑 → 比对 → 历史详情）通过或明确列出未验证项

## 回滚点

- 阶段 A/B 各自为独立回滚点（行为零变化）；前端回滚必须后于后端。
