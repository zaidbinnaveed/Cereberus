"""
Core Cereberus engine.

CereberusEngine.process_frame(frame) is the ONE function your friend's
UI layer needs to call. It takes a raw BGR frame (from cv2.VideoCapture,
a Flask upload, anything) and returns a plain dict - no drawing, no
OpenCV windows, no side-effecting UI logic. That separation is
deliberate: it means the UI can be a desktop app, a web app, or
anything else, without touching this file.

Run this file directly for a plain debug window (plain rectangle,
plain text) just to prove the backend logic works end-to-end:
    python -m src.main
"""

import cv2
import face_recognition

from . import alarm, config, database, recognizer
from .liveness import LivenessDetector
from .hud import ScanHUD


class CereberusEngine:
    def __init__(self):
        self.db = database.load_embeddings()
        self.liveness = LivenessDetector(
            ear_threshold=config.EAR_THRESHOLD,
            consec_frames=config.EAR_CONSEC_FRAMES,
            timeout_seconds=config.LIVENESS_TIMEOUT_SECONDS,
        )

    def reload_db(self):
        """Call this after enrolling a new user without restarting the process."""
        self.db = database.load_embeddings()

    def process_frame(self, frame):
        """
        frame: BGR numpy array (as read from cv2.VideoCapture)

        Returns:
        {
            "status": "NO_FACE" | "SCANNING" | "VERIFIED" | "DENIED" | "SPOOF_SUSPECTED",
            "name": str or None,
            "distance": float or None,      # lower = more confident match
            "box": (top, right, bottom, left) or None,
            "landmarks": dict or None        # raw face_recognition landmarks, for UI overlays
        }
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = recognizer.get_face_locations(rgb)

        if not locations:
            self.liveness.reset()
            return {"status": "NO_FACE", "name": None, "distance": None,
                    "box": None, "landmarks": None}

        # Only the first detected face is handled for now (single-person gate).
        location = locations[0]
        landmarks_list = face_recognition.face_landmarks(rgb, [location])
        landmarks = landmarks_list[0] if landmarks_list else None

        encoding = recognizer.get_face_encoding(rgb, location)
        name, distance = recognizer.match_encoding(encoding, self.db)
        matched = recognizer.is_match(name, distance)

        if not matched:
            alarm.trigger_denied(frame, name, distance)
            self.liveness.reset()
            return {"status": "DENIED", "name": name, "distance": distance,
                    "box": location, "landmarks": landmarks}

        # Known face -> still require a blink before granting, to catch
        # someone holding up a photo of an authorized person.
        is_live = self.liveness.update(landmarks)

        if is_live:
            alarm.log_granted(name, distance)
            self.liveness.reset()
            return {"status": "VERIFIED", "name": name, "distance": distance,
                    "box": location, "landmarks": landmarks}

        if self.liveness.timed_out():
            alarm.trigger_spoof(frame, name, distance)
            self.liveness.reset()
            return {"status": "SPOOF_SUSPECTED", "name": name, "distance": distance,
                    "box": location, "landmarks": landmarks}

        return {"status": "SCANNING", "name": name, "distance": distance,
                "box": location, "landmarks": landmarks}


# ---------------------------------------------------------------------------
# Debug loop - uses ScanHUD (corner brackets + sweeping scan line + status
# label) so you can see the real intended look while the backend is being
# tested. Note this loop only ever READS result - the HUD never feeds
# anything back into process_frame(). Your friend's UI can keep using
# ScanHUD as-is, or replace it with their own renderer built on the same
# process_frame() output.
# ---------------------------------------------------------------------------

def run_debug_loop():
    engine = CereberusEngine()
    hud = ScanHUD()
    cam = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cam.isOpened():
        print("Could not open webcam. Check CAMERA_INDEX in src/config.py.")
        return

    print("Cereberus backend debug loop running. Press ESC to quit.")
    if not database.list_users():
        print("WARNING: no users enrolled yet. Run 'python -m src.enroll' first.")

    while True:
        ret, frame = cam.read()
        if not ret:
            continue

        result = engine.process_frame(frame)
        frame = hud.draw(frame, result)

        cv2.imshow("Cereberus - Backend Debug", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_debug_loop()
