@echo off
echo 启动B站视频上传助手...
cd /d "%~dp0"
set QT_PLUGIN_PATH=%~dp0.venv\Lib\site-packages\PyQt5\Qt5\plugins
set PYTHONPATH=%~dp0;%PYTHONPATH%

echo 检查Python环境...
python --version

echo 尝试启动程序...
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 主程序启动失败，尝试备用启动方式...
    python gui.py
)

pause 