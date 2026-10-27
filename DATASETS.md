# Datasets and credits

| Use | Dataset | Size | Classes | Licence |
|---|---|---|---|---|
| **Training + test** | [Helmet Detection and License Plate Recognition](https://universe.roboflow.com/fpt-university-9oa0t/helmet-detection-and-license-plate-recognition-zfenu), FPT University, Roboflow Universe | 6,562 images | helmet, licenseplate, motorcyclist, nohelmet | CC BY 4.0 |
| **Cross-dataset test only** (never trained on) | [HelmetViolations](https://www.kaggle.com/datasets/pkdarabi/helmet), Kaggle | ~1,000 images | WithHelmet, WithoutHelmet, Plate | see the Kaggle page |
| **Plate OCR test** | Synthetic Pakistani plates, made by `evaluation/make_synthetic_plates.py` | 400 dev + 400 test | text | MIT (this repo) |
| Base model + backup bike finder | [Ultralytics YOLO11n](https://github.com/ultralytics/ultralytics), COCO-pretrained | | person, motorcycle, ... | AGPL-3.0 |
| Plate OCR model | [RapidOCR](https://github.com/RapidAI/RapidOCR) (PP-OCR models in ONNX) | | | Apache-2.0 |
| Fonts for synthetic plates | DejaVu Sans, Liberation Sans | | | free font licences |

The datasets are **not stored in this repository**. The Colab notebook downloads them with your own
free Roboflow / Kaggle keys. The demo photos in `evaluation/demo_images/` come from the test split of
the FPT dataset (CC BY 4.0, credit above).

**Note on Ultralytics:** YOLO11 is AGPL-3.0. That is fine for an open-source portfolio project.
A closed commercial product would need an Ultralytics licence or a differently licensed detector.
