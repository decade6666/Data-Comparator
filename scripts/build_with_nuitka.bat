@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Use UTF-8 for console output
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM Resolve project root (parent of scripts directory)
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." || (echo 无法进入项目根目录 & exit /b 1)

REM Entry script
set "ENTRY_SCRIPT=run.py"
if not exist "%ENTRY_SCRIPT%" (
  echo 错误: 未找到入口脚本 "%CD%\%ENTRY_SCRIPT%"
  popd
  exit /b 1
)

REM Output directory
set "OUTPUT_DIR=%CD%\dist_nuitka"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Quick environment checks
python --version >nul 2>&1
if errorlevel 1 (
  echo 错误: 未检测到 python，请确保已安装并已添加到 PATH 中  
  popd
  exit /b 1
)

REM Decide Python interpreter (prefer 3.12 when current is 3.13 for MinGW64 support)
for /f "tokens=1,2 delims=." %%a in ('python -c "import sys;print(str(sys.version_info[0])+'.'+str(sys.version_info[1]))"') do (
  set PY_MAJOR=%%a
  set PY_MINOR=%%b
)
set "PY_CMD=python"
if "%PY_MAJOR%"=="3" (
  for /f "tokens=1" %%m in ("%PY_MINOR%") do set /a MINOR=%%m
  if !MINOR! GEQ 13 (
    rem Try Windows launcher for Python 3.12
    py -3.12 -c "import sys" 1>nul 2>nul
    if errorlevel 1 (
      echo 致命: Python 3.13 不支持 MinGW64。请安装 Python 3.12 x64，并确保可通过 ^"py -3.12^" 调用。
      echo 建议: 安装 3.12 或改为使用 MSVC 构建（不推荐，因你要使用 MinGW64）。
      popd
      exit /b 1
    ) else (
      set "PY_CMD=py -3.12"
      echo 检测到 Python 3.13，已自动切换使用 Python 3.12 进行 MinGW64 构建�?
    )
  )
)

REM Ensure Nuitka is installed for selected interpreter
%PY_CMD% -c "import nuitka,sys;print(getattr(nuitka,'__version__','unknown'))" 1>nul 2>nul
if errorlevel 1 (
  echo 未检测到 Nuitka，正在安装 nuitka zstandard （目标解释器: %PY_CMD%）
  %PY_CMD% -m pip install -U pip setuptools wheel || (
    echo 错误: pip 升级失败（解释器: %PY_CMD%）
    popd
    exit /b 1
  )
  %PY_CMD% -m pip install -U nuitka zstandard || (
    echo 错误: 自动安装 Nuitka 失败，请手动执行: %PY_CMD% -m pip install -U nuitka zstandard
    popd
    exit /b 1
  )
)

REM Force using MinGW64 toolchain
set "TOOLCHAIN=--mingw64"

REM Build mode: default release; pass "fast" to speed up (no LTO, no onefile)
set "BUILD_MODE=%~1"
if /i "%BUILD_MODE%"=="fast" (
  echo 使用快速构建模式（关闭 LTO，不启用 onefile，保留 standalone）
) else (
  set "BUILD_MODE=release"
)

REM Base Nuitka arguments (without toolchain specifics)
set "BASE_ARGS=%ENTRY_SCRIPT% --standalone --remove-output --output-filename=比对程序_V1.6.3.exe"
set "BASE_ARGS=!BASE_ARGS! --output-dir=%OUTPUT_DIR% --assume-yes-for-downloads"
set "BASE_ARGS=!BASE_ARGS! --enable-plugin=tk-inter"
set "BASE_ARGS=!BASE_ARGS! --enable-plugin=multiprocessing"
set "BASE_ARGS=!BASE_ARGS! --include-package=win32com"
set "BASE_ARGS=!BASE_ARGS! --include-package=pythoncom"
set "BASE_ARGS=!BASE_ARGS! --include-package=win32"
REM Avoid pulling in heavy test packages to speed up analysis
set "BASE_ARGS=!BASE_ARGS! --nofollow-import-to=win32.test"
set "BASE_ARGS=!BASE_ARGS! --nofollow-import-to=unittest"
REM Ensure src is on PYTHONPATH for import resolution
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Add optional icon option if exists (prefer assets/icons path)
if exist "src\assets\icons\app_icon.ico" (
  set "ICON_OPT=--windows-icon-from-ico=src\assets\icons\app_icon.ico"
) else if exist "src\app_icon.ico" (
  set "ICON_OPT=--windows-icon-from-ico=src\app_icon.ico"
) else (
  set "ICON_OPT="
)

