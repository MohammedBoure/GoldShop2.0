from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel

from .helpers import value_label


class SupplierIdentityPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.set_supplier({})

    def _init_ui(self):
        self.setObjectName("officialPanel")
        layout = QGridLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        self.lbl_supplier_name = QLabel("Selectionner un fournisseur officiel")
        self.lbl_supplier_name.setObjectName("metricValue")
        self.lbl_supplier_code = value_label("Code: -")
        self.lbl_supplier_phone = value_label("Telephone: -")
        self.lbl_supplier_tax = value_label("NIF: -")
        self.lbl_supplier_link = value_label("Fournisseur interne: -")

        layout.addWidget(self.lbl_supplier_name, 0, 0, 1, 3)
        layout.addWidget(self.lbl_supplier_code, 1, 0)
        layout.addWidget(self.lbl_supplier_phone, 1, 1)
        layout.addWidget(self.lbl_supplier_tax, 1, 2)
        layout.addWidget(self.lbl_supplier_link, 2, 0, 1, 3)

    def set_supplier(self, supplier: dict):
        supplier = supplier or {}
        if not supplier:
            self.lbl_supplier_name.setText("Selectionner un fournisseur officiel")
            self.lbl_supplier_code.setText("Code: -")
            self.lbl_supplier_phone.setText("Telephone: -")
            self.lbl_supplier_tax.setText("NIF: -")
            self.lbl_supplier_link.setText("Fournisseur interne: -")
            return

        self.lbl_supplier_name.setText(str(supplier.get("name") or ""))
        self.lbl_supplier_code.setText(f"Code: {supplier.get('official_code') or '-'}")
        self.lbl_supplier_phone.setText(f"Telephone: {supplier.get('phone') or '-'}")
        self.lbl_supplier_tax.setText(f"NIF: {supplier.get('tax_identifier') or '-'}")
        linked = supplier.get("linked_supplier_name") or (
            f"#{supplier.get('supplier_id')}" if supplier.get("supplier_id") else "-"
        )
        self.lbl_supplier_link.setText(f"Fournisseur interne: {linked}")
