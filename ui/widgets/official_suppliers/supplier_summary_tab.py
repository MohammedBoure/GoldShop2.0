from __future__ import annotations

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.touch_design import apply_touch_input_defaults, apply_touch_table_defaults

from .helpers import fmt_money, fmt_weight, make_action_button


class SupplierSummaryTab(QWidget):
    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._build_metric_panel())
        layout.addLayout(self._build_summary_filters())

        self.summary_table = QTableWidget(0, 8)
        self.summary_table.setHorizontalHeaderLabels([
            "Fournisseur",
            "Annee",
            "Mois",
            "Entrees",
            "Sorties",
            "Diff poids",
            "Montant entree",
            "Montant sortie",
        ])
        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        apply_touch_table_defaults(self.summary_table)
        layout.addWidget(self.summary_table, 1)

    def _build_metric_panel(self):
        metrics = QFrame()
        metrics.setObjectName("officialPanel")
        metric_layout = QGridLayout(metrics)
        metric_layout.setContentsMargins(12, 12, 12, 12)
        metric_layout.setHorizontalSpacing(14)
        metric_layout.setVerticalSpacing(8)
        self.lbl_total_in = self._metric("Entrees", "0.000 g")
        self.lbl_total_out = self._metric("Sorties", "0.000 g")
        self.lbl_total_net = self._metric("Difference", "0.000 g")
        self.lbl_total_money = self._metric("Montant net", "0.00 DA")
        for index, widget in enumerate((
            self.lbl_total_in,
            self.lbl_total_out,
            self.lbl_total_net,
            self.lbl_total_money,
        )):
            metric_layout.addWidget(widget, 0, index)
        return metrics

    def _build_summary_filters(self):
        filters = QHBoxLayout()
        self.summary_year = QSpinBox()
        self.summary_year.setRange(2000, 2100)
        self.summary_year.setValue(QDate.currentDate().year())
        self.summary_month = QComboBox()
        self.summary_month.addItem("Tous les mois", None)
        for number, label in enumerate(
            [
                "Janvier",
                "Fevrier",
                "Mars",
                "Avril",
                "Mai",
                "Juin",
                "Juillet",
                "Aout",
                "Septembre",
                "Octobre",
                "Novembre",
                "Decembre",
            ],
            start=1,
        ):
            self.summary_month.addItem(label, number)
        self.btn_summary_refresh = make_action_button(
            "Recalculer",
            "fa5s.calculator",
            "official_supplier_summary",
        )
        for widget in (self.summary_year, self.summary_month):
            apply_touch_input_defaults(widget)
        filters.addWidget(QLabel("Annee"))
        filters.addWidget(self.summary_year)
        filters.addWidget(QLabel("Mois"))
        filters.addWidget(self.summary_month)
        filters.addWidget(self.btn_summary_refresh)
        filters.addStretch()
        return filters

    def _connect_signals(self):
        self.btn_summary_refresh.clicked.connect(self.refreshRequested.emit)

    @staticmethod
    def _metric(caption, value):
        frame = QFrame()
        frame.setObjectName("officialPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        label = QLabel(caption)
        label.setObjectName("metricCaption")
        number = QLabel(value)
        number.setObjectName("metricValue")
        frame.value_label = number
        layout.addWidget(label)
        layout.addWidget(number)
        return frame

    def refresh_summary(self, service, supplier_id):
        totals = {}
        rows = []
        if supplier_id:
            totals = service.get_totals(supplier_id) or {}
            rows = service.get_monthly_summary(
                year=self.summary_year.value(),
                month=self.summary_month.currentData(),
                official_supplier_id=supplier_id,
            )
        self.lbl_total_in.value_label.setText(fmt_weight(totals.get("incoming_weight_g")))
        self.lbl_total_out.value_label.setText(fmt_weight(totals.get("outgoing_weight_g")))
        self.lbl_total_net.value_label.setText(fmt_weight(totals.get("net_weight_g")))
        self.lbl_total_money.value_label.setText(fmt_money(totals.get("net_amount_da")))
        self._populate_summary_table(rows)

    def _populate_summary_table(self, rows):
        self.summary_table.setRowCount(0)
        for summary in rows:
            row = self.summary_table.rowCount()
            self.summary_table.insertRow(row)
            values = [
                summary.get("official_supplier_name") or "",
                summary.get("summary_year") or "",
                summary.get("summary_month") or "",
                fmt_weight(summary.get("incoming_weight_g")),
                fmt_weight(summary.get("outgoing_weight_g")),
                fmt_weight(summary.get("net_weight_g")),
                fmt_money(summary.get("incoming_amount_da")),
                fmt_money(summary.get("outgoing_amount_da")),
            ]
            for column, value in enumerate(values):
                self.summary_table.setItem(row, column, QTableWidgetItem(str(value)))
