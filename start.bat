@echo off
rem Construction Planner - Windows launcher
rem   double-click            -> open project "machi-demo"
rem   start.bat machi         -> open another project (folder name in projects\)
rem   start.bat machi --lan   -> allow phones on the same Wi-Fi
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if exist ".venv\Scripts\python.exe" goto :deps
echo [setup] Creating .venv ...
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if not exist ".venv\Scripts\python.exe" goto :nopython

:deps
echo [setup] Checking packages (first run takes a minute) ...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :pipfail

set PROJECT=%~1
if "%PROJECT%"=="" set PROJECT=machi-demo
start "" cmd /c "timeout /t 3 >nul & start http://localhost:5070"
".venv\Scripts\python.exe" app\server.py %PROJECT% %2
pause
exit /b

:nopython
echo.
echo Python not found. Install Python 3.9+ from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" during install), then run start.bat again.
pause
exit /b 1

:pipfail
echo.
echo pip install failed - check the internet connection, then run start.bat again.
pause
exit /b 1
