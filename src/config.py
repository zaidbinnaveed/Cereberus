"""
Central configuration for Cereberus.
Change thresholds/paths here rather than hunting through other files.
"""

import os

# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")

EMBEDDINGS_PATH = os.path.join(DATA_DIR, "embeddings.pkl")
ACCESS_LOG_PATH = os.path.join(LOG_DIR, "access_log.csv")
SNAPSHOT_DIR = os.path.join(LOG_DIR, "intruder_snapshots")

# ---- Camera ----
CAMERA_INDEX = 0  # change to 1, 2... if you have multiple cameras

# ---- Recognition ----
# face_recognition uses a "distance" score, not a similarity percentage.
# Lower distance = more similar. 0.6 is the library's default; we go a
# bit stricter since this is an access-control use case, not a photo app.
MATCH_THRESHOLD = 0.5

# ---- Liveness (blink detection) ----
EAR_THRESHOLD = 0.21          # eye-aspect-ratio below this = "eye closed"
EAR_CONSEC_FRAMES = 2         # frames in a row below threshold to count as a blink
LIVENESS_TIMEOUT_SECONDS = 8  # if no blink detected in this window, flag as suspected spoof
