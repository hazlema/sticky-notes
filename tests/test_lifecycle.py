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
    def run_install(self, applications_dir, autostart_dir, *flags):
        return subprocess.run([sys.executable, '-m', 'sticky_notes.install',
                               '--applications-dir', str(applications_dir),
                               '--autostart-dir', str(autostart_dir), *flags],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def test_menu_shortcut_explicitly_opens_editor(self):
        with tempfile.TemporaryDirectory() as applications, tempfile.TemporaryDirectory() as autostart:
            result = self.run_install(applications, autostart)
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = (Path(applications) / 'sticky-notes.desktop').read_text()
            self.assertIn('-m sticky_notes --editor', entry)

    def test_autostart_flag_writes_quiet_login_entry(self):
        with tempfile.TemporaryDirectory() as applications, tempfile.TemporaryDirectory() as autostart:
            result = self.run_install(applications, autostart, '--autostart')
            self.assertEqual(result.returncode, 0, result.stderr)
            entry = (Path(autostart) / 'sticky-notes.desktop').read_text()
            self.assertIn('-m sticky_notes\n', entry)
            self.assertNotIn('--editor', entry)
            self.assertIn('Path=', entry)
            self.assertIn('X-GNOME-Autostart-enabled=true', entry)

    def test_no_autostart_flag_skips_login_entry(self):
        with tempfile.TemporaryDirectory() as applications, tempfile.TemporaryDirectory() as autostart:
            result = self.run_install(applications, autostart, '--no-autostart')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(applications) / 'sticky-notes.desktop').exists())
            self.assertFalse((Path(autostart) / 'sticky-notes.desktop').exists())

    def test_non_tty_install_skips_login_entry_with_hint(self):
        with tempfile.TemporaryDirectory() as applications, tempfile.TemporaryDirectory() as autostart:
            result = self.run_install(applications, autostart)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((Path(autostart) / 'sticky-notes.desktop').exists())
            self.assertIn('--autostart', result.stdout)

    def test_uninstall_removes_both_entries_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as applications, tempfile.TemporaryDirectory() as autostart:
            self.run_install(applications, autostart, '--autostart')
            result = self.run_install(applications, autostart, '--uninstall')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((Path(applications) / 'sticky-notes.desktop').exists())
            self.assertFalse((Path(autostart) / 'sticky-notes.desktop').exists())
            again = self.run_install(applications, autostart, '--uninstall')
            self.assertEqual(again.returncode, 0, again.stderr)

    def test_uninstall_rejects_autostart_flags(self):
        with tempfile.TemporaryDirectory() as applications, tempfile.TemporaryDirectory() as autostart:
            result = self.run_install(applications, autostart, '--uninstall', '--autostart')
            self.assertEqual(result.returncode, 2)
