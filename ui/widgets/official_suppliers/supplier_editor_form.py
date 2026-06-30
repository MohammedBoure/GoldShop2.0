from __future__ import annotations

from typing import Any, Dict, Optional

import qtawesome as qta
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.dialogs.supplier_selection import SupplierSelectionDialog
from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults


class OfficialSupplierEditorForm(QWidget):
    def __init__(self, manager, supplier: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.supplier = dict(supplier or {})
        self.linked_supplier_id = self.supplier.get("supplier_id")
        self._init_ui()
        self._populate()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Fiche fournisseur officiel")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.name_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.tax_edit = QLineEdit()
        self.register_edit = QLineEdit()
        self.address_edit = QTextEdit()
        self.address_edit.setMaximumHeight(90)
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(90)
        self.active_check = QCheckBox("Actif")
        self.active_check.setChecked(True)

        for widget in (
            self.name_edit,
            self.code_edit,
            self.phone_edit,
            self.tax_edit,
            self.register_edit,
            self.address_edit,
            self.notes_edit,
        ):
            apply_touch_input_defaults(widget)

        form.addRow("Nom officiel:", self.name_edit)
        form.addRow("Code officiel:", self.code_edit)
        form.addRow("Fournisseur interne:", self._linked_supplier_row())
        form.addRow("Telephone:", self.phone_edit)
        form.addRow("NIF / Taxe:", self.tax_edit)
        form.addRow("Registre:", self.register_edit)
        form.addRow("Adresse:", self.address_edit)
        form.addRow("Notes:", self.notes_edit)
        form.addRow("", self.active_check)
        layout.addLayout(form, 1)

    def _linked_supplier_row(self):
        self.linked_supplier_display = QLineEdit()
        self.linked_supplier_display.setReadOnly(True)
        self.linked_supplier_display.setPlaceholderText("Aucun fournisseur interne lie")
        apply_touch_input_defaults(self.linked_supplier_display)

        self.btn_select_supplier = QPushButton("Lier")
        self.btn_select_supplier.setIcon(qta.icon("fa5s.truck", color="#0f8f83"))
        apply_touch_button_defaults(self.btn_select_supplier)
        self.btn_select_supplier.clicked.connect(self._select_supplier)

        self.btn_clear_supplier = QPushButton("Retirer")
        self.btn_clear_supplier.setIcon(qta.icon("fa5s.unlink", color="#7b8794"))
        apply_touch_button_defaults(self.btn_clear_supplier)
        self.btn_clear_supplier.clicked.connect(self._clear_supplier)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.linked_supplier_display, 1)
        row.addWidget(self.btn_select_supplier)
        row.addWidget(self.btn_clear_supplier)
        widget = QWidget()
        widget.setLayout(row)
        return widget

    def _populate(self):
        supplier = self.supplier
        self.name_edit.setText(str(supplier.get("name") or ""))
        self.code_edit.setText(str(supplier.get("official_code") or ""))
        self.phone_edit.setText(str(supplier.get("phone") or ""))
        self.tax_edit.setText(str(supplier.get("tax_identifier") or ""))
        self.register_edit.setText(str(supplier.get("register_number") or ""))
        self.address_edit.setPlainText(str(supplier.get("address") or ""))
        self.notes_edit.setPlainText(str(supplier.get("notes") or ""))
        self.active_check.setChecked(bool(supplier.get("is_active", True)))
        self._refresh_linked_supplier_label()

    def _select_supplier(self):
        dialog = SupplierSelectionDialog(self.manager, self)
        if dialog.exec() != QDialog.Accepted:
            return
        supplier_id = dialog.get_selected_supplier_id()
        if supplier_id:
            self.linked_supplier_id = int(supplier_id)
            self._refresh_linked_supplier_label()

    def _clear_supplier(self):
        self.linked_supplier_id = None
        self._refresh_linked_supplier_label()

    def _refresh_linked_supplier_label(self):
        if not self.linked_supplier_id:
            self.linked_supplier_display.clear()
            return
        label = f"Fournisseur #{self.linked_supplier_id}"
        try:
            for supplier in self.manager.suppliers.get_all_suppliers():
                if int(supplier.get("id") or 0) == int(self.linked_supplier_id):
                    label = supplier.get("name") or label
                    break
        except Exception:
            pass
        self.linked_supplier_display.setText(label)

    def validation_error(self):
        if not self.name_edit.text().strip():
            return "Veuillez saisir le nom officiel."
        return None

    def payload(self, user_id=None):
        return {
            "name": self.name_edit.text().strip(),
            "supplier_id": self.linked_supplier_id,
            "official_code": self.code_edit.text().strip() or None,
            "phone": self.phone_edit.text().strip() or None,
            "tax_identifier": self.tax_edit.text().strip() or None,
            "register_number": self.register_edit.text().strip() or None,
            "address": self.address_edit.toPlainText().strip() or None,
            "notes": self.notes_edit.toPlainText().strip() or None,
            "is_active": self.active_check.isChecked(),
            "user_id": user_id,
        }
