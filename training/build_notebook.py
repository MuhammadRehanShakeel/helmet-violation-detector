"""Builds train_roadguard_colab.ipynb from the cells below (keeps the notebook easy to review in Git)."""
import json, os

cells = []
def md(text): cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")})
def code(text): cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n")})

md("""
# RoadGuard: train the helmet & number-plate detector (free Colab GPU)

**What this notebook does (about 1 hour on a free T4 GPU):**
1. Downloads **6,562 real traffic images** from Roboflow Universe (CC BY 4.0) with 4 classes:
   `motorcyclist`, `helmet`, `no_helmet`, `plate`
2. Trains **YOLO11n** (the small, fast version that runs on a CPU laptop)
3. Measures accuracy on the **test images it never saw** (mAP, precision, recall per class)
4. Tests it on a **completely different dataset** from Kaggle, to see how well it works on new cameras
5. Exports the model to **ONNX** (runs on your laptop's CPU, no GPU needed) and downloads everything

**Before you start**
* `Runtime → Change runtime type → T4 GPU → Save`
* Click the 🔑 **Secrets** icon in the left bar and add (turn on "Notebook access" for each):
  * `ROBOFLOW_API_KEY`: from roboflow.com → Settings → API Keys (Private API Key)
  * `KAGGLE_API_TOKEN`: kaggle.com → Settings → API → **Generate New Token** (starts with `KGAT_`)
* Then `Runtime → Run all`. Your keys never appear in the notebook or on GitHub.
""")

code("""
# 1. Check the GPU and install the tools
!nvidia-smi --query-gpu=name,memory.total --format=csv
!pip -q install -U ultralytics==8.3.* roboflow "kaggle>=1.7.4" onnx onnxslim onnxruntime
import ultralytics; ultralytics.checks()
""")

code("""
# 2. Read your keys from Colab Secrets (never typed into the notebook)
import os
from google.colab import userdata

def secret(name):
    try:
        return userdata.get(name)
    except Exception:
        return None

os.environ["ROBOFLOW_API_KEY"] = secret("ROBOFLOW_API_KEY") or ""
# New Kaggle tokens (start with KGAT_) need only KAGGLE_API_TOKEN.
# Old-style kaggle.json keys need KAGGLE_USERNAME + KAGGLE_KEY. Either works.
if secret("KAGGLE_API_TOKEN"):
    os.environ["KAGGLE_API_TOKEN"] = secret("KAGGLE_API_TOKEN")
elif secret("KAGGLE_USERNAME") and secret("KAGGLE_KEY"):
    os.environ["KAGGLE_USERNAME"] = secret("KAGGLE_USERNAME")
    os.environ["KAGGLE_KEY"] = secret("KAGGLE_KEY")
kaggle_ok = bool(os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY"))
print("Roboflow key loaded:", bool(os.environ["ROBOFLOW_API_KEY"]))
print("Kaggle key loaded:  ", kaggle_ok, "(only needed for the cross-dataset test)")
""")

md("""
## Dataset 1 (training): Helmet Detection and License Plate Recognition
FPT University on Roboflow Universe, **CC BY 4.0**:
https://universe.roboflow.com/fpt-university-9oa0t/helmet-detection-and-license-plate-recognition-zfenu
""")

code("""
# 3. Download the newest version of the dataset in YOLO format
from roboflow import Roboflow
rf = Roboflow(api_key=os.environ["ROBOFLOW_API_KEY"])
project = rf.workspace("fpt-university-9oa0t").project("helmet-detection-and-license-plate-recognition-zfenu")

dataset, used_version = None, None
for v in range(12, 0, -1):                     # try the newest version first
    try:
        dataset = project.version(v).download("yolov11", location="/content/fpt")
        used_version = v
        break
    except Exception as e:
        pass
print("Downloaded version", used_version, "to", dataset.location)
""")

