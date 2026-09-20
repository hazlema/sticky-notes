# Installer autostart entry and README restructure

## Purpose and agreed direction

Extend `python3 -m sticky_notes.install` so one command manages both desktop-entry files: the existing application-menu launcher and a new login autostart entry. Add an uninstall mode that removes both. Restructure the README into a single logical flow and remove duplicated content, updating the sections the installer now owns.

Motivation: hand-adding a startup command through desktop "Startup Applications" dialogs invites shell syntax (`cd …; python3 …`) that desktop `Exec` lines do not support, producing silently broken entries. The installer already knows the correct pattern (`Path=` key, desktop-entry quoting) and should apply it for login startup too.

## Installer behavior

- `python3 -m sticky_notes.install` installs the application-menu launcher exactly as today, then decides about the autostart entry:
  - If `--autostart` or `--no-autostart` was passed, obey the flag without prompting. The two flags are mutually exclusive.
  - Otherwise, when stdin is a TTY, ask `Start notes automatically at login? [Y/n]` — empty input or `y`/`yes` (case-insensitive) means yes; `n`/`no` means no; EOF or interrupt means no.
  - When stdin is not a TTY and no flag was given, skip the autostart entry and print a hint that `--autostart` enables it. This preserves current behavior for non-interactive runs.
- `python3 -m sticky_notes.install --uninstall` removes both desktop files, prints each path it removed (or that nothing was installed), and reminds the user that saved notes are untouched. It succeeds when the files are already absent. `--uninstall` cannot be combined with `--autostart`/`--no-autostart`.
- A new `--autostart-dir` option mirrors the existing `--applications-dir`, defaulting to `$XDG_CONFIG_HOME/autostart` with fallback `~/.config/autostart`. Both options apply to install and uninstall modes.

## Desktop entry contents

Both entries come from one shared builder so quoting and shared fields cannot drift apart. Shared fields: `Type=Application`, `Version=1.0`, `Name=Sticky Notes`, `Icon` (project icon), `Path` (project checkout), `Terminal=false`, `StartupNotify=false`, `StartupWMClass=StickyNotes`, and the existing Exec quoting rules (`%` escaping, reserved-character backslash escaping, quoted interpreter path).

- Menu launcher (`<applications-dir>/sticky-notes.desktop`): unchanged from today — `Exec=<python> -m sticky_notes --editor`, `Categories`, `Keywords`, comment about the editor.
- Autostart entry (`<autostart-dir>/sticky-notes.desktop`): `Exec=<python> -m sticky_notes` with no `--editor`, so login quietly restores notes and resumes timers without opening a browser. Includes `X-GNOME-Autostart-enabled=true` and a comment describing login restore. No `Categories`/`Keywords` (not a menu item).

The interpreter recorded in both entries is `sys.executable` at install time, and `Path` is the project checkout, matching the existing launcher's behavior and its documented caveat: rerun the installer after moving the checkout.

## README restructure

Reorder into one flow — get it, use it, keep it, fix it, hack it — merging duplicates without dropping factual content:

1. Title, screenshot, intro: unchanged.
2. Install: single requirements paragraph (absorbing the duplicate from "Run from a terminal"), Debian/Ubuntu and Fedora prerequisites, clone, installer. Documents the autostart prompt and the `--autostart`/`--no-autostart` flags. The private-repository note shrinks to one sentence. Keeps the "keep the checkout in a permanent location" warning.
3. Open from your application menu: the four-step usage list and the process-lifetime explanation; drops its duplicate installer command.
4. Run from a terminal: flags and editor-link/token explanation; drops the duplicated requirements paragraph.
5. Using your notes: unchanged.
6. Reminders: unchanged.
7. Start notes automatically at login: rewritten — the installer manages the entry; describes the quiet-restore behavior (no `--editor`), and how to enable later (`--autostart`) or remove (`--uninstall`). The hand-written `sh -c 'cd …'` recipe is deleted.
8. Saved data, then Back up and restore: content unchanged, now adjacent.
9. Update: rewritten to lead with stopping the running app before `git pull` — quit from the editor (or Ctrl+C in the launching terminal), with `pgrep`/`pkill` commands to verify nothing is still running; then the existing pull/reinstall/relaunch commands.
10. Uninstall: becomes `python3 -m sticky_notes.install --uninstall`, noting it removes both entries and that notes data survives.
11. Troubleshooting: moved near the end; entries unchanged.
12. Development and tests: unchanged except the project-layout line for `install.py`, which becomes "application-menu launcher and login autostart installation".

## Error handling

- Conflicting flags (`--autostart` with `--no-autostart`, or either with `--uninstall`) exit with an argparse error.
- Directory creation and file writes use the same approach as today; failures surface as normal Python errors with the offending path.
- The prompt treats unrecognized input as a re-prompt, and EOF/KeyboardInterrupt as "no" so a wedged pipe cannot hang an install.

## Verification

Extend `LauncherTests` in `tests/test_lifecycle.py`, using the existing subprocess style with temporary directories for both `--applications-dir` and `--autostart-dir`:

- `--autostart` writes the autostart entry; its Exec ends with `-m sticky_notes` (no `--editor`) and the entry contains `Path=`.
- `--no-autostart` writes no autostart file; the menu launcher is still written.
- A flagless run with non-TTY stdin writes no autostart file.
- `--uninstall` removes both files, and succeeds again when they are already gone.
- The existing menu-launcher assertions continue to pass unchanged.

Manual verification: run the installer on the real system, confirm both `sticky-notes.desktop` files validate with `desktop-file-validate`, and confirm the autostart entry launches via `gio launch` with a scratch `--data-dir`.

## Out of scope

Systemd user units, Wayland-specific startup, packaging (pip/deb/rpm), migrating or deleting user note data on uninstall, and detecting or repairing foreign autostart entries created by hand.
