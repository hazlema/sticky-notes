# X11 Sticky Notes

## Purpose and agreed direction

Build a personal Linux X11 sticky-note application using Python and Tk, with a local browser interface for creating and managing notes. Notes float above ordinary windows and can be hidden without deleting them. Background colors are configurable. Include reminder timers that reveal and highlight a note and request an audible beep.

## User experience

- Run `python3 -m sticky_notes` from the project to start the app and open its local web editor. Provide `--no-browser`, `--port`, and `--data-dir` options.
- The editor lists visible and hidden notes, with a create/edit form for title, plain-text body, background color, and an optional reminder duration in minutes. Provide a small pastel palette plus a custom color picker.
- Each desktop note is a resizable Tk window with a paper-colored body, draggable header, and controls to hide, edit in the browser, and dismiss or snooze an active reminder. Desktop note content is read-only; the web editor is the editing interface.
- Set each note's always-on-top property. Notes keep their size and position; clamp restored positions to the available screen so notes remain reachable. Window-manager support determines exact stacking behavior.
- The web editor supports individual show/hide/delete and Show All / Hide All. Deletion asks for confirmation in the editor. Hiding retains content and timers.
- Closing a note hides it. Stopping the application is a separate, explicit action in the editor or Ctrl+C in its launching terminal.

## Components and data flow

Use Python's standard library and Tkinter, avoiding external Python dependencies. Separate persistence and note validation, the Tk window controller, the local HTTP service, and browser assets.

Tk runs on the main thread and owns all note state. A local HTTP server runs on a background thread. Requests enter a bounded command queue; the Tk loop processes them and returns results. HTTP handlers never call Tk directly. The browser polls for current state so timer alerts and desktop hide actions appear in the editor without a reload.

The HTTP service binds only to `127.0.0.1`. A random per-launch token authorizes API requests; the browser receives it in the launch URL fragment. Validate request origins and Host headers, limit request sizes, and accept JSON for mutations. Render note text as text, never HTML.

## Persistence and reminders

Store versioned JSON under `$XDG_DATA_HOME/sticky-notes/notes.json`, falling back to `~/.local/share/sticky-notes/notes.json`. Save mutations atomically and debounce geometry saves. Allow only one application instance per data directory so competing processes cannot overwrite notes.

Each note stores its ID, title, body, color, position, size, visibility, reminder deadline, and alert state. Validate colors, text lengths, dimensions, reminder durations, and saved data before use. Preserve an unreadable or invalid data file and report the problem instead of silently overwriting it.

Reminder durations become absolute deadlines that survive restart. When due, mark the reminder active, show and raise the note without requesting keyboard focus, highlight its border/header, and request one Tk system bell. Audio depends on the desktop's bell configuration. Dismiss clears the alert; snooze schedules it five minutes later. Cancel removes a pending reminder. Hiding an already active alert leaves it hidden until shown or snoozed; it does not continuously reappear.

If the app restarts after a deadline, trigger the overdue reminder once at startup. Persist active alerts so restarting does not repeatedly beep. Timers run only while the application is running; they do not wake a stopped app or suspended computer.

## Error handling and scope

Show actionable errors for unavailable X11 displays, occupied ports, a second instance, invalid input, and failed saves. A failed save must not be reported as successful. Shut down the HTTP service and flush pending geometry changes on normal exit.

This version does not include cloud sync, rich text, attachments, tray integration, or automatic login startup. Document how to launch the app and the dependency on a Linux X11 session and Tkinter.

## Verification

Use temporary data directories for tests. Cover validation, atomic persistence and reload, visibility changes, due and overdue reminders, dismiss/snooze/cancel, malformed requests, and API authorization. Use Xvfb for a real Tk smoke test covering creation, topmost configuration, hiding/showing, and reminder activation. Check the web interface in a browser where available, and document any unverified desktop-specific behavior.
