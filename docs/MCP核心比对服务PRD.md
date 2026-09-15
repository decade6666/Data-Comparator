# Excel 数据比对 MCP 服务核心 PRD

> 文档状态：Draft v1.0  
> 提取基线：Dataset Comparator 1.7.0  
> 目标读者：MCP 服务开发者、比对算法维护者、测试人员

## 1. 文档目的

本文档从当前项目中提取可复用的 Excel 数据比对与报告输出能力，并将其收敛为一个无前端、可由大模型客户端调用的 MCP 服务需求。

本文只描述以下核心能力：

- Excel 文件检查与结构识别；
- 新旧工作簿的 Sheet、列、行和单元格差异比对；
- 结构化差异结果；
- Excel 高亮报告与日志输出；
- 长任务状态查询与取消；
- MCP tools 与 resources 的最小接口。

## 2. 非目标

以下现有项目能力不进入 MCP v1：

- Vue 页面、表单编辑器、进度条和任何浏览器交互；
- 用户注册、登录、JWT、管理员和多租户管理；
- 配置模板的增删改查、复制、导入、导出与回收站；
- SQLite 历史记录、项目管理和前端任务状态恢复；
- 任意服务器目录浏览；
- 通过 URL 下载输入文件；
- 旧 GUI 兼容层；
- 与核心比对无关的 `anchor_row_content`、`header_row_content`。当前实现虽然接收这两个字段，但实际读取逻辑只使用行号。

## 3. 产品目标

MCP 客户端应能完成以下闭环：

1. 检查两个 Excel 文件，获得 Sheet、字段名和字段标签；
2. 指定表头行、字段名行、锚点列、比对范围与忽略规则；
3. 启动比对并获得稳定的 `job_id`；
4. 查询进度、增量日志或取消任务；
5. 获得适合模型消费的结构化差异结果；
6. 获得与当前项目语义一致的 Excel 高亮报告。

成功标准：调用方不依赖 Web UI，也不需要理解内部 pandas/openpyxl 实现，即可可靠完成一次可追踪、可取消、可下载结果的工作簿比对。

## 4. 核心术语

| 术语 | 定义 |
|---|---|
| 旧版本 | 比对基线工作簿，记为 `old` |
| 新版本 | 目标工作簿，记为 `new` |
| 字段名行 | 用作内部列标识的行，当前项目称 `SASFieldName`，由 `anchor_row_num` 指定 |
| 字段标签行 | 用作报告可读表头的行，当前项目称 `SASFieldLabel`，由 `header_row_num` 指定 |
| 锚点列 | 唯一标识一条业务记录的一列或多列，相当于复合主键 |
| 排除字段 | 读取后立即删除，不参与锚点、比对和输出，即 `common_cols` |
| 忽略字段 | 保留在输出中，但不参与差异判定、行标记、单元格高亮和汇总，即 `ignore_cols` |
| 删除数据合并 | 是否把旧版独有的 Sheet、列和行写入最终报告，即 `merge_deleted_data` |
| 差异报告 | 带汇总、行标记、颜色和筛选器的 `.xlsx` 文件 |

## 5. 总体架构

```text
MCP Client
   │
   ├── inspect_workbook
   ├── start_comparison
   ├── get_comparison_status
   ├── get_comparison_result
   └── cancel_comparison
          │
          ▼
MCP Contract Layer
  参数校验、路径授权、错误映射、ResourceLink 返回
          │
          ▼
Job Orchestration Layer
  任务状态、并发限制、进度、日志、取消、临时目录
          │
          ▼
Comparison Domain
  Sheet 选择 → 表头解析 → 锚点匹配 → 四层差异计算
          │
          ├── Structured Result Store (JSON)
          └── Excel Report Renderer (.xlsx)
                     │
                     ▼
MCP Resources
  comparison://jobs/{job_id}/report
  comparison://jobs/{job_id}/log
```

### 5.1 模块职责

