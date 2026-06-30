from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.touch_design import apply_touch_input_defaults, apply_touch_table_defaults

from .helpers import fmt_date, fmt_money, fmt_unit, fmt_weight, operation_label


class SupplierOperationsTab(QWidget):
    operationSelectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._build_filters())

        self.operations_table = QTableWidget(0, 10)
        self.operations_table.setHorizontalHeaderLabels([
            "ID",
            "Date",
            "Type",
            "Poids",
            "Montant",
            "Prix/g",
            "Metal",
            "Document",
            "Observation",
            "Source",
        ])
        self.operations_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.operations_table.setColumnHidden(0, True)
        self.operations_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.operations_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        apply_touch_table_defaults(self.operations_table)
        layout.addWidget(self.operations_table, 1)

    def _build_filters(self):
        filters = QFrame()
        filters.setObjectName("officialPanel")
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(10, 10, 10, 10)
        filter_layout.setSpacing(8)

        self.operation_type_filter = QComboBox()
        self.operation_type_filter.addItem("Entrees", "INCOMING")
        self.operation_search = QLineEdit()
        self.operation_search.setPlaceholderText("Document ou observation...")
        self.operation_start = QDateEdit(QDate.currentDate().addMonths(-1))
        self.operation_end = QDateEdit(QDate.currentDate())
        for widget in (
            self.operation_type_filter,
            self.operation_search,
            self.operation_start,
            self.operation_end,
        ):
            apply_touch_input_defaults(widget)
        for date_widget in (self.operation_start, self.operation_end):
            date_widget.setCalendarPopup(True)

        filter_layout.addWidget(QLabel("Type"))
        filter_layout.addWidget(self.operation_type_filter)
        filter_layout.addWidget(QLabel("Du"))
        filter_layout.addWidget(self.operation_start)
        filter_layout.addWidget(QLabel("Au"))
        filter_layout.addWidget(self.operation_end)
        filter_layout.addWidget(self.operation_search, 1)
        return filters

    def _connect_signals(self):
        self.operations_table.itemSelectionChanged.connect(self.operationSelectionChanged.emit)

    def connect_filters(self, callback):
        self.operation_type_filter.currentIndexChanged.connect(lambda _index: callback())
        self.operation_search.textChanged.connect(lambda _text: callback())
        self.operation_start.dateChanged.connect(lambda _date: callback())
        self.operation_end.dateChanged.connect(lambda _date: callback())

    def load_operations(self, service, supplier_id):
        self.operations_table.setRowCount(0)
        if not supplier_id:
            self.operationSelectionChanged.emit()
            return
        rows = service.list_operations(
            official_supplier_id=supplier_id,
            operation_type=self.operation_type_filter.currentData(),
            start_date=self.operation_start.date().toString("yyyy-MM-dd"),
            end_date=self.operation_end.date().toString("yyyy-MM-dd"),
            search_text=self.operation_search.text(),
            limit=500,
            offset=0,
        )
        for operation in rows:
            self._append_operation_row(operation)
        self.operationSelectionChanged.emit()

    def _append_operation_row(self, operation):
        row = self.operations_table.rowCount()
        self.operations_table.insertRow(row)
        values = [
            operation.get("id"),
            fmt_date(operation.get("operation_date")),
            operation_label(operation.get("operation_type")),
            fmt_weight(operation.get("weight_g")),
            fmt_money(operation.get("amount_da")),
            fmt_unit(operation.get("unit_price_per_gram")),
            operation.get("metal_type_name") or "-",
            operation.get("document_number") or "",
            operation.get("description") or "",
            operation.get("source_kind") or "",
        ]
        bg = QColor("#eafaf1") if operation.get("operation_type") == "INCOMING" else QColor("#fff1f0")
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setData(Qt.UserRole, operation)
            item.setBackground(bg)
            self.operations_table.setItem(row, column, item)

    def selected_operation(self):
        row = self.operations_table.currentRow()
        if row < 0:
            return None
        item = self.operations_table.item(row, 0)
        data = item.data(Qt.UserRole) if item else None
        return data if isinstance(data, dict) else None
