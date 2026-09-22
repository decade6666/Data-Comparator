# 技术设计 · 修复关浏览器后比对任务无法接管

## 现状与根因

| 侧 | 事实 | 位置 |
|---|---|---|
| 后端 | `_user_active: Dict[int, str]` 每用户 1 槽位，仅在 `_finalize_job` 释放 | `src/backend/application/job_manager.py:102,428-430` |
| 后端 | 比对跑在 `daemon=True` 线程，与 HTTP 连接解耦，无心跳/无 SSE/轮询停止不取消 | `job_manager.py:193-199` |
| 后端 | `submit()` fail-closed：映射指向的 job 缺失视为占用，抛 409 | `job_manager.py:168-180` |
| Web | 只有 `GET /api/jobs/{job_id}`，无「查我的活跃任务」端点 | `src/frontend/web_api.py:663` |
| 前端 | 任务状态为模块级内存 `reactive({})`，无持久化；`jobId` 仅 `submit()` 赋值 | `frontend/src/composables/useJob.js:22,111-120` |

关浏览器 → 后端照跑、槽位照占；前端状态归零 → UI idle 但提交 409、无法取消。

## 方案总览

让前端重开后**接管**（adopt）在跑任务，而不是杀掉它；另给一条不依赖 job_id 的显式兜底。

## 后端

### JobManager 新增方法（`src/backend/application/job_manager.py`）

```python
def active_job_snapshot(self, user_id: int, since: int = 0) -> Optional[dict]:
```
- 复用 `snapshot()`（:209-226）拼装，额外补 `config_name` 与 `stale` 标记。
- 线程安全沿用现有约定：`self._lock` 保护 `_jobs`/`_user_active`；`job.lock` 保护
  `JobState` 字段（`snapshot()` 内部已处理）。
- 悬空映射（`_user_active` 有值、`_jobs` 无对应 job）返回 `{"job_id": ..., "stale": True}`
  ——submit 会 fail closed，必须让前端知道并引导用户显式清除。

```python
def cancel_active_job(self, user_id: int) -> Optional[str]:
```
- 悬空映射：在 `self._lock` 内 `del self._user_active[user_id]` 后返回 job_id。
  安全性依据：`_finalize_job`（:428-430）删除前有 `== job_id` 等值判断，不会误删
  后续新任务的映射；且悬空意味着没有任何线程会再来 finalize 这条映射。
- 正常任务：锁外 `job.stop_flag.set()`，槽位照常由 `_finalize_job` 释放（与
  `cancel_job` :256-267 同型）。
- 不改 `submit()` fail-closed（:171-172 注释是有意设计：自动自愈不安全）。

### Web 端点（`src/frontend/web_api.py`）

- `ActiveJobResponse(BaseModel)`：`active/stale/job_id/config_name/status/
  progress_percent/progress_message/log_lines/log_cursor/output_path/error`。
- `GET /api/jobs/active` 与 `POST /api/jobs/active/cancel`，**必须声明在
  `get_job_status`（:663）之前**——FastAPI 按声明顺序匹配，`{job_id}` 会吞掉 `active`。
- 隔离性：入口即 `_user_active[current_user.id]`，无需额外归属校验。

## 前端

### useJob（`frontend/src/composables/useJob.js`）

```js
function adoptJob(name, body) { /* 灌桶 + _ensurePolling() */ }
async function cancelActive() { await api.post('/jobs/active/cancel') }
```
- `adoptJob` 用 `since=0` 的全量日志（后端 `job.log_lines` 全在内存，一次拉回使
  `downloadLogsFor` 的内存 Blob 兜底拿到完整日志；代价单次几百 KB，可接受）。
- `logCursor` 取 `body.log_cursor`，续接增量轮询。
- 两者加入 `useJob()` 返回对象；`adoptJob` 另入顶层 `export {}`（:215），
  供 `useConfigState.js` 与 `activateJob`/`dropJob` 同样方式引入。

### 启动接管（`frontend/src/composables/useConfigState.js` + `ConfigSidebar.vue`）

```js
export async function restoreActiveJob(availableNames) → true | false | 'stale'
```
- 顺序关键：先 `selectConfig(name)`（内部 `rememberConfig` → `activateJob` 设
  activeKey），**再** `adoptJob` 填桶；反过来 `adoptJob` 的内容会被 `selectConfig`
  路径覆盖（`selectConfig` 不清桶，`activateJob` 只切 key，所以先切再灌是安全的）。
- 项目已删/改名：`activateJob(name)` 直接建空桶再灌，仍能看到进度。
- 调用点选 `ConfigSidebar.vue` 的 `onMounted`（:161-169）而非 `App.vue`：该组件只在
  `isAuthenticated` 分支挂载，token 必然就绪；且排在 `refresh()` 之后（需先有配置列表
  才能 `selectConfig`）。接管优先于 `restoreLastConfig`。

### 409 兜底（`frontend/src/App.vue` `startCompare` :62-74）

- 先确认 `useApi.js` 抛错对象是否带 HTTP status；缺则补 `err.status`（不做字符串匹配）。
- 第二轮增强「先接管后询问」：409 → `adoptActiveJob(names)`（新增导出，返回
  `true`/`'stale'`/`'none'`/`'unavailable'`；`restoreActiveJob` 重构为它的封装）：
  - `true` → 提示已切换到进行中的比对并 return（用户要的「恢复显示之前的进度」）；
  - `'stale'` → `cancelActive()` + 重新提交（占位无数据可恢复，直接清除）；
  - `'none'` → 409 与查询之间的竞态（任务刚结束），直接重新提交；
  - `'unavailable'`（老后端 404）→ 才落 `ElMessageBox.confirm` 取消确认框。
- `ConfigSidebar` 页面加载的 `stale` 分支同样自动 `cancelActive()` 清除占位
  （stale 时不显示停止按钮，「点停止清除」的提示无法操作）。

## 数据流（接管路径）

```
页面加载 → ConfigSidebar.onMounted
  → refresh()（配置列表）
  → restoreActiveJob(userConfigs)
      → GET /api/jobs/active
      → active? selectConfig(config_name) → adoptJob(name, body)
  → useJob._poll 恢复 1s 轮询（jobId 已在桶里）
  → ActionBar running=true → 显示停止按钮
  → 终态 → setOnTerminal → 自动下载（照常）
```

## 兼容与风险

- 老前端 + 新后端：多出的端点无人调用，无影响。新前端 + 老后端：`GET /api/jobs/active`
  404 → `restoreActiveJob` 抛错 → 落入 catch → `ElMessage.error`。为平滑部署，
  catch 里 404 时静默回落 `restoreLastConfig`（见 implement.md 步骤 4 的处理）。
- `_user_active` 悬空释放与 `begin_user_guard`/`begin_project_rename`（:113-149）互不
  干扰：guard 检查的是 `_user_guarded`/`_renaming_users` 集合，不是 `_user_active`。
- `has_active_job()`（:151-153）语义不变。