| 模块 | 职责 | 不应承担 |
|---|---|---|
| MCP Contract Layer | JSON Schema、输入输出适配、错误码、资源链接 | Excel 算法 |
| Job Orchestration | 异步执行、任务状态、取消、并发、临时文件清理 | 差异判定规则 |
| Workbook Reader | 文件预处理、Sheet 列举、表头与数据读取、值规范化 | 报告样式 |
| Comparison Domain | 锚点校验、结构差异与数据差异计算、汇总计数 | MCP 协议细节 |
| Result Store | 保存结构化结果并支持分页读取 | 重新计算差异 |
| Report Renderer | 将领域结果渲染成 Excel 报告 | 决定差异是什么 |

领域比对结果必须独立于 Excel 渲染器。MCP 的 JSON 结果与 Excel 报告应由同一份领域结果生成，避免两种输出口径不一致。

## 6. 输入文件与运行边界

### 6.1 v1 部署假设

v1 采用本地或 sidecar 模式：MCP 服务与输入 Excel 位于同一受信文件系统。工具接收服务可访问的绝对路径，不在 MCP 内实现文件上传协议。

### 6.2 文件约束

- 必须支持 `.xlsx`；
- `.xlsm` 可作为 OOXML 输入支持，但 v1 不承诺保留宏；
- v1 不支持旧二进制 `.xls`，应返回转换提示。当前项目的上传层虽然接受 `.xls`，但主读取链路仍依赖 openpyxl，不能把它视为可靠能力；
- 输入文件必须存在、非空且可读；
- 输出由服务写入受管结果目录，调用方不能默认写任意路径；
- 所有输入路径必须位于服务配置的允许根目录内；
- 必须解析真实路径并拒绝 `..`、符号链接等造成的允许目录逃逸；
- 服务不得修改原始输入文件。

### 6.3 OOXML 预处理

为继承当前项目对被筛选数据的处理语义，服务应先将输入复制到任务独立临时目录，再对副本执行以下清理：

- 删除 worksheet `autoFilter`；
- 删除 table `autoFilter`，但保留 table；
- 恢复因筛选器而隐藏的行；
- 不恢复隐藏列；
- 默认保留 `_xlnm._FilterDatabase`；
- 清洁文件不重写；
- 重写使用同目录临时文件和原子替换；
- 非 OOXML 输入跳过此步骤并产生可观测警告。

每个任务必须使用独立临时目录，任务结束或取消后只清理本任务文件。

## 7. 比对配置

### 7.1 核心配置模型

```json
{
  "anchor_row_num": 2,
  "header_row_num": 1,
  "default_keys": ["SUBJID", "VISITNUM"],
  "sheet_key_map": {
    "AE": ["SUBJID", "AESEQ"]
  },
  "include_sheets": [],
  "exclude_sheets": ["Code_List"],
  "common_cols": ["UPDATETIME"],
  "sheet_common_cols": {
    "AE": ["AUDIT_USER"]
  },
  "ignore_cols": ["MODIFIED_AT"],
  "sheet_ignore_cols": {
    "DM": []
  },
  "sheet_order": ["DM", "AE"],
  "merge_deleted_data": true,
  "max_workers": 4,
  "colors": {
    "highlight_fill": "#FFE5E5",
    "missing_sheet_tab": "#DC143C",
    "new_sheet_tab": "#00FF00"
  }
}
```

### 7.2 字段定义

