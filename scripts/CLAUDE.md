[根目录](../CLAUDE.md) > **scripts**

# scripts 模块指南

## 模块职责

`scripts` 存放 Windows 桌面构建与打包脚本，包括 PyInstaller、Nuitka、版本资源和构建说明。它服务于历史 GUI 可执行文件交付，不属于当前 Linux Web Runtime 的主要运行路径。

## 入口与启动

主要脚本：

- `build.bat`：Windows 批处理入口，调用 `python .\scripts\build_script.py`。
- `build_script.py`：PyInstaller 自动打包脚本。
- `app.spec`：PyInstaller spec，入口为 `src/main.py`，输出 `比对程序`。
- `build_with_nuitka.bat`：Nuitka 打包脚本，入口为 `run.py`，输出 `比对程序_V1.6.3.exe`。
- `README_Nuitka.md`：Nuitka 打包说明。
- `version_info.txt`：Windows version resource，版本 `1.6.3`。

## 对外接口

`scripts` 不提供 Python 业务 API。它的外部接口是命令行/批处理执行入口。

重要限制：

- 构建脚本会安装依赖、删除构建目录、生成二进制产物。
- 文档扫描、代码审查和普通开发任务中只能读取，不应执行这些脚本。

## 关键依赖与配置

- PyInstaller：`build_script.py` 与 `app.spec`。
- Nuitka：`build_with_nuitka.bat`。
- Windows 资源：`version_info.txt`。
- 图标资源：脚本会检查 `src/app_icon.ico` 或相关图标路径。
- 构建产物目录：`build/`、`dist/`、`dist_nuitka/`，均应被忽略。

## 数据模型

本模块没有业务数据模型。配置主要表现为：

- PyInstaller spec 中的 hiddenimports、excludes、资源文件、输出名。
- Nuitka 批处理中的入口脚本、输出目录、插件和 include package。
- Windows version resource 字段。

## 测试与质量

当前未发现自动化测试直接覆盖构建脚本。

质量注意：

- 不要在未确认的情况下执行构建脚本。
- 修改入口、图标或依赖时，需要同步 `pyproject.toml`、`scripts/app.spec` 和对应说明文档。
- 新增 Linux Web Runtime 部署脚本时，建议与 Windows GUI 打包脚本分开，避免混合运行假设。

## 常见问题 (FAQ)

### 为什么脚本入口仍然是 GUI？

这些脚本服务于历史 Windows 桌面可执行文件，入口是 `src/main.py` 或 `run.py`。当前 Web/API 入口是 `src/main_web.py`，不由这些脚本负责。

### 可以直接运行 build_script.py 吗？

普通扫描或文档任务中不可以。它会安装依赖、清理目录并生成产物，属于高副作用操作。

### 构建产物是否应纳入扫描？

不应。`build/`、`dist/`、`dist_nuitka/` 和二进制产物应忽略。

## 相关文件清单

- `build_script.py`
- `app.spec`
- `build.bat`
- `build_with_nuitka.bat`
- `README_Nuitka.md`
- `version_info.txt`

## 变更记录 (Changelog)

| 时间 | 类型 | 说明 |
|---|---|---|
| 2026-05-24T03:25:49 | docs | 初始化 `scripts` 模块 Claude 指南。 |
