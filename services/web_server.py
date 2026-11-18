import logging
import threading
from typing import Callable

from werkzeug.serving import make_server


logger = logging.getLogger("JEWELLERY_SYS")


def _default_app_factory():
    from app import flask_app

    return flask_app


def _default_server_factory(host: str, port: int, app):
    server = make_server(host, port, app, threaded=True)
    server.allow_reuse_address = True
    return server


class WebServerManager:
    """Supervises the embedded Flask WSGI server and restarts it automatically on failure."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        app_factory: Callable | None = None,
        server_factory: Callable | None = None,
        initial_backoff: float = 1.0,
        max_backoff: float = 10.0,
    ):
        self.host = host
        self.port = int(port)
        self._app_factory = app_factory or _default_app_factory
        self._server_factory = server_factory or _default_server_factory
        self._initial_backoff = max(0.05, float(initial_backoff))
        self._max_backoff = max(self._initial_backoff, float(max_backoff))

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._server = None
        self._stopped_explicitly = False

    def is_running(self) -> bool:
        with self._lock:
            return (
                self._thread is not None
                and self._thread.is_alive()
                and not self._stop_event.is_set()
            )

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive() and not self._stop_event.is_set():
                return False
            self._stopped_explicitly = False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="FlaskWebServer",
                daemon=True,
            )
            self._thread.start()
            return True

    def ensure_running(self) -> bool:
        with self._lock:
            if self._stopped_explicitly:
                return False
            alive = self._thread is not None and self._thread.is_alive()
        if not alive:
            logger.warning("⚠️ Flask web server thread is inactive; restarting...")
            return self.start()
        return False

    def stop(self, timeout: float = 3.0) -> None:
        with self._lock:
            self._stopped_explicitly = True
            self._stop_event.set()
            server = self._server
            thread = self._thread

        if server is not None:
            try:
                server.shutdown()
            except Exception as exc:
                logger.debug("Flask server shutdown warning: %s", exc)
            try:
                server.server_close()
            except Exception as exc:
                logger.debug("Flask server close warning: %s", exc)

        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=timeout)

    def _run_loop(self) -> None:
        backoff = self._initial_backoff
        while not self._stop_event.is_set():
            server = None
            try:
                app = self._app_factory()
                server = self._server_factory(self.host, self.port, app)
                with self._lock:
                    self._server = server
                backoff = self._initial_backoff
                logger.info("🌐 Serveur Web Flask actif sur http://%s:%s ...", self.host, self.port)
                server.serve_forever(poll_interval=0.5)
                if not self._stop_event.is_set():
                    logger.warning("⚠️ Serveur Web Flask arrêté de façon inattendue; redémarrage automatique...")
            except Exception as exc:
                if not self._stop_event.is_set():
                    logger.error("❌ Erreur du serveur Web Flask: %s", exc, exc_info=True)
            finally:
                with self._lock:
                    if self._server is server:
                        self._server = None
                if server is not None:
                    try:
                        server.server_close()
                    except Exception:
                        pass

            if not self._stop_event.is_set():
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2.0, self._max_backoff)
