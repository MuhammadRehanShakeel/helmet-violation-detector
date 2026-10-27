@echo off
REM ===================================================================
REM  ONE-TIME SETUP for RoadGuard
REM  1. Python virtual environment + packages   2. backend\.env
REM  3. database + your admin account            4. frontend packages
REM ===================================================================
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
REM do not fill the C: drive with download caches
set PIP_NO_CACHE_DIR=1

echo [1/4] Creating the Python environment (Python 3.11) ...
cd backend
if not exist venv (
    py -3.11 -m venv venv 2>nul || python -m venv venv
)
venv\Scripts\python.exe -m pip install -q --upgrade pip
venv\Scripts\python.exe -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Package install failed. Check your internet connection and run this file again.
    pause
    exit /b 1
)

echo.
echo [2/4] Settings file backend\.env
set DBSERVER=
set /p DBSERVER=Type your SQL Server name (example: localhost\SQLEXPRESS) and press Enter: 
venv\Scripts\python.exe scripts\setup_env.py "%DBSERVER%"

echo.
echo [3/4] Database RoadGuard + your admin account
venv\Scripts\python.exe scripts\init_db.py
if errorlevel 1 (
    echo Database setup failed. Is SQL Server running? Is the server name right in backend\.env?
    pause
    exit /b 1
)

echo.
echo [4/4] Frontend packages ...
cd ..\frontend
call npm install --no-audit --no-fund

echo.
echo DONE. Start the app with start_project.bat
pause
