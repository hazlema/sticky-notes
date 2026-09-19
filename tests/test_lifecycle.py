import subprocess
import sys
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


class LauncherTests(unittest.TestCase):
    def test_menu_shortcut_explicitly_opens_editor(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-m', 'sticky_notes.install',
                                     '--applications-dir', directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = (Path(directory) / 'sticky-notes.desktop').read_text()
            self.assertIn('-m sticky_notes --editor', entry)
