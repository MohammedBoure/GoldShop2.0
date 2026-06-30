from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox, QVBoxLayout

from ui.touch_design import apply_touch_button_defaults

from .supplier_editor_form import OfficialSupplierEditorForm


class OfficialSupplierEditorDialog(QDialog):
    def __init__(
        self,
        manager,
        supplier: Optional[Dict[str, Any]] = None,
        current_user: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager
        self.service = manager.official_suppliers
        self.supplier = dict(supplier or {})
        self.current_user = current_user or {}
        self.result_id = self.supplier.get("id")
        self.setWindowTitle("Fournisseur officiel")
        self.setMinimumSize(720, 560)
        self._resize_for_touch_screen()
        self._init_ui()

    def _resize_for_touch_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            self.resize(760, 600)
            return
        available = screen.availableGeometry()
        self.resize(
            min(max(760, int(available.width() * 0.62)), available.width() - 40),
            min(max(600, int(available.height() * 0.72)), available.height() - 60),
        )

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.form = OfficialSupplierEditorForm(self.manager, self.supplier, self)
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
            QMessageBox.warning(self, "Fournisseur officiel", error)
            return

        payload = self.form.payload(user_id=self.current_user.get("id"))
        if self.result_id:
            payload.pop("user_id", None)
            ok = self.service.update_official_supplier(int(self.result_id), **payload)
            if not ok:
                QMessageBox.critical(self, "Fournisseur officiel", "Impossible de modifier le fournisseur.")
                return
        else:
            self.result_id = self.service.create_official_supplier(**payload)
            if not self.result_id:
                QMessageBox.critical(self, "Fournisseur officiel", "Impossible de creer le fournisseur.")
                return
        self.accept()
