@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist env\Scripts\python.exe (
    echo Avval setup.bat ni ishga tushiring.
    pause
    exit /b 1
)
env\Scripts\python.exe main.py %*
pause
