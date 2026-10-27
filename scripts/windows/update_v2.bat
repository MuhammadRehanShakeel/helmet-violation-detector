@echo off
REM One-time upgrade to RoadGuard v2 (CCTV, notifications, accounts, citizen portal, map, reports).
REM Safe to run again. Close the running backend/frontend windows first.
cd /d "%~dp0..\.."
echo === 1/3  Database upgrade (new columns + AccessRequests / Appeals tables) ===
cd backend
venv\Scripts\python.exe scripts\init_db.py
if errorlevel 1 (echo [ERROR] Database upgrade failed - see the message above & pause & exit /b 1)
cd ..
echo.
echo === 2/3  Demo CCTV stream ===
if not exist backend\data\demo_streams mkdir backend\data\demo_streams
if exist frontend\public\demo\demo_traffic.mp4 (
  copy /y frontend\public\demo\demo_traffic.mp4 backend\data\demo_streams\ >nul
  echo [OK] demo_traffic.mp4 copied. Use stream address  demo:demo_traffic.mp4  on the Cameras page.
) else (echo [!] frontend\public\demo\demo_traffic.mp4 not found - skip)
echo.
echo === 3/3  New frontend packages (map, notifications) ===
cd frontend
call npm install
if errorlevel 1 (echo [ERROR] npm install failed & pause & exit /b 1)
cd ..
echo.
echo [DONE] Now double-click start_project.bat
pause
