# Web UI 六项优化 — 执行计划

实现顺序：`1 → 3 → 2 → 4 → 6 → 5`（3 的 `api.download` 被 4 复用；2 的新字段被 4 剔除；5 纯文本放最后避免冲突）。

## Checklist

### 1. 去掉上传/扫描进度条
- [ ] `frontend/src/composables/useSheets.js`：删 `scanProgress` computed、`completed` ref 及所有赋值；return 移除 `scanProgress`
- [ ] `frontend/src/components/ProgressPanel.vue`：删 `scanProgress` prop；`displayProgress` 简化（idle → 0）；保留 `scanning` 用于文字与禁用
- [ ] `frontend/src/App.vue`：解构与 `:scan-progress` 绑定移除

### 3. 修复下载 "未授权"
- [ ] `frontend/src/composables/useApi.js`：新增 `parseFilenameFromCD` + `download(path, fallbackFilename)`，导出到 `api`
- [ ] `frontend/src/composables/useJob.js`：`download()` 改用 `api.download`
- [ ] `frontend/src/components/ConfigSidebar.vue`：`exportCurrent()` 改用 `api.download`（后续 item 4 包 confirm）

### 2. 表单扫描持久化
- [ ] `src/shared/contracts.py`：`ParameterDocument` 增 `old_file_sheets` / `new_file_sheets: List[str]`
- [ ] `frontend/src/composables/useConfig.js`：`emptyConfig()` 增字段；`FILE_STATE_KEYS` 增 key；`buildParameters()` 含字段；`buildJobPayload()` filter 剔除
- [ ] `frontend/src/composables/useSheets.js`：import `config`；`scanFile()` 写 config；`resetSheets()` 清 config；新增 `restoreSheetsFromConfig()`
- [ ] `frontend/src/composables/useConfigState.js`：`selectConfig()` 后调 `restoreSheetsFromConfig()`；`clearSelectedConfig()` 调 `resetSheets()`

### 4. 导出清理 + 提醒
- [ ] `src/frontend/web_api.py`：`_EXPORT_STRIP_FIELDS` 六字段剔除；`FileResponse` 加 `background=BackgroundTask(os.unlink, ...)`；import `BackgroundTask`
- [ ] `src/frontend/routers/admin.py`：`_UPLOAD_FIELDS` 补两字段
- [ ] `frontend/src/components/ConfigSidebar.vue`：`exportCurrent()` 包 `ElMessageBox.confirm`
- [ ] `tests/test_web_api_configs.py`：新增 `test_export_strips_file_and_sheet_fields`

### 6. 设置弹窗
- [ ] `frontend/src/components/AdvancedSettingsDialog.vue`：`isAdmin` prop（隐藏线程数行）；底部两按钮行；`change-password` / `logout` emit
- [ ] `frontend/src/App.vue`：两 header 移除修改密码/退出登录按钮；admin header 补设置按钮 + 挂载 dialog（isAdmin=true）；非 admin dialog 补 props/events；`openPasswordFromSettings()`

### 5. 全局改名「配置」→「项目」
- [ ] `ConfigSidebar.vue` ~14 处、`NewConfigDialog.vue` 4 处、`CompareForm.vue` 1 处、`useConfigState.js` 1 处、`UserAdminView.vue` ~20 处、`App.vue` help ~12 处
- [ ] `web_api.py` 5 处 detail、`routers/admin.py` 3 处 detail
- [ ] 测试同步：`UserAdminView.spec.js`、`UserAdminView.recycle.spec.js` 断言字符串

## 验证命令

```bash
# 后端（仓库根）
python -m pytest tests/ -v --tb=short
# 前端
cd frontend && npx vitest run
```

## 审查门

- [ ] `git diff` 全量复查（不信任子代理报告）
- [ ] 后端 pytest 全绿
- [ ] 前端 vitest 全绿
- [ ] 浏览器手动验证（`npm run dev` + 登录）：上传→扫描→进度条归零；保存项目→刷新→表单还原；下载报告/导出项目带鉴权成功；设置弹窗两按钮；文案全部「项目」

## 回滚点

- 每完成一项（1/3/2/4/6/5）可独立提交，任何一项出问题可单独 revert。
