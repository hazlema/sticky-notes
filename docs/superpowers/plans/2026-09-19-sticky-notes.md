# X11 Sticky Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver persistent, always-on-top X11 sticky notes with a local web editor and reminder alerts.

**Architecture:** Tk owns application state on its main thread. A loopback HTTP server submits commands through a bounded queue; browser assets poll for snapshots. A separate model validates and atomically persists changes before publishing them to the GUI.

**Tech Stack:** Python 3.10+, Tkinter 8.6, standard-library HTTP server, HTML/CSS/JavaScript, unittest, Xvfb.

**Spec:** `docs/superpowers/specs/2026-09-19-sticky-notes-design.md`

## Global Constraints

- Use Python's standard library and Tkinter, avoiding external Python dependencies.
- The HTTP service binds only to `127.0.0.1`.
- HTTP handlers never call Tk directly.
- A failed save must not be reported as successful.
- Render note text as text, never HTML.
- Timers run only while the application is running; they do not wake a stopped app or suspended computer.
- The current folder has no usable Git repository. Keep changes in this project; do not create a worktree or attempt commits unless a usable repository becomes available.

## Review Focus

1. Disk-full/permission errors must preserve the previous persisted and in-memory state (Task 1).
2. Corrupt files and non-finite numeric inputs must produce errors without overwriting data (Task 1).
3. Hidden overdue notes must appear once, and dismissed alerts must stay dismissed after restart (Tasks 1 and 2).
4. Disconnected monitors must not leave restored windows unreachable (Task 2).
5. Polling must not overwrite an unsaved browser draft; queued request timeouts must not later execute unnoticed (Task 3).

## Task 1: Persistent notes and reminder transitions

**Files:** `sticky_notes/__init__.py`, `sticky_notes/model.py`, `tests/test_model.py`.

**Interfaces:** `Store(directory: Path)` loads versioned notes; `snapshot() -> list[dict]` returns copies; `execute(command: str, payload: dict, now: float) -> dict` validates and persists a mutation; `tick(now: float) -> list[str]` returns newly activated reminder IDs. IDs are UUID strings. Commands are `create`, `update`, `delete`, `visibility`, `visibility_all`, `schedule`, `cancel`, `dismiss`, `snooze`, and `geometry`.

- [x] Write model tests before implementation, including this state transition:

```python
with TemporaryDirectory() as directory:
    store = Store(Path(directory))
    note = store.execute('create', {'title': 'Tea', 'body': 'Take a break',
                                  'color': '#fff2a8'}, now=100)
    store.execute('schedule', {'id': note['id'], 'minutes': 1}, now=100)
    store.execute('visibility', {'id': note['id'], 'visible': False}, now=101)
    assert store.tick(159) == []
    assert store.tick(160) == [note['id']]
    assert store.snapshot()[0]['visible'] is True
    assert Store(Path(directory)).tick(161) == []
```

- [x] Run `python3 -m unittest discover -s tests -p test_model.py -v`; confirm missing implementation fails.
- [x] Implement schema version 1, UUID IDs, default 300×260 geometry, title limit 200, body limit 100,000 characters, strict `#RRGGBB` color validation, strict booleans, finite deadlines, and reminder durations from 1/60 to 525600 minutes. Reject unknown fields and malformed stored schemas.
- [x] Write candidate state to a temporary file in the data directory, flush/fsync, then `os.replace`; only publish candidate state after replacement succeeds. Delete temporary files on failure. Use deep copies for snapshots.

```python
candidate = copy.deepcopy(self.notes)
result = apply_command(candidate, command, payload, now)
self._save(candidate)
self.notes = candidate
return copy.deepcopy(result)
```

- [x] Add tests for all commands, restart persistence, overdue startup, snooze at `now + 300`, hide while active, invalid IDs/colors/booleans/non-finite numbers, schema rejection, and save failure using `unittest.mock.patch` on `os.replace`. Assert both the old file contents and old snapshot survive failure.
- [x] Run the model tests to passing before proceeding.

## Task 2: X11 windows and application lifecycle

**Files:** `sticky_notes/desktop.py`, `sticky_notes/__main__.py`, `tests/test_desktop.py`.

**Interfaces:** `Desktop(root, store, open_editor)` owns `windows: dict[str, NoteWindow]`; `refresh(alert_ids=())` reconciles a store snapshot into Tk windows; `close()` flushes pending geometry. `NoteWindow` exposes its `window` Toplevel. `main()` parses `--port` (default 8765), `--data-dir`, and `--no-browser`.

- [x] Write a Tk smoke test before implementation:

```python
root = tkinter.Tk()
root.withdraw()
desktop = Desktop(root, store, lambda note_id=None: None)
note = store.execute('create', {'title': 'Visible'}, now=100)
desktop.refresh()
root.update()
window = desktop.windows[note['id']].window
assert window.state() != 'withdrawn'
store.execute('visibility', {'id': note['id'], 'visible': False}, now=101)
desktop.refresh()
assert window.state() == 'withdrawn'
desktop.close()
root.destroy()
```

