import unittest
from unittest.mock import patch

import numpy as np

from src.main import CereberusEngine


class EngineDecisionLifecycleTest(unittest.TestCase):
    def setUp(self):
        database_patch = patch("src.main.database.load_embeddings", return_value={"Known": [np.zeros(128)]})
        self.addCleanup(database_patch.stop)
        database_patch.start()
        self.engine = CereberusEngine()
        self.frame = np.zeros((80, 120, 3), dtype=np.uint8)

    def _face_patches(self, match):
        return (
            patch("src.main.cv2.cvtColor", side_effect=lambda frame, _code: frame),
            patch("src.main.recognizer.get_face_locations", return_value=[(10, 70, 60, 20)]),
            patch("src.main.face_recognition.face_landmarks", return_value=[{"left_eye": [], "right_eye": []}]),
            patch("src.main.recognizer.get_face_encoding", return_value=np.zeros(128)),
            patch("src.main.recognizer.match_encoding", return_value=match),
        )

    def test_denied_attempt_is_logged_once_until_subject_leaves(self):
        patches = self._face_patches((None, None))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patch("src.main.alarm.trigger_denied") as denied:
            self.assertEqual(self.engine.process_frame(self.frame)["status"], "DENIED")
            self.assertEqual(self.engine.process_frame(self.frame)["status"], "DENIED")
            denied.assert_called_once()

        with patch("src.main.cv2.cvtColor", side_effect=lambda frame, _code: frame), patch("src.main.recognizer.get_face_locations", return_value=[]):
            self.engine.process_frame(self.frame)
            self.engine.process_frame(self.frame)

        patches = self._face_patches((None, None))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patch("src.main.alarm.trigger_denied") as denied:
            self.engine.process_frame(self.frame)
            denied.assert_called_once()

    def test_verified_attempt_is_logged_once(self):
        patches = self._face_patches(("Known", 0.18))
        with patches[0], patches[1], patches[2], patches[3], patches[4], patch("src.main.recognizer.is_match", return_value=True), patch.object(self.engine.liveness, "update", return_value=True), patch("src.main.alarm.log_granted") as granted:
            self.assertEqual(self.engine.process_frame(self.frame)["status"], "VERIFIED")
            self.assertEqual(self.engine.process_frame(self.frame)["status"], "VERIFIED")
            granted.assert_called_once_with("Known", 0.18)


if __name__ == "__main__":
    unittest.main()
