# 技术设计：字节级 OOXML 筛选器清理

## 边界与数据流

保留现有入口：

```text
process_edc_multithreaded
  -> check_and_remove_file_protection(input, ..., work_dir)
      -> shutil.copy2(input, work_dir/*_nofilter_*.xlsx)
      -> remove_filters(copy_path)
  -> 后续 get_sheet_names/read_single_sheet_from_excel 读取副本
```

`remove_filters` 只修改任务工作目录中的副本。用户原始文件永不写入。输出报告的 `enable_filter_border_header_all_sheets` 仍由领域层负责并继续主动添加报告筛选器。

## 模块职责

新增 `src/backend/infrastructure/xlsx_filter_cleaner.py`，只依赖标准库和现有 `check_stop_frequently`：

- `NotAnOoxmlPackageError`：标识非 OOXML zip、损坏或不可读包。
- `CleanupOptions`：筛选器清理开关，默认清理 worksheet/table autoFilter 与行隐藏，默认不删 `_FilterDatabase`。
- `FilterCleanupResult`：记录是否重写、扫描/修改部件和各类清理计数。
- `strip_autofilter`、`unhide_rows`、`strip_filter_database`：无 IO 的 `bytes -> (bytes, count)` 纯函数。
- zip 部件识别、扫描、元数据克隆、按原顺序重写等内部函数。
- `remove_filters(path, *, options, log_func, stop_flag)`：对外门面。

`file_runtime.py` 保留副本创建、路径/临时目录、Excel 验证和 Sheet 名读取；删除 pywin32、Zone.Identifier 遗留和旧 ElementTree 解压重打包代码。`check_and_remove_file_protection` 捕获 `NotAnOoxmlPackageError` 记录信息并继续，其他文件系统/写入异常继续向上传播；返回四元组的长度和第三项路径不变。

## XML 处理策略

不使用 ElementTree/lxml/openpyxl 对源包做全量往返。正则只删除 OOXML 中受限且明确的元素/属性：

- `autoFilter` 元素：匹配可选前缀、属性和完整子树/自闭合标签。
- `row` 起始标签：仅删除其 `hidden` 属性，避免误伤 `rowBreaks`、文本节点和 `col`。
- `_FilterDatabase` definedName：只在显式 `remove_filter_database=True` 时删除。

所有未命中的字节原样保留，因此命名空间声明、`mc:Ignorable` 前缀列表、关系 ID、压缩包中的其他部件和用户数据不会因 XML 库重新序列化而改变。`remove_filters` 不对输入 XML 进行解析，所以不存在 ElementTree 前缀重写或进程级 `register_namespace` 并发状态。

## zip 重写策略

1. 打开源 zip，遍历 `infolist()`，对候选 XML 部件读取 bytes 做廉价探针；记录 dirty 部件。
2. 若没有 dirty 部件，返回 `rewritten=False`，不创建输出文件。
3. 在源文件同目录创建随机临时路径；重新打开源 zip 与临时输出 zip。
4. 再次按 `infolist()` 顺序读取每个条目：dirty 部件做定向转换，其他部件原样 bytes；用克隆的 `ZipInfo` 写入。
5. 关闭输出 zip 后 `os.replace(tmp_path, source_path)` 原子替换；所有异常和 `InterruptedError` 都在 finally 清理临时文件。

克隆 `ZipInfo` 的日期、压缩类型、external/internal attr、创建系统和 comment；不直接复制 flag bits，由 `writestr` 根据实际写入重新生成。entry 顺序跟随原中央目录顺序，不对 `[Content_Types].xml` 做人为重排。

## 错误与停止语义

- `BadZipFile`、读取 zip 条目失败等输入包问题转换为 `NotAnOoxmlPackageError`；调用方对 `.xls`/非 zip 副本记录跳过日志并继续读取。
- 缺少 `xl/worksheets/` 不是异常，扫描结果为空即可早退。
- 临时文件创建、写入、替换等 `OSError` 不隐藏，保证调用方收到真实失败且源包仍在。
- `check_stop_frequently` 在扫描和重写循环中调用。任何 `InterruptedError` 不捕获、不包装、不 fallback。

## 兼容与风险

- `exclude_sheets` 继续保留在 `check_and_remove_file_protection` 签名，仅为现有调用点兼容；Sheet 排除仍在 `data_comparison.py` 的单点过滤逻辑完成。
- `FilterCleanupResult` 作为四元组第 4 项返回；当前调用方只使用第三项，不需要跨层契约变更。
- 字节级匹配若遇到未覆盖的合法变体，会保持该部分不变而非重写损坏，失败形态为清理未完成而不是文件损坏；纯函数参数化测试覆盖默认/前缀/自闭合/带子节点形式。
- 列隐藏、customHeight、公式/值、表格结构及报告生成逻辑不在本设计范围。
