import logging
import json

import qtawesome as qta
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ui.login_dialog import LoginDialog
from ui.saved_accounts import (
    get_saved_account_password,
    load_saved_accounts,
    remove_saved_account,
    save_saved_account,
)
from ui.touch_design import apply_touch_button_defaults, apply_touch_table_defaults


class AccountSwitcherDialog(QDialog):
    def __init__(
        self,
        data_manager,
        current_user,
        parent=None,
        can_switch=True,
        can_logout=True,
        can_logout_all=None,
    ):
        super().__init__(parent)
        self.data_manager = data_manager
        self.current_user = current_user or {}
        self.can_switch = bool(can_switch)
        self.can_logout = bool(can_logout)
        self.can_logout_all = self.can_logout if can_logout_all is None else bool(can_logout_all)
        self.selected_user = None
        self.action = None

        self.setWindowTitle("Comptes")
        self.setMinimumSize(680, 620)
        self.resize(680, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._init_ui()
        self.refresh_accounts()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QDialog { background-color: #ffffff; }
            QLabel#title { font-size: 22px; font-weight: 800; color: #2c3e50; }
            QLabel#subtitle { color: #607d8b; font-size: 13px; }
            QLabel#message { border-radius: 8px; padding: 10px 12px; font-weight: bold; }
            QListWidget { border: 1px solid #d5dde2; border-radius: 8px; padding: 6px; }
            QListWidget::item { padding: 12px; border-bottom: 1px solid #edf2f5; }
            QListWidget::item:selected { background: #dff5f1; color: #143b36; }
            QPushButton { border-radius: 8px; padding: 10px 12px; font-weight: bold; }
            QPushButton#primary { background-color: #0f8f83; color: white; }
            QPushButton#secondary { background-color: #34495e; color: white; }
            QPushButton#danger { background-color: #e74c3c; color: white; }
            QPushButton#light { background-color: #ecf0f1; color: #34495e; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(qta.icon("fa5s.user-circle", color="#0f8f83").pixmap(44, 44))
        header.addWidget(icon)

        text_box = QVBoxLayout()
        title = QLabel("Gestion des comptes")
        title.setObjectName("title")
        current = QLabel(
            f"Compte actuel: {self.current_user.get('username', '')}"
            f" ({self.current_user.get('role', 'User')})"
        )
        current.setObjectName("subtitle")
        text_box.addWidget(title)
        text_box.addWidget(current)
        header.addLayout(text_box)
        header.addStretch()
        layout.addLayout(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        layout.addWidget(separator)

        self.message_label = QLabel()
        self.message_label.setObjectName("message")
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(False)
        layout.addWidget(self.message_label)

        layout.addWidget(QLabel("Comptes enregistres pour connexion directe:"))

        self.accounts_list = QListWidget()
        apply_touch_table_defaults(self.accounts_list)
        self.accounts_list.setSpacing(6)
        self.accounts_list.itemDoubleClicked.connect(self.login_selected_account)
        layout.addWidget(self.accounts_list, 1)

        row = QHBoxLayout()
        self.btn_login = QPushButton("Entrer")
        self.btn_login.setObjectName("primary")
        apply_touch_button_defaults(self.btn_login, primary=True)
        self.btn_login.clicked.connect(self.login_selected_account)
        row.addWidget(self.btn_login)

        self.btn_add = QPushButton("Ajouter compte")
        self.btn_add.setObjectName("secondary")
        apply_touch_button_defaults(self.btn_add)
        self.btn_add.clicked.connect(self.add_account)
        row.addWidget(self.btn_add)

        self.btn_remove = QPushButton("Retirer")
        self.btn_remove.setObjectName("light")
        apply_touch_button_defaults(self.btn_remove)
        self.btn_remove.clicked.connect(self.remove_selected_account)
        row.addWidget(self.btn_remove)
        layout.addLayout(row)

        bottom = QHBoxLayout()
        self.btn_logout = QPushButton("Deconnexion reelle")
        self.btn_logout.setObjectName("danger")
        apply_touch_button_defaults(self.btn_logout, danger=True)
        self.btn_logout.clicked.connect(self.logout_requested)
        bottom.addWidget(self.btn_logout)

        self.btn_logout_all = QPushButton("Déconnecter tous les comptes")
        self.btn_logout_all.setObjectName("danger")
        apply_touch_button_defaults(self.btn_logout_all, danger=True)
        self.btn_logout_all.clicked.connect(self.logout_all_requested)
        bottom.addWidget(self.btn_logout_all)
        bottom.addStretch()

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setObjectName("light")
        apply_touch_button_defaults(self.btn_cancel)
        self.btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(self.btn_cancel)
        layout.addLayout(bottom)

    def set_message(self, message, *, level="info"):
        colors = {
            "info": ("#e8f4fd", "#2471a3"),
            "success": ("#eafaf1", "#1e8449"),
            "warning": ("#fff4df", "#b9770e"),
            "error": ("#fdecea", "#c0392b"),
        }
        background, color = colors.get(level, colors["info"])
        self.message_label.setStyleSheet(
            f"background-color: {background}; color: {color}; border: 1px solid {color};"
        )
        self.message_label.setText(message)
        self.message_label.setVisible(bool(message))

    def _parse_permissions(self, user):
        permissions = (user or {}).get("permissions") or []
        if isinstance(permissions, str):
            try:
                permissions = json.loads(permissions)
            except Exception:
                return []
        return permissions if isinstance(permissions, list) else []

    def _has_application_access(self, user):
        if not user:
            return False
        if str(user.get("role") or "").casefold() == "admin":
            return True
        return bool(self._parse_permissions(user))

    def _known_user_record(self, username):
        try:
            users = self.data_manager.users.get_all_users()
        except Exception as exc:
            logging.exception("Could not verify saved account %s: %s", username, exc)
            return None
        for user in users or []:
            if str(user.get("username") or "").strip().casefold() == username.casefold():
                return user
        return None

    def refresh_accounts(self):
        self.accounts_list.clear()
        accounts = load_saved_accounts()
        for account in accounts:
            username = account.get("username", "")
            full_name = account.get("full_name") or username
            role = account.get("role") or "User"
            item = QListWidgetItem(f"{full_name} ({username}) - {role}")
            item.setSizeHint(QSize(0, 64))
            item.setData(Qt.UserRole, username)
            self.accounts_list.addItem(item)

        has_accounts = self.accounts_list.count() > 0
        self.btn_login.setEnabled(has_accounts and self.can_switch)
        self.btn_remove.setEnabled(has_accounts and self.can_switch)
        self.btn_add.setEnabled(self.can_switch)
        self.accounts_list.setEnabled(self.can_switch)
        self.btn_logout.setEnabled(self.can_logout)
        self.btn_logout_all.setEnabled(self.can_logout_all)
        if has_accounts:
            self.accounts_list.setCurrentRow(0)

    def _selected_username(self):
        item = self.accounts_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else ""

    def login_selected_account(self):
        username = self._selected_username()
        if not username:
            return

        password = get_saved_account_password(username)
        if not password:
            self.set_message(
                "Impossible de lire le mot de passe sauvegarde. Ajoutez ce compte de nouveau.",
                level="error",
            )
            QMessageBox.warning(self, "Compte", "Impossible de lire le mot de passe sauvegarde.")
            return

        known_user = self._known_user_record(username)
        if known_user is not None and not bool(known_user.get("is_active", True)):
            self.set_message(
                "Ce compte est desactive. Utilisez un autre compte ou contactez l'administrateur.",
                level="warning",
            )
            QMessageBox.warning(self, "Compte desactive", "Ce compte est desactive.")
            return

        try:
            user = self.data_manager.users.authenticate(username, password)
        except Exception as exc:
            logging.exception("Saved account switch failed for %s: %s", username, exc)
            self.set_message(
                "Connexion impossible pour le moment. Reessayez ou ajoutez le compte manuellement.",
                level="error",
            )
            QMessageBox.critical(self, "Connexion", "Connexion impossible. Verifiez la base de donnees puis reessayez.")
            return
        if not user:
            self.set_message(
                "Ce compte sauvegarde n'est plus valide. Ajoutez-le de nouveau.",
                level="warning",
            )
            QMessageBox.warning(
                self,
                "Connexion refusee",
                "Ce compte sauvegarde n'est plus valide. Ajoutez-le de nouveau.",
            )
            return
        if not self._has_application_access(user):
            self.set_message(
                "Ce compte n'a aucune autorisation. Un administrateur doit lui attribuer un profil.",
                level="warning",
            )
            QMessageBox.warning(
                self,
                "Aucune autorisation",
                "Connexion refusee: ce compte n'a aucune autorisation utilisable.",
            )
            return

        self.selected_user = user
        self.action = "switch"
        self.accept()

    def add_account(self):
        dialog = LoginDialog(self.data_manager)
        dialog.setWindowTitle("Ajouter un compte - GoldShop")
        if dialog.exec() != QDialog.Accepted:
            return

        user = dialog.authenticated_user
        username = dialog.inp_username.text().strip()
        password = dialog.inp_password.text()
        if not user or not username or not password:
            return

        try:
            save_saved_account(
                username,
                password,
                user.get("full_name") or "",
                user.get("role") or "",
            )
        except Exception as exc:
            logging.exception("Could not save account %s: %s", username, exc)
            QMessageBox.critical(self, "Compte", f"Impossible d'ajouter le compte:\n{exc}")
            return

        self.refresh_accounts()
        self.set_message("Compte ajoute. Vous pouvez maintenant l'utiliser en connexion directe.", level="success")

    def remove_selected_account(self):
        username = self._selected_username()
        if not username:
            return
        confirm = QMessageBox.question(
            self,
            "Retirer le compte",
            f"Retirer {username} de la liste des comptes enregistres ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            remove_saved_account(username)
            self.refresh_accounts()

    def logout_requested(self):
        self.action = "logout"
        self.accept()

    def logout_all_requested(self):
        self.action = "logout_all"
        self.accept()
