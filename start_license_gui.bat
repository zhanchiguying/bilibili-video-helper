@echo off
title B站视频上传助手 - 许可证生成器
cd /d "%~dp0"

echo.
echo ======================================
echo   B站视频上传助手 - 许可证生成器
echo ======================================
echo.

:: 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未检测到Python环境
    echo 请先安装Python 3.7+
    pause
    exit /b 1
)

:: 启动许可证生成器
echo 🚀 启动许可证生成器...
python license_gui.py

if errorlevel 1 (
    echo.
    echo ❌ 程序运行出错
    pause
) 