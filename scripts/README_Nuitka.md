## 使用 Nuitka 打包

本方案不会修改原有的 PyInstaller 内容，新增了独立的打包脚本（位于 `scripts/` 目录）：
- `scripts/build_with_nuitka.bat`（双击/命令行均可调用）

### 环境准备
1. 安装依赖（推荐在虚拟环境中执行）
   ```powershell
python -m pip install -U nuitka zstandard
   ```
   - `zstandard` 用于 `--onefile` 压缩，减小体积（可选）
   - 首次构建会自动下载并配置 MinGW（已包含在 Nuitka 中，无需额外安装）

### 一键构建
- 从项目根目录执行 CMD 或 PowerShell：
  ```bat
scripts\build_with_nuitka.bat
  ```
- 也可在资源管理器中双击 `scripts/build_with_nuitka.bat`

构建产物位于 `dist_nuitka/`，单文件可执行：`比对程序_V1.6.3.exe`

### 说明
- 入口文件 `run.py`（内部导入 `src.main`）
- 启用 `--onefile --lto --follow-imports` 等优化项
- 自动包含 `src/` 下常见资源文件（如 `.json/.yaml/.ini/.csv/.png/.xlsx` 等）
- 可执行文件图标优先使用 `src/assets/icons/app_icon.ico`（若存在）
- 如需额外包含/排除文件，可在 `scripts/build_with_nuitka.ps1` 中调整 `--include-data-files` 或添加 `--nofollow-import-to` 参数

### 常见问题
- 首次编译时间较长，属于正常现象（Nuitka 需编译所有依赖）
- 若遇 PowerShell 执行策略限制，可使用 `.bat` 启动或以管理员执行：
  ```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
  ``` 
