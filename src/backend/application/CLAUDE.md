[根目录](../../../CLAUDE.md) > [src](../../CLAUDE.md) > [backend](../CLAUDE.md) > **application**

# backend/application 模块指南

## 模块职责

`src/backend/application` 是应用编排层，负责把 Web/API 或 GUI 传入的参数组织成一次完整比对任务。它不实现 Excel 差异算法，而是负责路径校验、配置装配、输出文件命名、依赖注入和调用领域层主流程。

## 入口与启动

主要入口：

- `comparison_runner.py`
  - `run_comparison(...) -> str`：Web/API 优先使用的统一编排函数。
- `processing_service.py`
  - `validate_processing_paths(...)`：校验旧文件、新文件和输出目录。
  - `build_output_path(...) -> str`：生成比对报告输出路径。
  - `apply_processing_paths(...) -> ParameterDocument`：返回包含规范化路径的新参数文档。
  - `sanitize_output_name(...) -> str`：清洗配置名，生成安全文件名。

## 对外接口

上层调用方：

- `src/frontend/web_api.py`：`POST /api/compare` 将请求转换为 `ParameterDocument` 后调用 `run_comparison`。
- `src/gui/main_window.py`：历史 GUI 复用路径校验与参数应用函数。

下层依赖：

- `src/backend/domain/data_comparison.py`：默认通过延迟导入调用 `process_edc_multithreaded`。
- `src/backend/infrastructure/config_manager.py`：默认通过工厂函数创建 `ConfigManager`。

## 关键依赖与配置

`run_comparison` 支持依赖注入，便于测试：

- `process_func`：替换实际领域处理函数。
- `config_factory`：替换配置对象工厂。
- `path_exists`：替换路径存在性检查。
- `make_dirs`：替换目录创建函数。
- `now`：固定当前时间，便于断言输出路径。

输出路径格式由测试锁定：

```text
{safe_config_name}-比对报告-{YYYY-MM-DDTHH-MM-SS}.xlsx
```

## 数据模型

- `ProcessingPaths`：路径校验后的不可变路径对象。
- `ParameterDocument`：共享参数文档，来自 `src/shared/contracts.py`。
- `ComparisonConfig` Protocol：应用层对配置对象所需能力的最小约束。

## 测试与质量

对应测试：

- `tests/test_comparison_runner.py`
- `tests/test_processing_service.py`

重点行为：

- 缺失输入路径应快速失败。
- 输入文件不存在应抛 `FileNotFoundError`。
- 输出目录不存在时应创建。
- `apply_processing_paths` 必须返回新 mapping，不要就地修改原参数。
- `run_comparison` 应传播底层异常，不要隐藏失败。

## 常见问题 (FAQ)

### 为什么这里不直接写 Excel？

应用层只负责编排。Excel 读取、比较和写回属于领域层职责，避免业务算法和入口适配耦合。

### 修改输出文件名会影响什么？

会影响 `tests/test_processing_service.py` 和 `tests/test_comparison_runner.py` 的路径断言，也会影响用户脚本对报告命名的依赖。

### 如何让测试不依赖真实文件系统？

使用 `run_comparison` 的 `path_exists`、`make_dirs`、`process_func`、`config_factory`、`now` 注入点。

## 相关文件清单

- `comparison_runner.py`
- `processing_service.py`
- `__init__.py`
- `tests/test_comparison_runner.py`
- `tests/test_processing_service.py`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `backend/application` 模块 Claude 指南。 |
