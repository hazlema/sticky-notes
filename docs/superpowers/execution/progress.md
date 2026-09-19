# SDD ledger — plan: docs/superpowers/plans/2026-09-19-sticky-notes.md
Ruling: Work directly in the project and retain this ledger; Git-backed scripts/commits are unavailable because .git is not a repository. No user files or history are replaced.
Pre-flight: Task 1 Store snapshot/execute/tick are consumed by Tasks 2 and 3 unchanged.
Pre-flight: Task 2 Desktop refresh is consumed by Task 3 Bridge unchanged.
Design: cool gray desk (#e8edf0), ink (#243744), white editor, paper yellow (#fff2a8), lilac (#e6d7ff), mint (#ccebd9). System sans for controls; Georgia for paper content. A left-aligned note board and persistent editor column put the notes themselves first.
Task 1: in progress.
Task 1: complete — 8 model tests pass, including failed saves and overdue reminders. Initial tests failed on missing model module.
Ruling: create/update accepts an optional minutes field so saving text and setting a reminder is atomic; absent preserves the timer and null cancels it.
Task 2: in progress.
Task 2: complete — Tk creation, hide/show, geometry, reminder highlighting/bell and control visibility tested under Xvfb. Actual X11 window property confirmed _NET_WM_STATE_ABOVE. No usable Git repository, so Git finishing menus do not apply; files stay in the approved project.
Task 3: complete — full suite 21/21 passing, including actual subprocess start, HTTP create/hide, timed reveal, dismiss, shutdown, and restart. Browser smoke passed create/edit/color, draft preservation through polling, hide/show, timed reveal/dismiss, and mobile overflow check.
Debugging: sandbox blocked X11 sockets; tests passed with authorized elevated display/loopback access. Python 3.10 concurrent.futures.TimeoutError differs from built-in TimeoutError; normalized the bridge exception. Oversize-request test now sends oversized length headers without racing server rejection of the body.
Final review: independent reviewer found lone-surrogate input could persist before Tk rendering failed. Added failing validation regression; reject invalid surrogate characters before persistence. Model tests now pass.
Visual QA: form reset button shadowed form.reset; browser startup failed, fixed with explicit HTMLFormElement prototype call; browser smoke now passes. Desktop screenshot exposed clipped footer/alert controls; regression failed, pack order corrected, regression passes. Final screenshot confirms controls fit.
Final: no deferred review findings. System bell invocation verified; audible sound depends on desktop configuration and was not independently verified.
Final layout regression: long titles could consume Hide button space. Failing Tk test reproduced it; reserving button space before the title fixes it. Final suite: 22/22 pass; Python compilation and JavaScript syntax checks pass. Temporary real-desktop test app shut down cleanly.
Follow-up: reusable editor launcher
- Added private per-instance session metadata and authenticated loopback discovery. A second launch opens the running editor and exits successfully without changing note windows or visibility.
- Added a native SVG icon and per-user application-menu installer. Closing the browser is distinct from Quit notes app.
- Regression reproduced original second-launch failure, then passed. Full suite: 23/23, including actual second invocation, browser handoff, private metadata, and metadata cleanup.
Follow-up review: independent reviewer found no actionable issues in launcher/session handoff. Installed ~/.local/share/applications/sticky-notes.desktop and validated it. No existing notes were restarted or changed by installation.
Follow-up: startup defaults and timer controls
- Plain launches now restore notes without opening the editor; --editor explicitly opens/reopens it. --no-browser remains a compatibility alias; flags are mutually exclusive.
- Installed shortcut updated to include --editor. README documents startup commands and the changed defaults.
- Timer form uses Hours 0–24 and Minutes 0–60 dropdowns, initially 0. Zero total reports an error; hours/minutes convert to the existing API duration.
- New regression tests first failed on old launch behavior and missing dropdowns. Final Python suite 25/25 passing. Browser timer test passed all ranges/defaults, zero validation, 90-minute and 25-hour scheduling, and mobile layout; full browser smoke passed in a fresh temporary instance.
- Independent reviewer found no actionable issues. Test-data bulk cleanup was blocked by approval review; data was left intact and a fresh directory used instead.
