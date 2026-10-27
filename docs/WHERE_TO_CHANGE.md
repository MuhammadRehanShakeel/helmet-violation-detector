# Where to change things

| I want to... | Change this | File |
|---|---|---|
| Change a fine amount | `FINES` | `backend/app/config.py` |
| Add a new province word printed on plates | `PLATE_IGNORE_WORDS` | `backend/app/config.py` |
| Make detection stricter / looser | `DETECT_CONFIDENCE` (0.30) | `backend/app/config.py` |
| Change when a violation gets the "check carefully" flag | `LOW_CONFIDENCE` (0.55) | `backend/app/config.py` |
| Accept more / fewer OCR plates automatically | `PLATE_MIN_CONFIDENCE` (0.75) | `backend/app/config.py` |
| Count 2 people as "triple riding" (e.g. for a different law) | `TRIPLE_RIDING_MIN` | `backend/app/config.py` |
| Analyse more / fewer video frames per second | `VIDEO_SAMPLE_FPS` (5) | `backend/app/config.py` |
| Require more frames before a video violation counts | `MIN_VIOLATION_FRAMES` (2) | `backend/app/config.py` |
| Use a model trained with different class names | add the names to `CLASS_ALIASES` | `backend/app/config.py` |
| Use a different model file | `MODEL_FILE=` | `backend/.env` |
| Turn the backup bike finder off | `USE_BIKE_FALLBACK = False` | `backend/app/config.py` |
| Use more CPU cores | `CPU_THREADS=` | `backend/.env` |
| Change the login lockout | `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCK_MINUTES` | `backend/app/config.py` |
| Change upload limits | `MAX_IMAGE_MB`, `MAX_VIDEO_MB`, `MAX_VIDEO_SECONDS` | `backend/app/config.py` |
| Change the name printed on e-challans | `CHALLAN_AUTHORITY=` | `backend/.env` |
| Change the e-challan layout | `make_pdf()` | `backend/app/services/challan.py` |
| Add a new violation type (e.g. "no side mirror") | 1. train the class, 2. a rule in `judge()`, 3. `FINES` + `VIOLATION_LABELS`, 4. the `CHECK` constraint in `schema.sql` | `rules.py`, `config.py`, `schema.sql` |
| Change how heads are matched to bikes | `_best_owner()` | `backend/app/services/rules.py` |
| Change plate clean-up rules | `normalise_plate()` + add a test case | `backend/app/services/plates.py`, `tests/test_plates.py` |
| Change the blur on bystanders | `blur_region()` / `make_evidence()` | `backend/app/services/evidence.py` |
| Change colours / fonts of the app | `colors`, `theme` | `frontend/src/theme.js` |
| Add a menu item | `MENU` | `frontend/src/components/Layout.jsx` |
| Change frames per second of the live camera | `FRAME_EVERY_MS` | `frontend/src/pages/LiveCamera.jsx` |
| Change ports | `API_PORT` in `.env` + `vite.config.js` | both |
| Retrain with more data | add datasets in the notebook (step 3/4), run all | `training/train_roadguard_colab.ipynb` |

After any backend change, run `run_tests.bat`. All tests must pass.
