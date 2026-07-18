# Cereberus Backend

Modular backend for the face-gated access control system. No UI polish here on
purpose — this is the logic layer, built so a UI (yours or your friend's) can
be swapped in on top without touching any of this code.

## Folder structure

```
Cereberus/
├── venv/                    (already set up)
├── data/
│   └── embeddings.pkl       (created automatically on first enrollment)
├── logs/
│   ├── access_log.csv       (created automatically)
│   └── intruder_snapshots/  (created automatically)
├── src/
│   ├── __init__.py
│   ├── config.py            <- thresholds & paths live here
│   ├── database.py          <- enrolled-user storage
│   ├── recognizer.py        <- face detection/encoding/matching
│   ├── liveness.py          <- blink-based anti-spoofing
│   ├── alarm.py             <- beep + snapshot + CSV logging
│   ├── enroll.py            <- run this to register a person
│   └── main.py              <- CereberusEngine + debug loop
└── README.md
```

## Installation

Copy the `src/` folder and this `README.md` straight into your existing
`Cereberus` project folder (the one with `venv/` already set up). Nothing new
needs to be pip-installed — this uses only what you already have:
`opencv-python`, `face_recognition`, `numpy`.

## Step 1 — Enroll yourself (and anyone else authorized)

From the `Cereberus` folder, with your venv active:

```cmd
python -m src.enroll "Zaid"
```

A window opens showing your webcam with a green box around your face.
Move your head slightly between captures (look left, right, up, down, then
straight) and press **SPACE** each time to capture a sample — 5 total. Press
**ESC** to cancel without saving.

Repeat this command with a different name for anyone else who should be
authorized.

## Step 2 — Run the backend test loop

```cmd
python -m src.main
```

This opens a plain debug window (just a colored box + status text — the real
scan-line visual comes later in the UI layer). It cycles through:

- **NO_FACE** (gray) — nothing detected
- **SCANNING** (yellow) — a known face was matched, waiting for a blink to confirm liveness
- **VERIFIED** (green) — blink confirmed, access granted, logged
- **DENIED** (red) — face doesn't match anyone enrolled, alarm + snapshot + logged
- **SPOOF_SUSPECTED** (red) — matched a known face but never blinked within 8 seconds (likely a held-up photo), alarm + snapshot + logged

Press **ESC** to quit.

## Step 3 — Check the logs

After testing, look in `logs/access_log.csv` — every decision gets a row
with timestamp, status, matched name, and match distance. Denied/spoof
attempts also save a snapshot into `logs/intruder_snapshots/`.

## Tuning

All the knobs live in `src/config.py`:

| Setting | What it controls |
|---|---|
| `MATCH_THRESHOLD` | Lower = stricter matching (fewer false accepts, more false rejects) |
| `EAR_THRESHOLD` | How closed an eye must be to count as "blinking" |
| `LIVENESS_TIMEOUT_SECONDS` | How long to wait for a blink before flagging as spoof |

If it's rejecting you too often, raise `MATCH_THRESHOLD` slightly (e.g. 0.5 →
0.55). If it's letting strangers through, lower it.

## The interface your friend's UI should call

```python
from src.main import CereberusEngine

engine = CereberusEngine()

# in your UI's frame loop:
result = engine.process_frame(frame)  # frame = a BGR numpy array from OpenCV

# result = {
#     "status": "NO_FACE" | "SCANNING" | "VERIFIED" | "DENIED" | "SPOOF_SUSPECTED",
#     "name": str or None,
#     "distance": float or None,
#     "box": (top, right, bottom, left) or None,
#     "landmarks": dict or None,   # eye/nose/mouth points, for drawing custom overlays
# }
```

`landmarks` is the raw output of `face_recognition.face_landmarks()` — it has
keys like `left_eye`, `right_eye`, `nose_bridge`, `chin`, etc. Perfect for
drawing the corner-bracket / scan-line HUD on top of `box` and `landmarks`
without needing to touch any backend logic.

## What's intentionally NOT done yet

- No fancy visuals (scan line, corner brackets) — that's UI-layer work
- Only handles one face per frame (first detected) — fine for a single-person gate
- No web API wrapper — if your friend needs a REST endpoint instead of
  calling `process_frame()` directly in Python, that's a thin FastAPI wrapper
  we can add later without changing anything in `src/`
