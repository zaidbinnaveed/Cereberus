import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from src import database


class DatabaseTest(unittest.TestCase):
    def test_add_overwrite_and_remove_user(self):
        with tempfile.TemporaryDirectory() as directory:
            embeddings_path = Path(directory, "embeddings.pkl")
            with (
                patch.object(database.config, "DATA_DIR", directory),
                patch.object(database.config, "EMBEDDINGS_PATH", str(embeddings_path)),
            ):
                first = np.array([0.1, 0.2])
                replacement = np.array([0.3, 0.4])
                database.add_user("Zaid", [first])
                database.add_user("Zaid", [replacement])

                stored = database.load_embeddings()
                self.assertEqual(list(stored), ["Zaid"])
                np.testing.assert_array_equal(stored["Zaid"][0], replacement)

                database.remove_user("Zaid")
                self.assertEqual(database.load_embeddings(), {})

    def test_save_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            embeddings_path = Path(directory, "embeddings.pkl")
            with (
                patch.object(database.config, "DATA_DIR", directory),
                patch.object(database.config, "EMBEDDINGS_PATH", str(embeddings_path)),
            ):
                database.save_embeddings({"A": [np.array([1.0])]})

            self.assertTrue(embeddings_path.is_file())
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
