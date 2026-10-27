# Evaluation

| Script | Measures | Run |
|---|---|---|
| `eval_plates.py` | number-plate OCR + clean-up on 400 held-out synthetic Pakistani plates | `python evaluation/eval_plates.py test` |
| `benchmark_speed.py` | detector and OCR speed on this CPU | `python evaluation/benchmark_speed.py backend/models/roadguard_yolo11n.onnx` |
| `make_synthetic_plates.py` | regenerates the dev (seed 42) and test (seed 7) plate sets | `python evaluation/make_synthetic_plates.py` |
| `../training/train_roadguard_colab.ipynb` | detector mAP on the test split + cross-dataset test | Google Colab |

On Windows just double-click `scripts\windows\run_evaluation.bat`. Results go to `evaluation/results/` and are
summarised in `RESULTS.md`.

**Dev vs test:** every rule and threshold was tuned on the *dev* plates only. The *test* plates were
used once, for the final numbers, so they are not optimistic.
