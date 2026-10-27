@echo off
REM Cuts your videos in training\local_videos into frames and pre-labels them with the current model.
cd /d "%~dp0..\.."
if not exist training\local_videos mkdir training\local_videos
backend\venv\Scripts\python.exe training\prepare_local_data.py
start "" "training"
pause
