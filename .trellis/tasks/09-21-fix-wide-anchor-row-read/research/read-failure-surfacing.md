# Research: 读失败暴露（read-failure surfacing）落点调研

- **Query**: 调研「读失败伪装成缺失表单」的暴露链路，为最小修复方案提供 file:line 证据
- **Scope**: internal
- **Date**: 2026-09-21

## 1. 结果容器 SheetProcessResult

`src/backend/domain/sheet_process_result.py:7-28`，全部字段（构造器内初始化）：

| 字段 | 行号 | 说明 |
|---|---|---|
| `sheet_name` | :11 | sheet 名 |
| `success` | :12 | 默认 `False`，各成功分支显式置 `True` |
| `error_message` | :13 | **已存在**，`Optional[str]`，失败时存错误文本 |
| `change_type` | :14 | `"new"` / `"missing"` / `"data_changed"` / `None` |
| `differences` | :15 | 差异信息 |
| `add_sas_names` / `del_sas_names` | :16-17 | 新增/删除列 |
| `sas_file_names` / `sas_file_labels` / `sas_name_to_label` | :18-20 | SAS 元数据 |
| `is_split_result` / `split_chunks` | :21-22 | 拆分（已废弃使用） |
| `original_source_file` / `original_source_sheet_name` | :23-24 | 格式复制源 |
| `df` | :25 | 结果 DataFrame |
| `updated_rows_count` / `deleted_rows_count` / `added_rows_count` | :26-28 | 行级计数，供汇总表使用 |

**结论**：容器已有 `error_message` 字段，**无需新增 error 字段**。

`success=False` 的上层处理：`src/backend/domain/data_comparison.py:1412-1416` ——
```python
if not result.success:
    log_func(f"⚠️ 表单 [{sheet_name}] 处理失败: {result.error_message}")
    continue  # 跳过当前失败的 Sheet
```
失败的 sheet 仅记一行 ⚠️ 日志，**不写入报告、不进汇总、不让整体失败**。

## 2. 聚合层 process_edc_multithreaded

`src/backend/domain/data_comparison.py:1237-1680`：

- 线程池收集：`data_comparison.py:1385-1403`（`ThreadPoolExecutor` + `as_completed`）。
- **`success=False` 的 sheet 被静默跳过**：`:1412-1416`（见上），不抛错、不标记任务失败。
- 成功且有 `df` → 创建 sheet 写入：`:1440-1456`；高亮：`:1473-1482`；tab 颜色按 `change_type`：`:1509-1520`（`"missing"` 用缺失色 `:1509-1512`）。
- 写入阶段单 sheet 异常：`:1532-1534` —— 记日志后继续（第二个「部分失败继续」先例）。
- 汇总表生成：`:1588-1644`，只遍历已写入的 sheet；`deleted_rows_count > 0` 就进汇总（`:1629-1640`）。**读失败伪装成缺失时，汇总表会列出该表单与大量「删除」行**。
- 保存成功 → `:1657` `log_func("✅ 文件保存完成")`；保存失败 → `:1658-1661` 抛 `RuntimeError`。
- 整个函数级异常：`:1547-1552` 任意执行异常包成 `RuntimeError` 抛出。
- `InterruptedError` 传播：`:1524-1531`（写入循环内，取消未完成任务后 re-raise）、`:1544-1546`（外层 re-raise）。

## 3. 缺陷链路（已确认的事实，附证据）

- 读函数吞错：`src/backend/domain/excel_header_utils.py:246-253` —— broad `except Exception` → 记一行 `❌ 读取Sheet [{sheet_name}] 失败`（`:247`）→ `return None`。
- **sheet 不存在的正常路径也返回 None**：`excel_header_utils.py:37-39` 显式检查 `if sheet_name not in wb.sheetnames: return None`。两种 None 在调用方无法区分，这是根因。（函数内其余 `return None` 在 `:61/:69`，属 `_normalize_value` 的值归一化，无关。）
- `InterruptedError` 在读函数内已被正确放行：`excel_header_utils.py:239-245` re-raise。
- `process_single_sheet_complete` 的分支判定：`data_comparison.py:172-177`（双 None → 「均不存在」跳过，`success=True`）；`:207-247`（旧有新无 → 「缺失表单」→ `process_missing_sheet`（`:467` 起）把旧行全标「删除」→ `change_type="missing"`、`success=True`、写入报告）。
- `finally` 落终态：`data_comparison.py:458-462` —— `update_sheet_progress(sheet_name, "完成" if result.success else "失败")`。读失败伪装时落的是「完成」。

