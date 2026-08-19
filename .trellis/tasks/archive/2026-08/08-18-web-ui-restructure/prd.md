# Web UI 优化：14 项界面重构

## Goal

根据试用反馈，对 Data-Comparator 的 Vue Web UI 进行一轮系统性 UX 改进，覆盖配置管理、比对操作流程、文件持久化、参数编辑与帮助文档 5 个方面共 14 项改动。

## Background

- 当前 UI 分支 `worktree-feat-web-ui` 已有 2 次提交 + 未提交的差量修改（icon-only 化、ProgressPanel 新增按钮等）。
- 技术栈：Vue 3 + Element Plus 2.13 + Vite / FastAPI 后端。
- 上传文件的索引仅在内存，服务重启或页面刷新后上传 ID 即失效。
- 帮助弹窗仅 17 行内容，远不及迁移前桌面版 help_dialog.py 的 5 节完整说明。

## Requirements

### R01 — 模板从配置列表移至新建弹窗

- 配置列表不再显示 `【模板】CIMS数据集` / `【模板】TM数据集`。
- 新建配置使用独立的 `el-dialog`（替代 `ElMessageBox.prompt`）。
- 弹窗左下角增加「导入模板」下拉按钮，点击后可选择 TM 或 CIMS 模板，模板内容通过 `GET /api/configs/{name}` 获取并 `applyDocument`，名称由用户另行输入。
- 无需修改后端；前端使用 `builtin_templates` 列表过滤即可。

### R02 — 配置管理操作栏精简

- 从配置管理操作栏删除「保存配置」按钮。
- 每个配置名称右侧常显「复制」和「删除」图标按钮（不随 hover 显隐）。
- 保留「新建」「导入」「导出」。

### R03 — 比对参数卡片底部增加保存 / 取消保存

- 在 CompareForm 比对参数 `.panel` 底部右下角添加「保存配置」和「取消保存」按钮。
- 取消保存 = 撤销未保存修改，回退到当前选中配置最近一次保存的快照；无选中配置时回退到 `emptyConfig()` 默认值。
- 脏状态追踪：使用 JSON.stringify 对比 `buildParameters()` 与 `savedSnapshot`。
- 状态管理逻辑抽到新 composable `useConfigState.js`，导出 `currentName`、`savedSnapshot`、`isDirty`、`saveConfig`、`revertConfig`、`autoSaveBeforeStart`。

### R04 — 删除「我的配置」文字

- 移除 `ConfigSidebar.vue:200` 的 `<div class="sidebar-title">我的配置</div>`。

### R05 — 配置名称悬停提示

- 给配置列表项添加 `:title="name"` 或 `el-tooltip`，鼠标悬停时显示完整配置名称。

### R06 — 删除顶部下载报告按钮

- 从 ActionBar / header 移除下载报告按钮。ActionBar 组件在 R07 后彻底无内容，删除该文件。

### R07 — 开始比对放入进度卡片

- ProgressPanel `.panel-header-actions` 中按序放置：开始比对、下载报告、下载日志。
- 开始比对：`v-if="!running"`, `:disabled="finished"`；停止比对：`v-else`, `:disabled="status==='cancelling'"`。
- 下载报告：`v-if="finished"`。
- 下载日志：`v-if="hasLogs"`。
- 新增 emit `'start'`，App.vue 将 start handler 连到 ProgressPanel。

### R08 — 开始 → 停止按钮切换

- 与 R07 合并实现：`v-if="!running"` 显示开始，`v-else` 显示停止。

### R09 — 完成后可再次运行

- `status === 'completed'` 时，开始比对按钮仍显示且保持可用。
- 点击后复用同一配置和上传文件重新提交任务。
- failed / cancelled 同样允许重试。

### R10 — 开始比对自动保存配置

- 点击开始比对时先调用 `autoSaveBeforeStart()`。
- 若 `currentName` 非空：静默保存到该名称。
- 若 `currentName` 为空：弹出新建配置弹窗让用户输入名称，保存后再启动。

### R11 — 上传文件服务端持久化

- **上传索引落盘**：`UploadStore` 新增 `_index.json`（位于 `get_app_temp_dir()/uploads/`），原子写入 `os.replace`，线程安全。
- **服务重启恢复**：`UploadStore.__init__` 从 `_index.json` 加载记录；文件实际不存在的条目自动丢弃。
- **配置引用免清理**：`cleanup()` 扫描 configs 目录下所有 `*.json`，提取 `old_file_upload_id` / `new_file_upload_id`，被引用的上传不受 2 小时 TTL 清理。
- **契约扩展**：`ParameterDocument` 新增 `old_file_upload_id: str` / `new_file_upload_id: str`（可选字段，向后兼容）。
- **前端恢复**：`applyDocument` 加载配置时恢复 upload ID 与文件名；`localStorage['dc_last_config']` 记住最近选中配置，页面刷新自动恢复。
- **新增端点**（可选）：`GET /api/uploads/{id}` 返回 `{exists, filename, size}`，用于刷新后校验文件是否仍存在。

### R12 — 合并删除数据改为开关

- 替换 `el-checkbox` 为 `el-switch`，开启标签"保留删除数据"，关闭标签"舍弃删除数据"。
- 字段 `merge_deleted_data` 极性不变（`true`=保留，已验证）。

### R13 — 结构设置与颜色设置同行

- 两个 `.panel` 包在 `.structure-color-row` flex 容器中，`flex: 1`。
- 使用 CSS `@container` 查询，内容区过窄时回退为纵向排列。

### R14 — 使用帮助完整化

- 移植迁移前 `help_dialog.py` 的 5 节完整内容（使用步骤 / 配置管理 / 参数设置 / 高级设置 / 日志记录）+ 页脚。
- 适配 Web 版实际操作（按钮位置、文件上传方式、日志下载方式等）。
- 项目地址改为 `https://github.com/decade6666/Data-Comparator`。
- 弹窗宽度 800px。

## Acceptance Criteria

1. 配置列表仅显示用户创建的配置，不含模板项。
2. 新建配置弹窗左下角有「导入模板」按钮，可选择 TM / CIMS。
3. 配置管理操作栏无「保存」按钮；每条配置右侧常显「复制」「删除」图标。
4. 比对参数卡片底部右下角有「保存配置」「取消保存」按钮，取消保存可回退到上次保存的快照。
5. 无「我的配置」文字。
6. 配置名称 hover 显示完整名称 tooltip。
7. 顶部无下载报告按钮；ActionBar.vue 已删除。
8. 进度卡片按序含开始比对、下载报告、下载日志三个按钮。
9. 比对进行中，开始比对变为停止比对。
10. 比对完成后开始比对按钮保持显示并可再次运行；failed / cancelled 同样可重试。
11. 开始比对前自动保存配置；无选中配置时弹窗输入名称。
12. 上传文件后保存配置，刷新页面加载该配置后无需重新上传即可开始比对。
13. 合并删除数据为 switch 样式，标签随状态切换。
14. 结构设置和颜色设置卡片在同一行。
15. 使用帮助弹窗内容完整（5 节），项目地址已更新。
16. 所有既有 pytest 测试通过；上传持久化新增测试覆盖。

## Out of Scope

- 前端测试框架（Vitest）引入。
- `sheet_order` 拖拽排序编辑器。
- 多 worker 部署并发安全（当前单进程约束）。
- CORS 配置。
- `GET /api/jobs/{id}/download` 路径安全校验（低风险，另行追踪）。

## Open Questions

（无）
