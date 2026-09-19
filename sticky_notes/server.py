"""Loopback HTTP interface and main-thread command handoff."""
from concurrent.futures import Future, TimeoutError as FutureTimeout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hmac
import json
import queue
import time


class Bridge:
    def __init__(self, capacity=128, timeout=5, shutdown=None):
        self.queue = queue.Queue(capacity)
        self.timeout = timeout
        self.shutdown = shutdown

    def submit(self, command, payload):
        future = Future()
        try:
            self.queue.put_nowait((command, payload, future))
        except queue.Full:
            raise TimeoutError('The app is busy. Try again shortly.') from None
        try:
            return future.result(timeout=self.timeout)
        except FutureTimeout:
            if future.cancel():
                raise TimeoutError('The app did not respond. The queued request was cancelled.') from None
            # Already running: return its actual outcome, never claim it was cancelled.
            return future.result()

    def drain(self, store, desktop):
        for _ in range(32):
            try:
                command, payload, future = self.queue.get_nowait()
            except queue.Empty:
                break
            if not future.set_running_or_notify_cancel():
                continue
            try:
                if command == 'snapshot':
                    result = store.snapshot()
                elif command == 'shutdown':
                    if self.shutdown:
                        self.shutdown()
                    result = {'ok': True}
                else:
                    result = store.execute(command, payload, time.time())
                    if desktop:
                        desktop.refresh()
                future.set_result(result)
            except Exception as error:
                future.set_exception(error)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(bridge, port, token):
    assets = Path(__file__).with_name('web')

    class Handler(BaseHTTPRequestHandler):
        server_version = 'StickyNotes'

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass

        def send(self, status, data, content_type='application/json; charset=utf-8'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=True, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def trusted(self):
            host = f'127.0.0.1:{self.server.server_address[1]}'
            if self.headers.get_all('Host') != [host] or self.headers.get('Origin', f'http://{host}') != f'http://{host}':
                self.send(403, {'error': 'This editor only accepts requests from its local address.'})
                return False
            return True

        def authorized(self):
            value = self.headers.get('Authorization', '')
            if not hmac.compare_digest(value.encode(), ('Bearer ' + token).encode()):
                self.send(401, {'error': 'Open the editor link printed by the running app to reconnect.'})
                return False
            return True

        def dispatch(self, command, payload):
            try:
                result = bridge.submit(command, payload)
                self.send(200, result)
            except ValueError as error:
                self.send(400, {'error': str(error)})
            except TimeoutError as error:
                self.send(503, {'error': str(error)})
            except OSError as error:
                self.send(500, {'error': f'Could not save notes: {error}. Check disk space and permissions.'})
            except Exception:
                self.send(500, {'error': 'An unexpected error occurred. Check the app terminal.'})

        def do_GET(self):
            if not self.trusted():
                return
            if self.path == '/api/notes':
                if self.authorized():
                    self.dispatch('snapshot', {})
                return
            routes = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path not in routes:
                self.send(404, {'error': 'Not found.'})
                return
            name, content_type = routes[self.path]
            self.send(200, (assets / name).read_bytes(), content_type)

        def do_POST(self):
            if not self.trusted() or not self.authorized():
                return
            if self.path != '/api/command':
                self.send(404, {'error': 'Not found.'})
                return
            if self.headers.get_content_type() != 'application/json':
                self.send(415, {'error': 'Use application/json.'})
                return
            try:
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    raise ValueError()
                length = int(self.headers.get('Content-Length', ''))
                if length > 512 * 1024:
                    self.send(413, {'error': 'Request is too large.'})
                    return
                if length < 0:
                    raise ValueError()
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError()
                data = json.loads(raw)
                if (not isinstance(data, dict) or set(data) != {'command', 'payload'}
                        or not isinstance(data['command'], str) or not isinstance(data['payload'], dict)
                        or data['command'] == 'snapshot'):
                    raise ValueError()
            except (ValueError, UnicodeError):
                self.send(400, {'error': 'Send a JSON object with command and payload fields.'})
                return
            self.dispatch(data['command'], data['payload'])

        def unsupported(self):
            self.send(405, {'error': 'Method not allowed.'})

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = unsupported

    return LocalServer(('127.0.0.1', port), Handler)