| 字段 | 类型 | 默认值 | 规则 |
|---|---|---:|---|
| `anchor_row_num` | integer | `1` | 1-based 字段名行号，必须大于 0 |
| `header_row_num` | integer | `1` | 1-based 字段标签行号，必须大于 0 |
| `default_keys` | string[] | `[]` | 全局锚点列 |
| `sheet_key_map` | object | `{}` | 指定 Sheet 的锚点；命中时整体替换全局锚点 |
| `include_sheets` | string[] | `[]` | 非空时只处理所列 Sheet |
| `exclude_sheets` | string[] | `[]` | 从候选 Sheet 中排除；优先级在 include 之后 |
| `common_cols` | string[] | `[]` | 全局物理排除字段 |
| `sheet_common_cols` | object | `{}` | 指定 Sheet 的排除字段；命中时整体替换全局值，显式 `[]` 表示不排除任何字段 |
| `ignore_cols` | string[] | `[]` | 全局忽略差异字段，但保留输出 |
| `sheet_ignore_cols` | object | `{}` | 指定 Sheet 的忽略字段；命中时整体替换全局值，显式 `[]` 表示不忽略任何字段 |
| `sheet_order` | string[] | `[]` | 报告 Sheet 排列优先序 |
| `merge_deleted_data` | boolean | `true` | 是否输出旧版独有的 Sheet、列和行 |
| `max_workers` | integer | `CPU-1` | Sheet 级并发数，必须大于 0，并受服务端上限约束 |
| `colors` | object | 见示例 | 报告颜色，接受 6 位或 8 位十六进制颜色 |

### 7.3 配置优先级

对每个 Sheet：

```text
锚点列     = sheet_key_map[sheet]       若存在，否则 default_keys
排除字段   = sheet_common_cols[sheet]    若存在，否则 common_cols
忽略字段   = sheet_ignore_cols[sheet]    若存在，否则 ignore_cols
```

这里的“存在”必须使用键成员判断，不能使用值的真值判断。`{"AE": []}` 是有效配置，含义是 AE 不继承全局配置。

## 8. 工作簿读取规则

### 8.1 Sheet 集合

1. 获取旧、新工作簿 Sheet 名称并集；
2. `include_sheets` 非空时取交集；
3. 再移除 `exclude_sheets`；
4. 配置中未在文件出现的 Sheet 只产生警告，不导致任务失败。

### 8.2 表头与数据区

- `anchor_row_num` 指定内部字段名；
- `header_row_num` 指定报告显示标签；
- 数据从 `max(anchor_row_num, header_row_num) + 1` 行开始；
- 只读模式必须重置 worksheet 缓存维度，不能盲信错误的 `<dimension ref="A1"/>`；
- 公式按缓存后的显示值读取，即 `data_only=true`；
- 遇到第一行所有单元格都为空或空白字符串时停止读取；
- 单 Sheet 默认最多读取 1,000,000 条数据，达到限制时应明确失败或返回截断状态，禁止静默生成不完整报告；
- 行宽不一致时按最宽行补空值；
- 字段名不足时使用稳定的 `Unnamed_{index}` 补齐；
- 字段标签为空时回退字段名；
- 日期和时间规范化为稳定字符串，数值保持数值类型，其他值转为字符串。

### 8.3 字段处理

`common_cols` / `sheet_common_cols` 在读取后立即物理删除。因此它们：

- 不参与锚点构造；
- 不参与列增删检测；
- 不参与单元格比较；
- 不出现在结构化结果的数据列或 Excel 报告中。

若排除字段包含有效锚点，MCP 服务必须把该 Sheet 判为配置错误，不得继续生成可能错误的比对结果。

## 9. 锚点与行匹配规则

### 9.1 锚点要求

- 每个需要进行行级比对的 Sheet 必须至少有一个有效锚点列；
- 配置的每个锚点列必须同时存在于新旧 Sheet；
- 复合锚点按配置顺序组成；
- 锚点在同一版本、同一 Sheet 内必须唯一；
- 锚点不得为空；
- 锚点值应保留类型边界，禁止仅使用字符串加固定分隔符拼接，以免产生碰撞。

### 9.2 锚点失败策略

以下情况必须使对应 Sheet 失败，并使整个任务进入 `failed`，除非调用方未来显式选择宽松模式：

- 未配置任何锚点；
- 锚点列不存在；
- 锚点被排除字段删除；
- 锚点为空；
- 锚点重复；
- 字段名行存在重复字段名。

这是 MCP v1 相对当前实现的必要收紧。当前实现对部分锚点问题只记录警告并继续外连接，可能产生多对多笛卡尔结果；读取异常也可能被误判成“Sheet 不存在”。新服务不得继承这种不确定行为。

### 9.3 行集合

新旧数据按锚点执行全外连接：

