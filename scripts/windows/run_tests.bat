@echo off
REM Runs all backend tests and writes the result to test_results.txt
cd /d "%~dp0..\..\backend"
venv\Scripts\python.exe -m pytest tests -q -p no:warnings > "..\test_results.txt" 2>&1
type "..\test_results.txt"
pause
