# Changelog

Notable changes to Sticky Notes, newest first. The project is tracked by date rather than version numbers.

## 2026-09-20

### Added
- The installer now offers to start notes automatically at login (`Start notes automatically at login? [Y/n]`), or non-interactively with `--autostart` / `--no-autostart`. The entry restores notes quietly at login without opening the editor.
- `python3 -m sticky_notes.install --uninstall` removes the application-menu launcher and the login autostart entry in one step.

### Changed
- Reminders now play the desktop theme's alarm sound (`alarm-clock-elapsed` via PulseAudio/PipeWire) instead of a single quiet system bell; without a sound player the bell rings three times. Set `STICKY_NOTES_NO_AUDIO` to disable playback.
- README restructured: one install path, deduplicated requirements, explicit stop-before-upgrade steps, and installer-managed login startup instead of a hand-written startup command.

## 2026-09-19

### Added
- Reminder timers now use separate hour (0-24) and minute (0-60) selectors.

### Changed
- A plain launch (`python3 -m sticky_notes`) starts quietly: it restores notes and resumes timers without opening a browser. Use `--editor` to open the editor.

## 2026-09-19

### Added
- Themed confirmation dialogs shared by the desktop notes and the web editor.
- Desktop notes gained Delete controls (with confirmation) beside Edit; closing a note's window asks Hide / Delete / Cancel.

## 2026-09-19

### Added
- Initial release: X11 sticky notes that float above the desktop, a local token-authenticated web editor, reminder timers with snooze, pastel and custom colors, and persistent notes under `$XDG_DATA_HOME/sticky-notes/`.
