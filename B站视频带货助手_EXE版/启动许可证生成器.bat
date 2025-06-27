@echo off
chcp 65001 >nul
title B站许可证生成器
color 0B

echo.
echo ========================================
echo   B站许可证生成器 v2.0
echo ========================================
echo.

if not exist "B站许可证生成器.exe" (
    echo [错误] 找不到许可证生成器文件
    pause
    exit /b 1
)

echo [信息] 启动许可证生成器...
start "" "B站许可证生成器.exe"

echo [成功] 许可证生成器已启动
timeout /t 2 >nul
