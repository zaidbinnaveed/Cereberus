"""
Run this to register a new authorized user.

Usage (from the Cereberus project root, with venv active):
    python -m src.enroll
    python -m src.enroll "Zaid"

Captures multiple samples (different angles/expressions) per person,
which makes matching far more robust than a single photo.
"""

import sys

import cv2
import face_recognition

from . import config, database

SAMPLES_NEEDED = 5


def enroll_user(name):
    cam = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cam.isOpened():
        print("Could not open webcam. Check CAMERA_INDEX in src/config.py.")
        return

    print(f"Enrolling '{name}'.")
    print("Move your head slightly between captures (left, right, up, down, neutral).")
    print("Press SPACE to capture a sample, ESC to cancel.\n")

    samples = []

    while len(samples) < SAMPLES_NEEDED:
        ret, frame = cam.read()
        if not ret:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model="hog")

        display = frame.copy()
        for (top, right, bottom, left) in locations:
            cv2.rectangle(display, (left, top), (right, bottom), (0, 255, 0), 2)

        status = f"Samples: {len(samples)}/{SAMPLES_NEEDED}   SPACE=capture   ESC=cancel"
        cv2.putText(display, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        if len(locations) == 0:
            cv2.putText(display, "No face detected", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        elif len(locations) > 1:
            cv2.putText(display, "Multiple faces - only one person at a time", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        cv2.imshow("Cereberus - Enrollment", display)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            print("Enrollment cancelled. Nothing was saved.")
            cam.release()
            cv2.destroyAllWindows()
            return
        elif key == 32:  # SPACE
            if len(locations) != 1:
                print("Need exactly one face in frame. Try again.")
                continue
            encoding = face_recognition.face_encodings(rgb, locations)[0]
            samples.append(encoding)
            print(f"Captured sample {len(samples)}/{SAMPLES_NEEDED}")

    cam.release()
    cv2.destroyAllWindows()

    database.add_user(name, samples)
    print(f"\n'{name}' enrolled successfully with {len(samples)} samples.")
    print(f"Currently enrolled users: {database.list_users()}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        entered_name = " ".join(sys.argv[1:]).strip()
    else:
        entered_name = input("Enter name to enroll: ").strip()

    if not entered_name:
        print("Name cannot be empty.")
    else:
        enroll_user(entered_name)
