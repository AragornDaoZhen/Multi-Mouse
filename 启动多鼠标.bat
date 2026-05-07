@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =============================================
echo   Multi-Mouse - 多鼠标独立光标
echo   关闭此窗口即可退出
echo =============================================
python run.py
pause
