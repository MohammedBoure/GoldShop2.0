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
from PySide6.QtCore import QTimer

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

    login_dialog = LoginDialog(data_manager)
    
    if login_dialog.exec() == QDialog.Accepted:
        current_user = login_dialog.authenticated_user
        logging.info(f"User Logged In: {current_user['username']} ({current_user['role']})")
        
        from ui.main_window import MainWindow
        window = MainWindow(data_manager, current_user)
        window.show()
        #QTimer.singleShot(1500, lambda: start_flask_server(qt_app))
        
        sys.exit(qt_app.exec())
    else:
        logging.info("Login cancelled. Exiting.")
        sys.exit(0)

if __name__ == "__main__":
    main()
