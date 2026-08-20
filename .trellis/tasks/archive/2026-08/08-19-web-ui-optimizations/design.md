# Web UI 六项优化 — 技术设计

## 架构约束

- 无 Pinia：共享状态 = composables 模块级 `ref`（`useSheets.js`、`useConfig.js`、`useConfigState.js`）。
- API 客户端为手写 fetch 封装 `useApi.js`：`authHeaders()` 从 `localStorage['dc_token']` 读 Bearer token；处理 `X-Refreshed-Token` 滑动续期与 401 清会话。
- 配置持久化：`PUT /api/configs/{name}` 直接透传 `Dict[str, Any]` 存 JSON（`JsonParameterRepository`），无 schema 校验 → 新增字段零后端改动即可随项目保存。
- `CompareRequest` (`web_api.py:228`) 为 `model_config = {"extra": "forbid"}` → 前端任务提交 payload 不能带未声明字段。
- 认证：`get_current_user` 只认 `Authorization: Bearer` header（`OAuth2PasswordBearer`），无 cookie/query-token 兜底。

## 数据流

### 2. 表单扫描持久化

```
scanFile(uploadId, kind) ── GET /api/sheets ──> body.sheets
   │  写 useSheets refs (oldSheets/newSheets)
   └─> 写 config.old_file_sheets / config.new_file_sheets (reactive)
        │
        ├─ 保存: buildParameters() 含两字段 ── PUT /api/configs/{name} ──> 服务器 JSON
        └─ 提交: buildJobPayload() filter 掉两字段 (extra: forbid)
刷新:
restoreLastConfig ─> selectConfig ─> loadConfig ─> applyDocument(doc) [config 恢复两字段]
        └─> restoreSheetsFromConfig() [config → useSheets refs]
```

### 3/4. 鉴权下载 + 导出清理

```
api.download(path, fallback) [useApi.js, 新增]
   └─> request('GET', path)  ← 复用现有鉴权/续期/401 逻辑
   └─> response.blob() → Content-Disposition 解析文件名 → <a download> → revokeObjectURL

export_config [web_api.py] ← 序列化前剔除 _EXPORT_STRIP_FIELDS 六字段
   └─> FileResponse(..., background=BackgroundTask(os.unlink, tmp_path)) ← 修临时文件泄漏
```

## 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 表单字段命名 | `old_file_sheets` / `new_file_sheets` | 与 `old_file_upload_id` 命名一致；TypedDict total=False 兼容旧配置 |
| 导出剔除位置 | 后端 `export_config` | 产物永远干净，与调用方无关 |
| 导出是否剔除表单字段 | 是 | 表单名由文件推导，文件不导出则表单名无意义 |
| 管理员设置入口 | 两个 header 分支各自挂载 dialog（admin 传 `isAdmin=true`） | 避免统一 header 的大重构；admin 无比对 UI，隐藏线程数行 |
| 密码弹窗交互 | 点「修改密码」先关设置弹窗再开密码弹窗 | 一次只显示一个对话框（两 dialog 均 append-to-body） |
| `isDirty` 在扫描后翻转 | 接受 | 表示有未保存更改，语义正确；当前 UI 不展示 isDirty |
| 大文件 Blob 内存 | 接受 | 上传上限 200MB，报告通常更小 |

## 兼容性

- 旧配置 JSON 无新字段 → `applyDocument` 走默认 `[]`，向后兼容。
- `_UPLOAD_FIELDS` (admin.py) 补两字段 → 管理员批量转移/复制项目时也清理表单引用。
- API 路由/payload key/JS 符号/localStorage key 全部保持不变。

## 回滚

- 全部改动为前端文件 + 3 个后端文件；回滚 = 还原该分支提交，无数据迁移。
