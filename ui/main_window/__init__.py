# ui/main_window/__init__.py

import os
import sys
import logging
import json

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QWidget,
)

from database import active_user_id
from ui.account_switcher_dialog import AccountSwitcherDialog
from ui.dialog_theme import apply_dialog_theme
from ui.main_window.appearance import MainWindowAppearanceMixin, get_resource_path
from ui.main_window.background import MainWindowBackgroundMixin
from ui.main_window.pages import MainWindowPagesMixin


class ToolsDialog(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Outils")
        self.setFixedSize(400, 200) # تم تصغير حجم النافذة ليناسب زرين فقط
        self.setStyleSheet("QDialog { background-color: #ecf0f1; }")
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        button_style = """
            QPushButton {
                background-color: white; border: 2px solid #bdc3c7; border-radius: 10px;
                font-size: 16px; font-weight: bold; color: #2c3e50; padding: 15px; text-align: left;
            }
            QPushButton:hover { background-color: #3498db; color: white; border: 2px solid #2980b9; }
        """

        # تم حذف جميع الأدوات غير المرغوبة والاحتفاظ بالكلر والنمبر باد فقط
        tools = [
            ("Clavier Virtuel", "fa5s.keyboard", "tool_calculator", self.main_window.open_keyboard),
            ("Pavé Numérique", "fa5s.th", "tool_calculator", self.main_window.open_numpad),
        ]

        # وضع الزرين بجانب بعض في نفس الصف
        for column, (title, icon, permission_key, action) in enumerate(tools):
            if self.main_window.has_permission(permission_key):
                button = QPushButton(f"  {title}")
                button.setIcon(qta.icon(icon, color="#34495e"))
                button.setIconSize(QSize(30, 30))
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                button.setStyleSheet(button_style)
                button.clicked.connect(self.wrap_action(action))
                layout.addWidget(button, 0, column)

        close_button = QPushButton(" Fermer")
        close_button.setIcon(qta.icon("fa5s.times", color="white"))
        close_button.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; "
            "font-size: 16px; border-radius: 10px; padding: 10px;"
        )
        close_button.clicked.connect(self.reject)
        layout.addWidget(close_button, 1, 0, 1, 2) # زر الإغلاق يأخذ عرض الصف بالكامل

    def wrap_action(self, action):
        def wrapper():
            self.accept()
            action()
        return wrapper