code("""
# 4. Rename the classes to RoadGuard's 4 names and make sure there is a test split
import glob, random, shutil, yaml
from pathlib import Path

TARGET = ["motorcyclist", "helmet", "no_helmet", "plate"]
ALIASES = {
    "motorcyclist": ["motorcyclist", "rider", "motorbike", "motorcycle"],
    "helmet": ["helmet", "withhelmet", "with helmet", "with_helmet"],
    "no_helmet": ["nohelmet", "no_helmet", "no-helmet", "withouthelmet", "without helmet", "without_helmet"],
    "plate": ["licenseplate", "license_plate", "license plate", "plate", "numberplate", "number plate"],
}
def target_id(name):
    key = name.strip().lower()
    for i, t in enumerate(TARGET):
        if key in ALIASES[t]:
            return i
    return None

def remap_dataset(root, names):
    mapping = {i: target_id(n) for i, n in enumerate(names)}
    print("Class mapping:", {names[i]: (TARGET[t] if t is not None else "DROPPED") for i, t in mapping.items()})
    counts = {t: 0 for t in TARGET}
    for cache in glob.glob(f"{root}/**/*.cache", recursive=True):
        os.remove(cache)
    for txt in glob.glob(f"{root}/**/*.txt", recursive=True):
        if "labels" not in Path(txt).parts:          # only label files (labels/x.txt or labels/train/x.txt)
            continue
        lines = []
        for line in open(txt).read().split("\\n"):
            parts = line.split()
            if len(parts) < 5:
                continue
            new = mapping.get(int(parts[0]))
            if new is None:
                continue
            values = [float(v) for v in parts[1:]]
            if len(values) > 4:                       # polygon -> its bounding box
                xs, ys = values[0::2], values[1::2]
                values = [(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)]
            lines.append(" ".join([str(new)] + [f"{v:.6f}" for v in values[:4]]))
            counts[TARGET[new]] += 1
        open(txt, "w").write("\\n".join(lines))
    return counts

root = Path(dataset.location)
info = yaml.safe_load(open(root / "data.yaml"))
box_counts = remap_dataset(str(root), info["names"])

split_dir = {s: root / s for s in ["train", "valid", "test"]}
if not (split_dir["test"] / "images").exists() or not any((split_dir["test"] / "images").iterdir()):
    # no test split: move 10% of train into a test folder (fixed seed = repeatable)
    imgs = sorted((split_dir["train"] / "images").glob("*"))
    random.Random(0).shuffle(imgs)
    for d in ["images", "labels"]:
        (split_dir["test"] / d).mkdir(parents=True, exist_ok=True)
    for img in imgs[: max(1, len(imgs) // 10)]:
        lab = split_dir["train"] / "labels" / (img.stem + ".txt")
        shutil.move(str(img), split_dir["test"] / "images" / img.name)
        if lab.exists():
            shutil.move(str(lab), split_dir["test"] / "labels" / lab.name)

data_yaml = "/content/roadguard.yaml"
yaml.safe_dump({"path": str(root), "train": "train/images", "val": "valid/images", "test": "test/images",
                "names": {i: n for i, n in enumerate(TARGET)}}, open(data_yaml, "w"))
split_sizes = {s: len(list((split_dir[s] / "images").glob("*"))) for s in split_dir}
print("Images per split:", split_sizes)
print("Boxes per class:", box_counts)
""")

code("""
# 5. Look at a few training images with their boxes (sanity check)
try:
    from ultralytics.data.utils import visualize_image_annotations
    for img in sorted((split_dir["train"] / "images").glob("*"))[:3]:
        visualize_image_annotations(str(img), str(split_dir["train"] / "labels" / (img.stem + ".txt")),
                                    {i: n for i, n in enumerate(TARGET)})
except Exception as e:
    print("Preview skipped:", e)
""")

md("""
## Train YOLO11n
* `yolo11n.pt` = pretrained on COCO (already knows people and motorbikes), we fine-tune it
* 60 epochs with early stopping (stops if it does not improve for 15 epochs)
* 640 px images, the same size the laptop app uses
""")

