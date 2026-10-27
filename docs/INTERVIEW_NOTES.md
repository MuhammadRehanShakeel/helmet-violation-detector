# Interview notes: RoadGuard

## 30-second pitch
"RoadGuard detects motorcyclists riding without a helmet, or three on one bike, in traffic photos,
videos or a live phone camera, and reads their Pakistani number plates. I fine-tuned YOLO11n on 6.5k
labelled images on a free Colab GPU, exported it to ONNX so it runs on a normal laptop CPU, and built
the logic that turns boxes into violations: matching heads and plates to bikes, tracking bikes
across video frames so each one is counted once, and plate voting. An officer reviews every
detection before a PDF e-challan with a QR verification code is issued. Bystanders are blurred
automatically. It's FastAPI + SQL Server + React, with role-based access and 103 automated tests."

## Likely questions

**Why YOLO11n and not a bigger model?**
It has to run on a CPU laptop in real time. Nano is ~2.6M parameters and ~70 ms per frame on 2 CPU
cores in ONNX Runtime. A bigger model (s/m) is more accurate but 3-8× slower. Since I analyse 5 frames per
second and vote across frames, tracking recovers much of what a bigger model would add.

**Why ONNX?**
The backend then needs only `onnxruntime` (about 15 MB), not PyTorch (about 2 GB). That means a
faster start, less RAM on an 8 GB laptop, and the same file could run on a phone or an edge device.

**How do you know a head belongs to a particular bike?**
Containment, not just overlap: at least 50% of the head box must lie inside the bike box, and I
prefer the bike whose *upper* part contains it. The upper-part rule handles overlapping bikes in
dense traffic (`test_overlapping_bikes_head_goes_to_upper_part`).

**How do you avoid counting the same bike 20 times in a video?**
An IoU tracker. Each bike gets a track id. A violation is reported once per track, only if seen in
at least 2 frames, using the best frame as evidence.

**How accurate is the plate reading?**
On 400 held-out synthetic Pakistani plates (4 difficulty levels, 5 plate styles): see
`evaluation/RESULTS.md`. Raw OCR gets the plate exactly right only about a third of the time, mostly
because it reads "PUNJAB" and the registration year too. My position-aware clean-up raises that a lot.
The important number is **precision of accepted plates**: when the system says "I read this plate",
how often it is right. I tuned the confidence threshold on a separate *dev* set, so the *test* number
is honest.

**Why synthetic plates?**
There is no public labelled dataset of Pakistani *motorcycle* plates. Synthetic data gives an exact
ground truth and lets me control difficulty (distance, blur, darkness, JPEG quality). The limitation:
real plates are dirtier, bent and use different fonts, so real accuracy will be lower. The officer
review step and the plate-correction box exist exactly for this.

**What is your false-positive strategy?**
1. A confidence threshold, plus a "low confidence, check carefully" flag.
2. "Unclear" instead of guessing when no head is visible.
3. At least 2 frames in videos.
4. Human approval before any fine.
5. Measuring it in production: officer agreement (approved ÷ reviewed) on the dashboard.

**How did you test generalisation?**
A cross-dataset test: a different Kaggle dataset (other cameras, other annotators) that was never
used in training. A drop from the in-domain test score shows the domain gap. The fix would be
fine-tuning on a few hundred local Pakistani images.

**Privacy / ethics?**
Bystanders are blurred. Viewers see masked plates. Evidence is not publicly reachable. There is an
audit log of every decision. The AI only *suggests*; a human decides. The PDF states it is a demo,
not an official document.

**Security?**
bcrypt and account lockout, JWT with the user re-checked on every request, role checks, 404 for other
users' jobs, magic-byte upload validation, path-traversal guard, parameterised SQL, rate limits,
random QR codes, gitleaks in CI.

**What would you do next?**
* Collect and label ~500 local Rawalpindi/Islamabad frames, then fine-tune again.
* A dedicated plate-OCR model trained on Pakistani fonts.
* Run on an edge device at the camera (ONNX on a Jetson or Raspberry Pi with a Hailo accelerator),
  sending only violations to the server.
* SMS the challan to the registered owner (needs an Excise & Taxation database API).

## Numbers to remember
* Detector: **94.3% mAP50** on 328 unseen test images; no_helmet **94.3% precision, 88.7% recall**
* Cross-dataset: 8.7% mAP50, explained by a different labelling style (whole rider vs head)
* Full pipeline: caught 8/8 no-helmet riders on demo photos, only after I added the backup detector
* Plates: **87.5% exact**, **96.7% precision** on accepted plates (400 held-out synthetic plates)
* Speed: ~70-90 ms per frame on 2 CPU cores; 10.6 MB model
* 103 automated tests, CI on every push

## The best story to tell
"mAP said 94%, but when I ran the whole pipeline on demo photos it missed 7 of 12 violations. The
model found the bare heads, but not the motorcyclist boxes, because part of the training data never
labelled motorcyclists. My rules need a bike to attach a head to, so nothing was reported. I added a
backup: when a head has no bike, the COCO-pretrained YOLO finds motorcycles and people and I build
the rider box from those. After that it caught 8 of 8, and the extra model only runs when needed.
Lesson: test the system end to end, not just the model's metric."
