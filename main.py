import sys
import os
import logging
import threading
from pathlib import Path


def configure_runtime_directory():
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent
    os.chdir(app_dir)


configure_runtime_directory()

from database.base import Database
from database import LabDataManager

# Load PySide after mysql.connector to avoid Shiboken inspecting mysql's async deps.
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import QTimer, QtMsgType, qInstallMessageHandler

from ui.login_dialog import LoginDialog 
from ui.tools.focus_filter import GlobalFocusSelectFilter
from ui.tools.touch_scroll_filter import GlobalTouchScrollFilter
from ui.tools.virtual_keyboard import configure_auto_virtual_keyboard
from config import load_full_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.getLogger("mysql.connector").setLevel(logging.WARNING)


def qt_message_handler(mode, context, message):
    """Filter out noisy and harmless Qt internal warnings from terminal output."""
    if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtInfoMsg):
        if any(ign in message for ign in (
            "Could not parse stylesheet",
            "SetProcessDpiAwarenessContext",
            "QFontDatabase",
            "Note that Qt no longer ships fonts",
        )):
            return
        logging.debug(f"Qt Warning: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        logging.error(f"Qt Critical: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        logging.critical(f"Qt Fatal: {message}")


def run_flask_server():
    from app import flask_app
    flask_app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)


def start_flask_server(qt_app):
    if hasattr(qt_app, "flask_thread"):
        return
    logging.info("🚀 Starting Flask Web Server in background...")
    flask_thread = threading.Thread(
        target=run_flask_server,
        name="FlaskWebServer",
        daemon=True,
    )
    flask_thread.start()
    qt_app.flask_thread = flask_thread


def main():
    qInstallMessageHandler(qt_message_handler)
    qt_app = QApplication(sys.argv)

    focus_filter = GlobalFocusSelectFilter()
    qt_app.installEventFilter(focus_filter)
    qt_app.focus_filter = focus_filter

    touch_scroll_filter = GlobalTouchScrollFilter()
    qt_app.installEventFilter(touch_scroll_filter)
    qt_app.touch_scroll_filter = touch_scroll_filter

    qt_app.setStyle("Fusion")
    app_config = load_full_config()
    configure_auto_virtual_keyboard(
        bool(app_config.get("auto_virtual_keyboard_enabled", False)),
        app_config.get("auto_virtual_keyboard_targets"),
    )

    try:
        db = Database()
        with db.get_db_connection() as conn:
            logging.info("✅ Database connection established.")
    except Exception as e:
        QMessageBox.critical(None, "Fatal Error", f"Database Error:\n{e}")
        sys.exit(1)

    try:
        data_manager = LabDataManager(db)
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Manager Init Error:\n{e}")
        sys.exit(1)

    current_user = None

    # Try Auto-Login (Skip LoginDialog if session is saved)
    import json
    import base64
    from ui.login_dialog import SESSION_FILE, LEGACY_SESSION_FILE

    session_file = SESSION_FILE if os.path.exists(SESSION_FILE) else LEGACY_SESSION_FILE
    if os.path.exists(session_file):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            username = data.get("username", "")
            token = data.get("token", "")
            
            if token:
                password = base64.b64decode(token).decode('utf-8')
            else:
                password = ""

            if username and password:
                user_found = data_manager.users.authenticate(username, password)
                if user_found:
                    logging.info(f"Auto-login successful for user: {username}")
                    current_user = user_found
                else:
                    logging.warning("Auto-login failed. Clearing session.")
                    if os.path.exists(SESSION_FILE): os.remove(SESSION_FILE)
                    if os.path.exists(LEGACY_SESSION_FILE): os.remove(LEGACY_SESSION_FILE)
        except Exception as e:
            logging.error(f"Session recovery error: {e}")

    # If auto-login failed or no session, show LoginDialog
    if not current_user:
        login_dialog = LoginDialog(data_manager)
        if login_dialog.exec() == QDialog.Accepted:
            current_user = login_dialog.authenticated_user
        else:
            logging.info("Login cancelled. Exiting.")
            sys.exit(0)

    logging.info(f"User Logged In: {current_user['username']} ({current_user['role']})")
    
    from ui.main_window import MainWindow
    window = MainWindow(data_manager, current_user)
    window.show()
    QTimer.singleShot(1500, lambda: start_flask_server(qt_app))
    
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()
