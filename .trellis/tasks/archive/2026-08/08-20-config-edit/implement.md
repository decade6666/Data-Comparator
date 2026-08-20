# 实现清单：项目编辑（改名 + 导入模板覆盖参数）

## 设计要点

- **后端 rename 端点**：仅改名（保存到新名 + 删除旧名），校验顺序：新名非内置模板 → 源存在 → 目标不重名 → save + delete。
- **模板覆盖参数的持久化**：编辑弹窗中导入模板只改前端 `config`（`applyDocument(preserveFiles: true)` 已存在）。确认改名时前端先调 rename 端点，再调 `saveConfig(newName)` 把（可能被模板覆盖的）当前参数保存到新名，最后 `selectConfig(newName)`。未导入模板时 `saveConfig` 保存原参数，无害。
- **弹窗复用**：`NewConfigDialog` 增加编辑模式，通过 `editConfigVisible` 判定；可见性 = 新建或编辑任一打开；确认/取消按模式走不同 resolver；打开时备份 config、取消时恢复（沿用现有 `dialogBackup` 模式，编辑用独立 `editDialogBackup`）。
- 内置模板不出现在列表（`userConfigs` 已过滤），编辑按钮只对用户项目；后端仍加内置模板保护。

## 执行清单

### 后端

- [ ] `src/frontend/web_api.py`：新增 `POST /api/configs/{name}/rename`
  - body 复用 `CopyConfigRequest`（`new_name`）
  - `new_name in BUILTIN_TEMPLATES` → 400「不能覆盖内置模板」；`name in BUILTIN_TEMPLATES` → 400「不能修改内置模板」
  - 源不存在 → 404「项目不存在」；目标已存在 → 409「目标项目已存在」
  - `repository.save_document(new_name, document)` + `repository.delete_document(name)`，返回 `{"name": new_name, "renamed": True}`

- [ ] `tests/test_web_api_configs.py`：新增
  - `test_rename_config`：PUT 源 → rename → 新名 GET 等于原文档，旧名 404
  - `test_rename_config_errors`：目标已存在 409 / 源不存在 404 / 目标内置模板 400 / 源内置模板 400

### 前端

- [ ] `frontend/src/composables/useConfig.js`：新增 `renameConfig(name, newName)` → `api.post('/configs/{name}/rename', { new_name })`

- [ ] `frontend/src/composables/useConfigState.js`：
  - 新增 `editConfigVisible`、`editConfigName` refs，`editConfigResolver`、`editDialogBackup` 内部变量
  - `openEditConfigDialog(name)`：备份 config、记名、开弹窗、返回 Promise
  - `resolveEditConfigDialog(newName)`：关闭、resolve
  - `cancelEditConfigDialog()`：恢复 backup、关闭、resolve(null)

- [ ] `frontend/src/components/NewConfigDialog.vue`：编辑模式支持
  - `isEdit` computed（`editConfigVisible`）；`visible` computed（新建或编辑）
  - title / placeholder 按模式：「编辑项目」/「新建项目」；预填 `editConfigName`
  - confirm/cancel 按模式调对应 resolver

- [ ] `frontend/src/components/ConfigSidebar.vue`：
  - import `EditPen` 图标；每行复制按钮旁加编辑按钮（title/aria-label「编辑项目」）
  - `editConfig(name)`：`openEditConfigDialog` → 若新名不同则 `renameConfig` → `saveConfig(newName)` → `refresh()` → `selectConfig(newName)` → 成功提示（改名「已重命名项目」，仅模板「已保存」）

- [ ] `frontend/src/App.vue`：帮助文档「项目管理」增加「编辑：点击项目名称右侧的编辑按钮，可修改项目名称，并可导入模板覆盖当前参数。」

- [ ] 前端测试（轻量）：`frontend/src/__tests__/NewConfigDialog.spec.js` 或 useConfigState 测试：编辑模式预填名称、确认 resolve 新名、取消恢复 config

## 验证

```bash
cd /root/github/Data-Comparator && python -m pytest tests/ -v --tb=short
cd frontend && npx vitest run
```

- 浏览器 E2E（生产 8888）：新建临时项目 → 点编辑按钮 → 弹窗预填 → 改名 → 列表刷新选中新名；再编辑 → 导入模板 → 确认 → 重新加载验证参数已覆盖且文件引用保留 → 删除临时项目
- 部署：`cd frontend && npm run build` → `systemctl restart dataset-comparator`
