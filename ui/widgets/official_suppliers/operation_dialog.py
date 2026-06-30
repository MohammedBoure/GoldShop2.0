from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox, QVBoxLayout

from ui.touch_design import apply_touch_button_defaults

from .operation_form import OfficialOperationForm


class OfficialOperationDialog(QDialog):
    def __init__(
        self,
        manager,
        official_supplier: Dict[str, Any],
        operation: Optional[Dict[str, Any]] = None,
        operation_type: Optional[str] = None,
        current_user: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager
        self.service = manager.official_suppliers
        self.official_supplier = dict(official_supplier or {})
        self.operation = dict(operation or {})
        self.current_user = current_user or {}
        self.fixed_operation_type = operation_type
        self.result_id = self.operation.get("id")
        self.setWindowTitle("Operation officielle")
        self.setMinimumSize(780, 600)
        self._resize_for_touch_screen()
        self._init_ui()

    def _resize_for_touch_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            self.resize(820, 640)
            return
        available = screen.availableGeometry()
        self.resize(
            min(max(820, int(available.width() * 0.66)), available.width() - 40),
            min(max(640, int(available.height() * 0.76)), available.height() - 60),
        )

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.form = OfficialOperationForm(
            self.manager,
            self.official_supplier,
            operation=self.operation,
            fixed_operation_type=self.fixed_operation_type,
            parent=self,
        )
        layout.addWidget(self.form, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_button = buttons.button(QDialogButtonBox.Save)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        save_button.setText("Enregistrer")
        cancel_button.setText("Annuler")
        apply_touch_button_defaults(save_button, primary=True)
        apply_touch_button_defaults(cancel_button)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        error = self.form.validation_error()
        if error:
            QMessageBox.warning(self, "Operation officielle", error)
            return

        payload = self.form.payload(user_id=self.current_user.get("id"))
        if self.result_id:
            payload.pop("user_id", None)
            ok = self.service.update_operation(int(self.result_id), **payload)
            if not ok:
                QMessageBox.critical(self, "Operation officielle", "Impossible de modifier l'operation.")
                return
        else:
            self.result_id = self.service.record_operation(**payload)
            if not self.result_id:
                QMessageBox.critical(self, "Operation officielle", "Impossible de creer l'operation.")
                return
        self.accept()
