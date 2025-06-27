@echo off
echo 启动B站视频上传助手...
set QT_PLUGIN_PATH=%~dp0.venv\Lib\site-packages\PyQt5\Qt5\plugins
python main.py
pause 