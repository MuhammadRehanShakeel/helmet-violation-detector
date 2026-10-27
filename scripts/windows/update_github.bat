@echo off
REM Upload new changes to GitHub.
cd /d "%~dp0..\.."
git rm -r -q --cached . >nul
git add .
git status --short
set MSG=
set /p MSG=Short description of the change: 
if "%MSG%"=="" set MSG=Update
git commit -m "%MSG%"
git push
pause
