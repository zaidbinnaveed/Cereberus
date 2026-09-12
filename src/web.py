"""Cereberus web control plane.

Run with ``python -m src.web``. The server exposes a small JSON/JPEG API and
serves the production frontend from ``frontend/dist/client`` when available.
During frontend development Vite proxies ``/api`` to this process.
"""

from __future__ import annotations

import csv
import json
import mimetypes
import os
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import config, database

HOST = os.environ.get("CEREBERUS_HOST", "127.0.0.1")
PORT = int(os.environ.get("CEREBERUS_PORT", "8765"))
FRONTEND_DIR = Path(config.BASE_DIR, "frontend", "dist", "client").resolve()
MAX_IMAGE_BYTES = 8 * 1024 * 1024
NAME_PATTERN = re.compile(r"^[\w .'-]{1,80}$", re.UNICODE)

_engine = None
_engine_error = None
_engine_lock = threading.Lock()
_enrollment_lock = threading.Lock()
_pending_enrollments: dict[str, list] = {}


def _get_engine():
    global _engine, _engine_error
    if _engine is None and _engine_error is None:
        try:
            from .main import CereberusEngine
            _engine = CereberusEngine()
        except Exception as exc:  # keep the control UI available for diagnostics
            _engine_error = f"{type(exc).__name__}: {exc}"
    return _engine


def _read_events(limit=100):
    path = Path(config.ACCESS_LOG_PATH)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    events = []
    for index, row in enumerate(reversed(rows[-limit:])):
        distance = row.get("distance")
        try:
            distance = float(distance) if distance else None
        except ValueError:
            distance = None
        timestamp = row.get("timestamp", "")
        status = row.get("status", "")
        name = row.get("name") or None
        events.append({
            "id": f"{timestamp}-{status}-{name or 'unknown'}-{len(rows)-index}",
            "timestamp": timestamp,
            "status": status,
            "name": name,
            "distance": distance,
            "location": "Lobby / North",
            "snapshot": Path(row["snapshot"]).name if row.get("snapshot") else None,
        })
    return events


def _decode_frame(body):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(f"Recognition dependency unavailable: {exc}") from exc
    array = np.frombuffer(body, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("The uploaded image could not be decoded.")
    return frame


def _serialize_result(result, frame):
    top, right, bottom, left = result.get("box") or (None, None, None, None)
    height, width = frame.shape[:2]
    box = None
    if top is not None:
        left = min(width, max(0, left))
        right = min(width, max(left, right))
        top = min(height, max(0, top))
        bottom = min(height, max(top, bottom))
        box = {
            "left": left / width, "top": top / height,
            "width": (right - left) / width,
            "height": (bottom - top) / height,
        }
    return {
        "status": result.get("status"), "name": result.get("name"),
        "distance": result.get("distance"), "box_normalized": box,
    }


class CereberusHandler(BaseHTTPRequestHandler):
    server_version = "Cereberus/1.0"

    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} {fmt % args}")

    def _json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message, status=HTTPStatus.BAD_REQUEST):
        self._json({"error": message}, status)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid Content-Length header.")
        if length <= 0 or length > MAX_IMAGE_BYTES:
            raise ValueError("Image must be between 1 byte and 8 MB.")
        return self.rfile.read(length)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            engine = _get_engine()
            self._json({
                "ok": True, "recognition": engine is not None,
                "recognition_error": _engine_error,
                "match_threshold": config.MATCH_THRESHOLD,
                "enrolled_users": len(database.list_users()),
            })
            return
        if parsed.path == "/api/events":
            self._json({"events": _read_events()})
            return
        if parsed.path == "/api/users":
            db = database.load_embeddings()
            self._json({"users": [{"name": name, "samples": len(samples)} for name, samples in sorted(db.items())]})
            return
        if parsed.path.startswith("/api/snapshots/"):
            name = Path(unquote(parsed.path.rsplit("/", 1)[-1])).name
            target = Path(config.SNAPSHOT_DIR, name).resolve()
            snapshot_root = Path(config.SNAPSHOT_DIR).resolve()
            if target.parent != snapshot_root or not target.is_file():
                self._error("Snapshot not found.", HTTPStatus.NOT_FOUND)
                return
            self._serve_file(target)
            return
        self._serve_frontend(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/scan":
            engine = _get_engine()
            if engine is None:
                self._error(_engine_error or "Recognition engine unavailable.", HTTPStatus.SERVICE_UNAVAILABLE)
                return
            try:
                frame = _decode_frame(self._body())
                with _engine_lock:
                    result = engine.process_frame(frame)
                payload = _serialize_result(result, frame)
                if result.get("status") in {"VERIFIED", "DENIED", "SPOOF_SUSPECTED"}:
                    latest = _read_events(limit=1)
                    if latest:
                        payload["event"] = latest[0]
                self._json(payload)
            except ValueError as exc:
                self._error(str(exc))
            except Exception as exc:
                self._error(f"Scan failed: {exc}", HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        if parsed.path == "/api/enroll/sample":
            name = parse_qs(parsed.query).get("name", [""])[0].strip()
            if not NAME_PATTERN.fullmatch(name):
                self._error("Use a name of 1–80 letters, numbers, spaces, apostrophes, periods, or hyphens.")
                return
            try:
                import cv2
                import face_recognition
                frame = _decode_frame(self._body())
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                locations = face_recognition.face_locations(rgb, model="hog")
                if len(locations) != 1:
                    self._error("Keep exactly one face clearly visible in the frame.")
                    return
                encodings = face_recognition.face_encodings(rgb, locations)
                if not encodings:
                    self._error("A stable face encoding could not be captured. Adjust the light and try again.")
                    return
                with _enrollment_lock:
                    samples = _pending_enrollments.setdefault(name, [])
                    samples.append(encodings[0])
                    complete = len(samples) >= 5
                    if complete:
                        database.add_user(name, samples[:5])
                        del _pending_enrollments[name]
                        engine = _get_engine()
                        if engine:
                            engine.reload_db()
                    count = min(len(samples), 5)
                self._json({"name": name, "samples": count, "complete": complete})
            except ImportError as exc:
                self._error(f"Recognition dependency unavailable: {exc}", HTTPStatus.SERVICE_UNAVAILABLE)
            except ValueError as exc:
                self._error(str(exc))
            except Exception as exc:
                self._error(f"Enrollment failed: {exc}", HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._error("API route not found.", HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/users":
            self._error("API route not found.", HTTPStatus.NOT_FOUND)
            return
        name = parse_qs(parsed.query).get("name", [""])[0].strip()
        if not name or name not in database.list_users():
            self._error("Identity not found.", HTTPStatus.NOT_FOUND)
            return
        database.remove_user(name)
        engine = _get_engine()
        if engine:
            engine.reload_db()
        self._json({"removed": name})

    def _serve_frontend(self, request_path):
        if not FRONTEND_DIR.is_dir():
            self._error("Frontend is not built. Run npm run build in frontend/.", HTTPStatus.SERVICE_UNAVAILABLE)
            return
        relative = request_path.lstrip("/") or "index.html"
        target = (FRONTEND_DIR / relative).resolve()
        if FRONTEND_DIR not in target.parents and target != FRONTEND_DIR:
            self._error("Invalid path.", HTTPStatus.BAD_REQUEST)
            return
        if not target.is_file():
            target = FRONTEND_DIR / "index.html"
        self._serve_file(target)

    def _serve_file(self, path):
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache" if path.name == "index.html" else "public, max-age=31536000, immutable")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)


def run():
    server = ThreadingHTTPServer((HOST, PORT), CereberusHandler)
    print(f"Cereberus web console: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