## 4. 进度状态 update_sheet_progress

调用点全集（grep 确认无遗漏）：

| 位置 | 状态串 |
|---|---|
| `data_comparison.py:102` | `"跳过"` |
| `data_comparison.py:109` | `"正在处理"` |
| `data_comparison.py:181-183` | `"新增表单"` |
| `data_comparison.py:212-214` | `"缺失表单"` |
| `data_comparison.py:361-363` | `"正在比对"` |
| `data_comparison.py:460-462` | `"完成"` / `"失败"`（`is_final_update=True`） |

**关键发现**：`src/backend/infrastructure/progress_manager.py:22-49` 的 `update_sheet_progress` 函数体**根本不消费 `status` 字符串**——只用 `is_final_update` 计数并推送全局进度消息；`status` 与 `sheet_name` 均未存储。`src/shared/contracts.py:52-62` 的 `ProgressReporter` Protocol 同样只是签名约定。

**因此 sheet 级状态串目前到达不了前端，前端也没有任何 sheet 状态枚举映射**。前端 job 状态机只有 `idle/pending/running/completed/failed/cancelled/cancelling`（`frontend/src/composables/useJob.js:5,10`），仅映射进度条颜色（`frontend/src/components/ProgressPanel.vue:16-18`：failed 红 / cancelled 橙 / completed 绿）。新增「读取失败」状态串不需要改前端枚举（现状是无人消费），但也不能指望它本身产生任何用户可见效果。

## 5. 对外暴露链路

### run_comparison（应用层）

`src/backend/application/comparison_runner.py:35-69`：返回 `str`（输出报告路径，`:60-69`）；**不捕获任何异常，原样向上传播**（含 `InterruptedError`）。`run_comparison` 正常返回即视为整个任务成功——没有部分失败的中间语义。

### JobManager（任务终态与错误字段）

`src/backend/application/job_manager.py`：

- `JobStatus` 枚举：`pending/running/completed/failed/cancelled`（`:42-47`）。
- `JobState.error: Optional[str]` 字段：`:77`；`snapshot()` 把 `error` 放进 HTTP 快照：`:217-226`。
- 终态判定 `_run_with_semaphore`：`:357-393` —— 正常返回 → `COMPLETED`（`:384-387`）；`InterruptedError` → `CANCELLED`（`:388-389`）；**其余任意异常 → `FAILED`，error=「比对处理失败: …」**（`:390-391`）。
- 日志落盘：`_persist_job_log` `:435-450`，`job.log_lines` 全量写入与报告同时间戳的成对日志文件；`_finish` 保证 error 也追加进日志 `:457-459`。
- 结论：**任务级只有「全成 / 全败 / 取消」三态，无「部分失败」态**；`error` 字段只在整任务抛异常时非空。

### Web API

`src/frontend/web_api.py`：

- `JobStatusResponse` 含 `error: Optional[str]`：`:315-324`。
- `GET /api/jobs/{job_id}` 直接回传 snapshot：`:663-674`。
- 同步 `POST /api/compare` 异常映射：`FileNotFoundError→404`（`:387-388`）、`ValueError→400`、`InterruptedError→409`（`:391-392`）、`OSError/RuntimeError→500`（`:393-394`）、其余 `→500`「比对处理失败」（`:395-398`）。

### 前端展示

- `useJob.js:83` 轮询时把 `body.error` 存进 entry，但**没有任何组件渲染 `entry.error`**（grep 全部 `.vue` 仅命中请求失败的 `ElMessage.error`）。
- `ProgressPanel.vue` 只渲染 `message`（全局 progress_message）+ 状态色；无错误横幅、无 sheet 级状态展示。
- 用户感知错误的现行方式：任务 `failed` 红条 + 自动下载仅日志（completed→报告+日志；failed→仅日志；`frontend/src/App.vue:88-127`）。日志里能看到那行 ⚠️/❌。
- grep「缺失表单/新增表单」等中文状态串在前端**无命中**——前端确实没有 sheet 状态映射，后端加状态串无前端同步成本。

## 6. 既有「部分失败但整体继续」惯例（新设计应沿用）

