"""Launch with python3 -m sticky_notes."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import secrets
import signal
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser
from .model import Store
from .desktop import Desktop
from .server import Bridge, serve
from .session import AlreadyRunning, existing_editor, publish_session


@contextmanager
def instance_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AlreadyRunning(f'Sticky Notes is already running with data directory {directory}.') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description='X11 sticky notes with a local web editor.')
    parser.add_argument('--port', type=int, default=8765, help='local web port (default: 8765; 0 selects a free port)')
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'sticky-notes')
    editor_flags = parser.add_mutually_exclusive_group()
    editor_flags.add_argument('--editor', action='store_true', help='open the editor (default: restore notes without opening a browser)')
    editor_flags.add_argument('--no-browser', action='store_true', help='restore notes without opening a browser (compatibility alias for the default)')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port must be between 0 and 65535')
    root = server = desktop = thread = session_path = None
    try:
        with instance_lock(args.data_dir.expanduser()):
            try:
                store = Store(args.data_dir.expanduser())
                root = tk.Tk(className='StickyNotes')
                root.withdraw()
                if root.tk.call('tk', 'windowingsystem') != 'x11':
                    raise RuntimeError('This application requires an X11 display.')
                stopping = False
                last_error = None

                def stop():
                    nonlocal stopping
                    stopping = True

                def report(error):
                    nonlocal last_error
                    text = str(error)
                    print(f'Sticky Notes: {text}', file=sys.stderr, flush=True)
                    if text != last_error:
                        last_error = text
                        messagebox.showerror('Sticky Notes could not save', text, parent=root)

                def tk_error(kind, error, traceback):
                    report(error)

                root.report_callback_exception = tk_error
                bridge = Bridge(shutdown=stop)
                token = secrets.token_urlsafe(32)
                server = serve(bridge, args.port, token)
                url = f'http://127.0.0.1:{server.server_address[1]}/#token={token}'

                def open_editor(note_id=None):
                    target = url + (f'&note={note_id}' if note_id else '')
                    def launch():
                        try:
                            if not webbrowser.open(target):
                                print(f'Open your editor: {target}', flush=True)
                        except webbrowser.Error:
                            print(f'Open your editor: {target}', flush=True)
                    threading.Thread(target=launch, daemon=True).start()

                desktop = Desktop(root, store, open_editor)
                desktop.refresh(store.tick(time.time()))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                session_path = publish_session(store.directory, server.server_address[1], token)
                print(f'Sticky Notes editor: {url}', flush=True)
                print(f'Notes saved in: {store.path}\nQuit from the editor or press Ctrl+C.', flush=True)
                if args.editor:
                    open_editor()
                signal.signal(signal.SIGINT, lambda *_: stop())
                signal.signal(signal.SIGTERM, lambda *_: stop())
                last_tick = 0

                def pump():
                    nonlocal last_tick
                    if stopping:
                        root.quit()
                        return
                    bridge.drain(store, desktop)
                    now = time.time()
                    if now - last_tick >= 1:
                        last_tick = now
                        try:
                            desktop.refresh(store.tick(now))
                        except (OSError, ValueError) as error:
                            report(error)
                    root.after(30, pump)

                root.after(30, pump)
                root.mainloop()
            finally:
                if session_path:
                    session_path.unlink(missing_ok=True)
                if server:
                    if thread:
                        server.shutdown()
                        thread.join(timeout=2)
                    server.server_close()
                try:
                    if desktop:
                        desktop.close()
                finally:
                    if root:
                        root.destroy()
        return 0
    except AlreadyRunning:
        try:
            url = existing_editor(args.data_dir.expanduser())
            print(f'Sticky Notes editor: {url}', flush=True)
            if args.editor:
                if not webbrowser.open(url):
                    print('Open the link above in your browser.', flush=True)
            return 0
        except (OSError, ValueError, RuntimeError, webbrowser.Error) as error:
            print(f'Sticky Notes: {error}', file=sys.stderr)
            return 1
    except (OSError, ValueError, RuntimeError, tk.TclError) as error:
        print(f'Sticky Notes: {error}', file=sys.stderr)
        if isinstance(error, tk.TclError):
            print('Run from an X11 desktop with DISPLAY set and Tkinter installed.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