- 仅新版存在：新增行；
- 仅旧版存在：删除行；
- 两边都存在且至少一个非忽略单元格有差异：更新行；
- 两边都存在且无有效差异：未改变行。

行的新增/删除必须由锚点集合差异直接判定，不能依赖“非锚点单元格是否产生 diff”。这样即使一行只有锚点列，也能被正确标记。

## 10. 差异判定规则

### 10.1 四层差异

服务必须识别：

1. Sheet 级：新增 Sheet、删除 Sheet；
2. 列级：新增列、删除列；
3. 行级：新增行、删除行、更新行、未改变行；
4. 单元格级：新增值、删除值、更新值。

### 10.2 列差异

- 新版有、旧版无：新增列；
- 旧版有、新版无：删除列；
- 列增删基于应用“排除字段”后的字段集合；
- 锚点列不参与单元格差异，但仍属于输出列；
- 忽略字段仍参与列增删检测，即忽略只影响值变化，不隐藏结构变化。

### 10.3 单元格判等

空值规则：

- `None`、`NaN`、空字符串和仅含空白字符的字符串视为同一类空值；
- 旧空新非空：新增值；
- 旧非空新空：删除值。

非空值规则：

- 数值与数值按数值比较；
- 数值字符串与真实数值在可安全解析时按数值比较，例如 `"1"` 与 `1` 相等；
- 其余值先去除首尾空白，再进行区分大小写的精确文本比较；
- 布尔值不作为数值处理；
- v1 不提供浮点容差、大小写忽略、Unicode 模糊归一化或日期格式猜测。

`ignore_cols` / `sheet_ignore_cols` 中的字段：

- 不产生单元格差异；
- 不使行变为“更新”；
- 不高亮；
- 不计入汇总；
- 仍保留新版值并出现在结果中。

### 10.4 Sheet 变更类型

结构化结果使用稳定英文枚举：

- `new_sheet`
- `deleted_sheet`
- `modified`
- `unchanged`
- `failed`

Excel 展示继续使用中文标记“新增”“删除”“更新”“未改变”。协议枚举不得依赖展示文案。

## 11. 删除数据合并语义

当 `merge_deleted_data=true`：

- 删除 Sheet 写入报告；
- 删除行写入报告，并将旧值恢复到主输出列；
- 删除列保留在报告中；
- 对应行标记为“删除”。

当 `merge_deleted_data=false`：

- 旧版独有 Sheet 不写入；
- 删除行不写入明细表；
- 删除列不写入明细表；
- 结构化汇总仍应保留删除计数和删除元数据，避免“未展示”等于“未检测”。

最后一条是 MCP 输出相对当前 Excel-only 行为的增强要求。

## 12. 结构化结果模型

### 12.1 任务结果摘要

```json
{
  "job_id": "4a8d...",
  "status": "completed",
  "old_file": "old.xlsx",
  "new_file": "new.xlsx",
  "started_at": "2026-09-08T10:00:00+08:00",
  "finished_at": "2026-09-08T10:01:20+08:00",
  "totals": {
    "sheets_processed": 12,
    "sheets_changed": 3,
    "rows_added": 5,
    "rows_deleted": 2,
    "rows_updated": 8,
    "columns_added": 1,
    "columns_deleted": 1
  },
  "sheets": [
    {
      "sheet_name": "AE",
      "change_type": "modified",
      "rows_added": 1,
      "rows_deleted": 0,
      "rows_updated": 2,
      "added_columns": ["AENEW"],
      "deleted_columns": []
    }
  ],
  "artifacts": {
    "report_uri": "comparison://jobs/4a8d.../report",
    "log_uri": "comparison://jobs/4a8d.../log"
  },
  "warnings": []
}
```

### 12.2 行与单元格差异

```json
{
  "sheet_name": "AE",
  "anchor": {
    "SUBJID": "001",
    "AESEQ": 2
  },
  "row_change_type": "updated",
  "cells": [
    {
      "column_name": "AETERM",
      "column_label": "不良事件名称",
      "change_type": "updated",
      "old_value": "Headache",
      "new_value": "Severe headache"
    }
  ]
}
```

