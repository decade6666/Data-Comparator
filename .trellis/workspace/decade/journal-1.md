# Journal - decade (Part 1)

> AI development session journal
> Started: 2026-05-22

---



## Session 1: Frontend/backend split

**Date**: 2026-05-24
**Task**: Frontend/backend split
**Branch**: `main`

### Summary

拆分核心逻辑为 backend/frontend/shared 模块，新增 Web 入口和测试覆盖，并接入 Trellis 项目工作流。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `36e9186` | (see git log) |
| `d6e0933` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: 同步 gitee 比对配置功能并清理桌面入口

**Date**: 2026-08-17
**Task**: 同步 gitee 比对配置功能并清理桌面入口
**Branch**: `worktree-feat-sync-gitee-and-remove-gui`

### Summary

移植 include_sheets/ignore_cols/sheet_ignore_cols/sheet_order 到新分层（契约/配置/领域/Web API + 集成测试），修复 psutil 可选依赖被强制导入问题，删除 src/gui、run.py、src/main.py、scripts/ 等桌面遗留（+887/-4951），重写 README 与模块文档，版本 1.7.0

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `c26212e` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: 完成 Web UI 重构与上传持久化

**Date**: 2026-08-18
**Task**: 完成 Web UI 重构与上传持久化
**Branch**: `worktree-feat-web-ui`

### Summary

完成配置管理、比对操作、帮助内容和删除数据开关的 Web UI 优化；新增上传索引持久化与恢复能力，补充后端测试并创建 PR #3。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `c1234a3` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: README 生产环境后台部署步骤

**Date**: 2026-08-19
**Task**: README 生产环境后台部署步骤
**Branch**: `worktree-docs-production-deploy`

### Summary

新增 README 生产环境后台部署章节（systemd 推荐 + nohup 备用）：运行账号/目录准备、Python venv 依赖安装、Web UI 前端构建、systemd 服务配置与运维命令、健康检查、单进程限制说明。纯文档变更，已推送分支并创建 PR #4。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `c6835d6` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: 用户隔离与认证 + 配置回收站（三期）

**Date**: 2026-08-19
**Task**: 用户隔离与认证 + 配置回收站（三期）
**Branch**: `main`

### Summary

JWT 认证与按用户数据隔离；管理员用户管理视图（改名/硬删/批量配置操作）；配置回收站（软删/恢复/孤儿恢复/自动清理策略）复刻 CRF-Editor；182 后端测试 + 12 前端测试通过，浏览器 E2E 全链路验证

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `25267ef` | (see git log) |
| `f50e3ad` | (see git log) |
| `f633682` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete

## 2026-08-20 — Web UI 六项优化（feat/web-ui-optimizations → PR #6）

- 任务：08-19-web-ui-optimizations，worktree /tmp/dc-ui-optimizations 已提交（80b265d），PR 已开。
- 六项：进度条归零 / 表单扫描持久化到服务器项目文档 / 下载 fetch+blob 带鉴权修复 401 / 导出剔除文件字段+弹窗提醒+修临时文件泄漏 / 配置→项目全面改名 / 修改密码·退出登录移入设置弹窗。
- 关键坑：esbuild 具名导入只认可模块顶层具名导出，`useConfigState` 从 `useSheets` 具名导入函数导致生产构建失败（vitest 不报）→ 补顶层 `export { resetSheets, restoreSheetsFromConfig }`。
- 测试：后端 183 过（含新 test_export_strips_file_and_sheet_fields），前端 12 过，生产构建通过，浏览器 E2E 全验证。


## Session 6: Web UI 六项优化部署 + 设置弹窗修复 + 默认端口 8888 对齐

**Date**: 2026-08-20
**Task**: Web UI 六项优化部署 + 设置弹窗修复 + 默认端口 8888 对齐
**Branch**: `main`

### Summary

六项 UI 优化（进度条/表单持久化/下载鉴权/导出清理/项目改名/设置弹窗）经 PR #6 合并并部署到 8888；修复退出登录后重登自动弹出设置弹窗，高级设置改名设置；默认端口统一 8888 并同步文档

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `a291a35` | (see git log) |
| `3e33e6e` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: 项目编辑：改名 + 导入模板覆盖参数

**Date**: 2026-08-20
**Task**: 项目编辑：改名 + 导入模板覆盖参数
**Branch**: `main`

### Summary

项目列表新增编辑按钮：可改名（后端 rename 端点）与导入内置模板覆盖参数；修复编辑前未加载参数导致保存丢失的问题；E2E 验证改名/模板覆盖/取消/重名冲突，185 pytest + 15 vitest 全绿，已部署生产 8888

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `b298e58` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: 重写 xlsx 筛选器清理

**Date**: 2026-08-20
**Task**: 重写 xlsx 筛选器清理
**Branch**: `worktree-xlsx-filter-cleaner`

### Summary

移除 Linux 不可用的 pywin32 和会破坏命名空间的 ElementTree 重打包路径，新增保留 XML/ZIP 元数据的字节级筛选器清理；242 项测试通过，总覆盖率 81%，新增清理模块 98%。

### Main Changes

- Detailed change bullets were not supplied; see the summary above.

### Git Commits

| Hash | Message |
|------|---------|
| `dea439d` | (see git log) |

### Testing

- Validation was not recorded for this session.

### Status

[OK] **Completed**

### Next Steps

- None - task complete
