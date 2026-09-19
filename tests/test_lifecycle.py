import tempfile
import unittest
from pathlib import Path
from sticky_notes.__main__ import instance_lock


class LifecycleTests(unittest.TestCase):
    def test_exclusive_lock_and_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with instance_lock(path):
                with self.assertRaises(RuntimeError):
                    with instance_lock(path):
                        pass
            with instance_lock(path):
                pass
