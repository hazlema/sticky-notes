# Installer Autostart and README Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python3 -m sticky_notes.install` installs the menu launcher and (by prompt or flag) a login autostart entry, `--uninstall` removes both, and the README is restructured around the new installer.

**Architecture:** All installer logic stays in `sticky_notes/install.py`. A shared `desktop_entry()` builder produces both desktop files so quoting and shared fields cannot drift. New argparse flags (`--autostart`, `--no-autostart`, `--autostart-dir`, `--uninstall`) plus a TTY-aware prompt decide the autostart entry. Tests extend `LauncherTests` in `tests/test_lifecycle.py` using the existing subprocess style.

**Tech Stack:** Python 3.10+ standard library only (argparse, pathlib, sys, os). unittest for tests. No pip dependencies.

## Global Constraints

- Standard library only; no pip or npm dependencies (spec + project rule).
- Python 3.10 or newer.
- Desktop `Exec` lines are NOT shell: no `cd`, `;`, or env-var syntax; working directory comes from the `Path=` key.
- Both desktop files are named exactly `sticky-notes.desktop`.
- Menu launcher Exec ends with ` -m sticky_notes --editor`; autostart Exec ends with ` -m sticky_notes` (no `--editor`).
- Autostart prompt default is YES (`[Y/n]`, empty input = yes); EOF/interrupt = no; non-TTY without flags = skip with a hint.
- Tests must always pass `--applications-dir` AND `--autostart-dir` (temp dirs) and `stdin=subprocess.DEVNULL`, so test runs can never write to the real home directory or hang on the prompt.
- Run all commands from the worktree root: `/home/frosty/Dev/tools/sticky-note/.claude/worktrees/stoic-sammet-b98b60`.
- Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Extract the shared `desktop_entry()` builder (pure refactor)

**Files:**
- Modify: `sticky_notes/install.py`
- Test (existing, must stay green): `tests/test_lifecycle.py`

**Interfaces:**
- Consumes: existing `desktop_value(value)` and `exec_argument(value)` helpers (unchanged).
- Produces: `desktop_entry(project: Path, comment: str, exec_tail: str, extra_lines: list[str]) -> str` — returns the full text of a desktop file ending in a trailing newline. `exec_tail` is appended verbatim after `-m sticky_notes` (pass `' --editor'` or `''`). `extra_lines` are appended after the shared keys. Tasks 2 and 3 rely on this exact signature.

- [ ] **Step 1: Refactor install.py to use a builder, no behavior change**

Replace the entire contents of `sticky_notes/install.py` with:

```python
"""Install the application-menu launcher: python3 -m sticky_notes.install."""
import argparse
import os
from pathlib import Path
import sys


def desktop_value(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r')


def exec_argument(value):
    # Desktop Exec quoting is not shell quoting; percent signs are field codes.
    value = str(value).replace('%', '%%')
    value = ''.join('\\' + char if char in '\\"`$' else char for char in value)
    return desktop_value('"' + value + '"')


def desktop_entry(project, comment, exec_tail, extra_lines):
    return '\n'.join([
        '[Desktop Entry]', 'Version=1.0', 'Type=Application', 'Name=Sticky Notes',
        f'Comment={desktop_value(comment)}',
        f'Exec={exec_argument(sys.executable)} -m sticky_notes{exec_tail}',
        f'Path={desktop_value(project)}',
        f'Icon={desktop_value(project / "sticky_notes/icon.svg")}',
        'Terminal=false', 'StartupNotify=false', 'StartupWMClass=StickyNotes',
        *extra_lines, '',
    ])


