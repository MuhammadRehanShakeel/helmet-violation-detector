@echo off
REM Takes the README / LinkedIn screenshots of the running app (start_project.bat must be running).
REM Uses the Edge or Chrome already installed, so nothing big is downloaded.
cd /d "%~dp0..\.."
set PIP_NO_CACHE_DIR=1
if not exist DEMO_ACCOUNT.txt (
    echo DEMO_ACCOUNT.txt is missing.
    pause
    exit /b 1
)
echo Installing the screenshot tool (first time only) ...
backend\venv\Scripts\python.exe -m pip install -q playwright==1.48.0
echo Taking screenshots (about 1 minute) ...
backend\venv\Scripts\python.exe scripts\capture_screenshots.py > screenshot_log.txt 2>&1
type screenshot_log.txt
start "" "docs\screenshots"
pause
