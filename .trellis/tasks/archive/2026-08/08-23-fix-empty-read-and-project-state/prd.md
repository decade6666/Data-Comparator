# 修复空读取与项目状态串扰

## Goal

修复三个已定位根因的缺陷，让用户用 CRF-Editor 导出的 Excel 能正常跑出真实差异报告，并且前端项目管理状态不再跨项目串扰：

1. 比对报告不再全空（日志里成片的「Sheet [XXX] 在新旧版本中均为空」消失）。
2. 新建项目从完全空白开始，不带入上一个项目的比对文件与参数。
3. 报告与日志按项目各自记住：切回跑过的项目仍可下载它自己的报告/日志，切到没跑过的项目不显示上一个项目的下载按钮与日志。

用户价值：真实数据可以正确比对；多项目工作流下界面行为符合直觉，不会下错文件。

## Background / 已确认事实

- CRF-Editor（gitee 侧工具）导出的 xlsx 中，每个 `xl/worksheets/sheetN.xml` 都带 `<dimension ref="A1"/>`，但实际工作表有几十列 × 几行数据（实测旧文件 `LB` 7 行 × 40 列）。
- openpyxl `load_workbook(read_only=True)` 直接采信 `<dimension>`，把 `max_row/max_col` 锁成 1：`excel_header_utils.py:36` 读表头只得到 1 列，数据行循环不产出，`df.empty` 为真 → `data_comparison.py:237` 打印「在新旧版本中均为空」。
- 筛选器清理（`xlsx_filter_cleaner.remove_filters`）本身工作正常：重写成功、zip 校验通过、openpyxl 可读；不是故障点。
- 前端的 `config`（`useConfig.js:38`）是模块级 reactive 单例；`ConfigSidebar.createNew()`（`ConfigSidebar.vue:50`）只弹窗不清空，直接 `saveConfig(name)` 把当前 config 另存为新名字 → 新项目继承上个项目的文件与参数。
- `useJob.js` 的 `jobId/logLines/outputName` 在 `App.vue:23` 单例实例化，仅 `logout()` 调用 `job.reset()`；切换项目既不重置也不切换 → 下载仍打给上个项目的 jobId。
- 后端 `/api/jobs/{job_id}/download`（`web_api.py:672`）已校验 `job.user_id != current_user.id` → 404，后端无问题。
- openpyxl 3.1.5 / pandas 2.3.3；`read_only` 工作表的 `reset_dimensions()` 是 pandas `OpenpyxlReader` 对只读工作表的标准做法。
- 附带发现（本次不修）：`<autoFilter ref="1:1"/>` 不符合 openpyxl ref 正则，`validate_excel_file` 对原始文件返回 False；该函数不在比对主链路上。

## Requirements

- **R1 读取修复**：`read_single_sheet_from_excel` 在只读模式下不信任 `<dimension>` 声明，按实际数据范围读取。效果：`LB` 读出 5 数据行 × 40 列（TM 参数下行数 = 总行数减表头/锚点行），`FP`、`DM`、`IE` 等全部真值。
- **R2 新建项目空白**：`openNewConfigDialog({ blank: true })` 打开弹窗时先重置 `config`（`emptyConfig()`）并清空 old/new sheets 扫描结果；取消时还原全部内容（含 sheets）。`saveConfigWithPrompt` / `autoSaveBeforeStart` 路径不受影响（无参调用保持现状）。
- **R3 任务按项目分桶**：每个项目名独立保存 jobId/status/progress/logLines/outputPath/outputName/error；切换项目时展示该桶内容（没有则为 idle）；不轮询非当前项目；下载/导出日志始终针对当前项目。
- **R4 触发器**：
  - `selectConfig(name)` / `saveConfig` 成功后 → 激活 `name` 桶。
  - `clearSelectedConfig()` → 丢弃旧桶激活（如删除当前项目后）。
  - 删除项目（`removeConfig`）→ 丢弃该桶。
  - 项目改名 → 桶随之迁移（`renameJob`）。
  - 退出登录 → 全量清空。
- **R5 前端 `logout()` 改用 `resetAllJobs()`** 代替原先 `job.reset()`。

## Acceptance Criteria

- [ ] 新增 `tests/test_excel_header_utils.py`：构造「维度声明 A1 但实际多行多列」的工作簿，`read_single_sheet_from_excel` 返回完整数据（行数 = 实际总行数 − 表头行，列数 = 实际列数）。
- [ ] 上述测试在修复前失败、修复后通过（回归锁定）。
- [ ] 维度正确的普通工作簿读取结果与修复前一致；真正空表仍返回空 DataFrame（未被误改为非空）。
- [ ] 现有 `pytest` 全量通过（含 `test_xlsx_filter_cleaner.py` 筛选器清理与 `test_processing_control.py` 中断传播）。
- [ ] 新增 vitest：新建项目弹窗（blank 模式）打开后 `config` 的文件与参数为空；取消后完整还原（含 old/new sheets）。
- [ ] 新增 vitest：项目 A 完成任务 → 激活 B → 状态为 idle、无 jobId；切回 A → 恢复 A 的 jobId 与日志；`download` 请求打到当前项目的 jobId；`dropJob`/`renameJob` 生效。
- [ ] 真实文件端到端：旧 `EXCEL_ZZ-TEST_20260819090012537.xlsx` vs 新 `..._34925.xlsx` + TM 模板（锚点行 2 / 表头行 1，排除 Code_List、DOMAIN_NAME）比对，日志不再出现成片「均为空」，报告对应 Sheet 有数据行与高亮。
- [ ] 手工 UI 验证：新建项目后「比对文件」显示「未选择文件」；项目 A 跑完切到 B 无下载按钮，切回 A 仍可下载 A 的报告/日志。

## Out of Scope

- 修改 `xlsx_filter_cleaner.py` 筛选器清理逻辑（已验证正常）。
- 刷新/重启后恢复任务状态（任务仅存内存 30 分钟，`job_manager.py:26`；刷新本就显示 idle，无错误内容）。
- `validate_excel_file` 对 `autoFilter ref="1:1"` 误判的修复（不在比对链路上，另记为待办）。

## Risks / 风险

- `reset_dimensions()` 后行宽可能不齐：现有代码已按 `max(len(row))` 补 `Unnamed_i` 列名、DataFrame 以 NaN 补齐（已实测），无需额外处理。
- `useJob` 工厂改单例会影响 `App.vue` 的 `job.status.value` 引用方式（computed 解包不变），需跑现有 vitest 与 lint/build 确认无回归。
- 轮询竞态：`_poll()` 在途时用户切换项目 → 显式捕获当时的 `activeKey`，响应写回对应的桶，不写串。

## 参考（文件:行）

- `src/backend/domain/excel_header_utils.py:36`（read_only 打开）、`:163-178`（列数补齐逻辑）
- `src/backend/domain/data_comparison.py:237`（均为空日志）
- `frontend/src/components/ConfigSidebar.vue:50`（createNew）
- `frontend/src/composables/useConfigState.js`（openNewConfigDialog/cancel/selectConfig/clearSelectedConfig/rememberConfig）
- `frontend/src/composables/useJob.js`（单例任务状态）
- `frontend/src/composables/useSheets.js:32`（restoreSheetsFromConfig）
- `frontend/src/App.vue:23,101`（useJob 实例化 / logout）
- `frontend/src/components/NewConfigDialog.vue:31`（导入模板 applyDocument preserveFiles）
- `src/backend/application/job_manager.py:26`（任务保留 30 分钟）
- `src/frontend/web_api.py:672`（下载归属校验）
