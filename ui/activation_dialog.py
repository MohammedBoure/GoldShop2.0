from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from licensing import LicenseError, LicenseStatus, activate_license
from ui.dialogs.touch_dialog import TouchDialogMixin
from ui.touch_design import apply_touch_input_defaults


class ActivationDialog(TouchDialogMixin, QDialog):
    def __init__(self, status: LicenseStatus, parent=None):
        super().__init__(parent)
        self.status = status
        self.setWindowTitle("Activation GoldShop")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._build_ui()
        self.setup_touch_dialog(size="compact", dirty_tracking=True)
        self.activation_key_input.setFocus(Qt.OtherFocusReason)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Activation requise")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)

        message = QLabel(self._message_text())
        message.setWordWrap(True)
        message.setStyleSheet("font-size: 14px; color: #34495e;")
        layout.addWidget(message)

        form = QFormLayout()
        self.request_code_input = QLineEdit(self.status.request_code)
        self.request_code_input.setReadOnly(True)
        self.request_code_input.setAlignment(Qt.AlignCenter)
        self.request_code_input.setStyleSheet("font-size: 18px; font-weight: bold; letter-spacing: 2px;")
        apply_touch_input_defaults(self.request_code_input)

        self.activation_key_input = QLineEdit()
        self.activation_key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.activation_key_input.setAlignment(Qt.AlignCenter)
        self.activation_key_input.returnPressed.connect(self._activate)
        self.activation_key_input.textEdited.connect(self.mark_dirty)
        apply_touch_input_defaults(self.activation_key_input)

        form.addRow("Code demande:", self.request_code_input)
        form.addRow("Cle d'activation:", self.activation_key_input)
        layout.addLayout(form)

        hint = QLabel(
            "Copiez le code demande dans ActivateurRMS, choisissez Jewelry, "
            "puis collez ici la cle generee."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        layout.addWidget(hint)

        keyboard_button = self.add_keyboard_button(text="Clavier", target=self.activation_key_input)
        footer, _buttons = self.create_touch_footer(
            primary_text="Activer",
            cancel_text="Fermer",
            primary_slot=self._activate,
            extra_buttons=(keyboard_button,),
        )
        layout.addLayout(footer)

    def _message_text(self) -> str:
        if self.status.reason == "trial_expired":
            return "La periode d'essai de 7 jours est terminee. Activez ce poste pour continuer."
        if self.status.reason == "clock_rollback":
            return "La date du systeme semble avoir ete reculee. Activation requise pour continuer."
        if self.status.reason == "different_machine":
            return "La licence locale ne correspond pas a ce poste. Une nouvelle activation est requise."
        if self.status.reason == "license_state_invalid":
            return "Le fichier de licence local est invalide. Une activation est requise."
        return "Activez GoldShop pour continuer."

    def _activate(self):
        key = self.activation_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Activation", "Veuillez saisir la cle d'activation.")
            return

        try:
            activate_license(key)
        except LicenseError as exc:
            QMessageBox.warning(self, "Activation refusee", str(exc))
            self.activation_key_input.selectAll()
            self.activation_key_input.setFocus()
            return

        QMessageBox.information(self, "Activation", "GoldShop est active sur ce poste.")
        self.clear_dirty()
        self.accept()
