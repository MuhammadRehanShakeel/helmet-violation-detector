@echo off
REM Measures plate-reading accuracy and the speed of the AI on THIS laptop.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Number plate OCR on 400 held-out synthetic Pakistani plates (about 3 minutes) ...
backend\venv\Scripts\python.exe evaluation\eval_plates.py test > eval_log.txt 2>&1
echo Speed test on this CPU ...
backend\venv\Scripts\python.exe evaluation\benchmark_speed.py backend\models\roadguard_yolo11n.onnx laptop >> eval_log.txt 2>&1
type eval_log.txt
pause
