"""
Handles everything that happens on a decision: beeping, saving an
intruder snapshot, and writing a row to the access log CSV.

Uses Windows' built-in winsound for the beep (zero extra installs,
zero dependency headaches). Falls back to playsound only if winsound
isn't available (e.g. if this ever runs on Mac/Linux).
"""

import csv
import os
from datetime import datetime

import cv2

from . import config

try:
    import winsound
    _HAS_WINSOUND = True
except ImportError:
    _HAS_WINSOUND = False
    try:
        from playsound import playsound
    except ImportError:
        playsound = None


def _ensure_dirs():
    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)


def play_alarm_sound():
    if _HAS_WINSOUND:
        winsound.Beep(1000, 400)
        winsound.Beep(1400, 400)
    elif playsound:
        pass  # hook up a custom .wav/.mp3 here later if you want


def log_event(status, name, distance, snapshot_path=None):
    _ensure_dirs()
    file_exists = os.path.exists(config.ACCESS_LOG_PATH)
    with open(config.ACCESS_LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "status", "name", "distance", "snapshot"])
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            status,
            name or "",
            f"{distance:.4f}" if distance is not None else "",
            snapshot_path or "",
        ])


def save_snapshot(frame):
    _ensure_dirs()
    filename = f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = os.path.join(config.SNAPSHOT_DIR, filename)
    cv2.imwrite(path, frame)
    return path


def trigger_denied(frame, name=None, distance=None):
    snapshot_path = save_snapshot(frame)
    log_event("DENIED", name, distance, snapshot_path)
    play_alarm_sound()
    return snapshot_path


def trigger_spoof(frame, name=None, distance=None):
    snapshot_path = save_snapshot(frame)
    log_event("SPOOF_SUSPECTED", name, distance, snapshot_path)
    play_alarm_sound()
    return snapshot_path


def log_granted(name, distance):
    log_event("GRANTED", name, distance)
