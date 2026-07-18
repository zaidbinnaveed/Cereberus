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

from . import config


def load_embeddings():
    """Returns dict: {name: [embedding1, embedding2, ...]}"""
    if not os.path.exists(config.EMBEDDINGS_PATH):
        return {}
    with open(config.EMBEDDINGS_PATH, "rb") as f:
        return pickle.load(f)


def save_embeddings(db):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.EMBEDDINGS_PATH, "wb") as f:
        pickle.dump(db, f)


def add_user(name, embeddings_list):
    """Adds or overwrites a user's enrolled samples."""
    db = load_embeddings()
    db[name] = embeddings_list
    save_embeddings(db)
    return db


def remove_user(name):
    db = load_embeddings()
    if name in db:
        del db[name]
        save_embeddings(db)
    return db


def list_users():
    db = load_embeddings()
    return list(db.keys())