REM Add optimization/packaging per mode
if /i "%BUILD_MODE%"=="release" (
  set "BASE_ARGS=!BASE_ARGS! --onefile --lto=yes --windows-console-mode=disable !ICON_OPT!"
) else (
  rem Fast mode: parallel jobs, no LTO, keep console
  set "CPU_JOBS=%NUMBER_OF_PROCESSORS%"
  if not defined CPU_JOBS set "CPU_JOBS=4"
  set "BASE_ARGS=!BASE_ARGS! --jobs=!CPU_JOBS!"
)

REM Do not force numpy plugin (deprecated by Nuitka); leave default handling

REM Include resource file types under src/, but only if any exists to avoid Nuitka fatal errors
set "NUITKA_ARGS=%BASE_ARGS%"
call :maybe_include json
call :maybe_include yaml
call :maybe_include yml
call :maybe_include ini
call :maybe_include toml
call :maybe_include txt
call :maybe_include csv
call :maybe_include tsv
call :maybe_include xml
call :maybe_include jpg
call :maybe_include jpeg
call :maybe_include png
call :maybe_include gif
call :maybe_include svg
call :maybe_include ico
call :maybe_include bmp
call :maybe_include xlsx
call :maybe_include xls
call :maybe_include xlsm
call :maybe_include parquet
call :maybe_include feather
call :maybe_include avro

REM Attempt build with specified toolchain
call :do_build "%TOOLCHAIN%" || (
  popd & exit /b 1
)

REM Continue after build

REM Locate the resulting exe
set "EXE_NAME=比对程序_V1.6.3.exe"
set "ONEFILE=%OUTPUT_DIR%\%EXE_NAME%"
if exist "%ONEFILE%" (
  echo 构建成功: %ONEFILE%
) else (
  set "FOUND="
  for /r "%OUTPUT_DIR%" %%f in (*.exe) do (
    if not defined FOUND set "FOUND=%%f"
  )
  if defined FOUND (
    echo 构建成功: !FOUND!
  ) else (
    echo 构建完成，但未在 "%OUTPUT_DIR%" 下找到 .exe 文件，请检查上方日志以获取更多信息
  )
)

popd
endlocal
exit /b 0

:do_build
setlocal EnableDelayedExpansion
set "CHAIN=%~1"
echo 构建中...
echo 命令: %PY_CMD% -m nuitka !NUITKA_ARGS! !CHAIN!
%PY_CMD% -m nuitka !NUITKA_ARGS! !CHAIN!
set "EC=%ERRORLEVEL%"
endlocal & if not "%EC%"=="0" ( echo 错误: Nuitka 构建失败（退出代码: %EC%）& exit /b %EC% ) else ( exit /b 0 ) 

:maybe_include
setlocal EnableDelayedExpansion
set "EXT=%~1"
set "_FOUND_=0"
for /f "delims=" %%F in ('dir /b /s "src\*.%EXT%" 2^>nul') do (
  set "_FOUND_=1"
  goto :_found
)
:_found
if "!_FOUND_!"=="1" (
  endlocal & set "NUITKA_ARGS=%NUITKA_ARGS% --include-data-files=src\**\*.%EXT%=./src/" & goto :eof
)
endlocal & goto :eof

:after_build
