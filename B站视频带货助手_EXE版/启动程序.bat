@echo off
chcp 65001 >nul
title B站视频助手 v2.0
color 0A

echo.
echo ========================================
echo   B站视频助手 v2.0 纯净EXE版
echo ========================================
echo.

if not exist "B站视频助手.exe" (
    echo [错误] 找不到主程序文件
    pause
    exit /b 1
)

echo [信息] 启动程序...
echo 首次运行可能需要初始化
echo.

start "" "B站视频助手.exe"

echo [成功] 程序已启动
timeout /t 2 >nul