code("""
# 6. Train (about 45-70 minutes on a T4)
from ultralytics import YOLO
model = YOLO("yolo11n.pt")
model.train(data=data_yaml, epochs=60, patience=15, imgsz=640, batch=32, seed=0, deterministic=True,
            cos_lr=True, close_mosaic=10, project="/content/runs", name="roadguard", exist_ok=True,
            plots=True, workers=4)
""")

code("""
# 7. Accuracy on the TEST images (never seen during training)
import json
best = YOLO("/content/runs/roadguard/weights/best.pt")
def metrics_of(result, names):
    per_class = {}
    for i, c in enumerate(result.box.ap_class_index):
        p, r, ap50, ap = result.box.class_result(i)
        per_class[names[int(c)]] = {"precision": round(float(p), 3), "recall": round(float(r), 3),
                                    "mAP50": round(float(ap50), 3), "mAP50_95": round(float(ap), 3)}
    return {"mAP50": round(float(result.box.map50), 3), "mAP50_95": round(float(result.box.map), 3),
            "precision": round(float(result.box.mp), 3), "recall": round(float(result.box.mr), 3),
            "per_class": per_class}

test_result = best.val(data=data_yaml, split="test", imgsz=640, batch=32, plots=True,
                       project="/content/runs", name="test", exist_ok=True)
report = {"model": "YOLO11n", "image_size": 640, "dataset": "FPT University - Helmet Detection and License Plate "
          "Recognition (Roboflow Universe, CC BY 4.0)", "dataset_version": used_version,
          "images_per_split": split_sizes, "boxes_per_class": box_counts,
          "test": metrics_of(test_result, TARGET)}
print(json.dumps(report["test"], indent=2))
""")

md("""
## Dataset 2 (cross-dataset test only): HelmetViolations (Kaggle)
https://www.kaggle.com/datasets/pkdarabi/helmet. Different cameras, different country, labelled by different people.
The model never trains on it. If accuracy stays good here, the model **generalises** and is not just memorising one dataset.
This dataset has no `motorcyclist` label, so only `helmet`, `no_helmet` and `plate` are scored.
""")

code("""
# 8. Download the Kaggle dataset and score the model on it
if kaggle_ok:
    !kaggle datasets download -d pkdarabi/helmet -p /content/kaggle_helmet --unzip -q
cross_root = Path("/content/kaggle_helmet")
yamls = list(cross_root.rglob("data.yaml")) if cross_root.exists() else []
cross = None
if yamls:
    cinfo = yaml.safe_load(open(yamls[0]))
    names = cinfo["names"] if isinstance(cinfo["names"], list) else [cinfo["names"][k] for k in sorted(cinfo["names"])]
    croot = yamls[0].parent
    print("Kaggle classes:", names)
    remap_dataset(str(croot), names)
    # use every labelled image (train + valid + test) because none of it was used for training
    image_dirs = [str(p) for p in croot.rglob("images") if p.is_dir()]
    yaml.safe_dump({"path": str(croot), "train": image_dirs[0], "val": image_dirs,
                    "names": {i: n for i, n in enumerate(TARGET)}}, open("/content/cross.yaml", "w"))
    cross_result = best.val(data="/content/cross.yaml", split="val", imgsz=640, batch=32, plots=True,
                            project="/content/runs", name="cross", exist_ok=True)
    cross = metrics_of(cross_result, TARGET)
    cross["images"] = sum(len(list(Path(d).glob("*"))) for d in image_dirs)
    print(json.dumps(cross, indent=2))
else:
    print("Kaggle dataset layout not recognised - skipping the cross-dataset test")
report["cross_dataset_kaggle_helmetviolations"] = cross
""")

