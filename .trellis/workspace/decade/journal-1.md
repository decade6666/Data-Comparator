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
