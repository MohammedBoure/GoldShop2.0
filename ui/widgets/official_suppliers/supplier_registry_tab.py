from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.touch_design import apply_touch_input_defaults, apply_touch_table_defaults


class SupplierRegistryTab(QFrame):
    supplierSelected = Signal(dict)
    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_supplier = {}
        self._loading = False
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setObjectName("officialPanel")
        self.setMinimumWidth(330)
        self.setMaximumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.supplier_search = QLineEdit()
        self.supplier_search.setPlaceholderText("Rechercher fournisseur, code, NIF...")
        self.supplier_status = QComboBox()
        self.supplier_status.addItem("Actifs", True)
        self.supplier_status.addItem("Tous", False)
        for widget in (self.supplier_search, self.supplier_status):
            apply_touch_input_defaults(widget)
        layout.addWidget(self.supplier_search)
        layout.addWidget(self.supplier_status)

        self.suppliers_table = QTableWidget(0, 4)
        self.suppliers_table.setHorizontalHeaderLabels(["ID", "Nom", "Code", "Etat"])
        self.suppliers_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.suppliers_table.setColumnHidden(0, True)
        self.suppliers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.suppliers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.suppliers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        apply_touch_table_defaults(self.suppliers_table)
        layout.addWidget(self.suppliers_table, 1)

    def _connect_signals(self):
        self.supplier_search.textChanged.connect(lambda _text: self.refreshRequested.emit())
        self.supplier_status.currentIndexChanged.connect(lambda _index: self.refreshRequested.emit())
        self.suppliers_table.itemSelectionChanged.connect(self._on_selection_changed)

    def load_suppliers(self, service, select_id: Optional[int] = None):
        self._loading = True
        rows = service.list_official_suppliers(
            search_text=self.supplier_search.text(),
            active_only=bool(self.supplier_status.currentData()),
            limit=500,
            offset=0,
        )
        self.suppliers_table.setRowCount(0)
        selected_row = -1
        for supplier in rows:
            row = self.suppliers_table.rowCount()
            self.suppliers_table.insertRow(row)
            self._populate_supplier_row(row, supplier)
            if select_id and int(supplier.get("id") or 0) == int(select_id):
                selected_row = row

        self._loading = False
        if selected_row >= 0:
            self.suppliers_table.selectRow(selected_row)
        elif rows:
            self.suppliers_table.selectRow(0)
        else:
            self.current_supplier = {}
            self.supplierSelected.emit({})

    def _populate_supplier_row(self, row: int, supplier: dict):
        status = "Actif" if supplier.get("is_active", True) else "Inactif"
        values = [
            supplier.get("id"),
            supplier.get("name") or "",
            supplier.get("official_code") or "",
            status,
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setData(Qt.UserRole, supplier)
            if not supplier.get("is_active", True):
                item.setBackground(QColor("#f1f5f9"))
            self.suppliers_table.setItem(row, column, item)

    def selected_supplier(self):
        row = self.suppliers_table.currentRow()
        if row < 0:
            return None
        item = self.suppliers_table.item(row, 0)
        data = item.data(Qt.UserRole) if item else None
        return data if isinstance(data, dict) else None

    def _on_selection_changed(self):
        if self._loading:
            return
        self.current_supplier = dict(self.selected_supplier() or {})
        self.supplierSelected.emit(self.current_supplier)
