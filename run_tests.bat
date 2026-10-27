@echo off
REM Runs all backend tests and writes the result to test_results.txt
cd /d "%~dp0backend"
venv\Scripts\python.exe -m pytest tests -q -p no:warnings > "%~dp0test_results.txt" 2>&1
type "%~dp0test_results.txt"
pause
