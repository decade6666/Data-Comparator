@echo off
chcp 65001 > nul

set SCRIPT_DIR=%~dp0

pushd "%SCRIPT_DIR%"

rem 切换到项目根目录，因为 build_script.py 中的路径是相对项目根目录的
cd ..

python .\scripts\build_script.py

popd

pause 