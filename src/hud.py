"""
Draws the "face scanning" HUD on top of a frame, using only the plain
data process_frame() already returns (box, landmarks, status, name).

This is deliberately a separate file from main.py's engine logic - the
CereberusEngine.process_frame() API stays 100% pure data, no drawing.
This module is just ONE way to visualize that data with OpenCV. Your
friend's UI can reuse this file as-is, take it as a reference, or
ignore it completely and build something else entirely (web canvas,
Qt, whatever) from the same process_frame() output.
"""

import math
import time

import cv2

STATUS_TEXT = {
    "NO_FACE": "AWAITING SUBJECT",
    "SCANNING": "SCANNING...",
    "VERIFIED": "ACCESS GRANTED",
    "DENIED": "ACCESS DENIED",
    "SPOOF_SUSPECTED": "SPOOF DETECTED",
}

# BGR colors (OpenCV order, not RGB)
STATUS_COLORS = {
    "NO_FACE": (180, 180, 180),
    "SCANNING": (0, 215, 255),    # amber
    "VERIFIED": (100, 255, 120),  # green
    "DENIED": (60, 60, 255),      # red
    "SPOOF_SUSPECTED": (60, 60, 255),
}


class ScanHUD:
    def __init__(self, bracket_ratio=0.22, scan_speed=1.4):
        self.bracket_ratio = bracket_ratio  # how long each corner bracket arm is, relative to box size
        self.scan_speed = scan_speed        # sweeps per second

    def _corner_brackets(self, frame, box, color, thickness=3):
        top, right, bottom, left = box
        length = int(min(right - left, bottom - top) * self.bracket_ratio)

        corners = [
            ((left, top), (1, 0), (0, 1)),        # top-left
            ((right, top), (-1, 0), (0, 1)),      # top-right
            ((left, bottom), (1, 0), (0, -1)),    # bottom-left
            ((right, bottom), (-1, 0), (0, -1)),  # bottom-right
        ]
        for (x, y), dx, dy in corners:
            end_h = (x + dx[0] * length, y)
            end_v = (x, y + dy[1] * length)
            cv2.line(frame, (x, y), end_h, color, thickness)
            cv2.line(frame, (x, y), end_v, color, thickness)

    def _scan_line(self, frame, box, color):
        top, right, bottom, left = box
        h = bottom - top

        # Triangle wave 0 -> 1 -> 0, driven by wall-clock time so speed
        # is independent of frame rate.
        t = time.time() * self.scan_speed
        phase = t - math.floor(t)
        frac = phase * 2 if phase < 0.5 else 2 - phase * 2
        y = int(top + frac * h)

        # Bright core line + a softer glow band around it for a "laser scan" feel.
        overlay = frame.copy()
        cv2.line(overlay, (left, y), (right, y), color, 6)
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
        cv2.line(frame, (left, y), (right, y), color, 2)

    def _label(self, frame, box, text, color):
        top, right, bottom, left = box
        (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        pad = 6

        bg_top = top - text_h - 2 * pad
        if bg_top < 0:
            bg_top = bottom + pad
            bg_bottom = bg_top + text_h + 2 * pad
            text_y = bg_bottom - pad
        else:
            bg_bottom = top
            text_y = top - pad

        cv2.rectangle(frame, (left, bg_top), (left + text_w + 2 * pad, bg_bottom), color, -1)
        cv2.putText(frame, text, (left + pad, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (10, 10, 10), 2)

    def draw(self, frame, result):
        status = result["status"]
        color = STATUS_COLORS.get(status, (255, 255, 255))
        text = STATUS_TEXT.get(status, status)

        if result["box"] is None:
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            return frame

        box = result["box"]
        self._corner_brackets(frame, box, color)

        if status in ("SCANNING", "VERIFIED"):
            self._scan_line(frame, box, color)

        label = text
        if result["name"] and status in ("SCANNING", "VERIFIED"):
            label = f"{text}  {result['name']}"
        self._label(frame, box, label, color)

        return frame
