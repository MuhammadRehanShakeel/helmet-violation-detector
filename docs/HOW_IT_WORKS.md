# How RoadGuard works

A plain-language walk through the whole system, from a photo to a printed e-challan.

## 1. The big picture

```
 Photo / video / phone camera
          │
          ▼
 ┌──────────────────┐   finds 4 kinds of boxes:
 │ YOLO11n detector │   motorcyclist · helmet · no_helmet · plate
 │ (ONNX, CPU)      │
 └────────┬─────────┘
          ▼
 ┌──────────────────┐   which head and which plate belong to which bike?
 │ Rules            │   no_helmet on a bike → NO_HELMET
 │ (pure Python)    │   3+ heads on a bike  → TRIPLE_RIDING
 └────────┬─────────┘
          ▼  (videos and live camera only)
 ┌──────────────────┐   the same bike over many frames = ONE violation
 │ Tracker          │   must break the rule in ≥ 2 frames
 │ + plate voting   │   the most common plate reading wins
 └────────┬─────────┘
          ▼
 ┌──────────────────┐   RapidOCR reads the plate, then our clean-up
 │ Plate OCR        │   fixes PUNJAB / year / 0-O / 1-I mistakes
 └────────┬─────────┘
          ▼
 ┌──────────────────┐   bystanders' heads and plates are blurred
 │ Evidence photos  │
 └────────┬─────────┘
          ▼
 SQL Server  →  officer reviews  →  approve  →  PDF e-challan with QR code
```

Nothing goes to the internet. The model, the OCR and the database all run on your laptop.

## 2. The AI model: what it learned

* **YOLO11n** ("nano") is the smallest model in the YOLO11 family: 2.6 million parameters, a 10 MB file.
* It started from Ultralytics' COCO weights (it already knew "person" and "motorcycle") and was
  **fine-tuned** on 6,562 labelled traffic photos (Roboflow Universe, FPT University, CC BY 4.0).
* Training ran on a free Google Colab T4 GPU (`training/train_roadguard_colab.ipynb`).
* It was exported to **ONNX**, a standard format that **ONNX Runtime** runs fast on a normal CPU.
  The backend does not need PyTorch, which saves about 2 GB of disk space and RAM.

`backend/app/services/detector.py` does three things:
1. **Letterbox**: shrink the photo to fit 640×640 *without stretching it* (grey bars fill the rest).
2. **Run the model**: it returns 8,400 candidate boxes, each with a score per class.
3. **Decode + NMS**: keep boxes scoring above 0.30, convert them back to the photo's coordinates,
   and remove duplicates (Non-Maximum Suppression keeps the best box when several overlap > 50%).

### Backup bike finder
Part of the training data labels heads but not the motorcyclist, so sometimes the model finds a bare
head with no bike box around it. When that happens (and only then), a second model, the standard
COCO-pretrained YOLO11n (`models/yolo11n_coco.onnx`), finds `motorcycle` and `person` boxes, and
`rules.bikes_from_coco()` joins each motorcycle with the people sitting on it into a rider box.
A head that is still not on any bike (a pedestrian) is ignored.

## 3. Rules: turning boxes into violations (`rules.py`)

The model only says "there is a no_helmet head here". It does not know which bike that head is on.

* **Heads → bikes**: a head belongs to the bike box it is *inside* (at least 50% of it), preferring
  the bike whose *upper* part it is in. This matters when two bikes overlap in traffic.
* **Plates → bikes**: same idea, preferring the *lower* part of the bike box.
* **Duplicate heads**: sometimes the model puts both a `helmet` and a `no_helmet` box on one head.
  We keep the more confident one.
* **Verdicts**:
  * any `no_helmet` head → `NO_HELMET` (the pillion passenger counts too; that is the law)
  * 3 or more heads → `TRIPLE_RIDING`
  * no heads found → `unclear`. We **never guess**: a blurry bike is not a violation.
* A bare head that is **not on any bike** (a pedestrian) is ignored.

## 4. Videos: tracking (`tracker.py`)

A bike visible for 3 seconds appears in about 15 analysed frames (we analyse 5 frames per second).
Without tracking that would be 15 violations.

* Each bike is matched to the bike in the previous frame with the biggest box overlap (IoU ≥ 0.30).
  Unmatched bikes start a new track; a track ends after 10 frames without the bike.
* A violation must appear in **at least 2 frames** of the same track. One odd frame
  (motion blur, a hand covering the helmet) is not enough. This cuts false alarms.
* **Scene cuts**: edited videos jump from place to place. When the picture changes completely between
  two analysed frames, all tracks are ended, so a bike in a new scene is never joined to an old one.
* **Plate voting**: the plate is read in up to 8 frames, and the most common clean reading wins,
  weighted by OCR confidence. One bad frame cannot change the number on the challan.
* The **best frame** (highest confidence) becomes the evidence photo.

The **live camera** uses the same tracker, fed with one frame per second from the phone or webcam.

## 5. Number plates (`plates.py`)

1. The plate box is cut out with a 10% margin, enlarged to at least 96 px high, and contrast-boosted
   (CLAHE).
2. **RapidOCR** (PaddleOCR models in ONNX) finds and reads the text lines, top line first, because
   motorcycle plates have two lines.
