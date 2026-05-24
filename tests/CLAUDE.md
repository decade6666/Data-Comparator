[根目录](../CLAUDE.md) > **tests**

# tests 模块指南

## 模块职责

`tests` 存放 pytest 测试资产，覆盖 Web/API、应用编排、路径处理、配置仓储、进度管理、停止控制、导入烟测、日志工具、Sheet 结果容器和高亮优化器。

## 入口与启动

测试入口由 `pyproject.toml` 配置：

```bash
pytest
pytest -v --tb=short --strict-markers
```

如需覆盖率报告，可在安装 `pytest-cov` 后运行：

```bash
pytest --cov=src --cov-report=term-missing
```

## 对外接口

测试文件本身不对外提供运行时接口。它们定义项目质量边界，尤其是：

- Web/API 状态码映射。
- 输出路径命名格式。
- 路径校验行为。
- 配置仓储 JSON 读写行为。
- 中断传播语义。
- 高亮优化器缓存行为。

## 关键依赖与配置

- `pytest`
- `fastapi.testclient.TestClient`
- `monkeypatch`
- `tmp_path`
- `pyproject.toml` 中的 pytest 配置

pytest 配置摘要：

- 测试目录：`tests`
- 文件模式：`test_*.py`
- 类模式：`Test*`
- 函数模式：`test_*`
- 默认参数：`-v --tb=short --strict-markers`

## 数据模型

测试覆盖的数据结构包括：

- Web API 的 `CompareRequest`、`CompareResponse`。
- 应用层的 `ProcessingPaths` 与 `ParameterDocument`。
- 领域层的 `SheetProcessResult`。
- 高亮优化器缓存。
- JSON 配置文档。

## 测试与质量

测试文件索引：

- `test_web_api.py`：FastAPI 健康检查、比对成功路径、异常映射和 422 校验。
- `test_comparison_runner.py`：应用编排、输出路径、依赖注入、异常传播。
- `test_processing_service.py`：路径校验、输出名清洗、输出目录创建、不可变参数更新。
- `test_parameter_repository.py`：JSON 配置保存、加载、列表、删除、内置模板和非法文档。
- `test_progress_manager.py`：线程安全进度、最终进度、回调失败日志。
- `test_processing_control.py`：停止标志、节流、中断传播、workbook 关闭。
- `test_highlight_optimizer.py`：高亮缓存、空行判断、失败日志和 changed cells。
- `test_sheet_process_result.py`：Sheet 结果默认字段。
- `test_log_utils.py`：日志打印、回调和 console encoding fallback。
- `test_import_smoke.py`：包与关键模块导入。

## 常见问题 (FAQ)

### 新功能应该先写测试吗？

是。Bug 修复和新功能应遵循 TDD：先写失败测试，再实现，再重构。

### 哪些行为最不能破坏？

输出路径格式、Web/API 状态码映射、`InterruptedError` 传播、`apply_processing_paths` 返回新 mapping、配置 JSON 非对象报错。

### GUI 是否有充分测试？

当前 GUI 主要通过导入烟测和后端测试间接覆盖。若修改 GUI 关键流程，应补充可测试的应用层函数或轻量 UI 单元测试。

## 相关文件清单

- `test_web_api.py`
- `test_comparison_runner.py`
- `test_processing_service.py`
- `test_parameter_repository.py`
- `test_progress_manager.py`
- `test_processing_control.py`
- `test_highlight_optimizer.py`
- `test_sheet_process_result.py`
- `test_log_utils.py`
- `test_import_smoke.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `tests` 模块 Claude 指南。 |