要求：

- JSON 中同时保留字段名和字段标签；
- 更新必须返回旧值和新值；
- 新增/删除行也必须返回锚点和值快照；
- 日期、NaN、无穷值等必须转为合法 JSON；
- 大结果必须分页，不能在一次 MCP tool 响应中返回全部数据；
- 默认不返回未改变行。

## 13. Excel 报告输出

### 13.1 文件命名

```text
{安全任务名}-比对报告-{YYYY-MM-DDTHH-MM-SS}.xlsx
{安全任务名}-比对日志-{YYYY-MM-DDTHH-MM-SS}.txt
```

任务名中的 `\ / : * ? " < > |`、换行和制表符替换为 `-`；空名称回退为“默认配置”。报告与日志必须共用同一开始时间戳。

### 13.2 工作簿结构

- 第一个 Sheet 固定为“比对结果汇总”；
- 后续为参与处理且需要输出的业务 Sheet；
- 新旧均为空的 Sheet 默认不输出；
- 没有业务 Sheet 可输出时增加“无差异表单”说明 Sheet，保证工作簿有效。

汇总表列：

| Sheet 名称 | 更新行数 | 删除行数 | 新增行数 |
|---|---:|---:|---:|

- 只列出至少一种差异计数大于 0 的 Sheet；
- Sheet 名称链接到对应 Sheet 的 `A1`；
- 汇总计数必须来自领域结果，禁止通过重新扫描展示文本作为主逻辑。

### 13.3 业务 Sheet

- 第一列固定为“更新情况（标记）”；
- 表头展示字段标签，内部映射仍保留字段名；
- 输出数据以新版为主；删除数据合并开启时补入旧版独有数据；
- 未改变行也保留在报告中；
- 默认列顺序为：标记列、新版字段顺序、旧版独有字段；
- 所有有数据的 Sheet 启用首行筛选；
- 冻结窗格为 `A2`；
- 使用细边框；
- 表头加粗、自动换行，普通表头默认浅蓝色。

### 13.4 高亮规则

| 对象 | 规则 |
|---|---|
| 新增 Sheet | Sheet 标签使用 `new_sheet_tab` |
| 删除 Sheet | Sheet 标签使用 `missing_sheet_tab` |
| 数据有变化的 Sheet | Sheet 标签使用 `highlight_fill` |
| 新增列 | 表头使用 `new_sheet_tab` |
| 删除列 | 表头使用 `missing_sheet_tab` |
| 新增行 | 标记列红色加粗，整行使用 `highlight_fill` |
| 删除行 | 标记列红色加粗，整行使用 `highlight_fill` |
| 更新行 | 标记列红色加粗，仅变化单元格使用 `highlight_fill` |
| 忽略字段变化 | 不高亮 |

## 14. MCP 接口

### 14.1 `inspect_workbook`

用途：在启动比对前识别 Sheet 和字段，帮助调用方正确配置锚点及范围。

输入：

```json
{
  "file_path": "/allowed/data/new.xlsx",
  "anchor_row_num": 2,
  "header_row_num": 1,
  "include_sheets": []
}
```

输出至少包含：

- 文件名和文件类型；
- Sheet 原始顺序；
- 每个 Sheet 的字段名、字段标签、估算数据行数；
- 重复字段名、空字段名、读取失败等警告；
- 不默认返回业务数据样本，避免不必要的数据暴露。

### 14.2 `start_comparison`

用途：提交长耗时比对任务。

输入：

```json
{
  "old_file_path": "/allowed/data/old.xlsx",
  "new_file_path": "/allowed/data/new.xlsx",
  "job_name": "TM-2026-09",
  "config": {
    "anchor_row_num": 2,
    "header_row_num": 1,
    "default_keys": ["SUBJID", "VISTOID"],
    "exclude_sheets": ["Code_List"],
    "merge_deleted_data": true
  }
}
```

立即返回：

