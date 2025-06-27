@echo off
echo 正在清理 Git 中的大文件...

rem 移除已经被跟踪的大文件
git rm --cached "B站视频带货助手_完整EXE版.rar"
git rm --cached -r "B站视频带货助手_完整EXE版/"
git rm --cached -r "drivers/"
git rm --cached -r "ms-playwright/"

rem 移除可能的其他大文件
git rm --cached "*.exe" 2>nul
git rm --cached "*.dll" 2>nul
git rm --cached "*.rar" 2>nul

echo 大文件已从 Git 索引中移除
echo 您现在可以正常提交了
echo.
echo 注意：文件仍在您的本地文件系统中，只是不会再被 Git 跟踪

pause 