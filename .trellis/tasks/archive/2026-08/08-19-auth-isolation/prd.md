# 用户隔离与认证（子任务）

## Goal

为 Data-Comparator 引入完整认证体系与按用户数据隔离（对齐 CRF-Editor 设计），使多人可各自安全使用工具，且支持多用户并发比对任务。

## Requirements

- R1.1 账号体系：SQLite + SQLAlchemy `User` 表（id/username/hashed_password/is_admin/auth_version/created_at）；pbkdf2_sha256 密码；PyJWT HS256 token（`sub/username/ver/exp`）；`auth_version` 变更使旧 token 失效；初始管理员由 `DATASET_COMPARATOR_ADMIN_USERNAME`/`DATASET_COMPARATOR_ADMIN_PASSWORD` 创建（缺一拒绝创建并打印指引）；`DATASET_COMPARATOR_SECRET_KEY` 缺失启动失败。
- R1.2 认证 API：`POST /api/auth/login`（登录）、`PUT /api/auth/me/password`（普通用户自助改密）、管理员 `GET/POST /api/users`、`PUT /api/users/{id}/password`、`PUT /api/users/{id}/status`（停用/启用）；`X-Refreshed-Token` 响应头滑动续期；`get_current_user`/`require_admin` 依赖。
- R1.3 数据隔离：`JsonParameterRepository(base_dir_getter=user_configs_dir)`、`UploadStore(base_dir=user_uploads_dir, config_dir_getter=…)`、输出结果落 `<appdata>/users/<uid>/results`；`web_api.py` 模块级单例改按请求构造；内置模板全局只读不落盘；旧全局 `temp/configs/` 迁移到初始管理员（仅一次，建管理员后、放行请求前）。
- R1.4 任务隔离与并发：`JobState` 加 `user_id`，任务查询/取消/下载归属校验非本人一律 404；每用户至多 1 个运行中任务 + 全局信号量 `DATASET_COMPARATOR_MAX_CONCURRENT_JOBS`（默认 2）超限排队；前端进度面板显示排队。
- R1.5 拆除 `_global_stop_flag`：`check_stop`/`check_stop_frequently` 只接受显式 `stop_flag`；6 处调用点补传参（`data_comparison.py:1033`、`excel_header_utils.py:70,115`、`file_runtime.py:38,94,101`）；删除 `set_global_stop_flag`；临时文件按任务目录隔离，清理只清本任务目录（修复并发互删 `_nofilter_*` 文件问题）。
- R1.6 下线 `/api/browse` 与路径式比对：删除 `GET /api/browse`、`get_browse_roots`、`tests/test_web_api_browse.py`；`CompareRequest`/`JobSubmitRequest` 只接受 upload_id；`path_security.is_safe_path`/`validate_asset_raw_path` 保留（静态资源用）。
- R1.7 前端认证：`useApi.js` 加 Bearer 头、401 清 token 跳登录、`X-Refreshed-Token` 就地续期；`useAuth.js`（localStorage `dc_token`）、`LoginView.vue`、`UserAdminDialog.vue`（管理员可见）；`App.vue` 未登录只渲染登录页；`useConfigState.js` 最近配置键按用户名分键。
- R1.8 用户管理界面对齐 CRF-Editor 设计（参考 `/tmp/CRF-Editor-ref/frontend/src/components/AdminView.vue`）：**管理员登录后直接渲染用户管理视图，不显示比对主界面**（比对界面仅普通用户使用）；标题栏 + 新增/刷新工具栏 + border stripe 表格；管理员用户名旁显示「管理员」标签；操作列图标化（改名/重置密码/停用启用，带 tooltip）；新增/改名共用一个表单弹窗（新增含初始密码、改名不含），重置密码用表单弹窗；无机构管理概念，不引入机构/部门字段。原「用户管理」header 按钮移除（admin 直接可见界面，无需入口）。
- R1.9 用户改名：新增 `PUT /api/users/{user_id}` body `{username}`（管理员专用）；`UserAdminService.rename_user` 校验用户名非空、保留管理员用户名不可改、重名 400、不存在 404；改名后旧 token 因 username 不匹配自动失效（401，无需 auth_version 变更）。前端操作列加「改名」图标按钮 + 表单弹窗。
- R1.10 用户硬删除：`DELETE /api/users/{user_id}` 替换停用/启用；删除流程 = 取消用户运行中任务（`JobManager.cancel_all_for_user`）→ 全部配置入回收站（`deleted_by_user_deletion=True`）→ 删除用户数据目录 → 硬删 User 行；保留管理员/自己不可删；已删用户 token 自动失效。移除 `PUT /users/{id}/status`。
- R1.11 管理员配置操作：`GET /api/admin/users/{id}/configs`、`POST /api/admin/configs/batch-copy` / `batch-move` / `batch-delete`（批量复制/转移/软删配置到其他用户）；复制/转移/恢复时清空 `old_file_upload_id`/`new_file_upload_id`/`old_file_path`/`new_file_path`（目标用户需重新上传）；重名加 ` (副本)`/` (恢复)` 后缀；config_name 路径穿越校验。
- R1.12 配置回收站：软删（普通用户与管理员删除配置均入回收站）→ `recycled_config` SQLite 表（存原属主快照/JSON 全文/估算大小/删除时间）；`GET/POST /api/admin/recycle-bin`、`POST .../restore`（原用户已删须指定目标用户）、`DELETE .../{id}` 彻底删除；清理策略完整复刻 CRF-Editor（age day/month/year + size MB/GB + min_retain_hours 只保护容量规则 + 预览与执行共享 build_cleanup_plan + config.yaml 持久化 + 后台 threading.Timer 巡检，`DATASET_COMPARATOR_DISABLE_BACKGROUND_JOBS` 可关）；前端用户管理视图含配置列表两步式批量操作、回收站弹窗、清理策略弹窗。

