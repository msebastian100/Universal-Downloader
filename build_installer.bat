@echo off
chcp 65001 >nul
echo Building Universal Downloader Installer...
python build_installer.py
if errorlevel 1 pause
exit /b %errorlevel%
