from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults
from ui.widgets.inventory.touch_product_entry import wrap_with_numpad

from .helpers import _as_float, _as_int

class NewInventoryCountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouvel inventaire physique")
        self.setMinimumSize(560, 360)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Nouvelle session de comptage")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        info = QLabel(
            "La session va prendre une photo du stock attendu. "
            "Chaque article du stock ne pourra etre compte qu'une seule fois dans cette session."
        )
        info.setWordWrap(True)
        info.setObjectName("mutedLabel")
        layout.addWidget(info)

        self.auto_snapshot = QCheckBox("Creer automatiquement la liste complete du stock")
        self.auto_snapshot.setChecked(True)
        self.allow_parallel = QCheckBox("Autoriser plusieurs inventaires ouverts")
        self.allow_parallel.setChecked(False)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Notes internes...")
        apply_touch_input_defaults(self.notes)

        layout.addWidget(self.auto_snapshot)
        layout.addWidget(self.allow_parallel)
        layout.addWidget(QLabel("Notes:"))
        layout.addWidget(self.notes, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Creer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        for button in buttons.buttons():
            apply_touch_button_defaults(button, primary=button == buttons.button(QDialogButtonBox.Save))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def payload(self) -> Dict[str, Any]:
        return {
            "notes": self.notes.toPlainText().strip(),
            "auto_snapshot": self.auto_snapshot.isChecked(),
            "allow_parallel": self.allow_parallel.isChecked(),
        }


class InventoryAdjustmentDialog(QDialog):
    def __init__(self, manager, parent=None, item: Optional[dict] = None, extra: Optional[dict] = None):
        super().__init__(parent)
        self.manager = manager
        self.item = dict(item or {})
        self.extra = dict(extra or {})
        self.setWindowTitle("Correction inventaire")
        self.setMinimumSize(620, 440)
        self._init_ui()
        self._load_locations()
        self._prefill()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("sectionTitle")
        layout.addWidget(self.summary)

        form_box = QFrame()
        form_box.setObjectName("panel")
        form = QFormLayout(form_box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        self.action = QComboBox()
        if self.extra:
            self.action.addItem("Creer produit stock depuis cet element", "CREATE_INVENTORY")
            self.action.addItem("Ignorer cet element", "IGNORE")
        else:
            self.action.addItem("Marquer comme perdu", "MARK_LOST")
            self.action.addItem("Corriger le poids reel", "UPDATE_WEIGHT")
            self.action.addItem("Corriger la quantite reelle", "UPDATE_QUANTITY")
            self.action.addItem("Changer emplacement", "UPDATE_LOCATION")
            self.action.addItem("Ignorer dans ce comptage", "IGNORE")

        self.weight = self._double_spin(" g", maximum=999999)
        self.quantity = QSpinBox()
        self.quantity.setRange(0, 999999)
        self.location = QComboBox()
        self.location.addItem("Aucun changement", None)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Motif ou note de correction...")
        self.notes.setMaximumHeight(100)

        for widget in (self.action, self.weight, self.quantity, self.location, self.notes):
            apply_touch_input_defaults(widget)

        form.addRow("Action:", self.action)
        form.addRow("Poids:", wrap_with_numpad(self, self.weight, "Poids corrige", allow_decimal=True))
        form.addRow("Quantite:", wrap_with_numpad(self, self.quantity, "Quantite corrigee", allow_decimal=False))
        form.addRow("Emplacement:", self.location)
        form.addRow("Notes:", self.notes)
        layout.addWidget(form_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Appliquer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        for button in buttons.buttons():
            apply_touch_button_defaults(button, primary=button == buttons.button(QDialogButtonBox.Save))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _double_spin(suffix="", decimals=3, maximum=999999):
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(0, maximum)
        spin.setSuffix(suffix)
        spin.setSingleStep(0.1)
        return spin

    def _load_locations(self):
        service = getattr(self.manager, "storage_locations", None)
        if service is None:
            return
        try:
            rows = service.get_all_locations() if hasattr(service, "get_all_locations") else []
        except Exception:
            rows = []
        for row in rows or []:
            self.location.addItem(str(row.get("name") or row.get("id")), row.get("id"))

    def _prefill(self):
        source = self.extra or self.item
        name = source.get("observed_name") or source.get("snapshot_name") or ""
        barcode = source.get("observed_barcode") or source.get("snapshot_barcode") or ""
        self.summary.setText(f"{barcode or '-'} | {name or '-'}")
        self.weight.setValue(_as_float(
            source.get("observed_weight")
            or source.get("counted_weight")
            or source.get("expected_remaining_weight")
        ))
        self.quantity.setValue(_as_int(
            source.get("observed_quantity")
            or source.get("counted_quantity")
            or source.get("expected_remaining_quantity")
            or 1
        ))
        location_id = source.get("location_id") or source.get("snapshot_location_id")
        if location_id:
            for index in range(self.location.count()):
                if self.location.itemData(index) == location_id:
                    self.location.setCurrentIndex(index)
                    break

    def action_type(self) -> str:
        return str(self.action.currentData() or "IGNORE")

    def payload(self) -> Dict[str, Any]:
        return {
            "weight": self.weight.value(),
            "remaining_weight": self.weight.value(),
            "quantity": self.quantity.value(),
            "remaining_quantity": self.quantity.value(),
            "location_id": self.location.currentData(),
            "name": self.extra.get("observed_name"),
            "barcode": self.extra.get("observed_barcode"),
            "item_type": self.extra.get("observed_item_type") or self.item.get("snapshot_item_type") or "WEIGHT",
            "category_id": self.extra.get("category_id") or self.item.get("snapshot_category_id"),
            "metal_type_id": self.extra.get("metal_type_id") or self.item.get("snapshot_metal_type_id"),
        }

    def notes_text(self) -> str:
        return self.notes.toPlainText().strip()