```json
{
  "job_id": "4a8d13b6f2034f1a",
  "status": "pending"
}
```

该工具不应等待大型文件全部处理完毕。

### 14.3 `get_comparison_status`

输入：

```json
{
  "job_id": "4a8d13b6f2034f1a",
  "log_cursor": 20
}
```

输出：

```json
{
  "job_id": "4a8d13b6f2034f1a",
  "status": "running",
  "progress_percent": 63,
  "progress_message": "已完成表单 [8/12]: AE",
  "log_lines": ["..."],
  "next_log_cursor": 24,
  "error": null
}
```

状态枚举固定为：

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

### 14.4 `get_comparison_result`

用途：读取模型友好的结构化结果。

输入：

```json
{
  "job_id": "4a8d13b6f2034f1a",
  "sheet_name": "AE",
  "change_types": ["added", "deleted", "updated"],
  "cursor": null,
  "limit": 100
}
```

规则：

- 任务未完成时返回可重试错误和当前状态；
- `limit` 由服务端限制；
- 无 `sheet_name` 时返回总摘要与 Sheet 摘要；
- 有 `sheet_name` 时分页返回行/单元格差异；
- 终态响应包含报告与日志的 MCP ResourceLink。

### 14.5 `cancel_comparison`

输入：

```json
{
  "job_id": "4a8d13b6f2034f1a"
}
```

输出当前任务状态。取消采用协作式停止；服务必须在预处理、读取循环、列比较、结果写入和保存前检查停止标志。终态任务重复取消应幂等返回原状态。

### 14.6 Resources

| URI 模板 | MIME type | 内容 |
|---|---|---|
| `comparison://jobs/{job_id}/report` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | Excel 高亮报告 |
| `comparison://jobs/{job_id}/log` | `text/plain; charset=utf-8` | 完整任务日志 |

资源只在当前 MCP 会话有权访问该任务且文件仍处于保留期时可读。不存在、未完成或已过期时必须返回明确错误。

## 15. 任务与并发要求

- 每个任务拥有独立 `job_id`、停止标志、日志缓冲、结果记录和临时目录；
- Sheet 之间可并行，同一 Sheet 内保持确定性处理；
- 实际 Sheet worker 数为 `min(待处理 Sheet 数, 请求 max_workers, 服务端上限)`；
- 服务级任务并发必须可配置，默认可沿用当前项目的 2；
- 等待并发槽的任务状态为 `pending`；
- 进度必须单调不回退；
- 任务失败、取消或成功后都必须关闭工作簿并清理临时副本；
- 报告保存必须先写临时文件，再原子移动到最终路径，避免暴露半成品；
- 结构化结果和 artifact 元数据应在任务保留期内可查询。

## 16. 错误模型

MCP 错误响应应包含稳定代码、人类可读消息和可选细节：

```json
{
  "code": "DUPLICATE_ANCHOR",
  "message": "Sheet AE 的锚点不唯一",
  "details": {
    "sheet_name": "AE",
    "duplicate_count": 3
  },
  "retryable": false
}
```

建议错误码：

| 错误码 | 场景 | 可重试 |
|---|---|---|
| `FILE_NOT_FOUND` | 输入不存在 | 否 |
| `PATH_NOT_ALLOWED` | 路径越出允许根目录 | 否 |
| `UNSUPPORTED_FORMAT` | 非 `.xlsx` / `.xlsm` 输入 | 否 |
| `INVALID_WORKBOOK` | 文件为空、损坏、加密或不可解析 | 否 |
| `INVALID_CONFIG` | 行号、颜色、worker 等参数无效 | 否 |
| `DUPLICATE_COLUMN_NAME` | 字段名行有重复值 | 否 |
| `MISSING_ANCHOR` | 未配置或找不到锚点列 | 否 |
| `EMPTY_ANCHOR` | 锚点存在空值 | 否 |
| `DUPLICATE_ANCHOR` | 锚点不唯一 | 否 |
| `JOB_NOT_FOUND` | 任务不存在、无权访问或已过期 | 否 |
| `JOB_NOT_READY` | 结果尚未生成 | 是 |
| `JOB_CANCELLED` | 任务被取消 | 否 |
| `REPORT_WRITE_FAILED` | 报告落盘失败 | 视环境而定 |
| `INTERNAL_ERROR` | 未分类异常 | 视环境而定 |

