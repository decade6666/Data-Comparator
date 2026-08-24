# 设计：修复空读取与项目状态串扰

## 架构与边界

三个缺陷分别落在三层，改动互不依赖：

| 层 | 改动 | 边界 |
|---|---|---|
| 后端 domain | `excel_header_utils.py` 只读模式重置维度 | 只影响 `read_single_sheet_from_excel`；`xlsx_filter_cleaner.py`、`file_runtime.py` 不动 |
| 前端 composable | `useJob.js` 单例 + 按项目分桶 | 任务状态生命周期归属前端；后端 `/api/jobs/*` 契约不变 |
| 前端 composable/组件 | `useConfigState.js` + `ConfigSidebar.vue` + `App.vue` | 新建项目空白 + 任务桶触发器挂接 |

## 数据流与契约

### 1. 读取修复（R1）

```
load_workbook(path, read_only=True, data_only=True)
  → wb[sheet] → ws.reset_dimensions()   # 丢弃 <dimension ref="A1"/> 的声明
  → iter_rows(...) 按真实行流式读取
```

`reset_dimensions()` 对只读 worksheet 存在（openpyxl 3.x），`hasattr` 防御旧版本。pandas `OpenpyxlReader.get_sheet_data` 对只读工作表做同样调用，属既有标准做法。

### 2. 任务桶（R3）

```js
const entries = reactive({})   // configName -> entry
const activeKey = ref('')      // '' = 未命名项目
```

entry = `{ jobId, status, progress, progressMessage, logLines, logCursor, outputPath, outputName, error, pollTimer }`。

对外导出保持兼容：`useJob()` 返回 `{ status, progress, ... }`，其中 `status` 等是**模块级 computed ref**（由 `activeKey` + `entries` 派生），因此 `App.vue` 既有 `job.status.value` 模板解包写法无需改动；`useJob()` 退化为返回单例对象（`useSheets.js` 同款模块级单例写法）。

生命周期：

- `activateJob(name)`：停掉旧轮询 → `activeKey = name` → 若新桶 `pending/running/cancelling` 则开启轮询。
- `dropJob(name)`：删除桶（含停轮询）。
- `renameJob(from, to)`：迁移桶内容并重导 `activeKey`。
- `resetAllJobs()`：停全部轮询、清空 entries 与 activeKey。
- `submit()`：`reset()` 当前桶 → 发起提交 → 当前桶写 jobId/status。
- `_poll()`：进入时捕获 `const key = activeKey.value`；`fetch` 返回后写 `entries[key]`，防在途切换项目写串；本桶终态后停本桶轮询。

### 3. 新建项目空白（R2）

`openNewConfigDialog(options = {})`：

```
dialogBackup = clone(config)      # 先备份
if (options.blank) {
  Object.assign(config, emptyConfig())
  resetSheets()                   # useSheets 全局 oldSheets/newSheets + config.*_file_sheets
}
```

`cancelNewConfigDialog()`：还原 `config` 后追加 `restoreSheetsFromConfig()`（`useSheets.js:32`），使扫描结果回滚。

`ConfigSidebar.createNew()` → `openNewConfigDialog({ blank: true })`；`saveConfigWithPrompt()`/`autoSaveBeforeStart()` 保持无参调用。

组件 `NewConfigDialog.vue` 不改：其「导入模板」走 `applyDocument(doc, { preserveFiles: true })`，在空白 config 上保持文件为空。

### 4. 触发器挂接（R4/R5）

| 位置 | 动作 |
|---|---|
| `useConfigState.selectConfig` 末尾 | `activateJob(name)` |
| `useConfigState.saveConfig` 内（`rememberConfig`） | `activateJob(name)` |
| `useConfigState.clearSelectedConfig` | `dropJob(旧 currentName)` + `activateJob('')` |
| `ConfigSidebar.removeConfig` | `dropJob(name)` |
| `ConfigSidebar.editConfig` 成功改名 | `renameJob(oldName, newName)` |
| `App.vue logout()` | `resetAllJobs()` 替代 `job.reset()` |

注意循环依赖：`useConfigState.js` 引入 `useJob.js`（`useJob` 不依赖 `useConfigState`），无环。`ConfigSidebar` 内的 `renameJob` 需拿到改名前的 `name` 参数（`editConfig(name)` 已持有）。

## 兼容与迁移

- 后端 API 无变化；`useJob.js` 对外方法签名不变（`submit/cancel/download/downloadLogs/reset` 保留；`reset()` 语义改为「重置当前桶」，`logout` 走 `resetAllJobs`）。
- `job.reset()` 在 `App.vue` 唯一调用点被替换，其余地方不再引用。
- 「未命名项目」与「临时保存项目」：`startCompare` 中 `autoSaveBeforeStart()` 先命名并保存，随后 `submit()` 时 `activeKey` 已是项目名，任务入对桶。

## 权衡

- 选「按项目分桶」而非「切换即清空」（用户已选前者）：切回跑过的项目仍可下载。任务仅存内存 30 分钟（`job_manager.py:26`），服务重启或超时后切回显示 idle，属可接受的降级。
- 选「新建空白」而非「只清文件保留参数」（用户已选前者）：行为最可预期；想要复用参数的用户用「复制项目」。
- 不改为 `read_only=False` 读 Excel：大文件内存退化；`reset_dimensions` 以最小改动复现 pandas 行为。

## 回滚

- 仅 5 个前端/后端文件；`git revert` 或 `git checkout` 任务分支单个 commit 即可完整回滚。
- JWT/上传/任务后端逻辑零改动，无数据迁移。
