@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =============================================
echo   Multi-Mouse Settings - 设置面板
echo =============================================
python settings_gui.py
