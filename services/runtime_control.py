import json
import logging
import os
import socket
import threading
import uuid
import webbrowser
from datetime import datetime, timezone

from database.base import get_external_path


logger = logging.getLogger("JEWELLERY_SYS")

DEFAULT_FORCE_LOGOUT_URL = "https://www.bullionvault.com/gold-price-chart.do"
FORCE_LOGOUT_METADATA_KEY = "runtime_force_logout_command"

_RUNTIME_STATE_FILE = os.path.join(get_external_path("runtime"), "runtime_control_state.json")
_EXECUTION_LOCK = threading.Lock()
_EXECUTED_COMMAND_IDS = set()


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_metadata_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS AppMetadata (
            meta_key VARCHAR(100) PRIMARY KEY,
            meta_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )


def _metadata_row_value(row):
    if not row:
        return None
    if isinstance(row, dict):
        return row.get("meta_value")
    if isinstance(row, (list, tuple)):
        return row[0] if row else None
    return None


def _read_state():
    try:
        with open(_RUNTIME_STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("Could not read runtime control state: %s", exc)
        return {}


def _write_state(state):
    try:
        os.makedirs(os.path.dirname(_RUNTIME_STATE_FILE), exist_ok=True)
        with open(_RUNTIME_STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Could not persist runtime control state: %s", exc)


def _command_id(command):
    if not isinstance(command, dict):
        return ""
    return str(command.get("id") or "").strip()


def create_force_logout_command(db, url=DEFAULT_FORCE_LOGOUT_URL, issued_by="api"):
    command = {
        "id": uuid.uuid4().hex,
        "type": "force_logout",
        "url": DEFAULT_FORCE_LOGOUT_URL,
        "requested_url": str(url or "").strip(),
        "issued_at": _utc_now(),
        "issued_by": str(issued_by or "api").strip() or "api",
        "issued_from_device": socket.gethostname(),
    }

    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        _ensure_metadata_table(cursor)
        cursor.execute(
            """
            INSERT INTO AppMetadata (meta_key, meta_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                meta_value = VALUES(meta_value),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                FORCE_LOGOUT_METADATA_KEY,
                json.dumps(command, ensure_ascii=False),
            ),
        )
    return command


def load_latest_force_logout_command(db):
    with db.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT meta_value FROM AppMetadata WHERE meta_key = %s",
            (FORCE_LOGOUT_METADATA_KEY,),
        )
        raw_value = _metadata_row_value(cursor.fetchone())

    if not raw_value:
        return None
    try:
        command = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        logger.warning("Invalid runtime force logout command payload.")
        return None
    return command if isinstance(command, dict) else None


def mark_force_logout_command_handled(command):
    command_id = _command_id(command)
    if not command_id:
        return
    state = _read_state()
    state["last_force_logout_command_id"] = command_id
    state["last_force_logout_handled_at"] = _utc_now()
    _write_state(state)


def remember_current_force_logout_command(db):
    command = load_latest_force_logout_command(db)
    if command:
        mark_force_logout_command_handled(command)
    return command


def should_handle_force_logout_command(command):
    command_id = _command_id(command)
    if not command_id:
        return False
    if command_id in _EXECUTED_COMMAND_IDS:
        return False
    return _read_state().get("last_force_logout_command_id") != command_id


def clear_local_login_sessions():
    runtime_dir = get_external_path("runtime")
    paths = [
        os.path.join(runtime_dir, "session.json"),
        os.path.join(runtime_dir, "saved_accounts.json"),
        get_external_path("session.json"),
    ]
    removed = []
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                removed.append(path)
        except OSError as exc:
            logger.warning("Could not remove local login session file %s: %s", path, exc)
    return removed


def _request_qt_exit():
    try:
        from PySide6.QtCore import QMetaObject, Qt
        from PySide6.QtWidgets import QApplication
    except Exception:
        return False

    app = QApplication.instance()
    if app is None:
        return False

    try:
        for widget in app.topLevelWidgets():
            if hasattr(widget, "_skip_exit_confirmation"):
                widget._skip_exit_confirmation = True
    except Exception:
        pass

    try:
        QMetaObject.invokeMethod(app, "quit", Qt.QueuedConnection)
    except Exception:
        app.quit()
    return True


def _request_process_exit(delay_seconds):
    def stop_process():
        if _request_qt_exit():
            return
        os._exit(0)

    timer = threading.Timer(max(0.0, float(delay_seconds or 0.0)), stop_process)
    timer.daemon = True
    timer.start()


def execute_force_logout_command(command, exit_delay_seconds=0.35):
    command_id = _command_id(command)
    if not command_id:
        return False

    with _EXECUTION_LOCK:
        if not should_handle_force_logout_command(command):
            return False
        _EXECUTED_COMMAND_IDS.add(command_id)

    removed_paths = clear_local_login_sessions()
    mark_force_logout_command_handled(command)

    url = str(command.get("url") or DEFAULT_FORCE_LOGOUT_URL).strip() or DEFAULT_FORCE_LOGOUT_URL
    try:
        webbrowser.open(url, new=2, autoraise=True)
    except Exception as exc:
        logger.warning("Could not open force logout browser URL %s: %s", url, exc)

    logger.warning(
        "Runtime force logout command %s handled; removed %s local session files.",
        command_id,
        len(removed_paths),
    )
    _request_process_exit(exit_delay_seconds)
    return True
