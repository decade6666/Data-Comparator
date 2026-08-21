# 重写 xlsx 筛选器清理

## Goal

修复 Linux Web/API 运行时的 xlsx 筛选器预处理：不再调用不可用的 pywin32，不再通过破坏 OOXML 命名空间的 ElementTree 解压重打包；在不修改用户原始文件的前提下，可靠清理工作表和表格筛选器，并恢复被筛选隐藏的行。

## Requirements

- 将筛选器清理从 `file_runtime.py` 拆到独立基础设施模块，使用不解析、不重构 XML 的字节级定向删除。
- 删除项目不支持的 pywin32/COM 分支及其每次运行产生的噪声失败日志。
- xlsx 清理必须：
  - 删除 `xl/worksheets/*.xml` 中的 worksheet `autoFilter`；
  - 删除 `xl/tables/*.xml` 中的 table `autoFilter`，但保留表格本身；
  - 删除 worksheet 行元素的 `hidden="1"` / `hidden="true"` 属性；
  - 不删除列隐藏属性或其他用户格式；
  - 默认保留 `_xlnm._FilterDatabase`，但提供显式可选开关。
- 采用 scan-first：没有可清理内容时不重写 zip 包。
- 重写时按原始 `ZipInfo.infolist()` 顺序逐条写回，保留每个条目的压缩方式和关键元数据，并使用同目录临时文件 + 原子替换，源文件异常时保持完好。
- `.xls`、非 zip、损坏或加密 OOXML 输入必须有清晰可观测的可恢复语义：比对预处理继续使用副本，日志说明跳过筛选器清理；磁盘写入故障不能静默吞掉。
- `InterruptedError` 必须原样传播，不得进入普通错误或 fallback 分支。
- 保持现有 `check_and_remove_file_protection` 返回元组长度和调用方取第三项路径的兼容性。
- 不改变报告输出阶段主动设置筛选器的逻辑。
- 按 TDD 增加纯函数、zip 往返、错误语义和中断传播测试，并同步更新受影响的项目文档/测试索引。

## Acceptance Criteria

- [x] 带 worksheet/table autoFilter 和隐藏行的 xlsx 清理后仍可被 openpyxl 打开。
- [x] 清理后 worksheet/table autoFilter 消失、隐藏行恢复、列隐藏和单元格数据保持不变。
- [x] XML 根标签的命名空间前缀及 `mc:Ignorable` 等未修改内容不被 ElementTree 改写或丢失。
- [x] 清洁 xlsx 不发生重写；重写包保留原 entry 顺序与压缩类型。
- [x] 非 zip 输入、缺少 worksheets 部件、磁盘写失败和用户中断均符合约定的可观测行为；中断与写失败不损坏源文件。
- [x] 生产代码不再包含 pywin32/COM 筛选器路径或旧的 `remove_auto_filters_from_xlsx` 实现。
- [ ] `python3 -m pytest tests -q`、覆盖率检查和格式/静态检查通过；新增清理模块覆盖率达到 95% 以上。（242 个测试通过；新增清理模块 98% 覆盖率、全项目总覆盖率 81%；全项目既有格式/静态问题仍存在。）
- [x] 输出报告侧 `enable_filter_border_header_all_sheets` 行为未改变。
