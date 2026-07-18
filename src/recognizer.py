"""
Wraps face_recognition for detection, encoding, and matching.
Keeping this isolated means if we ever swap face_recognition for
DeepFace/ArcFace later, only this file needs to change.
"""

import face_recognition
import numpy as np

from . import config, database


def get_face_locations(rgb_frame):
    """Returns list of (top, right, bottom, left) boxes."""
    return face_recognition.face_locations(rgb_frame, model="hog")


def get_face_encoding(rgb_frame, location):
    """Returns a 128-d embedding for a single face location, or None."""
    encodings = face_recognition.face_encodings(rgb_frame, [location])
    if not encodings:
        return None
    return encodings[0]


def match_encoding(encoding, db=None):
    """
    Compares an encoding against every enrolled user's stored samples.
    Returns (best_name, best_distance). (None, None) if db is empty
    or encoding is None.
    """
    if encoding is None:
        return None, None

    if db is None:
        db = database.load_embeddings()

    if not db:
        return None, None

    best_name = None
    best_distance = None

    for name, encodings_list in db.items():
        distances = face_recognition.face_distance(encodings_list, encoding)
        min_dist = float(np.min(distances))
        if best_distance is None or min_dist < best_distance:
            best_distance = min_dist
            best_name = name

    return best_name, best_distance


def is_match(name, distance, threshold=None):
    if threshold is None:
        threshold = config.MATCH_THRESHOLD
    return name is not None and distance is not None and distance <= threshold