3. **Clean-up** (`normalise_plate`). Pakistani plates are *letters (2-4) + digits (1-4)*, so:
   * remove printed words: PUNJAB, SINDH, ICT ... and also OCR misreads of them (PUNIAB, PUNJAG)
   * remove the small registration year: `LEA 19 1234 → LEA-1234`
   * fix look-alikes depending on the position: `0→O, 4→A, 8→B` in the letter part,
     `O→0, I→1, S→5, B→8` in the digit part
   * fix the OCR's habit of doubling the first digit across the gap: `HU5 552 → HU-552`
4. Plates read with less than 75% OCR confidence are marked **unreadable**. The officer must
   type them before approving. A wrong plate on a challan is worse than no plate.

## 6. Privacy

* **Bystanders are blurred** in every evidence photo: the heads and plates of all bikes that broke
  no rule. Only the offender stays clear.
* **Viewers** (read-only users) see plates as `LEA-**34` and cannot open plate photos.
* Evidence photos are **not public files**. They are served only to logged-in users through
  `GET /violations/{id}/image/...`.
* The public QR verification page shows only what is printed on the ticket (with a masked plate).

## 7. Human in the loop

The AI never fines anyone by itself:

```
pending ──officer approves──► approved ──officer issues──► e-challan (PDF)
   └─────officer rejects────► rejected
```

* The officer can **correct the plate** before approving. The correction is validated and written
  to the audit log.
* After a challan is issued the violation is **locked**.
* The dashboard's **"officer agreement"** (approved ÷ reviewed) is the real-world precision of the
  AI. It is the number to watch after deploying at a new camera.

## 8. Security

| Threat | Protection |
|---|---|
| Password guessing | bcrypt hashes, 5 wrong tries lock the account for 15 min, login rate limit (10/min/IP), same error for wrong email and wrong password |
| Stolen / old token | JWT expires after 2 h; the user is re-read from the DB on every request, so a disabled account is blocked at once |
| Officer doing admin things | role checks on every route (`ADMIN`, `OFFICER`, `ANY_USER` in `core/auth.py`) |
| Seeing someone else's job | returns 404 (not 403), so the job's existence is not revealed |
| Malicious upload | extension + magic-byte check, the file must really open as image/video, size and length limits, random file names |
| Path traversal (`../../`) | evidence files are looked up by database id, and the real path must stay inside the evidence folder |
| SQL injection | every query uses `?` parameters (`database.py`) |
| Flooding | global rate limit (600/min/IP), live camera limit (120 frames/min) |
| Fake challans | random 24-character verify code in the QR, checked against the database |
| Leaked secrets | `.env` is git-ignored; CI runs gitleaks on every push |
| Tampering | audit log of logins, reviews, plate corrections, challans and user changes |

## 9. Where the data lives

| What | Where |
|---|---|
| Users, cameras, jobs, violations, challans, audit log | SQL Server database `RoadGuard` |
| Uploaded photos/videos | `backend/data/uploads/` (random names) |
| Evidence photos | `backend/data/evidence/` |
| E-challan PDFs | `backend/data/challans/` |
| Model | `backend/models/roadguard_yolo11n.onnx` |

## 10. Online vs offline

| Part | Needs internet? |
|---|---|
| Detection, OCR, tracking, challans, dashboard | **No**, everything runs locally |
| First-time `pip install` / `npm install` | Yes (once) |
| Training the model | Yes: Google Colab + Roboflow/Kaggle downloads (once) |
| Android app | Same Wi-Fi as the PC that runs the backend |

## 11. Version 2: running it like a real control room

**CCTV / IP cameras (`services/streams.py`).** Each watched camera gets its own background thread.
It opens the stream with OpenCV (RTSP over TCP, with timeouts), takes 2 frames per second, and feeds
them to the same `VideoSession` used for uploaded videos, so tracking, plate voting and the
"at least 2 frames" rule are identical. If the stream drops, it waits 2 s, then 4, 8 ... up to 30 s
and tries again. The newest frame (with boxes) is kept in memory as a JPEG for the live wall.
Stream passwords are never sent back to the browser (`rtsp://***@...`).
`demo:demo_traffic.mp4` loops a video file so the feature can be shown without a real camera.

**Live notifications (`services/events.py`, `routes/event_routes.py`).** Server-Sent Events: the
browser keeps one HTTP request open and the server writes a line whenever something happens.
Simpler than WebSockets because data only goes one way. The detector runs in worker threads, so
events are handed to the web server's loop with `call_soon_threadsafe`. Viewers get masked plates.
The frontend reads the stream with `fetch` (not `EventSource`) so the login token stays in a header.

**Accounts.** Nobody signs up by themselves. A person fills "request access"; an admin approves and
gets a one-time temporary password; the first login is forced to the Profile page to change it.
Every token carries a `tv` (token version). Changing the password or "log out everywhere" adds 1, so
all old tokens stop working at once.

**Citizen portal (`routes/citizen_routes.py`).** A citizen types the plate *and* the challan number
(either alone could be guessed). They get a 30-minute token for that one challan: see the photo,
pay (demo) or appeal. Appeals go to officers; "accepted" cancels the challan.

**Map and reports (`routes/report_routes.py`).** Cameras with GPS are drawn on OpenStreetMap,
bigger and redder where there are more violations. Officers can download a one-page PDF summary
or all rows as CSV for Excel (cells starting with `=` `+` `-` `@` are escaped, so a fake plate
cannot run an Excel formula).
