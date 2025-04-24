@echo off
:: 检查Python是否安装
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not added to PATH.
    exit /b 1
)

:: 设置Python脚本的路径
set SCRIPT_PATH=.\dltools\ChipsBankUWBTool.py

:: 运行Python脚本
python "%SCRIPT_PATH%" %*

:: 检查Python脚本是否成功运行
if %errorlevel% neq 0 (
    echo Python script failed.
    exit /b 1
) else (
    echo Python script executed successfully.
)

:: 结束批处理文件
exit /b 0