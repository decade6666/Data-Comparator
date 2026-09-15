# 修复关浏览器后比对任务无法接管

## Goal

用户在比对进行到一半时关闭浏览器，重新打开后前端丢失任务状态（无 job_id、UI 显示 idle），
但后端任务仍在运行并占用 `_user_active` 槽位，导致每次提交都被 409 挡住、无法查看进度、
无法取消。本任务让前端重开后能**自动接管**正在跑的任务（恢复进度/日志/停止/下载），
并提供不依赖 job_id 的僵尸兜底，消除「永久 409 只能重启服务」的死角。

本任务兑现 2026-09-15 锚点爆炸事故 PRD 记为 P1 的遗留项
（`.trellis/tasks/archive/2026-09/09-15-anchor-explosion/prd.md:41`：「`GET /api/jobs/current`
与前端刷新恢复」）。

## Requirements

### R1 后端活跃任务查询

- 新增 `GET /api/jobs/active`：返回当前登录用户占用槽位的任务快照
  （job_id、config_name、status、progress、日志增量、output_path、error）。
- 无活跃任务时返回 `active: false`；槽位映射悬空（job 已不在注册表）时返回
  `stale: true` 供前端提示。
- 响应只含本人任务（入口即 `_user_active[current_user.id]`，天然隔离）。
- 路由必须声明在 `GET /api/jobs/{job_id}` 之前，避免 `active` 被吃成 job_id。

### R2 后端无 id 取消（僵尸兜底）

- 新增 `POST /api/jobs/active/cancel`：取消当前用户的活跃任务，不需要 job_id。
- 正常任务：置位 stop_flag，槽位由 `_finalize_job` 正常释放。
- 悬空映射：直接释放 `_user_active` 槽位（没有线程会再来 finalize）。
- 无活跃任务时返回 404。
- **不得**修改 `JobManager.submit()` 的 fail-closed 语义：悬空映射只能由用户显式清除。

### R3 前端任务接管

- `useJob` 新增 `adoptJob(name, body)`：把后端快照灌进指定项目桶并恢复轮询；
  接管时以 `since=0` 拉全量日志（保证内存 Blob 日志下载兜底可用）。
- 新增 `cancelActive()`：调 `POST /api/jobs/active/cancel`。
- 登录后页面加载时调用 `restoreActiveJob`：
  - 有活跃任务 → 自动 `selectConfig` 切到任务所属项目并 `adoptJob`；
  - 项目已被删除/改名 → 任务仍恢复到该名称的桶；
  - `stale` → 自动清除残留占位并提示（stale 时不显示停止按钮，提示无法操作；
    第二轮改为自动清除）；
  - 无活跃任务 → 回落现有 `restoreLastConfig` 逻辑。
- 接管后 ActionBar 应显示「停止比对」（running 态），进度条续走，完成触发自动下载。

### R4 前端 409 兜底

- `startCompare` 捕获 409 时弹确认框：「检测到有比对任务正在运行或残留，是否取消它并
  重新开始？」确认后调 `cancelActive()` 再重新提交。
- `useApi` 抛出的错误对象需携带 HTTP 状态码（若缺失则补充），不做字符串匹配。

## Acceptance Criteria

- [ ] AC1 比对进行中关闭浏览器再打开：自动切到任务所属项目，进度从当前百分比继续、
      日志接上、「停止比对」可点、任务完成自动下载报告与日志。
      （代码与单测已覆盖，端到端需真实浏览器 + 真实比对文件手动验证）
- [x] AC2 `GET /api/jobs/active` 返回 200 JSON（不得落进 `/api/jobs/{job_id}` 返回 404）；
      无任务时 `active: false`。（test_active_job_endpoint_none / test_active_job_endpoint_returns_running_job）
- [x] AC3 `POST /api/jobs/active/cancel` 能取消运行中任务并释放槽位，取消后可立即提交
      新比对；无任务时 404。（test_active_job_cancel_endpoint）
- [x] AC4 悬空映射回归：手工删除 `_jobs` 条目后 `submit()` 仍 409（fail-closed 不变），
      调 `cancel_active_job` 后 `submit()` 成功。（test_dangling_user_active_fail_closed_then_active_cancel_releases）
- [x] AC5 多用户隔离：用户 B 查不到用户 A 的活跃任务，B 的 active/cancel 不影响 A。
      （test_active_job_snapshot_requires_owner / test_cancel_active_job_scoped_to_user）
- [x] AC6 前端单测覆盖 `adoptJob` 与 `restoreActiveJob`（含 stale 分支）。
      （useJob.adopt.spec.js / useConfigState.restoreActiveJob.spec.js，10 用例）
- [x] AC7 后端单测覆盖 R1/R2（含路由顺序回归）。后端 316 通过、前端 90 通过。
- [x] AC8 模块 CLAUDE.md（frontend、backend/application、根）同步更新并记 changelog。

## Non-Goals

- 不做心跳/超时自动杀任务：关浏览器去喝咖啡是正常操作，长比对本来要跑几十分钟，
  自动杀会毁掉正在进行的工作；槽位释放仍以任务真实结束为准。
- 不改 `submit()` fail-closed：悬空映射只能由用户显式 `active/cancel` 清除。
- 不做服务重启后的在途任务恢复：`JobManager` 进程内单例，重启丢任务是既有已接受降级
  （`.trellis/tasks/archive/2026-08/08-23-fix-empty-read-and-project-state/design.md:84`）。
- 接管到已终态任务不触发自动下载（`_poll` 跳过终态条目），用户手动点下载即可；
  实际窗口极窄（`_user_active` 在 finalize 时即释放）。

## Notes

- 根因与代码路径追踪见规划文件 `/home/weiq/.claude/plans/glittery-greeting-cake.md`（已批准）。
