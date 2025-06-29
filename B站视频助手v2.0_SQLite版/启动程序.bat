@echo off
chcp 65001 >nul
title B站视频助手 v2.0 SQLite版
color 0A

echo.
echo ========================================
echo   B站视频助手 v2.0 SQLite纯净版
echo ========================================
echo.
echo 🚀 SQLite数据库版本特性：
echo    ✅ 高性能数据库存储
echo    ✅ 支持1000+账号规模  
echo    ✅ 查询速度提升50-300倍
echo    ✅ 完全数据库化架构
echo.

if not exist "B站视频助手v2.0.exe" (
    echo [错误] 找不到主程序文件
    pause
    exit /b 1
)

echo [信息] 启动程序...
echo 首次运行将自动创建SQLite数据库
echo.

start "" "B站视频助手v2.0.exe"

echo [成功] 程序已启动
timeout /t 3 >nul
