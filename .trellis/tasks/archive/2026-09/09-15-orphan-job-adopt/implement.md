# 执行计划 · 修复关浏览器后比对任务无法接管

前置：读 `.trellis/tasks/09-15-orphan-job-adopt/prd.md` 与 `design.md`。

## 步骤

### 1. 后端 JobManager（src/backend/application/job_manager.py）

- [ ] 新增 `active_job_snapshot(self, user_id, since=0)`（design.md §后端 1a）
- [ ] 新增 `cancel_active_job(self, user_id)`（design.md §后端 1b）
- 两个方法放 `cancel_job`（:256）附近；docstring 说明悬空语义与 fail-closed 不变。

### 2. Web 端点（src/frontend/web_api.py）

- [ ] 新增 `ActiveJobResponse` Pydantic 模型（放 `JobStatusResponse` 旁）
- [ ] 新增 `GET /api/jobs/active` + `POST /api/jobs/active/cancel`，
      **声明在 `get_job_status`（:663）之前**

### 3. 前端 useJob（frontend/src/composables/useJob.js）

- [ ] 新增 `adoptJob(name, body)`：灌桶 + `_ensurePolling()`
- [ ] 新增 `cancelActive()`
- [ ] 两者加入 `useJob()` 返回对象；`adoptJob` 入顶层 `export {}`（:215）

### 4. 前端启动接管（frontend/src/composables/useConfigState.js + ConfigSidebar.vue）

- [ ] `useConfigState.js` 新增 `restoreActiveJob(availableNames)`：先 `selectConfig`
      再 `adoptJob`；stale 返回 `'stale'`；无任务返回 false
- [ ] `ConfigSidebar.vue` onMounted：`refresh()` 后先接管、失败回落
      `restoreLastConfig`；`GET /api/jobs/active` 404（新前端+老后端）时静默回落
- [ ] `App.vue` `startCompare` 409 → `ElMessageBox.confirm` → `cancelActive()` → 重提交；
      先检查 `useApi.js` 抛错对象，缺 `status` 字段则补

### 5. 后端测试

- [ ] `tests/test_job_manager.py`：`active_job_snapshot` 带 config_name；
      `cancel_active_job` 置位 stop_flag；悬空回归（删 `_jobs` 条目 → submit 仍 409 →
      cancel_active_job → submit 成功）
- [ ] `tests/test_web_api_jobs.py`：无任务 `active:false`；运行中返回
      job_id/config_name/log_cursor；路由顺序回归（`/api/jobs/active` 非 404）；
      active/cancel 无任务 404
- [ ] `tests/test_job_manager_user_isolation.py`：B 查不到 A 的任务；B 的 cancel 不影响 A

### 6. 前端测试（frontend/src/__tests__/）

- [ ] 新建 `useJob.adopt.spec.js`：adoptJob 后状态/进度/logCursor、轮询启动、cancel 可用
- [ ] 新建 `useConfigState.restoreActiveJob.spec.js`：接管切项目 / 无任务回落 /
      stale 不切

### 7. 质量检查

- [ ] `pytest tests/test_job_manager.py tests/test_web_api_jobs.py tests/test_job_manager_user_isolation.py`
      （注意：venv 若缺 httpx2 导致 conftest 崩，按记忆 pytest-httpx2-missing.md 规避并如实报告未跑项）
- [ ] `cd frontend && npx vitest run`
- [ ] `black --check` / `isort --check` 于改动 py 文件（行宽 88，pyproject 配置）

### 8. 文档与收尾

- [ ] `src/frontend/CLAUDE.md`：接口清单 + changelog
- [ ] `src/backend/application/CLAUDE.md`：JobManager 新方法 + changelog
- [ ] 根 `CLAUDE.md`：changelog（注明兑现 09-15 事故 PRD 的 P1 遗留项）
- [ ] Trellis 3.3 spec update / 3.4 commit（提交前看 diff，不 force push）

## 回滚点

- 步骤 1-2（后端）与 3-4（前端）可独立回滚：前端对端点 404 有静默回落。
- 测试失败先回滚对应侧，不带病提交。

## 验证命令

```bash
pytest tests/test_job_manager.py tests/test_web_api_jobs.py tests/test_job_manager_user_isolation.py -v --tb=short
cd frontend && npx vitest run
```
