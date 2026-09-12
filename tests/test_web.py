import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from src import web


class WebHelpersTest(unittest.TestCase):
    def test_serialize_result_normalizes_face_box(self):
        frame = np.zeros((400, 800, 3), dtype=np.uint8)
        payload = web._serialize_result(
            {"status": "SCANNING", "name": "Zaid", "distance": 0.25,
             "box": (40, 600, 360, 200)},
            frame,
        )
        self.assertEqual(payload["status"], "SCANNING")
        self.assertEqual(payload["box_normalized"], {
            "left": 0.25, "top": 0.1, "width": 0.5, "height": 0.8,
        })

    def test_serialize_result_clips_face_box_to_frame(self):
        frame = np.zeros((100, 200, 3), dtype=np.uint8)
        payload = web._serialize_result(
            {"status": "SCANNING", "box": (-20, 250, 130, -50)},
            frame,
        )
        self.assertEqual(payload["box_normalized"], {
            "left": 0.0, "top": 0.0, "width": 1.0, "height": 1.0,
        })

    def test_event_reader_returns_newest_first_and_parses_distance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "events.csv")
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["timestamp", "status", "name", "distance", "snapshot"])
                writer.writerow(["2026-09-04T09:00:00", "GRANTED", "A", "0.2", ""])
                writer.writerow(["2026-09-04T09:01:00", "DENIED", "", "0.8", "shot.jpg"])
            with patch.object(web.config, "ACCESS_LOG_PATH", str(path)):
                events = web._read_events()
        self.assertEqual(events[0]["status"], "DENIED")
        self.assertEqual(events[0]["snapshot"], "shot.jpg")
        self.assertEqual(events[1]["distance"], 0.2)

    def test_missing_event_log_is_an_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(web.config, "ACCESS_LOG_PATH", str(Path(directory, "missing.csv"))):
                self.assertEqual(web._read_events(), [])


if __name__ == "__main__":
    unittest.main()
