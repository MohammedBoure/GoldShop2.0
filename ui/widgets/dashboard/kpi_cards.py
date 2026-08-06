# ui/widgets/dashboard/kpi_cards.py

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class KPICard(QFrame):
    def __init__(self, title, value, icon_char, color="#007572"):
        super().__init__()
        self.setMinimumHeight(110)
        self.setMinimumWidth(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(f"""
            QFrame {{ background-color: white; border-radius: 12px; border: 1px solid #ecf0f1; }}
            QFrame:hover {{ border: 1px solid {color}; background-color: #fdfdfd; }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 10))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        text_side = QVBoxLayout()
        text_side.setSpacing(5)

        lbl_title = QLabel(title.upper())
        lbl_title.setWordWrap(True)
        lbl_title.setStyleSheet("color: #7f8c8d; font-size: 12px; font-weight: bold; border:none;")

        self.lbl_value = QLabel(value)
        self.lbl_value.setWordWrap(True)
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 900; border:none;")

        text_side.addWidget(lbl_title)
        text_side.addWidget(self.lbl_value)
        text_side.addStretch()

        icon_circle = QLabel(icon_char)
        icon_circle.setFixedSize(52, 52)
        icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_circle.setStyleSheet(
            f"background-color: {color}15; border-radius: 26px; font-size: 24px; color: {color}; border:none;"
        )

        layout.addLayout(text_side, 1)
        layout.addWidget(icon_circle)


class KPICardsSection(QWidget):
    def __init__(self):
        super().__init__()
        self.cards = []
        self._current_columns = None
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange_cards()

    def _column_count(self):
        width = max(1, self.width())
        if width < 460:
            return 1
        if width < 760:
            return 2
        if width < 1080:
            return 3
        return 4

    def _arrange_cards(self, force=False):
        if not self.cards:
            return

        columns = self._column_count()
        if not force and self._current_columns == columns:
            return
        self._current_columns = columns

        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        for index, card in enumerate(self.cards):
            row, col = divmod(index, columns)
            self.layout.addWidget(card, row, col)

        for col in range(columns):
            self.layout.setColumnStretch(col, 1)

    def _add_card(self, title, value, icon_char, color):
        self.cards.append(KPICard(title, value, icon_char, color))

    def update_data(self, data_dict):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.cards = []

        total_gold_weight = 0.0
        total_silver_weight = 0.0

        for item in data_dict.get('gold_inventory_by_karat', []):
            name = str(item.get('name', '')).lower()
            if 'casse' not in name:
                total_gold_weight += float(item.get('weight', 0) or 0)

        for item in data_dict.get('silver_inventory_by_karat', []):
            name = str(item.get('name', '')).lower()
            if 'casse' not in name:
                total_silver_weight += float(item.get('weight', 0) or 0)

        self._add_card("POIDS OR (VITRINE)", f"{total_gold_weight:,.2f} g", "🥇", "#f39c12")
        self._add_card("POIDS ARGENT (VITRINE)", f"{total_silver_weight:,.2f} g", "🥈", "#95a5a6")

        gold_equivalent = float(data_dict.get('gold_inventory_equivalent_750', 0) or 0)
        silver_equivalent = float(data_dict.get('silver_inventory_equivalent_925', 0) or 0)
        self._add_card("POIDS OR (EQUIV. 750)", f"{gold_equivalent:,.2f} g", "750", "#d35400")
        self._add_card("POIDS ARGENT (EQUIV. 925)", f"{silver_equivalent:,.2f} g", "925", "#7f8c8d")

        # Liquidité en caisse is removed per user request
        c_debts = data_dict.get('client_debts', 0) or 0
        s_debts = data_dict.get('supplier_debts', 0) or 0

        self._add_card("CREANCES CLIENTS", f"{c_debts:,.2f} DA", "📉", "#2980b9")
        self._add_card("DETTES FOURNISSEURS", f"{s_debts:,.2f} DA", "💸", "#c0392b")

        s_debts_gold = data_dict.get('supplier_debts_gold', 0) or 0
        s_debts_silver = data_dict.get('supplier_debts_silver', 0) or 0

        if s_debts_gold > 0:
            self._add_card("DETTES FOURN. (OR)", f"{s_debts_gold:,.2f} g", "🟡", "#d35400")

        if s_debts_silver > 0:
            self._add_card("DETTES FOURN. (ARG)", f"{s_debts_silver:,.2f} g", "⚪", "#7f8c8d")

        self._current_columns = None
        self._arrange_cards(force=True)