不得把以下情况静默降级为“无差异”：Sheet 读取失败、锚点无效、比较异常、报告保存失败。

## 17. 日志与可观测性

日志至少覆盖：

- 任务创建、开始、成功、失败、取消；
- 输入副本与 OOXML 清理结果；
- Sheet 候选、过滤、处理开始和完成；
- 每个 Sheet 实际使用的锚点、排除字段和忽略字段；
- 未匹配的 include/exclude/ignore 配置；
- 新增/删除 Sheet 与列；
- 锚点和表头校验错误；
- 报告与结构化结果保存结果；
- 临时文件清理失败。

日志不得默认记录完整数据行、单元格业务值或绝对路径中的敏感目录。MCP 增量日志使用游标读取，避免每次返回全量日志。

## 18. 非功能要求

### 18.1 正确性

- 相同输入和配置必须产生相同的差异集合与 Sheet 顺序；
- 并发完成顺序不得改变最终报告顺序；
- JSON 汇总与 Excel 汇总必须一致；
- 任一 Sheet 失败时不得把任务标记为成功。

### 18.2 性能与资源

- 工作簿采用只读方式逐 Sheet 读取；
- 不同时把两个工作簿的所有 Sheet 全量载入内存；
- 写入大 Sheet 时分批检查取消和内存压力；
- 并发 worker 必须有服务端硬上限；
- 超过行数、文件大小或结果大小限制时明确失败，不静默截断。

### 18.3 安全

- 路径 allowlist 与真实路径校验是强制要求；
- 原始文件只读，预处理仅操作副本；
- Sheet 名写入超链接前正确转义单引号；
- 所有用户可控文件名必须净化；
- 禁止把 Excel 单元格内容解释为命令或模板；
- 若未来支持远程 MCP，多会话任务、资源和临时目录必须隔离。

## 19. 验收标准

### 19.1 读取与配置

- [ ] 可读取 `<dimension ref="A1"/>` 错误但实际有多行多列的 xlsx；
- [ ] 字段名行、字段标签行和数据起始行符合配置；
- [ ] 行宽不一致时不崩溃；
- [ ] `sheet_common_cols` / `sheet_ignore_cols` / `sheet_key_map` 均为整体替换语义；
- [ ] per-sheet 显式空列表可以禁用全局配置；
- [ ] include 后 exclude 的 Sheet 范围正确；
- [ ] 原始输入文件在成功、失败和取消后字节不变。

### 19.2 差异逻辑

- [ ] 完全相同的 Sheet 无差异；
- [ ] 新增/删除 Sheet、列、行和单元格均正确识别；
- [ ] 更新单元格返回 old/new 值；
- [ ] `None`、`NaN`、空串和空白串互相判等；
- [ ] `1` 与 `"1"` 判等，`true` 与 `1` 不判等；
- [ ] 忽略字段变化不影响行标记、汇总和高亮，但字段仍输出；
- [ ] 排除字段完全不输出；
- [ ] 只有锚点列的新增/删除行仍能识别；
- [ ] 缺失、空或重复锚点使任务明确失败；
- [ ] 字段名重复使任务明确失败；
- [ ] `merge_deleted_data=false` 不输出删除明细，但结构化摘要保留删除计数。

### 19.3 输出

- [ ] JSON 摘要计数、JSON 明细和 Excel 汇总一致；
- [ ] Excel 第一列为“更新情况（标记）”；
- [ ] 新增/删除行整行高亮，更新行只高亮变化单元格；
- [ ] 新增/删除列与 Sheet 标签颜色正确；
- [ ] 汇总 Sheet 位于第一位并可跳转；
- [ ] 顺序优先级为 `sheet_order > include_sheets > 源文件顺序`；
- [ ] 默认源文件顺序以新版为主，旧版独有 Sheet 按旧版相对顺序追加；
- [ ] 报告与日志名称安全并共享时间戳；
- [ ] 没有可输出业务 Sheet 时仍生成有效工作簿。

