# AI model

Put the trained model here as **`roadguard_yolo11n.onnx`** (about 10 MB).

How to get it:
1. Open `training/train_roadguard_colab.ipynb` in Google Colab (free T4 GPU).
2. Add your Roboflow and Kaggle keys in Colab **Secrets** and press **Run all** (about 1 hour).
3. Unzip the downloaded `roadguard_results.zip` and copy `roadguard_yolo11n.onnx` into this folder.

The model file is not stored in Git (it is a build output, like a compiled program).
