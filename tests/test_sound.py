import subprocess
import unittest
from unittest.mock import patch
from sticky_notes.sound import Alarm, SOUND_FILE


class StubRoot:
    def __init__(self):
        self.bells = 0

    def bell(self):
        self.bells += 1

    def after(self, _delay_ms, callback):
        callback()


class FakeProcess:
    def __init__(self, running=False):
        self.running = running

    def poll(self):
        return None if self.running else 0


class FakePopen:
    def __init__(self, running=False, error=None):
        self.calls = []
        self.running = running
        self.error = error

    def __call__(self, command, stdout=None, stderr=None):
        if self.error is not None:
            raise self.error
        self.calls.append((command, stdout, stderr))
        return FakeProcess(self.running)


class AlarmTests(unittest.TestCase):
    def test_plays_sound_file_with_first_available_player(self):
        root, popen = StubRoot(), FakePopen()
        alarm = Alarm(root, popen=popen,
                      which=lambda name: f'/usr/bin/{name}' if name == 'pw-play' else None,
                      exists=lambda path: True)
        alarm.ring()
        self.assertEqual(popen.calls, [(['/usr/bin/pw-play', SOUND_FILE],
                                        subprocess.DEVNULL, subprocess.DEVNULL)])
        self.assertEqual(root.bells, 0)

    def test_skips_ring_while_previous_playback_is_running(self):
        root, popen = StubRoot(), FakePopen(running=True)
        alarm = Alarm(root, popen=popen,
                      which=lambda name: f'/usr/bin/{name}', exists=lambda path: True)
        alarm.ring()
        alarm.ring()
        self.assertEqual(len(popen.calls), 1)

    def test_rings_again_after_playback_finishes(self):
        root, popen = StubRoot(), FakePopen(running=False)
        alarm = Alarm(root, popen=popen,
                      which=lambda name: f'/usr/bin/{name}', exists=lambda path: True)
        alarm.ring()
        alarm.ring()
        self.assertEqual(len(popen.calls), 2)

    def test_bell_fallback_when_no_player(self):
        root, popen = StubRoot(), FakePopen()
        alarm = Alarm(root, popen=popen,
                      which=lambda name: None, exists=lambda path: True)
        alarm.ring()
        self.assertEqual(popen.calls, [])
        self.assertEqual(root.bells, 3)

    def test_bell_fallback_when_sound_file_missing(self):
        root, popen = StubRoot(), FakePopen()
        alarm = Alarm(root, popen=popen,
                      which=lambda name: f'/usr/bin/{name}', exists=lambda path: False)
        alarm.ring()
        self.assertEqual(popen.calls, [])
        self.assertEqual(root.bells, 3)

    def test_no_audio_env_var_forces_bell_fallback(self):
        root, popen = StubRoot(), FakePopen()
        with patch.dict('os.environ', {'STICKY_NOTES_NO_AUDIO': '1'}):
            alarm = Alarm(root, popen=popen,
                          which=lambda name: f'/usr/bin/{name}', exists=lambda path: True)
        alarm.ring()
        self.assertEqual(popen.calls, [])
        self.assertEqual(root.bells, 3)

    def test_popen_failure_falls_back_and_stays_on_bells(self):
        root = StubRoot()
        popen = FakePopen(error=OSError('missing player'))
        alarm = Alarm(root, popen=popen,
                      which=lambda name: f'/usr/bin/{name}', exists=lambda path: True)
        alarm.ring()
        self.assertEqual(root.bells, 3)
        popen.error = None
        alarm.ring()
        self.assertEqual(popen.calls, [])
        self.assertEqual(root.bells, 6)


if __name__ == '__main__':
    unittest.main()
