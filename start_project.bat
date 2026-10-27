@echo off
REM Starts the backend (port 5001) and the frontend (port 5174) in two windows.
cd /d "%~dp0"
start "RoadGuard Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\python.exe main.py"
start "RoadGuard Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo Backend API docs: http://localhost:5001/docs
echo App:              http://localhost:5174
timeout /t 6 >nul
start http://localhost:5174
