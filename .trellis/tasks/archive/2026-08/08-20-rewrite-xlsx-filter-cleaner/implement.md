# 实施计划

## 阶段 1：规划门禁

- [x] 记录用户选择：字节级重写、删除 pywin32、恢复隐藏行、保留 `_FilterDatabase` 默认关闭。
- [x] 检查现有调用链、测试、Linux 依赖和输出侧筛选器逻辑。
- [x] 建立任务分支与隔离 worktree。
- [x] 完成 `task.py start`，将状态切换到 `in_progress`。

## 阶段 2：TDD 实现顺序

1. **纯函数测试先行**
   - [x] 新建 `tests/test_xlsx_filter_cleaner.py`。
   - [x] 先覆盖 `strip_autofilter`、`unhide_rows`、`strip_filter_database` 的字节保真、前缀、自闭合、嵌套和误伤边界。
   - [x] 运行目标测试，确认在实现前失败。
2. **实现纯函数与数据模型**
   - [x] 新建 `xlsx_filter_cleaner.py`。
   - [x] 实现 regex 纯函数、选项/结果 dataclass、部件识别和转换分派。
   - [x] 运行纯函数目标测试至通过。
3. **zip 往返测试与实现**
   - [x] 用 openpyxl fixture 构造 worksheet autoFilter、table autoFilter、隐藏行、列隐藏和定义名。
   - [x] 增加可重开、数据不变、table 保留、entry 顺序/压缩类型、干净包早退和 `_FilterDatabase` 开关测试。
   - [x] 实现 scan-first、ZipInfo 克隆、按原顺序重写和原子替换。
4. **错误语义测试与实现**
   - [x] 覆盖非 zip、缺 worksheets 部件、用户停止、写失败源文件完整和临时文件清理。
   - [x] 增加 `tests/test_file_runtime.py`，覆盖副本预处理、验读、Sheet 名回退和 nofilter 清理分支。
   - [x] 将 `InterruptedError` 保持为独立控制流。
5. **运行时接线**
   - [x] 在 `file_runtime.py` 删除 pywin32、Zone.Identifier 和 ElementTree 旧路径。
   - [x] 接入 `remove_filters`；非 OOXML 转为信息日志继续使用副本；保留元组兼容性。
   - [x] 改写 `tests/test_processing_control.py` 中依赖旧 COM/fallback 符号的测试。
6. **调用方清理**
   - [x] 删除 `data_comparison.py` 中关于预处理删除 Sheet 的误导注释和永远不匹配的临时文件分支。
   - [x] 保持输出侧 `enable_filter_border_header_all_sheets` 不变。
7. **文档与规范同步**
   - [x] 更新 infrastructure/tests/根级索引和变更记录。
   - [x] 更新 error-handling、logging、开发文档，删除 pywin32/旧解压 fallback 的陈述，记录字节级清理和停止语义。

## 验证门禁

按顺序执行：

```bash
python3 -m pytest tests/test_xlsx_filter_cleaner.py -q
python3 -m pytest tests/test_processing_control.py -q
python3 -m pytest tests -q
python3 -m pytest --cov=src --cov-report=term-missing
black --check src tests
isort --profile black --check src tests
flake8 src tests
```

必要时运行真实临时目录端到端脚本：创建带筛选器的 xlsx，调用 `remove_filters`，再用 openpyxl 和 zipfile 校验报告；启动 Web API 的 `/health` 作为入口烟测。最终报告区分通过、失败、未运行和环境跳过项。

## 评审门禁

- 检查 `git diff`，确认没有修改原始输入路径、输出侧筛选器或无关依赖。
- 检查新增函数长度、类型标注、异常边界和 `InterruptedError` 传播。
- 检查新增测试覆盖率达到 95% 目标，整体覆盖率不因本次变更下降。
- 代码完成后进行独立代码审查；发现问题先修复再重复聚焦测试和全量测试。

## Verification Results

- `python3 -m pytest tests/test_xlsx_filter_cleaner.py tests/test_processing_control.py -q`：51 passed。
- `python3 -m pytest tests/test_file_runtime.py -q`：17 passed。
- `python3 -m pytest tests -q`：242 passed。
- `python3 -m pytest tests/test_xlsx_filter_cleaner.py --cov=src.backend.infrastructure.xlsx_filter_cleaner --cov-report=term-missing -q`：新增清理模块 98% 覆盖率。
- `python3 -m pytest tests --cov=src --cov-report=term-missing -q`：242 passed，总覆盖率 81%；`xlsx_filter_cleaner.py` 98%，`file_runtime.py` 97%。main 分支基线为 185 个测试、总覆盖率 75%，覆盖率未下降。
- `black --check`、`isort --profile black --check`：变更文件通过；全项目检查仍被既有 `src/frontend/web_api.py` 格式/import 问题阻塞。
- `flake8`：新增清理模块、file_runtime 测试、筛选器测试和停止控制测试通过；全项目存在本次范围外的既有 E501/F401/F541 问题。
- 生产预处理烟测：创建带 worksheet AutoFilter/隐藏行的临时 xlsx，经 `check_and_remove_file_protection` 生成任务副本，清理后可由 openpyxl 打开，日志包含成功统计，原始副本路径不同且未被覆盖。

## 回滚点

- 如果字节级清理不能通过真实 OOXML 往返测试，保留副本流程和输出报告逻辑，先回滚接线，仅保留测试/模块实验改动，不恢复已知会损坏 XML 的 ElementTree 实现。
- 原子替换失败时源文件应保持不变；只删除同目录临时文件。