1. **sheet 处理失败 → ⚠️ 日志 + 跳过 + 整体继续**：`data_comparison.py:1412-1416`。这是最直接的先例：把读失败标记为 `success=False` 即可复用整条现有路径（不写入、不进汇总、整体仍完成）。
2. **写入阶段单 sheet 异常 → 记日志继续**：`data_comparison.py:1532-1534`。
3. **汇总生成容错**：单表单汇总出错仅记日志（`data_comparison.py:1641-1642`）。
4. **结束前无醒目汇总告警的先例不存在**——失败信息只在发生时打一行，没有结束时统一汇总的机制；`job.error` 也不用于部分失败。

## 7. 结论性建议：两个候选方案比较

### 方案 A（推荐）：读失败显式标记为 sheet 失败 + 结束时汇总告警，整体任务仍完成

改动面（全部在领域层，复用现有失败路径）：

1. `excel_header_utils.py`：`except Exception` 分支不再只返回 None——改为抛出一个领域内异常（如 `SheetReadError(Exception)`，**不继承 InterruptedError 语义**），或在返回 None 前通过某种通道带出错误。最小写法是直接 `raise`，让 `process_single_sheet_complete` 的既有 `except Exception`（`data_comparison.py:452-457`，已置 `success=False + error_message`）自然接住——**这条路径本来就正确传播 InterruptedError（`:450-451`），不冲突**。
2. `process_single_sheet_complete` 无需新字段（`error_message` 已存在，`sheet_process_result.py:13`）；可把错误文案改为「读取失败: …」便于区分。
3. `process_edc_multithreaded` 聚合循环（`:1403-1435`）已有 `not result.success` 分支，可在其内收集失败清单，保存前（`:1651` 前）若存在读失败 sheet，打多行醒目告警（`⚠️ N 个表单读取失败，报告中缺失: …`）。任务仍返回 `output_path`（与现有 sheet 失败先例一致，不新增「部分失败」任务终态）。

效果：读失败 sheet 不再被写成「缺失表单」、不再进汇总误导用户；日志有明确告警；改动集中在 2 个文件、复用全部现有机制。局限：任务终态仍是 `completed`、报告仍会生成（少几个 sheet）、前端无额外提示——用户需看日志或打开报告发现缺表。

### 方案 B：读失败直接抛异常终止整个比对

让 `read_single_sheet_from_excel` 抛错后一路冒泡（`process_edc_multithreaded:1547-1552` 会包成 `RuntimeError`）→ `JobManager:390-391` → 任务 `FAILED`、前端红条、`error` 字段非空。

效果：用户一定注意到（failed 状态 + error 文案）。代价：**一个无关紧要的坏 sheet（甚至可选 sheet）废掉整份报告**，与既有「单 sheet 失败整体继续」的产品语义（`:1412-1416`）冲突；且 4 个表单崩的线上案例里，其余表单的比对结果也被丢弃。`InterruptedError` 传播不受影响（优先级更高，`:1544` 先接）。

### 比较

| 维度 | A（部分失败暴露） | B（整体终止） |
|---|---|---|
| 改动面 | 小（2 文件，复用既有失败路径） | 更小（1 处改 raise） |
| 用户可见性 | 日志醒目告警 + 报告缺表 | 任务 failed + error 字段 + 红条 |
| 与既有惯例一致性 | 完全一致（沿用 :1412-1416 先例） | 相悖 |
| 误伤面 | 无（其余表单结果保留） | 大（好表单一并作废） |

若希望进一步增强 A 的可见性而不扩大改动面，可加一步（可选）：在聚合循环统计到读失败时，把汇总信息也写进报告内新增的说明行（`比对结果汇总` 表已在 `:1588-1644` 有写入点）——但这属于增量项，非最小方案必需。

## Caveats / 未验证

- `update_sheet_progress` 的 `status` 参数无消费者这一结论基于 `progress_manager.py` 全文（55 行）与 grep 全部调用点；若有未来分支消费该参数则以最新代码为准。
- 前端「无任何组件渲染 `entry.error`」基于对 `frontend/src/components/*.vue` 与 `App.vue` 的 grep；未逐行通读全部组件模板。
- 方案 A 中「读失败抛 SheetReadError 会被 `:452-457` 接住」未实际运行验证，但该分支为普通 `except Exception` 且 `InterruptedError` 有更早的专门分支（`:450-451`），逻辑上成立。
- 测试现状：`tests/test_excel_header_utils.py` 未锁定「读失败返回 None」行为（现有用例均为成功路径与 ragged-row 填充）；无 `tests/test_data_comparison.py`，聚合层行为无直接单测锁定，改动约束较小。