### 19.4 MCP 生命周期

- [ ] 提交立即返回 `job_id`；
- [ ] 状态按 `pending → running → completed/failed/cancelled` 转换；
- [ ] 日志游标只返回增量内容；
- [ ] 取消在读取、比较和写入阶段均可生效；
- [ ] 取消后不暴露半成品报告；
- [ ] 结构化结果可按 Sheet 和 cursor 分页；
- [ ] 完成后报告和日志 ResourceLink 可读取；
- [ ] 过期或越权资源返回 `JOB_NOT_FOUND`，不泄露任务是否真实存在。

## 20. 当前代码复用映射

| 目标能力 | 当前来源 | MCP 化处理 |
|---|---|---|
| 应用入口编排 | `src/backend/application/comparison_runner.py` | 保留领域入口，移除 Web 专属参数映射 |
| 输出路径与日志命名 | `src/backend/application/processing_service.py` | 复用净化和配对时间戳，输出目录改为服务受管 |
| 配置对象 | `src/backend/infrastructure/config_manager.py` | 改为显式校验模型，颜色与业务配置可拆分 |
| Excel 副本及预处理 | `src/backend/infrastructure/file_runtime.py` | 保留任务隔离，收紧格式和错误语义 |
| OOXML 筛选器清理 | `src/backend/infrastructure/xlsx_filter_cleaner.py` | 可直接复用并补充调用边界测试 |
| Sheet 读取 | `src/backend/domain/excel_header_utils.py` | 复用维度重置与表头解析，禁止异常返回 `None` |
| 核心比对 | `src/backend/domain/data_comparison.py` | 拆分 Sheet/列/行/单元格纯领域逻辑，修正锚点失败策略 |
| Excel 高亮 | `src/backend/domain/excel_utils.py` | 作为独立 renderer 复用 |
| 任务状态与取消 | `src/backend/application/job_manager.py` | 复用状态机、日志游标和 stop flag，删除用户/项目管理耦合 |
| 跨层参数契约 | `src/shared/contracts.py` | 替换为严格 MCP 输入和领域结果模型 |

## 21. 已识别的迁移注意事项

以下是当前实现行为，不应无条件复制到 MCP 服务：

1. 当前锚点缺失或重复主要记录警告，随后仍可能执行外连接；MCP v1 必须失败关闭。
2. 当前 Sheet 读取捕获普通异常后返回 `None`，上层可能把读取失败当成 Sheet 缺失；MCP v1 必须保留真实错误类型。
3. 当前完整比较异常可能返回空 DataFrame 和零计数；MCP v1 不得把算法异常伪装成成功。
4. 当前锚点通过字符串和 `###` 拼接，存在类型模糊和分隔符碰撞；MCP v1 应使用结构化复合键。
5. 当前重复锚点可能触发 pandas 多对多合并并放大结果；MCP v1 在 merge 前必须验证唯一性。
6. 当前结构化中间差异主要服务于 Excel 高亮，不完整保留 old/new 值；MCP v1 需新增稳定的领域结果模型。
7. 当前无删除合并时，Excel 删除明细被移除；MCP JSON 摘要仍应保留已检测到的删除计数。
8. 当前进度和任务表主要面向 Web 轮询；MCP 化后保留状态机即可，不需要移植认证、数据库历史和 UI 项目状态。

## 22. 建议实施顺序

1. 定义严格配置、错误和结构化结果模型；
2. 抽取无 MCP、无 openpyxl 样式依赖的纯比对核心；
3. 补齐锚点校验、行集合判定和 old/new 值输出；
4. 让现有 Excel renderer 消费新的领域结果；
5. 接入异步任务、取消、日志和受管 artifact；
6. 实现五个 MCP tools 与两个 resources；
7. 用现有 pytest 资产做兼容回归，再增加 MCP 合同测试和端到端测试。
