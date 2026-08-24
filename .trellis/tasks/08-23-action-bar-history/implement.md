# implement.md — 比对操作区重构 + 历史记录

🔴 = 高风险文件 · 🟡 = 不改会破坏现有测试

## Phase 0 — 脚手架（无行为变化）

1. 🔴 `src/backend/infrastructure/models/comparison_run.py`（新建）+ 在 `models/__init__.py` 按现有 `# noqa: E402,F401` 模式注册。
2. `src/backend/infrastructure/file_runtime.py`：新增 `get_user_results_dir(user_id)`；`web_api._user_results_dir`（web_api.py:69-72）改为一行委托。
3. 扩展 `tests/test_import_smoke.py` → 跑 pytest 必须绿。

## Phase 1 — 日志落盘

4. `processing_service.py`：`build_log_path()` + `write_log_file()`（紧邻 `build_output_path` :73-81）。
5. 扩展 `tests/test_processing_service.py`（命名 + 配对不变式 + 空 lines → None + 自动建目录）→ 跑。
6. 🔴 `job_manager.py`：`run_started = self._now()` → `run_comparison(..., now=run_started)`；四条终止路径写日志（锁内 copy、锁外写）。
7. 🟡 13 处 fake 补 `now=None,`：`test_job_manager.py:46,82,109,142,171,196,225,251,279` · `test_job_manager_user_isolation.py:39` · `test_user_delete_with_recycle.py:74` · `test_web_api_jobs.py:50,94`（`test_web_api.py:30,49` 是 /api/compare 替身，不动）。
8. 扩展 `tests/test_job_manager.py`（失败任务也写日志 / 空日志不建文件）→ 跑。

## Phase 2 — 历史持久化

9. 新建 `src/backend/application/comparison_history_service.py`：`record_run` / `list_runs` / `get_run` / `delete_runs_for_user` / `record_job_finished`（自开 Session，照 `background_jobs._run_cleanup_once` :30-45；剥离上传字段与路径；只存 basename）。
10. 🔴 `job_manager.py`：`on_finished` hook + `set_finished_hook()`；`_finish` 扩为四参并收敛四条终止路径；**同一次编辑里修 `_user_active` 泄漏**（:281-285 早退路径纳入 finally 清理）。
11. `web_api.py`：2 行接线（:220 旁）+ 1 个 import。
12. 新建 `tests/test_comparison_history_service.py` → 跑。

## Phase 3 — API

13. 新建 `src/frontend/routers/history.py`（4 端点 + 4 模型）+ `include_router(prefix="/api")`（web_api.py:216-218 旁）。
14. `web_api.py:555-573` `rename_config`：迁移 `comparison_run.config_name`（copy 不迁移）。
15. 新建 `tests/test_web_api_history.py` + 扩展 `test_web_api_configs.py` → 跑。

## Phase 4 — 用户删除关联

16. `user_admin_service.py:153-158`：`session.delete(user)` 前删 `comparison_run` 行。
17. 扩展 `test_user_delete_with_recycle.py`（硬删用户连带清历史行 + fake 已补 now）→ 跑。

## Phase 5 — 前端重构

18. 新建 `frontend/src/components/ActionBar.vue`（按钮组 + 迁移 saveParameters/cancelSave + HistoryDialog 挂载 + scoped 样式 + 吸底）。
19. `ProgressPanel.vue`：删 `.panel-header-actions`（:50-91）、`running`/`finished`（:15-18）、`hasLogs` prop（:9）、全部 emits（:13）、图标 import（:3）。
20. `CompareForm.vue`：删 footer（:158-163）、`saveParameters`/`cancelSave`（:54-66）、相关 import（:3-4）。ESLint 会抓残留。
21. `App.vue`：删 4 个绑定（:204-207），挂 `<ActionBar>`（:209-213 之后）。
22. 🟡 `App.auth.spec.js:124-131` 加 `ActionBar` stub。
23. 新建 `ActionBar.spec.js` + `ProgressPanel.spec.js` → npm test。

## Phase 6 — 自动下载

24. 新建 `frontend/src/composables/useAutoDownload.js`（模块级 ref + localStorage `dc_auto_download`，照 useTheme.js）。
25. `AdvancedSettingsDialog.vue`：加 `<el-switch>`（+ prop/emit 经 App.vue）。
26. `App.vue`：`watch(job.status, …, { flush: 'post' })` + `triggerAutoDownload()`（jobId 幂等、串行 800ms、try/catch → ElMessage.warning）。当前任务日志改走 `GET /api/jobs/{id}/log`（后端镜像 /download + JobState 加 log_path），客户端 Blob 保留兜底。
27. 新建 `App.autoDownload.spec.js` → 跑。

## Phase 7 — 历史弹窗

28. 新建 `frontend/src/composables/formatDateTime.js`。
29. `ParameterCard.vue`：加 `readonly` prop（隐藏编辑按钮）。
30. 新建 `HistoryRunDetail.vue`（结构设置 / 比对参数 / 颜色设置三组，标签取自 CompareForm.CARDS 与 StructureRow）。
31. 新建 `HistoryDialog.vue`（el-table + type="expand" + 懒加载详情 + 刷新 + 空态）。
32. 新建 `HistoryDialog.spec.js` + `HistoryRunDetail.spec.js` + ParameterCard readonly 用例 → npm test 全绿。

## Phase 8 — 文档

33. 🔴 `App.vue` 帮助弹窗：:233-234、:243-244、:274-276 三处文案更新 + 新增历史记录/自动下载条目。
34. `CLAUDE.md` 变更记录表、`src/frontend/CLAUDE.md` 端点清单、`tests/CLAUDE.md`、`src/backend/application/CLAUDE.md`、`README.md:261-268`。

## 验证命令

```bash
pytest -v --tb=short --strict-markers
pytest --cov=src --cov-report=term-missing   # ≥80% 且不下降
black --check src tests && isort --check src tests
cd frontend && npm test && npm run build
# 人工：起服务后按计划「四、验证」清单走浏览器流程
```

## 风险点 / 回滚点

- `job_manager.py`：终止路径重构是行为核心，改完先跑 `test_job_manager.py` 全套；hook 触发次数「恰好一次」有专项断言。
- web_api.py 余量 45 行：只加 2 行接线，端点全部放新 router。
- 13 处 fake 修补是机械性但不可漏（漏一处 TypeError）。
- 前端重构后先 npm test 再 build；`App.auth.spec.js` 不补 ActionBar stub 现有套件必挂。
