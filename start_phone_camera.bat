@echo off
REM ===================================================================
REM  Use your PHONE as the live traffic camera.
REM  The laptop runs the AI; the phone only sends ~1 photo per second over Wi-Fi.
REM  Phone and laptop must be on the SAME Wi-Fi.
REM ===================================================================
cd /d "%~dp0"
echo Installing the HTTPS helper (first time only) ...
cd frontend
if not exist node_modules\@vitejs\plugin-basic-ssl (
    call npm install --no-audit --no-fund
)
if not exist node_modules\@vitejs\plugin-basic-ssl (
    echo Installing the HTTPS helper failed. Check your internet and run this file again.
    pause
    exit /b 1
)
cd ..
start "RoadGuard Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\python.exe main.py"
start "RoadGuard Frontend (phone mode)" cmd /k "cd /d "%~dp0frontend" && set PHONE=1&& npm run dev"
echo.
echo ===================================================================
echo  Your laptop's Wi-Fi address (IPv4) is:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do for /f "tokens=*" %%b in ("%%a") do echo     https://%%b:5174
echo.
echo  (also shown as "Network:" in the "RoadGuard Frontend (phone mode)" window)
echo  On your PHONE (Chrome), open the https address above.
echo  1. Chrome warns "Your connection is not private":
echo     tap Advanced, then "Proceed" (it is your own laptop).
echo  2. Log in, open the menu, choose "Live camera", press Start, allow the camera.
echo.
echo  If Windows asks to allow Node.js on the network, tick PRIVATE networks and Allow.
echo ===================================================================
pause
