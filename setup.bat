@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   UzDublyaj - o'rnatish
echo ============================================================

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo Python topilmadi. https://www.python.org/downloads/ dan o'rnating
    echo va o'rnatishda "Add python.exe to PATH" belgisini qo'ying.
    goto :end
)
%PY% --version

if not exist env\Scripts\python.exe (
    echo.
    echo [1/3] env virtual muhiti yaratilmoqda...
    %PY% -m venv env || goto :end
) else (
    echo [1/3] env allaqachon mavjud.
)

echo.
echo [2/3] pip yangilanmoqda...
env\Scripts\python.exe -m pip install --upgrade pip

echo.
echo [3/3] Kutubxonalar o'rnatilmoqda (bir necha daqiqa)...
env\Scripts\python.exe -m pip install -r requirements.txt || goto :end

env\Scripts\python.exe -c "from core.ffmpeg_utils import ffmpeg_path; print('ffmpeg:', ffmpeg_path())"
echo.
echo TAYYOR! Endi config.py faylga API kalitni yozing va run.bat ni ishga tushiring.

:end
if /i not "%~1"=="nopause" pause
