# design.md — 比对操作区重构 + 历史记录

## 架构与边界

```
用户请求 → web_api.py → JobManager（内存调度）→ run_comparison → 写报告 xlsx
                                          │
                                          └─ on_finished hook（job.lock 外）
                                                → comparison_history_service.record_job_finished
                                                      → 自开 Session 写 comparison_run 表
                                                      → 日志文件写 results/
```

新增模块：
- `src/backend/infrastructure/models/comparison_run.py` — New 表模型
- `src/backend/application/comparison_history_service.py` — 记录/查询/删除
- `src/frontend/routers/history.py` — 4 个历史端点（web_api.py 755/800 行，必须另起文件）

JobManager 对 DB 保持零认知：只持有一个 `on_finished: Callable[[JobState], None]` 回调（`__init__` 注入 + `set_finished_hook()`），由 `web_api.py` 在单例处接线。

## 数据流与契约

### 日志落盘（processing_service.py）
```python
def build_log_path(config_name, output_dir, now=None) -> str
    # {sanitize_output_name(config_name)}-比对日志-{YYYY-MM-DDTHH-MM-SS}.txt
def write_log_file(path, lines) -> Optional[str]
    # makedirs(exist_ok=True); utf-8/newline="\n"; lines 空 → None
```
JobManager 在 `_run_with_semaphore` 开头 `run_started = self._now()`，传 `now=run_started` 给 `run_comparison`（已支持 `now` 参数，comparison_runner.py:46），保证报告与日志时间戳一致。
锁纪律：在 `job.lock` 内 copy `job.log_lines`，锁外写文件（持锁 IO 会阻塞 snapshot → 卡死轮询）。

### comparison_run 表
| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | |
| user_id | Integer, index | 普通 Integer 不设 FK（database.py:33 开了 foreign_keys=ON，配 session.delete(user) 会抛异常；沿 RecycledConfig 先例） |
| job_id | String(32), index | |
| config_name | String(500), index | 项目仅以名字标识 |
| status | String(20) | completed / failed / cancelled |
| report_filename | String(500), null | **只存 basename** |
| log_filename | String(500), null | **只存 basename** |
| report_size_bytes | Integer, default 0 | |
| parameters_json | Text | `ensure_ascii=False` |
| error | Text, null | |
| started_at | DateTime, null | |
| finished_at | DateTime, index | |

落库前剥离 `old_file_upload_id / new_file_upload_id / old_file_path / new_file_path / output_directory`（照 `_UPLOAD_FIELDS`／`_EXPORT_STRIP_FIELDS` 元组形态）。

### 已知事实：无迁移框架
`database.py:42-43` 用 `create_all`。新表自动创建，零风险；列加在已有表上才危险，本次不做。

### 回调触发点
四条终止路径收敛到一个 `_finish(job, status, error=None, output_path=None, log_path=None)`：
1. `stop_flag` 早退（job_manager.py:283-285）
2. `InterruptedError`（:314）
3. `Exception`（:316）
4. 成功分支（:318-322）

hook 在 `job.lock` 外调用，`try/except` 包住并 `log(...)`——记录失败不得翻转任务状态。

### 顺带修复：_user_active 泄漏（job_manager.py:281-285）
`job is None` / `stop_flag` 早退路径的 `return` 早于 `try:`（:304），清理 `_user_active` 的 `finally`（:323-327）永不执行 → 用户被永久 409。修复：把 status 检查后的清理也纳入 finally 范围。

### API（routers/history.py）
`APIRouter(prefix="/history", tags=["history"])`，`web_api.py` 里 `include_router(..., prefix="/api")`。

| 方法 | 路由 | 返回 |
|---|---|---|
| GET | `/history?config_name=&limit=` | `List[ComparisonRunSummary]` |
| GET | `/history/{run_id}` | `ComparisonRunDetail`（含 parameters） |
| GET | `/history/{run_id}/report` | FileResponse xlsx |
| GET | `/history/{run_id}/log` | FileResponse text/plain |

- `ComparisonRunSummary` 含 `report_available` / `log_available`（序列化时 os.path.isfile 实测）。
- 边界校验：`config_name: Optional[str] = Query(None, max_length=500)`；`limit: int = Query(20, ge=1, le=100)`。
- 查询永远 `WHERE user_id = current_user.id`，不信任客户端。
- 归属错误 → 404（不使用 403，对齐 web_api.py:678-679 防存在性泄露）；DB 有记录文件已不在 → 410；路径逃逸 → 400。

### 循环依赖解
`web_api._user_results_dir`（:69-72）→ 提到 `file_runtime.get_user_results_dir(user_id)`，web_api 改一行委托。

### 关联缺口
- `rename_config`（web_api.py:555-573）是存新名+删旧名：加 `UPDATE comparison_run SET config_name=:new WHERE user_id=:uid AND config_name=:old`。`copy_config` 不迁移（副本无历史）。
- `user_admin_service.py:153-158` 硬删用户：`session.delete(user)` 前先删 `comparison_run` 行。

## 兼容性

- 现有 `config.yaml` 无新增配置键 → 不改 `get_app_config`（本次无保留策略）。
- Python 3.8+：签名 `Optional[...]` 不带 `|` 语法。
- 现有测试兼容：13 处 `fake_run_comparison` 需补 `now=None`（见 implement.md）。
- MIME：xlsx 用 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`（照 download_job_result）；日志用 `text/plain; charset=utf-8`。

## 权衡

- 存储选新建表而非 sidecar JSON / 目录扫描：目录扫描表达不了参数与失败记录；sidecar 无原子写、列表扫描 O(n)；新建表零迁移、复用既有 Session 管线、RecycledConfig 有同量级先例。
- 自动下载钩在 App.vue watcher 而非 useJob._poll：策略属于应用层；`_poll` 保持纯数据同步、可单测。jobId 键幂等防重入；`flush: 'post'` 保证 outputName 先于 watcher 就绪。
- 多文件下载拦截：串行 + 报告优先 + 800ms 间隔；拦截时 ElMessage.warning 响亮降级。
- 历史弹窗用 el-table `type="expand"`（一行=一次运行，符合「下拉框」描述）；展开内容抽独立组件 `HistoryRunDetail.vue` 使 vitest 可绕开 el-table expand stub 难题。参数展示复用 `ParameterCard.vue`（加 readonly prop），不重写标签渲染。

## 运维与回滚

- 无 DB 迁移动作（新表 create_all 自动建）。
- 回滚：删掉 hook 接线（web_api.py 2 行）即回到无历史记录状态；历史行与磁盘文件保留，无害。
- 日志文件写入失败仅记录，不改变任务状态（hook 内 try/except）。
