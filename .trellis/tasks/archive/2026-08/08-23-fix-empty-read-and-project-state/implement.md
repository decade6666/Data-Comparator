# 执行计划：修复空读取与项目状态串扰

## 实施顺序

1. **后端读取修复（TDD）**
   - 新建 `tests/test_excel_header_utils.py`：
     - `test_reads_full_data_when_dimension_declares_a1`：openpyxl 写 5 行 × 4 列表，字节级把 `xl/worksheets/sheet1.xml` 的 `<dimension ref="..."/>` 替换为 `<dimension ref="A1"/>`，读锚点行 2/表头行 1 → 断言 5 数据行 × 4 列真实值。
     - `test_normal_dimension_unchanged`：正常维度文件读取结果与值一致。
     - `test_truly_empty_sheet_stays_empty`：只有表头/锚点行的空表 → 空 DataFrame。
     - 先跑确认失败（RED）→ `excel_header_utils.py` 在 `ws = wb[sheet_name]` 后加：
       ```python
       # CRF-Editor 等生成器写死 <dimension ref="A1"/>，只读模式会据此把工作表
       # 截断成 1x1；清空缓存维度后按实际行流式推断（pandas 同样做法）。
       if hasattr(ws, "reset_dimensions"):
           ws.reset_dimensions()
       ```
     - 重跑确认通过（GREEN）。
2. **前端 useJob 分桶（TDD）**
   - 重写 `frontend/src/composables/useJob.js` 为模块级单例 + `entries`/`activeKey`/`current` computed，新增 `activateJob`/`dropJob`/`renameJob`/`resetAllJobs`；`_poll` 捕获 key 防竞态。
   - 新建 `frontend/src/__tests__/useJob.perConfig.spec.js`：mock `useApi`：
     - A 桶完成（注入 mock 响应）→ `activateJob('B')` → idle、jobId null、无日志；
     - `activateJob('A')` → 恢复 A 的 jobId/status/logLines；
     - `download()` → `api.download` 收到 A 的 jobId；
     - `dropJob('A')` / `renameJob('A','A2')` → 桶迁移/删除生效；
     - `resetAllJobs()` → 全部清空。
3. **前端新建空白**
   - `useConfigState.js`：`openNewConfigDialog(options)` 支持 `blank`；`cancelNewConfigDialog` 还原 sheets；`rememberConfig`/`saveConfig`/`selectConfig`/`clearSelectedConfig` 挂接 activate/drop。
   - `ConfigSidebar.vue`：`createNew` 传 `{ blank: true }`；`removeConfig` 加 `dropJob`；`editConfig` 改名成功后 `renameJob`。
   - `App.vue`：`logout()` 用 `resetAllJobs()`。
   - 新建 `frontend/src/__tests__/useConfigState.newConfig.spec.js`：
     - 设 config 有文件与参数 → `openNewConfigDialog({blank:true})` → 断言 `config` 为空、sheets 空；
     - `cancelNewConfigDialog()` → 断言完全还原（含 sheets）；
     - 无参 `openNewConfigDialog()` → 不清空；
     - `rememberConfig('A')` 触发 `activateJob`。
4. **验证**（见下）。
5. **提交**：任务分支 commit（按 git-security 规范审 diff、staged 指定文件）。
6. **PR**：推分支 → `gh pr create`（Summary / Test plan / TODO）→ 等审核合并后清理 worktree。

## 验证命令

```bash
pytest tests/test_excel_header_utils.py -v          # 新后端测试
pytest                                              # 全量回归（筛选器清理/中断传播等）
cd frontend && npm test && npm run lint && npm run build   # vitest + eslint + vite build
```

## 端到端验证（真实文件）

```bash
DATASET_COMPARATOR_WEB_HOST=0.0.0.0 DATASET_COMPARATOR_WEB_PORT=8888 python -m src.main_web
```

上传 `/root/github/CRF-Editor/image/EXCEL_ZZ-TEST_20260819090012537.xlsx`（旧）与
`EXCEL_ZZ-TEST_20260819090034925.xlsx`（新）→ 导入 TM 模板（锚点行 2 / 表头行 1）→ 开始比对。

- 日志无成片「在新旧版本中均为空」；通过标准：`LB`/`FP`/`DM`/`IE` 产生真实差异行。
- 手工 UI：新建项目 → 文件区「未选择文件」；A 跑完 → B 无下载按钮 → 切回 A 可下载 A 的报告/日志。

## 风险文件 / 回滚点

- `frontend/src/composables/useJob.js`（最大改动，单例迁移）——回滚点：迁移前先本地 `git stash`/commit。
- `frontend/src/composables/useConfigState.js`（弹窗语义变更，影响「保存项目」路径）——保持无参调用兼容。
- `src/backend/domain/excel_header_utils.py`（读取语义变更）——`hasattr` 防御 + 新测试锁定。

## start 前检查

- [ ] `prd.md`/`design.md`/`implement.md` 三者齐备（复杂任务）。
- [ ] prd 验收标准与 implement 步骤一一对应。
- [ ] 未在 `main` 上直接实现：进入 worktree 任务分支后再动代码。
