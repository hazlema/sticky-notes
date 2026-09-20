# Reminder alarm sound

## Purpose and agreed direction

Replace the single quiet X11 bell that announces a due reminder with the desktop theme's alarm sound, played once through the normal audio system (the file carries its own few seconds of ringing). Fall back to the X11 bell — repeated three times — when no player or sound file is available. No new dependencies; the sound file and players come from the desktop.

## Behavior

- When `Desktop.refresh(alert_ids=...)` receives alert ids (the existing trigger), play `/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga` once via the first available player: `paplay`, then `pw-play`.
- If the previous alarm playback is still running, a new ring is skipped — simultaneous or rapid reminders produce one clean alarm, never overlapping playback.
- If no player or the sound file is missing, or launching the player fails with `OSError`, ring the X11 bell three times, 500 ms apart, scheduled with `Tk.after` (never blocking the Tk loop). A launch failure permanently downgrades to the bell path for the rest of the session.
- Trigger semantics are unchanged: snoozed reminders ring again when due; restored active alerts do not re-ring at startup beyond current behavior.

## Implementation

New module `sticky_notes/sound.py` with an `Alarm` class:
- Constructor resolves the player command once (`shutil.which` + file existence check); injectable hooks for tests.
- `ring()` uses `subprocess.Popen` with output to `DEVNULL` and no shell; keeps the process handle to `poll()` for the skip-if-playing check.
- `Desktop.__init__` gains `self.alarm = Alarm(root)`; `refresh()` calls `self.alarm.ring()` instead of `self.root.bell()`.

## Verification

New `tests/test_sound.py` with a stub root (records `bell`/`after`, runs callbacks synchronously) and a fake `Popen`:
- player available: `ring()` launches the player with the sound file; a second `ring()` while playing is skipped; after playback finishes a new `ring()` plays again
- no player: exactly three bells
- `Popen` raising `OSError`: falls back to bells and stays on the bell path
Full suite under Xvfb stays green; manual check by triggering a reminder on the real desktop.

## Docs

README: Reminders section describes the alarm sound and bell fallback; the "No sound" troubleshooting entry mentions the freedesktop sound theme and PulseAudio/PipeWire. CHANGELOG gains an entry under 2026-09-20.

## Out of scope

Shipping a custom sound file, per-note sounds, volume control, Wayland-specific audio handling.