## Acceptance Criteria

- [ ] 未登录访问 API 一律 401（除 `/health`、`/api/auth/login`、静态资源）；前端未登录跳登录页。
- [ ] 错误口令 401；正确口令返回 token；token 过期 401；改密后旧 token 立即失效。
- [ ] 管理员可创建/重置密码/停用/启用用户；普通用户不能访问用户管理（403）。
- [ ] 两用户互不可见对方配置/上传/任务/结果；他人 job_id 一律 404。
- [ ] 两用户能同时运行各自比对任务且互不取消、中间文件互不删除。
- [ ] 同用户已有运行中任务时提交第二个任务被 409 拒绝（前端提示等待完成或取消）；跨用户并发超过 `MAX_CONCURRENT_JOBS` 时任务保持 pending 排队，前端进度面板显示排队；`MAX_CONCURRENT_JOBS=1` 时跨用户第二个任务排队等待。
- [ ] 无 `SECRET_KEY` 服务拒绝启动；无初始管理员配置时打印指引。
- [ ] 旧全局配置迁移到初始管理员，日志可查；内置模板无需落盘即可被读取且不可覆盖/删除。
- [ ] `/api/browse` 返回 404 或已移除；请求体不再接受 `old_file_path`/`new_file_path`。
- [ ] 前端登录/改密/用户管理流程可用；换账号不串配置（最近配置键按用户分）。
- [ ] 覆盖率 ≥80% 不下降；**豁免说明**：全量 `pytest --cov=src` 当前 75%，缺口全部来自存量领域文件（file_runtime.py 44%、data_comparison.py 55%、excel_utils.py 58%、web_api.py 78%），本轮新增文件均 ≥85%（admin.py 91%、recycle_bin_cleanup 96%、recycle_bin_service 92%、user_admin_service 94%、job_manager 93%、app_config 89%）；补足存量文件覆盖率超出本任务范围，另行处理。`tests/test_processing_control.py` 重写为显式传参。

## Out of Scope

- 找回密码、邮箱、SSO/OAuth、多角色（仅 admin/普通）。
- 上传文件迁移（旧全局 uploads 过期自然清理）。
- 数据库迁移框架（create_all 幂等建表）。

## Key Decisions

- 认证组件分层：基础设施（database/models）+ 应用（auth_service/user_admin_service）+ HTTP（dependencies/routers）。
- 归属校验一律 404 防 job_id 枚举。
- 并发默认 2，环境变量可调至 1 退回旧行为。
- SECRET_KEY 强制缺失即失败，不提供默认值。

## Risks

- `data_comparison.py`/`excel_header_utils.py`/`file_runtime.py` 签名变化：先补停止传播测试（TDD）再改。
- `web_api.py` 单例改按请求构造：`tests/test_web_api_*.py` 依赖多，改动后全量回归。
- 破坏性 API（browse/路径字段）：README、CLAUDE.md 变更记录、`.trellis/spec/backend/error-handling.md` 同步。
