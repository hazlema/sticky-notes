"""Exercise the real app, HTTP bridge, Tk loop, and persistence together."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.request


@unittest.skipUnless(os.environ.get('DISPLAY'), 'An X11 display is required')
class IntegrationTests(unittest.TestCase):
    def start_app(self, directory, env=None):
        env = dict(os.environ if env is None else env)
        env['STICKY_NOTES_NO_AUDIO'] = '1'
        process = subprocess.Popen([sys.executable, '-m', 'sticky_notes',
                                    '--port', '0', '--data-dir', directory],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        self.addCleanup(self.stop_process, process)
        ready, _, _ = select.select([process.stdout], [], [], 5)
        self.assertTrue(ready, 'App did not print its editor link')
        line = process.stdout.readline().strip()
        self.assertTrue(line.startswith('Sticky Notes editor: '), line)
        url = line.removeprefix('Sticky Notes editor: ')
        parts = urllib.parse.urlsplit(url)
        token = urllib.parse.parse_qs(parts.fragment)['token'][0]
        return process, f'http://{parts.netloc}', token

    @staticmethod
    def stop_process(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()

    def request(self, base, token, command=None, payload=None):
        body = json.dumps({'command': command, 'payload': payload or {}}).encode() if command else None
        request = urllib.request.Request(base + ('/api/command' if command else '/api/notes'),
                                         data=body, headers={'Authorization': 'Bearer ' + token,
                                                             'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_second_launch_reopens_existing_instance_without_changing_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            process, base, token = self.start_app(directory)
            visible = self.request(base, token, 'create', {'title': 'Keep visible'})
            hidden = self.request(base, token, 'create', {'title': 'Keep hidden'})
            self.request(base, token, 'visibility', {'id': hidden['id'], 'visible': False})
            before = self.request(base, token)
            second = subprocess.run([sys.executable, '-m', 'sticky_notes', '--no-browser',
                                     '--port', '0', '--data-dir', directory],
                                    capture_output=True, text=True, timeout=8)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn(base + '/#token=' + token, second.stdout)
            self.assertIsNone(process.poll())
            browser_script = Path(directory) / 'browser.py'
            browser_log = Path(directory) / 'opened-url.txt'
            browser_script.write_text('from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text(sys.argv[2])\n')
            reopened = subprocess.run([sys.executable, '-m', 'sticky_notes', '--editor', '--data-dir', directory],
                                      env={**os.environ, 'BROWSER': f'{sys.executable} {browser_script} {browser_log} %s'},
                                      capture_output=True, text=True, timeout=8)
            self.assertEqual(reopened.returncode, 0, reopened.stderr)
            self.assertEqual(browser_log.read_text(), base + '/#token=' + token)
            self.assertIsNone(process.poll(), 'Exiting the editor must not stop the notes')
            self.assertEqual(self.request(base, token), before)
            session = Path(directory) / 'session.json'
            self.assertEqual(session.stat().st_mode & 0o777, 0o600)
            self.request(base, token, 'shutdown')
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertFalse(session.exists())

    def test_default_launch_never_opens_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            browser_script = Path(directory) / 'browser.py'
            browser_log = Path(directory) / 'opened-url.txt'
            browser_script.write_text('from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text(sys.argv[2])\n')
            env = {**os.environ, 'BROWSER': f'{sys.executable} {browser_script} {browser_log} %s'}
            process, base, token = self.start_app(directory, env=env)
            second = subprocess.run([sys.executable, '-m', 'sticky_notes', '--data-dir', directory],
                                    env=env, capture_output=True, text=True, timeout=8)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.request(base, token, 'shutdown')
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertFalse(browser_log.exists(), 'Default startup must not launch a browser')

    def test_real_app_reminder_shutdown_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            process, base, token = self.start_app(directory)
            note = self.request(base, token, 'create', {'title': 'Integration', 'minutes': .02})
            self.request(base, token, 'visibility', {'id': note['id'], 'visible': False})
            self.assertFalse(self.request(base, token)[0]['visible'])
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                snapshot = self.request(base, token)
                if snapshot[0]['alert']:
                    break
                time.sleep(.1)
            self.assertTrue(snapshot[0]['alert'])
            self.assertTrue(snapshot[0]['visible'])
            self.request(base, token, 'dismiss', {'id': note['id']})
            self.request(base, token, 'shutdown')
            self.assertEqual(process.wait(timeout=5), 0, process.stderr.read())
            process2, base2, token2 = self.start_app(directory)
            loaded = self.request(base2, token2)[0]
            self.assertEqual(loaded['title'], 'Integration')
            self.assertFalse(loaded['alert'])
            self.assertIsNone(loaded['deadline'])
            self.request(base2, token2, 'shutdown')
            self.assertEqual(process2.wait(timeout=5), 0, process2.stderr.read())
            self.assertTrue((Path(directory) / 'notes.json').exists())