- [x] Run with `xvfb-run -a python3 -m unittest discover -s tests -p test_desktop.py -v` and confirm failure before implementation.
- [x] Implement paper-colored Toplevels, `attributes('-topmost', True)`, a drag header, wrapped read-only body, hide/edit controls, an explicit resize grip, and dismiss/snooze controls for active alerts. Bind close to hide. Choose dark/light text based on background luminance. Preserve scroll position when content is unchanged.
- [x] Clamp restored rectangles to Tk's virtual screen bounds; save moved/resized geometry after a 300 ms debounce. Cancel pending callbacks when a window is deleted. Batch due timers each second, show and lift newly alerted notes, call the bell once per newly activated batch, and never call focus-forcing APIs.
- [x] Extend smoke tests to cover show, deletion, alert reveal, bell invocation once, dismiss, geometry restoration/clamping, and topmost configuration. Use a window manager if available to verify actual stacking, otherwise report that limitation.
- [x] Implement exclusive `fcntl.flock` on a data-directory lock file, XDG data resolution, clear startup errors, signal-driven shutdown, and lifecycle cleanup in `try/finally`. Keep the lock until desktop and HTTP shutdown are complete.
- [x] Run model and Xvfb tests to passing.

## Task 3: Local web service, editor, and delivery

**Files:** `sticky_notes/server.py`, `sticky_notes/web/index.html`, `sticky_notes/web/app.js`, `sticky_notes/web/style.css`, `tests/test_server.py`, `README.md`, `.gitignore`.

**Interfaces:** `Bridge.submit(command, payload)` returns a result through a per-request future; `Bridge.drain(store, desktop)` executes on the Tk thread. `serve(bridge, port, token)` returns an HTTP server bound to loopback. GET `/api/notes` returns a snapshot; POST `/api/command` accepts `{command, payload}`. An authenticated `shutdown` command initiates orderly app exit.

- [x] Write HTTP tests against an ephemeral loopback port. Exercise missing/wrong/correct bearer tokens, invalid Host and Origin, unsupported routes/methods, malformed JSON, oversized bodies, queue-full and cancelled queued requests.

```python
request = urllib.request.Request(base_url + '/api/notes')
with self.assertRaises(urllib.error.HTTPError) as error:
    urllib.request.urlopen(request)
self.assertEqual(error.exception.code, 401)
```

- [x] Run server tests to confirm missing implementation fails.
- [x] Implement a queue of at most 128 requests, five-second queue deadline, and futures whose cancellation is checked before executing a command. Distinguish queued timeout from already-running commands so completed mutations are not misreported as cancelled. Set connection read timeouts and limit JSON bodies to 512 KiB. Restrict static assets to exact known paths.
- [x] Generate a random 32-byte URL-safe token, send it in the launch URL fragment, remove it from the address bar after storing it in session storage, and use an Authorization bearer header for API calls. Validate exact loopback Host/port and same-origin Origin when supplied. Send no CORS permissions; disable caching and use a restrictive Content Security Policy with external local scripts/styles.
- [x] Build a responsive paper-inspired editor with note cards, visible/hidden filters, create/edit form, palette/custom color picker, timer minutes field, reminder state, show/hide/delete, global visibility controls, and explicit quit. Use accessible labels, keyboard focus styles, textContent for note text, and inline actionable error messages.
- [x] Poll every two seconds without rewriting the open form. Await each mutation and refresh afterward; disable submitting controls during requests and retain draft text on errors. Confirm deletions and quitting. Show the authenticated editor URL in the launching terminal for `--no-browser` and browser-launch failure.
- [x] Run all tests, then launch under Xvfb with a temporary directory and exercise real HTTP create/edit/hide/show/schedule/dismiss/reload behavior. Launch the editor in an available browser and check narrow/wide layouts, custom colors, empty state, and preservation of drafts during polling.
- [x] Write README instructions for launching, Tkinter installation, data location, timers, beep/window-manager limitations, restart behavior, and the test commands. Include a concrete launch example:

```sh
python3 -m sticky_notes
python3 -m sticky_notes --no-browser --port 8766
python3 -m unittest discover -s tests -v
xvfb-run -a python3 -m unittest discover -s tests -v
```

- [x] Review the completed change against the spec, run `python3 -m compileall -q sticky_notes`, and report verified results and any remaining environment limitations with the launch command.

## Plan self-review

The three tasks cover the specification's data model, timers, desktop controls, editor, security boundaries, persistence, startup/shutdown, and verification requirements. Each review-focus condition has an owning task and test. Desktop-specific stacking and audible sound require the actual window manager and sound configuration; Xvfb alone cannot establish those behaviors.
