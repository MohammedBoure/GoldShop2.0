from __future__ import annotations

from typing import Any, Dict, Optional

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults

class SupplierEditorForm(QWidget):
    def __init__(self, manager, supplier: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.supplier = dict(supplier or {})
        self.linked_supplier_id = self.supplier.get("supplier_id")
        self._init_ui()
        self._populate()

    def _show_keyboard(self, target=None):
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog
        if target is None:
            target = self.focusWidget() or getattr(self, "name_edit", None)
        if target:
            target.setFocus()
        kb = VirtualKeyboardDialog(self)
        kb.show()
        kb.raise_()

    def _wrap_with_keyboard(self, widget):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("⌨️")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(38, 38)
        btn.setStyleSheet(
            "background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 16px;"
        )
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._show_keyboard(widget))
        lay.addWidget(btn)
        return container

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Fiche fournisseur")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.name_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.supplier_type_combo = QComboBox()
        self.supplier_type_combo.addItem("Or (Gold)", "Gold")
        self.supplier_type_combo.addItem("Argent (Silver)", "Silver")
        
        self.primary_purity_edit = QLineEdit()
        self.primary_purity_edit.setPlaceholderText("Ex: 750, 875, 925, 999...")

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
            self.supplier_type_combo,
            self.primary_purity_edit,
            self.phone_edit,
            self.tax_edit,
            self.register_edit,
            self.address_edit,
            self.notes_edit,
        ):
            apply_touch_input_defaults(widget)

        form.addRow("Nom du Fournisseur *:", self._wrap_with_keyboard(self.name_edit))
        form.addRow("Code Fournisseur:", self._wrap_with_keyboard(self.code_edit))
        form.addRow("Type (Or / Argent):", self.supplier_type_combo)
        form.addRow("Titre de base (Pureté) *:", self._wrap_with_keyboard(self.primary_purity_edit))
        form.addRow("Téléphone:", self._wrap_with_keyboard(self.phone_edit))
        form.addRow("NIF / Taxe:", self._wrap_with_keyboard(self.tax_edit))
        form.addRow("Registre:", self._wrap_with_keyboard(self.register_edit))
        form.addRow("Adresse:", self._wrap_with_keyboard(self.address_edit))
        form.addRow("Notes:", self._wrap_with_keyboard(self.notes_edit))
        form.addRow("", self.active_check)
        layout.addLayout(form, 1)

    def _populate(self):
        supplier = self.supplier
        self.name_edit.setText(str(supplier.get("name") or ""))
        self.code_edit.setText(str(supplier.get("official_code") or supplier.get("code") or ""))
        
        stype = str(supplier.get("supplier_type") or "Gold").strip()
        idx_t = self.supplier_type_combo.findData(stype)
        if idx_t < 0:
            if stype.lower() in ["silver", "argent"]:
                idx_t = self.supplier_type_combo.findData("Silver")
            else:
                idx_t = self.supplier_type_combo.findData("Gold")
        if idx_t >= 0: self.supplier_type_combo.setCurrentIndex(idx_t)
        
        purity = str(supplier.get("primary_purity") or "750")
        self.primary_purity_edit.setText(purity)

        self.phone_edit.setText(str(supplier.get("phone") or ""))
        self.tax_edit.setText(str(supplier.get("tax_identifier") or ""))
        self.register_edit.setText(str(supplier.get("register_number") or ""))
        self.address_edit.setPlainText(str(supplier.get("address") or ""))
        self.notes_edit.setPlainText(str(supplier.get("notes") or ""))
        self.active_check.setChecked(bool(supplier.get("is_active", True)))

    def validation_error(self):
        if not self.name_edit.text().strip():
            return "Veuillez saisir le nom du fournisseur."
        return None

    def payload(self, user_id=None):
        return {
            "name": self.name_edit.text().strip(),
            "official_code": self.code_edit.text().strip() or None,
            "supplier_type": self.supplier_type_combo.currentData() or "Gold",
            "primary_purity": self.primary_purity_edit.text().strip() or "750",
            "phone": self.phone_edit.text().strip() or None,
            "tax_identifier": self.tax_edit.text().strip() or None,
            "register_number": self.register_edit.text().strip() or None,
            "address": self.address_edit.toPlainText().strip() or None,
            "notes": self.notes_edit.toPlainText().strip() or None,
            "is_active": self.active_check.isChecked(),
            "user_id": user_id,
        }

OfficialSupplierEditorForm = SupplierEditorForm
