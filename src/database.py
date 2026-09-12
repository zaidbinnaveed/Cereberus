"""
Handles the "authorized users" database.

Design choice: instead of storing one averaged embedding per person, we
store a LIST of embeddings per person (multiple samples taken from
different angles/lighting during enrollment). When matching, we compare
against all of a person's samples and take the closest one. This makes
matching noticeably more robust than a single-sample average.
"""

import os
import pickle
import tempfile
import threading

from . import config

_write_lock = threading.RLock()


def load_embeddings():
    """Returns dict: {name: [embedding1, embedding2, ...]}"""
    if not os.path.exists(config.EMBEDDINGS_PATH):
        return {}
    with open(config.EMBEDDINGS_PATH, "rb") as f:
        return pickle.load(f)


def save_embeddings(db):
    """Persist the database atomically so an interrupted write cannot corrupt it."""
    with _write_lock:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=config.DATA_DIR, prefix="embeddings_", suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = handle.name
                pickle.dump(db, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, config.EMBEDDINGS_PATH)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


def add_user(name, embeddings_list):
    """Adds or overwrites a user's enrolled samples."""
    with _write_lock:
        db = load_embeddings()
        db[name] = embeddings_list
        save_embeddings(db)
        return db


def remove_user(name):
    with _write_lock:
        db = load_embeddings()
        if name in db:
            del db[name]
            save_embeddings(db)
        return db


def list_users():
    db = load_embeddings()
    return list(db.keys())
