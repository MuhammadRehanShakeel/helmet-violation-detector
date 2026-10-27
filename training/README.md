# Training the RoadGuard model

`train_roadguard_colab.ipynb` trains the detector on a free Google Colab GPU in about an hour.

1. Open https://colab.research.google.com → **File → Upload notebook** → choose this file
   (or, once the repo is on GitHub: **File → Open notebook → GitHub** → paste the repo URL).
2. **Runtime → Change runtime type → T4 GPU**.
3. 🔑 **Secrets** (left bar) → add `ROBOFLOW_API_KEY` and `KAGGLE_API_TOKEN` (or the old `KAGGLE_USERNAME` + `KAGGLE_KEY`) and switch on
   *Notebook access* for each. Your keys stay in your Google account; they are never written in the notebook.
4. **Runtime → Run all**. At the end `roadguard_results.zip` downloads.
5. Copy `roadguard_yolo11n.onnx` into `backend/models/`.

The notebook is generated from `build_notebook.py` (easier to review in Git). If you change the
training, edit that file and run `python training/build_notebook.py`.

| Setting | Value | Why |
|---|---|---|
| Model | YOLO11n, COCO-pretrained | small enough for a CPU laptop |
| Image size | 640 | same as the app uses |
| Epochs | 60, stops early after 15 epochs without improvement | about 1 h on a T4 |
| Augmentation | Ultralytics defaults (mosaic, HSV, flip, scale), mosaic off for the last 10 epochs | |
| Seed | 0, deterministic | repeatable |

## Make it better on Pakistani roads (your own videos)

1. Record 2-3 short videos (1-2 minutes) of motorbike traffic in Rawalpindi / Islamabad from the roadside
   (phone held steady, 5-15 m from the road). Put them in `training/local_videos/`.
2. Double-click `scripts\windows\prepare_local_data.bat` (or run `training/prepare_local_data.py`).
   It saves ~1 frame per second, skips near-duplicates, and lets the current model **pre-draw the boxes**
   in `training/local_dataset/`.
3. roboflow.com → **New project** (Object detection) → **Upload** → choose the `local_dataset` folder.
   Check every image: fix wrong boxes, add missed ones, delete false ones. Then **Generate** a version.
4. In the notebook set `LOCAL_PROJECT = "your-workspace/your-project/1"` and **Run all**.
   Upload your current `roadguard_yolo11n.onnx` to Colab's file panel first to get a before/after
   comparison on your local test images (`local_test_old_model` vs `local_test_new_model`).

Local videos and frames are git-ignored (they show real people and real plates).
