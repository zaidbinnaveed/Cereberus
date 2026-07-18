"""
Simple, dependency-free liveness check: watches the eye-aspect-ratio (EAR)
over consecutive frames and waits for a blink. A static photo or a video
replayed on a phone screen won't blink on cue within the timeout window,
which is enough to catch the common "hold up a picture" spoof attempt.

This is intentionally lightweight (no extra model download). It can be
swapped for a trained anti-spoofing model later without touching any
other file - main.py only calls .update() and .timed_out().
"""

import time

import numpy as np


def eye_aspect_ratio(eye_points):
    eye_points = np.array(eye_points)
    a = np.linalg.norm(eye_points[1] - eye_points[5])
    b = np.linalg.norm(eye_points[2] - eye_points[4])
    c = np.linalg.norm(eye_points[0] - eye_points[3])
    if c == 0:
        return 0.0
    return (a + b) / (2.0 * c)


class LivenessDetector:
    def __init__(self, ear_threshold=0.21, consec_frames=2, timeout_seconds=8):
        self.ear_threshold = ear_threshold
        self.consec_frames = consec_frames
        self.timeout_seconds = timeout_seconds
        self.reset()

    def reset(self):
        self._counter = 0
        self._blink_detected = False
        self._start_time = time.time()

    def update(self, landmarks):
        """
        landmarks: one entry from face_recognition.face_landmarks(rgb, [box])
        Returns True once a blink has been detected since the last reset().
        """
        if self._blink_detected:
            return True

        if not landmarks:
            return False

        left_eye = landmarks.get("left_eye")
        right_eye = landmarks.get("right_eye")
        if not left_eye or not right_eye:
            return False

        ear = (eye_aspect_ratio(left_eye) + eye_aspect_ratio(right_eye)) / 2.0

        if ear < self.ear_threshold:
            self._counter += 1
        else:
            if self._counter >= self.consec_frames:
                self._blink_detected = True
            self._counter = 0

        return self._blink_detected

    def timed_out(self):
        return (time.time() - self._start_time) > self.timeout_seconds