code("""
# 9. Export to ONNX for the laptop (CPU) and check the speed on Colab's CPU
import onnxruntime as ort, numpy as np, time
onnx_path = best.export(format="onnx", imgsz=640, simplify=True, opset=12)
final = "/content/roadguard_yolo11n.onnx"
shutil.copy(onnx_path, final)
session = ort.InferenceSession(final, providers=["CPUExecutionProvider"])
x = np.random.rand(1, 3, 640, 640).astype(np.float32)
session.run(None, {session.get_inputs()[0].name: x})
t = time.time()
for _ in range(10):
    session.run(None, {session.get_inputs()[0].name: x})
report["onnx_cpu_ms_colab"] = round((time.time() - t) / 10 * 1000, 1)
report["onnx_size_mb"] = round(os.path.getsize(final) / 1e6, 1)
print("ONNX:", report["onnx_size_mb"], "MB,", report["onnx_cpu_ms_colab"], "ms per image on Colab CPU")
""")

code("""
# 10. Keep 12 test images (with attribution) as demo pictures for the app
demo_dir = Path("/content/demo_images"); demo_dir.mkdir(exist_ok=True)
test_imgs = sorted((split_dir["test"] / "images").glob("*"))
random.Random(1).shuffle(test_imgs)
def label_classes(img):
    lab = split_dir["test"] / "labels" / (img.stem + ".txt")
    return {int(l.split()[0]) for l in open(lab).read().splitlines() if l.strip()} if lab.exists() else set()
with_violation = [i for i in test_imgs if 2 in label_classes(i)]          # 2 = no_helmet
others = [i for i in test_imgs if i not in with_violation and label_classes(i)]
picked = (with_violation[:8] + others)[:12]
for n, img in enumerate(picked):
    shutil.copy(img, demo_dir / f"demo_{n:02d}{img.suffix}")
open(demo_dir / "SOURCE.txt", "w").write(
    "Images from 'Helmet Detection and License Plate Recognition' by FPT University, Roboflow Universe, "
    "licensed CC BY 4.0: https://universe.roboflow.com/fpt-university-9oa0t/helmet-detection-and-license-plate-recognition-zfenu\\n")
if picked:
    best.predict(source=str(demo_dir), imgsz=640, conf=0.3, save=True, project="/content/runs", name="demo_predictions",
                 exist_ok=True)
print("Demo images:", len(picked))
""")

code("""
# 11. Save everything into one zip and download it
out = Path("/content/roadguard_results"); out.mkdir(exist_ok=True)
json.dump(report, open(out / "training_report.json", "w"), indent=2)
shutil.copy(final, out / "roadguard_yolo11n.onnx")
for f in ["results.png", "results.csv", "confusion_matrix_normalized.png", "BoxPR_curve.png", "PR_curve.png",
          "labels.jpg", "val_batch0_pred.jpg"]:
    for folder in ["/content/runs/roadguard", "/content/runs/test"]:
        p = Path(folder) / f
        if p.exists():
            shutil.copy(p, out / f"{Path(folder).name}_{f}")
for p in Path("/content/runs/cross").glob("*.png"):
    shutil.copy(p, out / f"cross_{p.name}")
shutil.copytree(demo_dir, out / "demo_images", dirs_exist_ok=True)
if Path("/content/runs/demo_predictions").exists():
    shutil.copytree("/content/runs/demo_predictions", out / "demo_predictions", dirs_exist_ok=True)
shutil.make_archive("/content/roadguard_results", "zip", out)
from google.colab import files
files.download("/content/roadguard_results.zip")
print(json.dumps({k: v for k, v in report.items() if k in ("test", "cross_dataset_kaggle_helmetviolations")}, indent=2))
""")

md("""
## Next
Unzip `roadguard_results.zip`, then copy:
* `roadguard_yolo11n.onnx` → `F:\\Portfolio\\helmet-violation-detector\\backend\\models\\`
* `training_report.json` and the `.png` charts → `evaluation\\results\\training\\`
* `demo_images\\` → `evaluation\\demo_images\\`
""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
      "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_roadguard_colab.ipynb")
json.dump(nb, open(path, "w"), indent=1)
print("Wrote", path)
