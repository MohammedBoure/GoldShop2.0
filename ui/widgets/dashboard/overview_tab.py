# ui/widgets/dashboard/overview_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QGroupBox, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt
from .kpi_cards import KPICardsSection
from .charts_section import ChartsSection


class MetalBreakdownSection(QGroupBox):
    def __init__(self, title, is_vitrine=True):
        super().__init__(title)
        self.is_vitrine = is_vitrine
        self.item_widgets = []
        self.empty_label = None
        self._current_columns = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 14px; color: #2c3e50;"
            " border: 1px solid #dcdde1; border-radius: 8px; margin-top: 10px; }"
            " QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(15, 25, 15, 15)
        self.layout.setSpacing(12)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange_items()

    def _column_count(self):
        width = max(1, self.width())
        if width < 360:
            return 1
        if width < 620:
            return 2
        if width < 880:
            return 3
        return 4

    def _clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

    def _arrange_items(self, force=False):
        columns = self._column_count()
        if not force and self._current_columns == columns:
            return
        self._current_columns = columns

        self._clear_layout()

        if self.empty_label is not None:
            self.layout.addWidget(self.empty_label, 0, 0)
            self.layout.setColumnStretch(0, 1)
            return

        for index, frame in enumerate(self.item_widgets):
            row, col = divmod(index, columns)
            self.layout.addWidget(frame, row, col)

        for col in range(columns):
            self.layout.setColumnStretch(col, 1)

    def update_data(self, items):
        self._clear_layout()
        for widget in self.item_widgets:
            widget.deleteLater()
        self.item_widgets = []
        if self.empty_label is not None:
            self.empty_label.deleteLater()
            self.empty_label = None

        if not items:
            self.empty_label = QLabel("Aucune donnee" if self.is_vitrine else "Coffre vide")
            self.empty_label.setStyleSheet("color: #95a5a6; font-style: italic;")
            self.empty_label.setAlignment(Qt.AlignCenter)
            self._current_columns = None
            self._arrange_items(force=True)
            return

        for item in items:
            frame = QFrame()
            frame.setMinimumHeight(74)
            frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            frame.setStyleSheet(
                "QFrame { background-color: #f8f9fa; border-radius: 8px; border: 1px solid #ecf0f1; }"
            )

            flay = QVBoxLayout(frame)
            flay.setContentsMargins(10, 10, 10, 10)
            flay.setSpacing(5)

            lname = QLabel(str(item['name']))
            lname.setWordWrap(True)
            lname.setStyleSheet("font-weight: bold; color: #34495e; font-size: 13px; border: none;")
            lname.setAlignment(Qt.AlignCenter)

            w_val = float(item.get('weight') or 0.0)
            lval = QLabel(f"{w_val:.2f} g")
            lval.setStyleSheet("font-weight: 900; color: #d35400; font-size: 16px; border: none;")
            lval.setAlignment(Qt.AlignCenter)

            flay.addWidget(lname)
            flay.addWidget(lval)
            self.item_widgets.append(frame)

        self._current_columns = None
        self._arrange_items(force=True)


class OverviewTab(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        self.kpi_section = KPICardsSection()
        layout.addWidget(self.kpi_section)

        self.vitrine_section = MetalBreakdownSection("💎 Repartition Or & Argent (Vitrine)")
        layout.addWidget(self.vitrine_section)

        self.charts_section = ChartsSection()
        layout.addWidget(self.charts_section, stretch=1)

    def update_content(self, metrics, sales_trend, purchases_trend, alerts_data):
        if self.kpi_section:
            self.kpi_section.update_data(metrics)

        if hasattr(self, 'vitrine_section'):
            vitrine_gold = metrics.get('gold_inventory_by_karat', [])
            vitrine_silver = metrics.get('silver_inventory_by_karat', [])
            self.vitrine_section.update_data(vitrine_gold + vitrine_silver)

        if hasattr(self, 'charts_section'):
            self.charts_section.update_data(sales_trend, purchases_trend)