class MainWindow(
    MainWindowBackgroundMixin,
    MainWindowAppearanceMixin,
    MainWindowPagesMixin,
    QMainWindow,
):
    def __init__(self, data_manager, current_user):
        super().__init__()
        self.data_manager = data_manager
        self.current_user = current_user

        active_user_id.set(self.current_user["id"])

        raw_perms = self.current_user.get("permissions")
        if isinstance(raw_perms, str):
            try:
                parsed = json.loads(raw_perms)
                self.user_permissions = [k for k, v in parsed.items() if v] if isinstance(parsed, dict) else (parsed or [])
            except Exception:
                self.user_permissions = []
        elif isinstance(raw_perms, dict):
            self.user_permissions = [k for k, v in raw_perms.items() if v]
        elif isinstance(raw_perms, list):
            self.user_permissions = raw_perms
        else:
            self.user_permissions = []
            
        self.user_permissions_set = set(self.user_permissions)
        self._skip_exit_confirmation = False

        self.config_file = "config.json"
        self._ui_customization_cache = None
        self._ui_customization_cache_mtime = None

        self.zoom_scale = 1.0
        self.load_saved_zoom()
        self.base_sidebar_full = 250
        self.base_sidebar_compact = 70
        self.loaded_pages = {}
        self.is_sidebar_expanded = True
        self.sidebar_full_width = int(self.base_sidebar_full * self.zoom_scale)
        self.sidebar_compact_width = int(self.base_sidebar_compact * self.zoom_scale)
        self.button_texts = {}

        role_display = current_user.get("role", "User")
        self.setWindowTitle(f"GoldShop Manager - {current_user['username']} ({role_display})")
        self.setMinimumSize(QSize(1024, 700))
        self.setWindowState(Qt.WindowMaximized)

        self.main_widget = QWidget()
        self.main_widget.setObjectName("main_widget")
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._setup_sidebar()

        self.content_area = QStackedWidget()
        self.main_layout.addWidget(self.content_area)

        self._init_placeholders()
        self.refresh_ui_scaling()

        QTimer.singleShot(120, self._open_first_available_page)
        QTimer.singleShot(3000, self._start_auto_backup)
        self.setup_runtime_command_watcher()
        QTimer.singleShot(4500, self.setup_duckdns_timer)
        app = QApplication.instance()
        if app is not None:
            app.current_main_window = self
            app.aboutToQuit.connect(self._stop_background_workers)

    def closeEvent(self, event):
        if not self._skip_exit_confirmation and not self._confirm_application_exit():
            event.ignore()
            return
        self._stop_background_workers()
        event.accept()

    def _confirm_application_exit(self):
        dialog = QMessageBox(self)
        apply_dialog_theme(dialog, self, "exitConfirmationDialog")
        dialog.setIcon(QMessageBox.Question)
        dialog.setWindowTitle("Confirmation de sortie")
        dialog.setText("Voulez-vous vraiment quitter le programme ?")
        dialog.setInformativeText("Verifiez que les operations en cours sont terminees avant de fermer.")
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.setDefaultButton(QMessageBox.No)

        yes_button = dialog.button(QMessageBox.Yes)
        no_button = dialog.button(QMessageBox.No)
        if yes_button is not None:
            yes_button.setText("Quitter")
            yes_button.setProperty("danger", True)
        if no_button is not None:
            no_button.setText("Annuler")
            no_button.setProperty("primary", True)

        return dialog.exec() == QMessageBox.Yes

    def open_numpad(self):
        if not hasattr(self, "numpad_dialog") or self.numpad_dialog is None:
            from ui.tools.virtual_numpad import VirtualNumpad
            self.numpad_dialog = VirtualNumpad("Pavé Numérique", allow_decimal=True, parent=self)
        self.numpad_dialog.clear_display()
        self.numpad_dialog.show()
        self.numpad_dialog.raise_()
        self.numpad_dialog.activateWindow()

    def open_keyboard(self):
        if not hasattr(self, "keyboard_dialog") or self.keyboard_dialog is None:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog
            self.keyboard_dialog = VirtualKeyboardDialog(parent=self)
        self.keyboard_dialog.display.clear()
        self.keyboard_dialog.show()
        self.keyboard_dialog.raise_()
        self.keyboard_dialog.activateWindow()

    def open_tools_dialog(self):
        dialog = ToolsDialog(self, self)
        dialog.exec()

    def switch_to_user(self, new_user):
        if not new_user:
            return
        replacement = MainWindow(self.data_manager, new_user)
        app = QApplication.instance()
        if app is not None:
            app.current_main_window = replacement
        replacement.show()
        self._skip_exit_confirmation = True
        try:
            self.close()
        finally:
            self._skip_exit_confirmation = False

    def has_permission(self, permission_key):
        """التحقق مما إذا كان المستخدم يمتلك الصلاحية المطلوبة"""
        # السماح دائماً إذا لم تكن هناك صلاحية محددة مطلوبة
        if not permission_key:
            return True
            
        # ⚠️ صلاحيات أساسية إلزامية لكل المستخدمين (الخروج وإدارة الحساب)
        if permission_key in ("footer_account", "act_account_logout"):
            return True
            
        # السماح المطلق لمدير النظام (Admin)
        if self.current_user.get("role") == "Admin":
            return True
            
        # التحقق من وجود الصلاحية في قائمة صلاحيات المستخدم الحالي
        return permission_key in self.user_permissions_set

    def _open_first_available_page(self):
        if hasattr(self, "nav_group") and self.nav_group.buttons():
            first_button = self.nav_group.buttons()[0]
            first_button.setChecked(True)
            self.switch_page(self.nav_group.id(first_button))

    def open_account_menu(self):
        dialog = AccountSwitcherDialog(
            self.data_manager,
            self.current_user,
            self,
            can_switch=self.has_permission("act_account_switch"),
            can_logout=self.has_permission("act_account_logout"),
            can_logout_all=self.has_permission("act_account_logout"),
        )
        if dialog.exec() != QDialog.Accepted:
            return

        if dialog.action == "logout":
            self.logout_app()
            return
        if dialog.action == "logout_all":
            self.logout_all_accounts()
            return
        if dialog.action == "switch":
            self.switch_to_user(dialog.selected_user)

    def logout_app(self):
        confirm = QMessageBox.question(
            self, "Déconnexion", "Voulez-vous vraiment vous déconnecter ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._skip_exit_confirmation = True
            try:
                if self.close():
                    os.execl(sys.executable, sys.executable, *sys.argv)
            finally:
                self._skip_exit_confirmation = False

    def logout_all_accounts(self):
        try:
            from services.runtime_control import create_force_logout_command, execute_force_logout_command
            command = create_force_logout_command(
                self.data_manager.db,
                issued_by=f"ui:{self.current_user.get('username', 'unknown')}",
            )
            execute_force_logout_command(command, exit_delay_seconds=0.1)
        except Exception as exc:
            logging.exception("Global account logout failed: %s", exc)
            QMessageBox.critical(self, "Déconnexion globale", f"Impossible de lancer la déconnexion globale:\n{exc}")