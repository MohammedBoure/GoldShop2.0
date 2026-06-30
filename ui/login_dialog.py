# ui/login_dialog.py

import sys
import json
import os
import base64
import logging
from typing import Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
    QMessageBox, QFrame, QHBoxLayout, QCheckBox, QApplication, QComboBox, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
import qtawesome as qta

from database.base import get_external_path
from licensing import check_license
from ui.activation_dialog import ActivationDialog
from ui.saved_accounts import save_saved_account
from ui.touch_design import TOUCH_BUTTON_HEIGHT, apply_touch_button_defaults, apply_touch_input_defaults
from config import load_full_config
from ui.ui_customization import (
    active_theme,
    build_application_palette,
    build_application_stylesheet,
    ensure_ui_customization,
    is_dark_theme,
    sync_application_inline_styles,
)

RUNTIME_DIR = get_external_path("runtime")
SESSION_FILE = os.path.join(RUNTIME_DIR, "session.json")
LEGACY_SESSION_FILE = get_external_path("session.json")

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class LoginDialog(QDialog):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.authenticated_user = None 
        self.current_request_code = ""
        self.ui_config = ensure_ui_customization(load_full_config())
        self.theme_palette = active_theme(self.ui_config).get("palette", {})
        self.dark_theme = is_dark_theme(self.ui_config)
        
        self.vkb = None 

        self.setWindowTitle("Connexion - GoldShop")
        self.setMinimumSize(780, 520)
        self.resize(840, 560)
        logging.info(
            "Login dialog initialized. cwd=%s session_file=%s legacy_session_file=%s",
            os.getcwd(),
            SESSION_FILE,
            LEGACY_SESSION_FILE,
        )

        try:
            icon_path = get_resource_path(os.path.join("ui", "logo.png"))
            
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logging.warning(f"⚠️ Icône introuvable: {icon_path}")
                
        except Exception as e:
            logging.error(f"Erreur chargement icône: {e}")
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.apply_saved_theme()
        self.init_ui()
        self.refresh_license_status()
        self.load_available_users()
        self.load_session()

    def showEvent(self, event):
        super().showEvent(event)
        screen_geom = QApplication.primaryScreen().availableGeometry()
        x = (screen_geom.width() - self.width()) // 2
        y = 0  # الحافة العلوية
        self.move(x, y)

    def close_keyboard(self):
        if self.vkb and self.vkb.isVisible():
            self.vkb.close()

    def accept(self):
        self.close_keyboard()
        super().accept()

    def reject(self):
        self.close_keyboard()
        super().reject()

    def apply_saved_theme(self):
        app = QApplication.instance()
        if app is None:
            return
        app.setPalette(build_application_palette(self.ui_config))
        app.setStyleSheet(build_application_stylesheet(self.ui_config))
        sync_application_inline_styles(app, self.ui_config)

    def init_ui(self):
        palette = self.theme_palette
        background = palette.get("background", "#f5f7f9")
        surface = palette.get("surface", "#ffffff")
        surface_alt = palette.get("surface_alt", "#eef3f7")
        text = palette.get("text", "#1f2933")
        muted = palette.get("muted", "#6b7280")
        border = palette.get("border", "#d9e1e8")
        primary = palette.get("primary", "#0f8f83")
        primary_hover = palette.get("primary_hover", "#0a7c72")
        selection = palette.get("selection", "#dff2f1")
        danger = palette.get("danger", "#e74c3c")

        self.setStyleSheet(f"""
            QDialog {{ background-color: {background}; color: {text}; }}
            QLabel {{ color: {text}; background: transparent; }}
            QLineEdit {{
                padding: 12px;
                border: 2px solid {border};
                border-radius: 6px;
                font-size: 16px;
                background-color: {surface};
                color: {text};
                selection-background-color: {selection};
                selection-color: {text};
            }}
            QLineEdit:focus {{
                border: 2px solid {primary};
                background-color: {surface};
                color: {text};
            }}
            QComboBox {{
                padding: 8px 12px;
                border: 2px solid {border};
                border-radius: 8px;
                font-size: 15px;
                background-color: {surface};
                color: {text};
                selection-background-color: {selection};
                selection-color: {text};
            }}
            QComboBox:focus {{ border: 2px solid {primary}; }}
            QComboBox QAbstractItemView {{
                background-color: {surface};
                color: {text};
                border: 1px solid {border};
                selection-background-color: {selection};
                selection-color: {text};
            }}
            QPushButton#btn_login {{
                background-color: {primary}; color: white; font-weight: bold;
                padding: 15px; border-radius: 6px; font-size: 18px;
            }}
            QPushButton#btn_login:hover {{ background-color: {primary_hover}; }}
            QPushButton#btn_cancel {{
                background-color: {surface_alt};
                color: {muted};
                font-weight: bold;
                border: 1px solid {border};
                font-size: 16px;
                padding: 15px;
                border-radius: 6px;
            }}
            QPushButton#btn_cancel:hover {{ background-color: {danger}; color: white; }}
            QCheckBox {{ font-size: 15px; font-weight: bold; color: {text}; padding: 5px; }}
            QCheckBox::indicator {{
                width: 24px;
                height: 24px;
                background-color: {surface};
                border: 1px solid {border};
            }}
            QCheckBox::indicator:checked {{
                background-color: {primary};
                border-color: {primary};
            }}
            QLabel#login_message {{
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 14px;
                font-weight: bold;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("login_shell")
        shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        shell.setStyleSheet(f"""
            QFrame#login_shell {{
                background-color: {surface};
                border: none;
                border-radius: 6px;
            }}
        """)
        self.login_shell = shell
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        brand_panel = QFrame()
        brand_panel.setObjectName("login_brand_panel")
        brand_panel.setMinimumWidth(285)
        brand_panel.setMaximumWidth(330)
        brand_panel.setStyleSheet(f"""
            QFrame#login_brand_panel {{
                background-color: {surface_alt};
                border: none;
                border-radius: 6px;
            }}
        """)
        self.login_brand_panel = brand_panel
        brand_layout = QVBoxLayout(brand_panel)
        brand_layout.setContentsMargins(28, 30, 28, 28)
        brand_layout.setSpacing(16)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(qta.icon('fa5s.gem', color=primary).pixmap(94, 94))
        lbl_icon.setAlignment(Qt.AlignCenter)
        brand_layout.addWidget(lbl_icon)

        lbl_brand = QLabel("GoldShop")
        lbl_brand.setAlignment(Qt.AlignCenter)
        lbl_brand.setStyleSheet(f"font-size: 30px; font-weight: 900; color: {text};")
        brand_layout.addWidget(lbl_brand)

        lbl_brand_hint = QLabel("Espace caisse et gestion")
        lbl_brand_hint.setAlignment(Qt.AlignCenter)
        lbl_brand_hint.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {muted};")
        brand_layout.addWidget(lbl_brand_hint)
        brand_layout.addSpacing(8)

        self.license_frame = QFrame()
        self.license_frame.setObjectName("login_license_frame")
        self.license_frame.setStyleSheet(f"""
            QFrame#login_license_frame {{
                background-color: {surface};
                border: none;
                border-radius: 5px;
            }}
            QFrame#login_license_frame QLabel {{
                border: none;
                background: transparent;
                color: {text};
                font-size: 13px;
            }}
            QFrame#login_license_frame QPushButton {{
                background-color: {surface_alt};
                color: {text};
                border: none;
                border-radius: 4px;
                padding: 7px 11px;
                font-weight: bold;
            }}
            QFrame#login_license_frame QPushButton:hover {{ background-color: {primary}; color: white; }}
        """)
        license_layout = QVBoxLayout(self.license_frame)
        license_layout.setContentsMargins(14, 12, 14, 12)
        license_layout.setSpacing(9)

        self.lbl_license_status = QLabel()
        self.lbl_license_status.setWordWrap(True)
        self.lbl_license_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        license_layout.addWidget(self.lbl_license_status)

        license_actions = QHBoxLayout()
        license_actions.setContentsMargins(0, 0, 0, 0)
        license_actions.setSpacing(8)
        self.btn_copy_request_code = QPushButton("Copier")
        self.btn_copy_request_code.setIcon(qta.icon("fa5s.copy", color=primary))
        self.btn_copy_request_code.setIconSize(QSize(16, 16))
        self.btn_copy_request_code.setToolTip("Copier le code demande")
        self.btn_copy_request_code.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_copy_request_code.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(self.btn_copy_request_code)
        self.btn_copy_request_code.clicked.connect(self.copy_request_code)

        self.btn_activate_license = QPushButton("Activer")
        self.btn_activate_license.setIcon(qta.icon("fa5s.key", color=primary))
        self.btn_activate_license.setIconSize(QSize(16, 16))
        self.btn_activate_license.setToolTip("Activer la licence")
        self.btn_activate_license.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_activate_license.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(self.btn_activate_license)
        self.btn_activate_license.clicked.connect(self.open_activation_dialog)
        license_actions.addWidget(self.btn_copy_request_code)
        license_actions.addWidget(self.btn_activate_license)
        license_layout.addLayout(license_actions)

        brand_layout.addWidget(self.license_frame)
        brand_layout.addStretch()

        form_panel = QFrame()
        form_panel.setObjectName("login_form_panel")
        form_panel.setStyleSheet(f"""
            QFrame#login_form_panel {{
                background-color: {surface};
                border: none;
                border-radius: 6px;
            }}
        """)
        self.login_form_panel = form_panel
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(30, 30, 30, 28)
        form_layout.setSpacing(14)

        lbl_title = QLabel("Bienvenue")
        lbl_title.setStyleSheet(f"font-size: 28px; font-weight: 900; color: {text};")
        form_layout.addWidget(lbl_title)

        lbl_subtitle = QLabel("Connectez-vous a votre espace de travail.")
        lbl_subtitle.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {muted};")
        form_layout.addWidget(lbl_subtitle)

        self.lbl_login_message = QLabel()
        self.lbl_login_message.setObjectName("login_message")
        self.lbl_login_message.setWordWrap(True)
        self.lbl_login_message.setVisible(False)
        form_layout.addWidget(self.lbl_login_message)

        # --- 3. حقول الإدخال ---
        self.combo_known_users = QComboBox()
        apply_touch_input_defaults(self.combo_known_users)
        self.combo_known_users.addItem("Choisir un compte...", "")
        self.combo_known_users.currentIndexChanged.connect(self.apply_selected_user)
        form_layout.addWidget(self.combo_known_users)

        self.inp_username = QLineEdit()
        apply_touch_input_defaults(self.inp_username)
        self.inp_username.setPlaceholderText("Nom d'utilisateur")
        self.inp_username.setClearButtonEnabled(True)
        
        self.inp_password = QLineEdit()
        apply_touch_input_defaults(self.inp_password)
        self.inp_password.setPlaceholderText("Mot de passe")
        self.inp_password.setEchoMode(QLineEdit.Password)
        self.inp_password.setClearButtonEnabled(True)
        self.inp_password.returnPressed.connect(self.handle_login)

        credentials_frame = QFrame()
        credentials_frame.setObjectName("login_credentials_frame")
        credentials_frame.setStyleSheet("QFrame#login_credentials_frame { background: transparent; border: none; }")
        self.login_credentials_frame = credentials_frame
        credentials_layout = QHBoxLayout(credentials_frame)
        credentials_layout.setContentsMargins(0, 0, 0, 0)
        credentials_layout.setSpacing(10)
        credentials_layout.addWidget(self.inp_username, 1)

        password_frame = QFrame()
        password_frame.setObjectName("login_password_frame")
        password_frame.setStyleSheet("QFrame#login_password_frame { background: transparent; border: none; }")
        password_layout = QHBoxLayout(password_frame)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(8)
        password_layout.addWidget(self.inp_password, 1)
        self.btn_toggle_password = QPushButton("")
        self.btn_toggle_password.setIcon(qta.icon("fa5s.eye", color=muted))
        self.btn_toggle_password.setIconSize(QSize(20, 20))
        self.btn_toggle_password.setFixedWidth(54)
        self.btn_toggle_password.setToolTip("Afficher ou masquer le mot de passe")
        apply_touch_button_defaults(self.btn_toggle_password)
        self.btn_toggle_password.setAutoDefault(False)
        self.btn_toggle_password.setDefault(False)
        self.btn_toggle_password.clicked.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.btn_toggle_password)
        credentials_layout.addWidget(password_frame, 1)
        form_layout.addWidget(credentials_frame)

        # --- 4. خيارات إضافية (تذكرني + زر الكيبورد) ---
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(0, 4, 0, 2)
        options_layout.setSpacing(10)
        
        self.chk_remember = QCheckBox("Se souvenir de moi")
        self.chk_remember.setCursor(Qt.PointingHandCursor)
        options_layout.addWidget(self.chk_remember)
        
        options_layout.addStretch() 
        
        # 🟢 زر تشغيل الكيبورد الافتراضي
        self.btn_vkb = QPushButton("Clavier")
        self.btn_vkb.setIcon(qta.icon("fa5s.keyboard", color=text))
        self.btn_vkb.setIconSize(QSize(18, 18))
        self.btn_vkb.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(self.btn_vkb)
        self.btn_vkb.setStyleSheet(f"""
            QPushButton {{
                background-color: {surface_alt}; color: {text}; font-weight: bold;
                border: none;
                min-height: {TOUCH_BUTTON_HEIGHT}px;
                padding: 5px 16px; border-radius: 5px; font-size: 14px;
            }}
            QPushButton:hover {{ background-color: {primary}; color: white; }}
        """)
        self.btn_vkb.clicked.connect(self.show_virtual_keyboard)
        options_layout.addWidget(self.btn_vkb)

        form_layout.addLayout(options_layout)

        # --- 5. الأزرار ---
        self.btn_login = QPushButton("Se connecter")
        self.btn_login.setObjectName("btn_login")
        self.btn_login.setIcon(qta.icon("fa5s.sign-in-alt", color="white"))
        self.btn_login.setIconSize(QSize(20, 20))
        self.btn_login.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(self.btn_login, primary=True)
        self.btn_login.clicked.connect(self.handle_login)
        
        self.btn_cancel = QPushButton("Fermer l'application")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setIcon(qta.icon("fa5s.power-off", color=muted))
        self.btn_cancel.setIconSize(QSize(18, 18))
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(self.btn_cancel)
        self.btn_cancel.clicked.connect(self.reject)

        actions_frame = QFrame()
        actions_frame.setObjectName("login_actions_frame")
        actions_frame.setStyleSheet("QFrame#login_actions_frame { background: transparent; border: none; }")
        self.login_actions_frame = actions_frame
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 8, 0, 0)
        actions_layout.setSpacing(10)
        actions_layout.addWidget(self.btn_login, 2)
        actions_layout.addWidget(self.btn_cancel, 1)
        form_layout.addWidget(actions_frame)
        form_layout.addStretch()

        shell_layout.addWidget(brand_panel)
        shell_layout.addWidget(form_panel, 1)
        layout.addWidget(shell)

    def set_login_message(self, message: str, *, level: str = "info"):
        if self.dark_theme:
            background = self.theme_palette.get("surface_alt", "#22303d")
            colors = {
                "info": self.theme_palette.get("primary", "#33c7b8"),
                "success": self.theme_palette.get("success", "#58d68d"),
                "warning": self.theme_palette.get("accent", "#f1a849"),
                "error": self.theme_palette.get("danger", "#ff7b72"),
            }
            color = colors.get(level, colors["info"])
        else:
            colors = {
                "info": ("#e8f4fd", "#2471a3"),
                "success": ("#eafaf1", "#1e8449"),
                "warning": ("#fff4df", "#b9770e"),
                "error": ("#fdecea", "#c0392b"),
            }
            background, color = colors.get(level, colors["info"])
        self.lbl_login_message.setStyleSheet(
            f"background-color: {background}; color: {color}; border: 1px solid {color};"
        )
        self.lbl_login_message.setText(message)
        self.lbl_login_message.setVisible(bool(message))

    def clear_login_message(self):
        self.lbl_login_message.clear()
        self.lbl_login_message.setVisible(False)

    def toggle_password_visibility(self):
        if self.inp_password.echoMode() == QLineEdit.Password:
            self.inp_password.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_password.setIcon(qta.icon("fa5s.eye-slash", color=self.theme_palette.get("muted", "#6b7280")))
            self.btn_toggle_password.setToolTip("Masquer le mot de passe")
        else:
            self.inp_password.setEchoMode(QLineEdit.Password)
            self.btn_toggle_password.setIcon(qta.icon("fa5s.eye", color=self.theme_palette.get("muted", "#6b7280")))
            self.btn_toggle_password.setToolTip("Afficher le mot de passe")
        self.inp_password.setFocus()

    def _parse_permissions(self, user: dict[str, Any] | None) -> list[str]:
        if not user:
            return []
        permissions = user.get("permissions") or []
        if isinstance(permissions, str):
            try:
                permissions = json.loads(permissions)
            except Exception:
                return []
        return [str(item) for item in permissions] if isinstance(permissions, list) else []

    def _has_application_access(self, user: dict[str, Any] | None) -> bool:
        if not user:
            return False
        if str(user.get("role") or "").casefold() == "admin":
            return True
        return bool(self._parse_permissions(user))

    def _known_user_record(self, username: str) -> dict[str, Any] | None:
        try:
            users = self.data_manager.users.get_all_users()
        except Exception as exc:
            logging.exception("Could not verify user status for %s: %s", username, exc)
            return None
        for user in users or []:
            if str(user.get("username") or "").strip().casefold() == username.casefold():
                return user
        return None

    def _reject_inactive_or_missing_access(self, username: str, user: dict[str, Any] | None = None) -> bool:
        record = self._known_user_record(username)
        candidate = user or record
        if record is not None and not bool(record.get("is_active", True)):
            self.set_login_message(
                "Ce compte est desactive. Demandez a un administrateur de le reactiver.",
                level="warning",
            )
            QMessageBox.warning(
                self,
                "Compte desactive",
                "Ce compte est desactive. Utilisez un autre compte ou contactez l'administrateur.",
            )
            return True
        if candidate is not None and not self._has_application_access(candidate):
            self.set_login_message(
                "Ce compte n'a aucune autorisation. Un administrateur doit lui attribuer un profil.",
                level="warning",
            )
            QMessageBox.warning(
                self,
                "Aucune autorisation",
                "Connexion refusee: ce compte n'a aucune autorisation utilisable.",
            )
            return True
        return False

    def refresh_license_status(self):
        try:
            status = check_license()
        except Exception as exc:
            logging.exception("License status could not be read: %s", exc)
            self.lbl_license_status.setText(
                "Licence: erreur de lecture. Activation requise."
            )
            self.license_frame.setVisible(True)
            self.resize(840, 580)
            self.btn_copy_request_code.setEnabled(False)
            self.btn_activate_license.setEnabled(True)
            return

        self.current_request_code = status.request_code

        if status.activated:
            self.license_frame.setVisible(False)
            self.resize(840, 540)
            return
        elif status.trial_active:
            self.license_frame.setVisible(True)
            self.resize(840, 580)
            text = (
                f"Licence: essai - {status.days_remaining} jour(s) restant(s)\n"
                f"Code demande: {status.request_code}"
            )
            self.btn_activate_license.setText("Activer")
        else:
            self.license_frame.setVisible(True)
            self.resize(840, 580)
            text = (
                "Licence: essai termine - activation requise\n"
                f"Code demande: {status.request_code}"
            )
            self.btn_activate_license.setText("Activer")

        self.lbl_license_status.setText(text)
        self.btn_copy_request_code.setEnabled(bool(self.current_request_code))
        self.btn_activate_license.setEnabled(not status.activated)

    def copy_request_code(self):
        if not self.current_request_code:
            return
        QApplication.clipboard().setText(self.current_request_code)
        QMessageBox.information(
            self,
            "Code copie",
            "Le code demande a ete copie.",
        )

    def open_activation_dialog(self):
        status = check_license()
        dialog = ActivationDialog(status, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh_license_status()
            return True
        self.refresh_license_status()
        return False

    def ensure_license_allows_login(self):
        status = check_license()
        if status.can_run:
            return True
        QMessageBox.warning(
            self,
            "Activation requise",
            "La periode d'essai est terminee. Activez GoldShop pour continuer.",
        )
        return self.open_activation_dialog()

    # 🟢 دالة إظهار الكيبورد الافتراضي
    def load_available_users(self):
        try:
            users = self.data_manager.users.get_all_users()
        except Exception as exc:
            logging.exception("Could not load login users list: %s", exc)
            return

        self.combo_known_users.blockSignals(True)
        try:
            for user in users or []:
                if not user.get("is_active", True):
                    continue
                username = str(user.get("username") or "").strip()
                if not username:
                    continue
                full_name = str(user.get("full_name") or "").strip()
                role = str(user.get("role") or "").strip()
                label = username
                if full_name:
                    label = f"{full_name} ({username})"
                if role:
                    label = f"{label} - {role}"
                self.combo_known_users.addItem(label, username)
        finally:
            self.combo_known_users.blockSignals(False)

    def apply_selected_user(self):
        username = self.combo_known_users.currentData()
        if not username:
            return
        self.inp_username.setText(username)
        self.inp_password.clear()
        self.inp_password.setFocus()

    def show_virtual_keyboard(self):
        if self.vkb is None:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog
            self.vkb = VirtualKeyboardDialog(self)
        
        # وضع التركيز تلقائياً على حقل اسم المستخدم إذا لم يكن هناك حقل محدد
        if not self.inp_username.hasFocus() and not self.inp_password.hasFocus():
            self.inp_username.setFocus()
            
        self.vkb.show()
        self.vkb.raise_() # إجبار الكيبورد على البقاء في المقدمة

    def handle_login(self):
        if not self.ensure_license_allows_login():
            return

        self.clear_login_message()
        username = self.inp_username.text().strip()
        password = self.inp_password.text().strip()
        logging.info(
            "Login button pressed. username=%r password_length=%d",
            username,
            len(password),
        )

        if not username or not password:
            logging.warning("Login rejected before authentication: missing username or password.")
            self.set_login_message(
                "Saisissez le nom d'utilisateur et le mot de passe avant de continuer.",
                level="warning",
            )
            QMessageBox.warning(self, "Attention", "Veuillez entrer le nom d'utilisateur et le mot de passe.")
            return

        if self._reject_inactive_or_missing_access(username):
            return

        # محاولة تسجيل الدخول
        try:
            users_manager = self.data_manager.users
            logging.info("User manager resolved: %s", type(users_manager).__name__)
            user = users_manager.authenticate(username, password)
        except Exception as e:
            logging.exception("Unexpected error during login authentication: %s", e)
            QMessageBox.critical(self, "Erreur", f"Erreur technique pendant la connexion:\n{e}")
            return

        if user:
            if self._reject_inactive_or_missing_access(username, user):
                return
            logging.info("Login accepted by authentication for username=%r", username)
            self.authenticated_user = user
            self.save_session(username, password, user)
            self.accept() # دالة القبول ستغلق الكيبورد تلقائياً
        else:
            logging.warning("Login rejected by authentication for username=%r", username)
            self.set_login_message(
                "Nom d'utilisateur ou mot de passe incorrect. Verifiez la saisie ou choisissez un compte enregistre.",
                level="error",
            )
            QMessageBox.critical(
                self,
                "Connexion refusee",
                "Nom d'utilisateur ou mot de passe incorrect. Vous pouvez reessayer ou choisir un autre compte.",
            )
            self.inp_password.clear()
            self.inp_password.setFocus()

    def save_session(self, username, password, user=None):
        if self.chk_remember.isChecked():
            try:
                os.makedirs(RUNTIME_DIR, exist_ok=True)
                pwd_bytes = password.encode('utf-8')
                pwd_b64 = base64.b64encode(pwd_bytes).decode('utf-8')
                
                data = {"username": username, "token": pwd_b64}
                with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f)
                logging.info("Login session saved to %s for username=%r", SESSION_FILE, username)
                save_saved_account(
                    username,
                    password,
                    (user or {}).get("full_name") or "",
                    (user or {}).get("role") or "",
                )
            except Exception as e:
                logging.exception("Erreur sauvegarde session: %s", e)
        else:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            if os.path.exists(LEGACY_SESSION_FILE):
                os.remove(LEGACY_SESSION_FILE)

    def load_session(self):
        session_file = SESSION_FILE if os.path.exists(SESSION_FILE) else LEGACY_SESSION_FILE
        logging.info("Loading login session from %s exists=%s", session_file, os.path.exists(session_file))
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
                    self.inp_username.setText(username)
                    self.inp_password.setText(password)
                    self.chk_remember.setChecked(True)
                    idx = self.combo_known_users.findData(username)
                    if idx >= 0:
                        self.combo_known_users.blockSignals(True)
                        self.combo_known_users.setCurrentIndex(idx)
                        self.combo_known_users.blockSignals(False)
                    logging.info("Login session loaded for username=%r", username)
            except Exception as e:
                logging.exception("Erreur chargement session: %s", e)
