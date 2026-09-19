"""Discover a running instance without creating or changing its notes."""
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.error
import urllib.request


class AlreadyRunning(RuntimeError):
    pass


def publish_session(directory, port, token):
    path = Path(directory) / 'session.json'
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                         suffix='.tmp', delete=False) as handle:
            name = handle.name
            os.chmod(name, 0o600)
            json.dump({'port': port, 'token': token}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return path


def existing_editor(directory, timeout=5):
    """Wait for startup and authenticate against loopback before using metadata."""
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while True:
        try:
            data = json.loads((Path(directory) / 'session.json').read_text(encoding='utf-8'))
            port, token = data['port'], data['token']
            if (type(port) is not int or not 1 <= port <= 65535
                    or not isinstance(token, str) or not 20 <= len(token) <= 100
                    or any(char not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for char in token)):
                raise ValueError('Invalid session metadata')
            base = f'http://127.0.0.1:{port}'
            request = urllib.request.Request(base + '/api/notes',
                                             headers={'Authorization': 'Bearer ' + token})
            with opener.open(request, timeout=min(1, max(.01, deadline - time.monotonic()))) as response:
                if response.status != 200:
                    raise ValueError('Instance is not ready')
            return base + '/#token=' + token
        except (OSError, ValueError, KeyError, TypeError):
            if time.monotonic() >= deadline:
                raise RuntimeError('Sticky Notes is running but its editor is not responding. '
                                   'If it was started before this update, quit that instance once and launch again.') from None
            time.sleep(.1)
