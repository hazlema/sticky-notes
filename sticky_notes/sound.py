"""Reminder alarm sound with an X11 bell fallback."""
import os
import shutil
import subprocess

SOUND_FILE = '/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga'
PLAYERS = ('paplay', 'pw-play')
BELL_REPEATS = 3
BELL_INTERVAL_MS = 500


class Alarm:
    """Plays the desktop alarm sound once per ring; falls back to repeated Tk bells."""

    def __init__(self, root, sound_file=SOUND_FILE, popen=subprocess.Popen,
                 which=shutil.which, exists=os.path.exists):
        self.root = root
        self.popen = popen
        self.command = None
        self.process = None
        if os.environ.get('STICKY_NOTES_NO_AUDIO'):
            return
        if exists(sound_file):
            for player in PLAYERS:
                executable = which(player)
                if executable:
                    self.command = [executable, sound_file]
                    break

    def ring(self):
        if self.command is not None:
            if self.process is not None and self.process.poll() is None:
                return
            try:
                self.process = self.popen(self.command, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
                return
            except OSError:
                self.command = None
        self._bell(BELL_REPEATS)

    def _bell(self, remaining):
        self.root.bell()
        if remaining > 1:
            self.root.after(BELL_INTERVAL_MS, lambda: self._bell(remaining - 1))
