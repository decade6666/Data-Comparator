# PRD · 修复比对任务笛卡尔积爆炸与停止无响应

## 背景

2026-09-15 08:38，用户 7 提交比对任务 `16ebcd363f824c9a`（项目「羟尼酮IIIc医学审阅列表比对」）。
任务运行 2 小时以上未结束，进程 RSS 达 15.3 GB，单线程 100% CPU。用户刷新页面后
前端回到 idle，此后每次提交都被 `POST /api/jobs` 拒为 **409 已有比对任务正在运行**。

输入文件仅 688 KB / 969 KB —— **不是数据量问题**。同一项目 2026-09-14 17:47 运行
只用 8 分钟正常完成。

### 决定性对照

| | 9/14 成功运行 | 9/15 卡死运行 |
|---|---|---|
| 「未找到任何匹配的锚点」告警 | 2 条 | **96 条**（48 表单 × 新旧各一次） |
| 耗时 | 8 分钟 | 2h+ 未结束 |
| 进程 RSS | 正常 | 15.3 GB |

## 问题陈述

`create_anchor_by_sas_names` 在锚点完全匹配不上时，把**全表所有行**的 `_ANCHOR` 设为
同一个常量空字符串并**继续执行**。下游 `perform_full_comparison` 直接拿它做
`pd.merge(..., on="_ANCHOR", how="outer")` —— 所有行连接键相同，外连接退化为
**笛卡尔积 N_new × N_old**。2000×2000 的表单膨胀成 400 万行且列数翻倍。

膨胀后的行数再喂给 `apply_highlight_to_worksheet`，而该函数在**每一个数据行的循环体内**
重建整个 `diff_info` 字典，把本该 O(M) 的预处理变成 O(N×M)。

该函数还完全不检查停止标志，所以单个巨型表单高亮期间（实测超过 16 分钟）用户点
「停止比对」毫无响应。

## 目标

1. 锚点不可用时**快速失败**，绝不进入 `pd.merge`，杜绝笛卡尔积爆炸。
2. 消除 `apply_highlight_to_worksheet` 的 O(N×M) 重复字典构建。
3. 让高亮阶段响应停止标志，使「停止比对」在秒级生效。

## 非目标（本轮不做）

- `GET /api/jobs/current` 与前端刷新恢复（P1，已记入根计划「后续待办」）。
- 任务超时/心跳/僵尸回收、`submit()` 线程启动失败回滚、`BaseException` 兜底（P2）。
- 改变锚点匹配算法本身，或为该项目补配 `sheet_key_map`（属于用户配置层面）。

## 验收标准

### AC1 · 锚点不可用必须快速失败
- 当某表单一个 `key_sas_names` 都匹配不上时，该表单的 `SheetProcessResult.success`
  为 `False`，`error_message` 明确指出「锚点匹配失败」并列出期望的 key。
- 该表单**不得**执行 `pd.merge`（用 monkeypatch 断言 `pd.merge` 未被调用）。
- 同样覆盖另外 3 条兜底路径：无 SASFieldName、matched key 不在 `df.columns`、
  锚点构造抛异常。

### AC2 · 单表单失败不拖垮整个任务
- 失败表单被 `data_comparison.py:1412-1416` 既有路径记录并跳过。
- 其余表单正常写入，任务最终状态为 `completed`，而非整体 `failed`。

### AC3 · 防爆闸
- 即使未来出现其他路径产生全同锚点，`pd.merge` 前的检查也必须拦下并给出诊断信息。
- 合法的小表、以及锚点存在正常重复（`:955` 已有「锚点重复」告警的场景）**不得**被误伤。

### AC4 · 高亮性能
- `diff_keys` 只构建一次；改动前后高亮结果**逐单元格一致**（等价性测试）。

### AC5 · 停止可响应
- `apply_highlight_to_worksheet` 接受 `stop_flag`，置位时抛 `InterruptedError`。
- 默认 `stop_flag=None`，既有调用方与测试不受影响。
- `InterruptedError` 沿既有链路传播（`process_single_sheet_complete:450` → `:1524` → `:1544`），
  最终由 `JobManager` 映射为 `cancelled`。

### AC6 · 回归
- `pytest` 全绿，尤其 `test_processing_control.py::test_perform_full_comparison_propagates_interrupted_error`
  （该测试 monkeypatch 了 `create_anchor_by_sas_names`，改动不得破坏它）。

## 约束

- `src/backend/domain/data_comparison.py` 是项目 CLAUDE.md 点名的复杂核心文件：
  **修改前必须先读相关测试并增加针对性用例**。
- `InterruptedError` 是用户停止的正常控制流，必须继续传播，不得被宽 `except` 吞掉。
- 不得在日志或错误信息中输出用户 Excel 单元格内容；只输出表单名与列名。
