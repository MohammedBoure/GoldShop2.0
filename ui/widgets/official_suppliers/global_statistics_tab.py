from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from ui.touch_design import apply_touch_input_defaults

from .helpers import fmt_money, fmt_weight, make_action_button
from .operation_dialog import OfficialOperationDialog


class GlobalStatisticsTab(QFrame):
    def __init__(self, manager, current_user=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.current_user = current_user or {}
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setObjectName("officialPanel")
        self.setMinimumWidth(330)
        self.setMaximumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addLayout(self._build_filters())

        self.lbl_global_in_weight = self._stat_value("Poids entree", "0.000 g")
        self.lbl_global_out_weight = self._stat_value("Poids sortie", "0.000 g")
        self.lbl_global_net_weight = self._stat_value("Difference poids", "0.000 g")
        self.lbl_global_in_amount = self._stat_value("Montant entree", "0.00 DA")
        self.lbl_global_out_amount = self._stat_value("Montant sortie", "0.00 DA")
        self.lbl_global_net_amount = self._stat_value("Difference montant", "0.00 DA")
        self.lbl_global_operation_count = self._stat_value("Operations", "0")

        for widget in (
            self.lbl_global_in_weight,
            self.lbl_global_out_weight,
            self.lbl_global_net_weight,
            self.lbl_global_in_amount,
            self.lbl_global_out_amount,
            self.lbl_global_net_amount,
            self.lbl_global_operation_count,
        ):
            layout.addWidget(widget)
        layout.addStretch()

    def _build_filters(self):
        self.global_start_date = QDateEdit(QDate.currentDate().addMonths(-1))
        self.global_end_date = QDateEdit(QDate.currentDate())
        for date_edit in (self.global_start_date, self.global_end_date):
            date_edit.setCalendarPopup(True)
            apply_touch_input_defaults(date_edit)

        filters = QGridLayout()
        filters.setHorizontalSpacing(8)
        filters.setVerticalSpacing(6)
        filters.addWidget(QLabel("Du"), 0, 0)
        filters.addWidget(self.global_start_date, 0, 1)
        filters.addWidget(QLabel("Au"), 1, 0)
        filters.addWidget(self.global_end_date, 1, 1)
        self.btn_global_stats_refresh = make_action_button(
            "Recalculer",
            "fa5s.calculator",
            "official_supplier_summary",
        )
        self.btn_global_outgoing = make_action_button(
            "Sortie officielle",
            "fa5s.arrow-up",
            "official_supplier_operation_create",
        )
        filters.addWidget(self.btn_global_stats_refresh, 2, 0, 1, 2)
        filters.addWidget(self.btn_global_outgoing, 3, 0, 1, 2)
        return filters

    @staticmethod
    def _stat_value(caption, value):
        frame = QFrame()
        frame.setObjectName("officialPanel")
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)
        label = QLabel(caption)
        label.setObjectName("metricCaption")
        number = QLabel(value)
        number.setObjectName("metricValue")
        number.setProperty("ui_element_type", "display_field")
        frame.value_label = number
        row.addWidget(label, 1)
        row.addWidget(number)
        return frame

    def _connect_signals(self):
        self.btn_global_stats_refresh.clicked.connect(lambda _checked=False: self.load_global_statistics())
        self.btn_global_outgoing.clicked.connect(self.create_global_outgoing)
        self.global_start_date.dateChanged.connect(lambda _date: self.load_global_statistics())
        self.global_end_date.dateChanged.connect(lambda _date: self.load_global_statistics())

    def create_global_outgoing(self):
        dialog = OfficialOperationDialog(
            self.manager,
            {},
            operation_type="OUTGOING",
            current_user=self.current_user,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.load_global_statistics()

    def load_global_statistics(self):
        totals = self.manager.official_suppliers.get_totals(
            start_date=self.global_start_date.date().toString("yyyy-MM-dd"),
            end_date=self.global_end_date.date().toString("yyyy-MM-dd"),
        ) or {}
        self.lbl_global_in_weight.value_label.setText(fmt_weight(totals.get("incoming_weight_g")))
        self.lbl_global_out_weight.value_label.setText(fmt_weight(totals.get("outgoing_weight_g")))
        self.lbl_global_net_weight.value_label.setText(fmt_weight(totals.get("net_weight_g")))
        self.lbl_global_in_amount.value_label.setText(fmt_money(totals.get("incoming_amount_da")))
        self.lbl_global_out_amount.value_label.setText(fmt_money(totals.get("outgoing_amount_da")))
        self.lbl_global_net_amount.value_label.setText(fmt_money(totals.get("net_amount_da")))
        self.lbl_global_operation_count.value_label.setText(str(totals.get("operation_count") or 0))
