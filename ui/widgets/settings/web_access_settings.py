from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults
from web_security import clear_web_password, set_web_password, web_password_configured


class WebAccessSettingsGroup(QGroupBox):
    def __init__(self, config, parent=None):
        super().__init__("Mot de passe API Web", parent)
        self._configured = web_password_configured(config)
        layout = QFormLayout(self)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self._refresh_status()

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Minimum 8 caracteres; vide = conserver")
        apply_touch_input_defaults(self.password)

        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setPlaceholderText("Confirmer le nouveau mot de passe")
        apply_touch_input_defaults(self.confirm_password)

        self.btn_toggle_password = QPushButton("Afficher")
        self.btn_toggle_password.setCheckable(True)
        self.btn_toggle_password.clicked.connect(self._toggle_secret_visibility)
        apply_touch_button_defaults(self.btn_toggle_password)

        self.btn_keyboard = QPushButton("Clavier")
        self.btn_keyboard.clicked.connect(lambda: self._show_virtual_keyboard(self.password))
        apply_touch_button_defaults(self.btn_keyboard)

        self.clear_password = QCheckBox("Supprimer le mot de passe et bloquer l'acces Web")
        self.clear_password.toggled.connect(self._toggle_inputs)

        note = QLabel(
            "Les donnees API restent bloquees sans ce mot de passe. "
            "Le navigateur le conserve localement apres saisie. Utilisez HTTPS pour un acces distant."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #7f8c8d; font-size: 11px;")

        layout.addRow("Etat:", self.status)
        password_row = QHBoxLayout()
        password_row.addWidget(self.password, 1)
        password_row.addWidget(self.btn_toggle_password)
        password_row.addWidget(self.btn_keyboard)
        layout.addRow("Nouveau mot de passe:", password_row)
        layout.addRow("Confirmation:", self.confirm_password)
        layout.addRow(self.clear_password)
        layout.addRow(note)

    def _refresh_status(self):
        if self._configured:
            self.status.setText("Configure - chaque appel API doit fournir le mot de passe.")
            self.status.setStyleSheet("color: #1e8449; font-weight: bold;")
        else:
            self.status.setText("Non configure - acces aux donnees API bloque.")
            self.status.setStyleSheet("color: #c0392b; font-weight: bold;")

    def _toggle_inputs(self, clear_requested):
        self.password.setEnabled(not clear_requested)
        self.confirm_password.setEnabled(not clear_requested)
        self.btn_toggle_password.setEnabled(not clear_requested)
        self.btn_keyboard.setEnabled(not clear_requested)

    def _toggle_secret_visibility(self, checked):
        mode = QLineEdit.Normal if checked else QLineEdit.Password
        self.password.setEchoMode(mode)
        self.confirm_password.setEchoMode(mode)
        self.btn_toggle_password.setText("Masquer" if checked else "Afficher")

    def _show_virtual_keyboard(self, target):
        if target is not None:
            target.setFocus(Qt.OtherFocusReason)
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog

        keyboard = getattr(self, "_touch_keyboard", None)
        if keyboard is None:
            keyboard = VirtualKeyboardDialog(self)
            self._touch_keyboard = keyboard
        keyboard.show()
        keyboard.raise_()

    def update_config(self, config):
        if self.clear_password.isChecked():
            clear_web_password(config)
            self._configured = False
            self.password.clear()
            self.confirm_password.clear()
            self._refresh_status()
            return True

        password = self.password.text()
        confirmation = self.confirm_password.text()
        if not password and not confirmation:
            return True
        if password != confirmation:
            QMessageBox.warning(self, "Acces Web", "Les mots de passe Web ne correspondent pas.")
            return False
        try:
            set_web_password(config, password)
        except ValueError as error:
            QMessageBox.warning(self, "Acces Web", str(error))
            return False

        self._configured = True
        self.password.clear()
        self.confirm_password.clear()
        self._refresh_status()
        return True
