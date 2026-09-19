import concurrent.futures
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from sticky_notes.model import Store
from sticky_notes.server import Bridge, serve


class BridgeTests(unittest.TestCase):
    def test_cancelled_queue_does_not_mutate(self):
        bridge = Bridge(timeout=.01)
        with self.assertRaises(TimeoutError):
            bridge.submit('create', {})
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            bridge.drain(store, None)
            self.assertEqual(store.snapshot(), [])

    def test_queue_full(self):
        bridge = Bridge(capacity=1, timeout=.01)
        bridge.queue.put(('snapshot', {}, concurrent.futures.Future()))
        with self.assertRaises(TimeoutError):
            bridge.submit('snapshot', {})

    def test_real_roundtrip(self):
        bridge = Bridge()
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory))
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(bridge.submit, 'create', {'title': 'Web'})
                item = bridge.queue.get(timeout=1)
                bridge.queue.put(item)
                bridge.drain(store, None)
                self.assertEqual(future.result()['title'], 'Web')
                self.assertEqual(store.snapshot()[0]['title'], 'Web')


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = serve(Bridge(timeout=.01), 0, 'test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)
        self.port = self.server.server_address[1]

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method='GET', path='/api/notes', body=None, **headers):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def test_requires_token(self):
        self.assertEqual(self.request()[0], 401)
        self.assertEqual(self.request(Authorization='Bearer wrong')[0], 401)
        self.assertEqual(self.request(Authorization='Bearer test-token')[0], 503)

    def test_rejects_cross_origin_and_bad_host(self):
        self.assertEqual(self.request(path='/', Host='evil.example')[0], 403)
        self.assertEqual(self.request(Origin='https://evil.example')[0], 403)

    def test_malformed_and_oversize_requests(self):
        headers = {'Authorization': 'Bearer test-token', 'Content-Type': 'application/json'}
        for body in ('not json', '[]', '{"command": "create", "payload": {}, "extra": 2}'):
            self.assertEqual(self.request('POST', '/api/command', body, **headers)[0], 400)
        self.assertEqual(self.request('POST', '/api/command', '{}', Authorization='Bearer test-token')[0], 415)
        self.assertEqual(self.request('POST', '/api/command', '{}', **{**headers, 'Content-Length': str(512 * 1024 + 1)})[0], 413)

    def test_static_files_and_unknown_route(self):
        status, body, headers = self.request(path='/')
        self.assertEqual(status, 200)
        self.assertIn(b'Sticky notes', body)
        self.assertIn('Content-Security-Policy', headers)
        self.assertEqual(self.request(path='/../model.py')[0], 404)
        self.assertEqual(self.request('PUT')[0], 405)


if __name__ == '__main__':
    unittest.main()
