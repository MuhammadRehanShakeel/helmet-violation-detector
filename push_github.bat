@echo off
REM FIRST upload of RoadGuard to GitHub. Create an EMPTY repository first:
REM   github.com -> New repository -> name: helmet-violation-detector -> no README -> Create
cd /d "%~dp0"
where git >nul 2>nul || (echo Git is not installed. & pause & exit /b 1)
if not exist .git git init
git branch -M main
git add .
git status --short
echo.
echo Check the list above: no .env, no DEMO_ACCOUNT.txt, no venv, no node_modules, no backend\data.
pause
git commit -m "RoadGuard: helmet and number-plate violation detection (YOLO11 + OCR + e-challans)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_01QVx4BnmKHCrVzhdkVSq8XP"
git remote remove origin 2>nul
git remote add origin https://github.com/MuhammadRehanShakeel/helmet-violation-detector.git
git push -u origin main
pause
