import threading
import time
import unittest
from pathlib import Path

from services.web_server import WebServerManager


class _FakeServer:
    def __init__(self, should_crash_once: bool, events: list, stop_after_starts: int = 2):
        self.allow_reuse_address = False
        self._should_crash_once = should_crash_once
        self._events = events
        self._stop_after_starts = stop_after_starts
        self._stop_serving = threading.Event()
        self.closed = False

    def serve_forever(self, poll_interval=0.5):
        self._events.append("serve")
        if self._should_crash_once and len(self._events) == 1:
            raise RuntimeError("Simulated socket failure")
        while not self._stop_serving.is_set():
            time.sleep(0.02)

    def shutdown(self):
        self._events.append("shutdown")
        self._stop_serving.set()

    def server_close(self):
        self.closed = True


class TestWebServerSupervisor(unittest.TestCase):
    def test_web_server_restarts_automatically_after_crash_and_stops_cleanly(self):
        events = []
        servers = []

        def fake_app_factory():
            return object()

        def fake_server_factory(host, port, app):
            srv = _FakeServer(should_crash_once=True, events=events)
            servers.append(srv)
            return srv

        manager = WebServerManager(
            host="127.0.0.1",
            port=8000,
            app_factory=fake_app_factory,
            server_factory=fake_server_factory,
            initial_backoff=0.05,
            max_backoff=0.1,
        )

        try:
            self.assertTrue(manager.start())
            deadline = time.monotonic() + 3.0
            while len(servers) < 2 and time.monotonic() < deadline:
                time.sleep(0.03)

            self.assertGreaterEqual(len(servers), 2)
            self.assertTrue(manager.is_running())
            self.assertTrue(servers[0].closed)
        finally:
            manager.stop(timeout=2.0)

        self.assertFalse(manager.is_running())
        self.assertTrue(all(s.closed for s in servers))

    def test_pyinstaller_script_does_not_copy_local_env(self):
        script_text = Path("scripts/pyinstaller/pyinstaller.py").read_text(encoding="utf-8")
        self.assertNotIn('shutil.copy(env_path, dist_path)', script_text)
        self.assertIn('--collect-all=qrcode', script_text)
        self.assertIn('--collect-all=pyzipper', script_text)
        self.assertIn('--hidden-import=services.web_server', script_text)


if __name__ == "__main__":
    unittest.main()
