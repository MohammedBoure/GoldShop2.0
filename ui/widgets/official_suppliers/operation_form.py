from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.touch_design import apply_touch_input_defaults
from ui.widgets.partners.supplier_touch_helpers import wrap_supplier_numpad

from .helpers import as_float, fmt_date


class OfficialOperationForm(QWidget):
    def __init__(
        self,
        manager,
        official_supplier: Dict[str, Any],
        operation: Optional[Dict[str, Any]] = None,
        fixed_operation_type: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager
        self.official_supplier = dict(official_supplier or {})
        self.operation = dict(operation or {})
        self.fixed_operation_type = fixed_operation_type
        self._init_ui()
        self._load_metals()
        self._populate()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_text = self.official_supplier.get("name") or "Sortie officielle globale"
        title = QLabel(f"Operation officielle - {title_text}")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Entree officielle", "INCOMING")
        self.type_combo.addItem("Sortie officielle", "OUTGOING")
        if self.fixed_operation_type:
            self.type_combo.setEnabled(False)

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.metal_combo = QComboBox()
        self.weight_spin = self._double_spin(" g", decimals=3)
        self.amount_spin = self._double_spin(" DA", decimals=2, maximum=999999999999)
        self.document_edit = QLineEdit()
        self.description_edit = QLineEdit()
        self.source_combo = QComboBox()
        self.source_combo.addItem("Manuel", "MANUAL")
        self.source_combo.addItem("Import Excel", "IMPORT")
        self.source_combo.addItem("Vente", "SALE")
        self.source_combo.addItem("Ajustement", "ADJUSTMENT")
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)

        for widget in (
            self.type_combo,
            self.date_edit,
            self.metal_combo,
            self.weight_spin,
            self.amount_spin,
            self.document_edit,
            self.description_edit,
            self.source_combo,
            self.notes_edit,
        ):
            apply_touch_input_defaults(widget)

        form.addRow("Type:", self.type_combo)
        form.addRow("Date:", self.date_edit)
        form.addRow("Titre / metal:", self.metal_combo)
        form.addRow("Poids:", wrap_supplier_numpad(self, self.weight_spin, "Poids officiel"))
        form.addRow("Montant:", wrap_supplier_numpad(self, self.amount_spin, "Montant officiel"))
        form.addRow("Document:", self.document_edit)
        form.addRow("Observation:", self.description_edit)
        form.addRow("Source:", self.source_combo)
        form.addRow("Notes:", self.notes_edit)
        layout.addLayout(form, 1)

    @staticmethod
    def _double_spin(suffix="", decimals=2, maximum=9999999):
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(0, maximum)
        spin.setSingleStep(0.1 if decimals else 1)
        spin.setSuffix(suffix)
        return spin

    def _load_metals(self):
        self.metal_combo.clear()
        self.metal_combo.addItem("Non precise", None)
        try:
            for metal in self.manager.metal_types.get_all_metal_types():
                label = f"{metal.get('name')} - {metal.get('purity_value')}/1000"
                self.metal_combo.addItem(label, metal.get("id"))
        except Exception:
            pass

    def _populate(self):
        operation = self.operation
        op_type = self.fixed_operation_type or operation.get("operation_type") or "INCOMING"
        self._set_combo_value(self.type_combo, op_type)
        date_text = fmt_date(operation.get("operation_date"))
        if date_text:
            qdate = QDate.fromString(date_text, "yyyy-MM-dd")
            if qdate.isValid():
                self.date_edit.setDate(qdate)
        self._set_combo_value(self.metal_combo, operation.get("metal_type_id"))
        self.weight_spin.setValue(as_float(operation.get("weight_g")))
        self.amount_spin.setValue(as_float(operation.get("amount_da")))
        self.document_edit.setText(str(operation.get("document_number") or ""))
        self.description_edit.setText(str(operation.get("description") or ""))
        self._set_combo_value(self.source_combo, operation.get("source_kind") or "MANUAL")
        self.notes_edit.setPlainText(str(operation.get("notes") or ""))

    @staticmethod
    def _set_combo_value(combo: QComboBox, value):
        for index in range(combo.count()):
            if combo.itemData(index) == value or str(combo.itemData(index)) == str(value):
                combo.setCurrentIndex(index)
                return

    def validation_error(self):
        if self.weight_spin.value() <= 0 and self.amount_spin.value() <= 0:
            return "Veuillez saisir un poids ou un montant."
        return None

    def payload(self, user_id=None):
        operation_type = self.type_combo.currentData()
        return {
            "official_supplier_id": int(self.official_supplier.get("id") or 0) if operation_type == "INCOMING" else None,
            "operation_type": operation_type,
            "weight_g": self.weight_spin.value(),
            "amount_da": self.amount_spin.value(),
            "operation_date": self.date_edit.date().toString("yyyy-MM-dd"),
            "metal_type_id": self.metal_combo.currentData(),
            "document_number": self.document_edit.text().strip() or None,
            "description": self.description_edit.text().strip() or None,
            "notes": self.notes_edit.toPlainText().strip() or None,
            "source_kind": self.source_combo.currentData(),
            "user_id": user_id,
        }
