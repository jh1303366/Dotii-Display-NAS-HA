"""Exercise the NAS HTTP boundary and persistence using the actual backend."""
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'bridge'))
from platforms.linux import LinuxPlatformAdapter
from codex_bridge import BridgeHandler, device_snapshot_url

class NasTests(unittest.TestCase):
    def test_headless_capabilities_and_paths(self):
        adapter = LinuxPlatformAdapter()
        self.assertFalse(adapter.bluetooth_available)
        self.assertFalse(adapter.serial_flash_available)
        self.assertFalse(adapter.startup_available)
        with mock.patch.dict(os.environ, {'DOTII_RUNTIME_DIR': '/data'}):
            self.assertEqual(adapter.runtime_folder(), Path('/data'))
        with mock.patch.dict(os.environ, {'DOTII_RUNTIME_DIR': 'relative'}):
            with self.assertRaises(ValueError):
                adapter.runtime_folder()

    def test_public_address_validation(self):
        with mock.patch.dict(os.environ, {'DOTII_PUBLIC_URL': 'http://192.168.1.10:18787/'}):
            self.assertEqual(device_snapshot_url(8787), 'http://192.168.1.10:18787/api/v1/snapshot')
        for bad in ['ftp://example.com', 'http://user:pass@example.com', 'http://example.com/api', 'http://example.com?token=x']:
            with mock.patch.dict(os.environ, {'DOTII_PUBLIC_URL': bad}):
                with self.assertRaises(ValueError):
                    device_snapshot_url(8787)

    def test_desktop_keeps_remote_management_closed(self):
        handler = object.__new__(BridgeHandler)
        handler.client_address = ('192.168.1.5', 1234)
        handler.headers = {}
        with mock.patch.dict(os.environ, {'DOTII_ADMIN_PASSWORD': ''}):
            self.assertFalse(handler._local_admin())
            handler.client_address = ('127.0.0.1', 1234)
            self.assertTrue(handler._local_admin())

    def test_http_auth_device_token_save_and_restart(self):
        with tempfile.TemporaryDirectory() as data:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            env = {**os.environ, 'DOTII_RUNTIME_DIR': data, 'DOTII_ADMIN_PASSWORD': 'test-password-12345', 'DOTII_ADMIN_USER': 'admin', 'DOTII_PUBLIC_URL': 'http://192.168.1.10:18787'}
            env.pop('STATE_DISPLAY_BRIDGE_TOKEN', None)
            auth = 'Basic ' + base64.b64encode(b'admin:test-password-12345').decode()
            launcher = "import sys,runpy; sys.path.insert(0,'bridge'); sys.platform='linux'; sys.argv=['bridge/codex_bridge.py','--host','127.0.0.1','--port',sys.argv[1]]; runpy.run_path('bridge/codex_bridge.py',run_name='__main__')"
            def request(path, headers=None, payload=None):
                body = json.dumps(payload).encode() if payload is not None else None
                req = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=body, headers=headers or {})
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return response.status, response.headers, response.read()
                except urllib.error.HTTPError as response:
                    return response.code, response.headers, response.read()
            token = None
            for iteration in range(2):
                process = subprocess.Popen([sys.executable, '-c', launcher, str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                try:
                    for _ in range(100):
                        if process.poll() is not None:
                            self.fail(process.stderr.read().decode())
                        try:
                            if request('/health')[0] == 200:
                                break
                        except OSError:
                            pass
                        time.sleep(.05)
                    else:
                        self.fail('backend startup timed out')
                    status, headers, _ = request('/')
                    self.assertEqual(status, 401)
                    self.assertIn('Basic', headers['WWW-Authenticate'])
                    self.assertEqual(request('/', {'Authorization': auth})[0], 200)
                    self.assertEqual(request('/api/v1/admin/overview', {'Authorization': 'Basic bad'})[0], 401)
                    status, _, body = request('/api/v1/admin/overview', {'Authorization': auth})
                    self.assertEqual(status, 200)
                    overview = json.loads(body)
                    self.assertEqual(overview['bridge']['device_url'], 'http://192.168.1.10:18787/api/v1/snapshot')
                    self.assertFalse(overview['bluetooth']['available'])
                    if iteration:
                        self.assertEqual(overview['bridge']['token'], token)
                        self.assertEqual(overview['snapshot']['custom']['title'], 'NAS test')
                    else:
                        token = overview['bridge']['token']
                        self.assertEqual(request('/api/v1/snapshot')[0], 401)
                        self.assertEqual(request('/api/v1/snapshot', {'Authorization': auth})[0], 401)
                        self.assertEqual(request('/api/v1/snapshot', {'X-Bridge-Token': token})[0], 200)
                        self.assertEqual(request('/api/v1/admin/overview', {'X-Bridge-Token': token})[0], 401)
                        status, _, _ = request('/api/v1/admin/custom', {'Authorization': auth, 'Content-Type': 'application/json'}, {'title': 'NAS test', 'enabled': True})
                        self.assertEqual(status, 200)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        self.fail('SIGTERM failed to stop backend')
                    process.stderr.close()