def main():
    parser = argparse.ArgumentParser(description='Install the Sticky Notes application-menu icon for this user.')
    parser.add_argument('--applications-dir', type=Path,
                        default=Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'applications')
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    entry = desktop_entry(project, 'Open your sticky note editor; notes keep running when the editor closes',
                          ' --editor', ['Categories=Utility;', 'Keywords=notes;sticky;reminders;'])
    directory = args.applications_dir.expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'sticky-notes.desktop'
    target.write_text(entry, encoding='utf-8')
    print(f'Installed: {target}')
    print('Open Sticky Notes from your application menu. You can pin it to your launcher.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

Note the only content change to the generated file: the key order now puts `Terminal`, `StartupNotify`, `StartupWMClass` before `Categories`/`Keywords`. Desktop-entry key order is not significant.

- [ ] **Step 2: Run the existing launcher test to verify no regression**

Run: `python3 -m unittest discover -s tests -p test_lifecycle.py -v`
Expected: `test_menu_shortcut_explicitly_opens_editor ... ok` and `test_exclusive_lock_and_release ... ok`, `OK` at the end.

- [ ] **Step 3: Verify the module still compiles cleanly**

Run: `python3 -m compileall -q sticky_notes`
Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add sticky_notes/install.py
git commit -m "$(cat <<'EOF'
Extract shared desktop_entry builder in installer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Autostart entry — flags, prompt, and non-TTY skip

**Files:**
- Modify: `sticky_notes/install.py`
- Modify: `tests/test_lifecycle.py` (extend `LauncherTests`, update existing test)

**Interfaces:**
- Consumes: `desktop_entry(project, comment, exec_tail, extra_lines)` from Task 1.
- Produces: CLI flags `--autostart`, `--no-autostart` (mutually exclusive), `--autostart-dir <path>`; helper `wants_autostart(args) -> bool`; test helper `LauncherTests.run_install(self, applications_dir, autostart_dir, *flags) -> subprocess.CompletedProcess`. Task 3 relies on `run_install` and on `--autostart-dir` existing.

- [ ] **Step 1: Write the failing tests**

In `tests/test_lifecycle.py`, replace the whole `LauncherTests` class with:

```python
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
```

(The existing `test_menu_shortcut_explicitly_opens_editor` is rewritten to use `run_install`; its assertion is unchanged.)

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 -m unittest discover -s tests -p test_lifecycle.py -v`
Expected: `test_menu_shortcut_explicitly_opens_editor` FAILS (installer rejects the unknown `--autostart-dir` option, returncode 2), and the three new tests FAIL for the same reason. `test_exclusive_lock_and_release` still passes.

- [ ] **Step 3: Implement flags, prompt, and autostart install**

In `sticky_notes/install.py`:

Update the module docstring:

```python
"""Install the launcher and optional login autostart: python3 -m sticky_notes.install."""
```

Add this function after `desktop_entry`:

```python
def wants_autostart(args):
    if args.autostart:
        return True
    if args.no_autostart:
        return False
    if not sys.stdin.isatty():
        print('Skipped the login autostart entry; rerun with --autostart to enable it.')
        return False
    while True:
        try:
            answer = input('Start notes automatically at login? [Y/n] ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if answer in ('', 'y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print('Please answer y or n.')
```

Replace `main()` with:

```python
def main():
    parser = argparse.ArgumentParser(description='Install the Sticky Notes launcher and optional login autostart for this user.')
    parser.add_argument('--applications-dir', type=Path,
                        default=Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'applications')
    parser.add_argument('--autostart-dir', type=Path,
                        default=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'autostart')
    autostart_flags = parser.add_mutually_exclusive_group()
    autostart_flags.add_argument('--autostart', action='store_true',
                                 help='install the login autostart entry without asking')
    autostart_flags.add_argument('--no-autostart', action='store_true',
                                 help='skip the login autostart entry without asking')
    args = parser.parse_args()
    project = Path(__file__).resolve().parent.parent
    entry = desktop_entry(project, 'Open your sticky note editor; notes keep running when the editor closes',
                          ' --editor', ['Categories=Utility;', 'Keywords=notes;sticky;reminders;'])
    directory = args.applications_dir.expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'sticky-notes.desktop'
    target.write_text(entry, encoding='utf-8')
    print(f'Installed: {target}')
    print('Open Sticky Notes from your application menu. You can pin it to your launcher.')
    if wants_autostart(args):
        autostart = desktop_entry(project, 'Restore sticky notes at login', '',
                                  ['X-GNOME-Autostart-enabled=true'])
        directory = args.autostart_dir.expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / 'sticky-notes.desktop'
        target.write_text(autostart, encoding='utf-8')
        print(f'Installed: {target}')
        print('Sticky notes will restore automatically at login.')
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -p test_lifecycle.py -v`
Expected: all `LauncherTests` and `LifecycleTests` pass, `OK`.

- [ ] **Step 5: Commit**

```bash
git add sticky_notes/install.py tests/test_lifecycle.py
git commit -m "$(cat <<'EOF'
Install a login autostart entry from the installer

Prompt on a TTY (default yes), obey --autostart/--no-autostart
non-interactively, and skip with a hint when stdin is not a TTY.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `--uninstall` mode

**Files:**
- Modify: `sticky_notes/install.py`
- Modify: `tests/test_lifecycle.py` (extend `LauncherTests`)

**Interfaces:**
- Consumes: `run_install` helper and `--autostart-dir` flag from Task 2.
- Produces: CLI flag `--uninstall`; function `uninstall(applications_dir: Path, autostart_dir: Path) -> int` returning 0.

- [ ] **Step 1: Write the failing tests**

Append to `LauncherTests` in `tests/test_lifecycle.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -p test_lifecycle.py -v`
Expected: `test_uninstall_removes_both_entries_and_is_idempotent` FAILS (unknown option `--uninstall`, returncode 2 instead of 0). `test_uninstall_rejects_autostart_flags` may already pass (unknown option also exits 2) — that is acceptable; the removal test is the real gate.

- [ ] **Step 3: Implement uninstall**

In `sticky_notes/install.py`, add after `wants_autostart`:

```python
def uninstall(applications_dir, autostart_dir):
    removed = False
    for target in (applications_dir / 'sticky-notes.desktop', autostart_dir / 'sticky-notes.desktop'):
        try:
            target.unlink()
        except FileNotFoundError:
            continue
        print(f'Removed: {target}')
        removed = True
    if not removed:
        print('Nothing to remove; no Sticky Notes desktop entries were installed.')
    print('Saved notes were not touched.')
    return 0
```

In `main()`, update the parser description and add the flag (with the other `add_argument` calls, before `parse_args`):

```python
    parser = argparse.ArgumentParser(description='Install or remove the Sticky Notes launcher and login autostart entry for this user.')
```

```python
    parser.add_argument('--uninstall', action='store_true',
                        help='remove the application-menu launcher and login autostart entry')
```

Immediately after `args = parser.parse_args()`, add:

```python
    if args.uninstall:
        if args.autostart or args.no_autostart:
            parser.error('--uninstall cannot be combined with --autostart or --no-autostart')
        return uninstall(args.applications_dir.expanduser(), args.autostart_dir.expanduser())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -p test_lifecycle.py -v`
Expected: all tests pass, `OK`.

- [ ] **Step 5: Commit**

```bash
git add sticky_notes/install.py tests/test_lifecycle.py
git commit -m "$(cat <<'EOF'
Add --uninstall to remove both desktop entries

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: README restructure

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: installer behavior from Tasks 2–3 (prompt text, flag names, file paths). No code interfaces.
- Produces: documentation only.

New section order: intro → Install → Open from your application menu → Run from a terminal → Using your notes → Reminders → Start notes automatically at login → Saved data → Back up and restore → Update → Uninstall → Troubleshooting → Development and tests.

- [ ] **Step 1: Rewrite the changed sections and reorder**

Keep the title block (heading, image, intro paragraph) unchanged. Then apply these section changes; sections not listed here move verbatim into the order above.

Replace **## Install on a new computer** with:

````markdown
## Install on a new computer

Requirements: Linux with an X11 display (including an accessible XWayland display), Python 3.10 or newer, Tkinter, and a web browser. There are no pip or npm dependencies and no build step. A Wayland compositor may limit XWayland stacking behavior; this app targets X11.

On Debian/Ubuntu:

```sh
sudo apt update
sudo apt install git python3 python3-tk
git clone https://github.com/hazlema/sticky-notes.git
cd sticky-notes
python3 -m sticky_notes.install
python3 -m sticky_notes --editor
```

On Fedora, install the prerequisites with `sudo dnf install git python3 python3-tkinter`, then use the same clone and launch commands. For a private repository, authenticate to GitHub first (for example `gh auth login`, then `gh repo clone hazlema/sticky-notes`).

The installer creates the application-menu launcher at `~/.local/share/applications/sticky-notes.desktop` (or the corresponding location under `$XDG_DATA_HOME`) and offers to start your notes automatically at login. Answer the prompt, or decide ahead of time in scripts:

```sh
python3 -m sticky_notes.install --autostart     # install the login entry without asking
python3 -m sticky_notes.install --no-autostart  # skip the login entry without asking
```

Both entries point to this checkout and the Python interpreter used for installation. Keep the checkout in a permanent location. If you move it, run the installer again from its new location.
````

Replace **## Open from your application menu** with (drops its duplicate installer command; the rest is the existing text):

````markdown
## Open from your application menu

Find **Sticky Notes** in your application menu and pin it to your launcher if you like.

1. Click the Sticky Notes icon to open the web editor.
2. Create or edit your notes; they appear on the desktop.
3. Close the browser tab/window. The notes and timers keep running.
4. Click the icon again to reopen the editor for the same notes.

The Python process remains running because it owns the desktop windows. Reopening the editor reuses that process; it does not create another set of notes or change which notes are hidden. **Quit notes app** is the separate action that closes all note windows and stops timers.
````

In **## Run from a terminal**, delete the duplicated requirements paragraph (the one beginning `Requirements: Linux with an X11 display …`) and the sentence `This is suitable for login/startup commands.` — everything else stays as is.

Replace **## Start notes automatically at login** with:

````markdown
## Start notes automatically at login

The installer manages login startup: it asks `Start notes automatically at login? [Y/n]` and creates `~/.config/autostart/sticky-notes.desktop` (or the corresponding location under `$XDG_CONFIG_HOME`) when you accept. At login the entry runs `python3 -m sticky_notes` without `--editor`, quietly restoring visible notes and resuming timers without opening a browser. Hidden notes stay hidden unless a reminder comes due. Your application-menu shortcut still includes `--editor`, so clicking the icon opens the editor.

To enable login startup later, rerun `python3 -m sticky_notes.install --autostart`. To disable it, delete the autostart file (`--uninstall` also removes it):

```sh
rm "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/sticky-notes.desktop"
```

Avoid adding a hand-written command in your desktop's Startup Applications dialog: desktop `Exec` lines are not shell commands, so `cd` and `;` fail silently there. The installer writes the entry with the correct working directory instead.

After updating from an older version, quit the running app once and rerun `python3 -m sticky_notes.install` so your shortcuts pick up the current options.
````

Replace **## Uninstall** with:

````markdown
## Uninstall

Quit the app, then remove the menu entry and the login autostart entry with one command from this directory:

```sh
python3 -m sticky_notes.install --uninstall
```

You can then remove the cloned project directory. Your saved notes remain in the separate data directory unless you explicitly delete them.
````

Replace **## Update** with:

````markdown
## Update

Stop the running app before updating so the old code is not still holding your notes: use **Quit notes app** in the editor (this saves its last changes), or press Ctrl+C in the terminal that launched it. Confirm nothing is still running:

```sh
pgrep -af sticky_notes   # no output means the app is stopped
```

If an instance is still listed and you cannot reach its editor, stop it with:

```sh
pkill -f "python3 -m sticky_notes"
```

Then, from your checkout:

```sh
git pull --ff-only
python3 -m sticky_notes.install
python3 -m sticky_notes
```

Saved notes are separate from the checkout and survive updates.
````

In **## Development and tests**, change the project-layout line for the installer to:

```markdown
- `sticky_notes/install.py`: application-menu launcher and login autostart installation.
```

- [ ] **Step 2: Verify the result**

Run: `grep -n "^## " README.md`
Expected order: Install on a new computer, Open from your application menu, Run from a terminal, Using your notes, Reminders, Start notes automatically at login, Saved data, Back up and restore your notes, Update, Uninstall, Troubleshooting, Development and tests.

Run: `grep -c "Requirements:" README.md` → expected `1`.
Run: `grep -n "sh -c" README.md` → expected no matches.
Run: `awk '/^## Open from your application menu/,/^## Run from a terminal/' README.md | grep -c "sticky_notes.install"` → expected `0` (the menu section no longer repeats the installer command).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Restructure README around the installer-managed autostart

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Full-suite and real-system verification

**Files:**
- No changes; verification only.

**Interfaces:**
- Consumes: everything above.
- Produces: evidence for the completion claim.

- [ ] **Step 1: Run the full Python test suite**

Run: `xvfb-run -a python3 -m unittest discover -s tests -v` (fall back to `python3 -m unittest discover -s tests -v` if Xvfb is unavailable; Tk tests need a display).
Expected: `OK` with no failures.

- [ ] **Step 2: Compile check**

Run: `python3 -m compileall -q sticky_notes`
Expected: no output, exit 0.

- [ ] **Step 3: Validate generated desktop files**

```bash
SCRATCH=$(mktemp -d)
python3 -m sticky_notes.install --applications-dir "$SCRATCH/apps" --autostart-dir "$SCRATCH/auto" --autostart
desktop-file-validate "$SCRATCH/apps/sticky-notes.desktop" && echo MENU_VALID
desktop-file-validate "$SCRATCH/auto/sticky-notes.desktop" && echo AUTOSTART_VALID
rm -rf "$SCRATCH"
```

Expected: `MENU_VALID` and `AUTOSTART_VALID` (desktop-file-validate prints nothing on success).

- [ ] **Step 4: Real-launch smoke test of the autostart entry**

```bash
SCRATCH=$(mktemp -d)
python3 -m sticky_notes.install --applications-dir "$SCRATCH/apps" --autostart-dir "$SCRATCH/auto" --autostart
sed "s|-m sticky_notes$|-m sticky_notes --data-dir $SCRATCH/data --port 0|" "$SCRATCH/auto/sticky-notes.desktop" > "$SCRATCH/test-launch.desktop"
gio launch "$SCRATCH/test-launch.desktop"
sleep 3
pgrep -af "sticky_notes --data-dir $SCRATCH" && echo LAUNCHED_OK
pkill -f -- "--data-dir $SCRATCH/data"
rm -rf "$SCRATCH"
```

Expected: `LAUNCHED_OK` printed; process appears without `--editor`.

- [ ] **Step 5: Push the branch**

```bash
git push origin claude/stoic-sammet-b98b60
```
