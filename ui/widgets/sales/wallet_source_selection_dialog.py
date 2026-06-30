from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.touch_design import (
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)


class WalletSourceSelectionDialog(QDialog):
    """Detailed selection of free-versement sources used by a sale payment."""

    def __init__(self, deposits, max_amount=None, current_plan=None, parent=None):
        super().__init__(parent)
        self.deposits = [
            dep for dep in (deposits or [])
            if self._is_selectable_deposit(dep)
        ]
        self.max_amount = float(max_amount) if max_amount is not None else None
        self.current_plan = current_plan or {}
        self.rows = []
        self._updating = False

        self.setWindowTitle("Detail versement libre")
        self.setMinimumSize(940, 520)
        self._resize_for_screen()
        self._build_ui()

    def _resize_for_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            self.resize(1120, 600)
            return
        available = screen.availableGeometry()
        width = min(max(1120, int(available.width() * 0.88)), max(940, available.width() - 40))
        height = min(max(600, int(available.height() * 0.72)), max(520, available.height() - 80))
        self.resize(width, height)

    @staticmethod
    def _remaining_amount(dep):
        remaining = dep.get("remaining_amount")
        if remaining is not None:
            return max(0.0, float(remaining or 0.0))
        return max(0.0, float(dep.get("amount") or 0.0) - float(dep.get("used_amount") or 0.0))

    @staticmethod
    def _source_rate(dep):
        rate = float(dep.get("metal_rate_at_payment") or 0.0)
        if rate > 0:
            return rate
        remaining = WalletSourceSelectionDialog._remaining_amount(dep)
        available_weight = float(dep.get("available_weight") or 0.0)
        if remaining > 0 and available_weight > 0:
            return remaining / available_weight
        amount = float(dep.get("amount") or dep.get("total_amount") or 0.0)
        weight = float(dep.get("purchased_weight") or dep.get("total_weight") or 0.0)
        if amount > 0 and weight > 0:
            return amount / weight
        return 0.0

    @classmethod
    def _available_weight(cls, dep):
        explicit_weight = float(dep.get("available_weight") or 0.0)
        if explicit_weight > 0:
            return explicit_weight
        remaining = cls._remaining_amount(dep)
        rate = cls._source_rate(dep)
        if remaining > 0 and rate > 0:
            return remaining / rate
        amount = float(dep.get("amount") or dep.get("total_amount") or 0.0)
        weight = float(dep.get("purchased_weight") or dep.get("total_weight") or 0.0)
        if amount > 0 and weight > 0:
            return weight * (remaining / amount)
        return 0.0

    @classmethod
    def _is_selectable_deposit(cls, dep):
        if cls._remaining_amount(dep) <= 0.005:
            return False
        status = str(dep.get("status") or "").strip().upper()
        if status in {"CANCELLED", "ABANDONED", "INVOICED"}:
            return False
        if dep.get("linked_sale_id"):
            return False
        if dep.get("parent_free_versement_id"):
            return False
        versement_type = str(dep.get("versement_type") or "").strip().upper()
        if versement_type and versement_type != "VERSEMENT_LIBRE":
            return False
        source_kind = str(dep.get("source_kind") or "").strip().upper()
        payment_type = str(dep.get("payment_type") or "").strip().upper()
        if source_kind == "CLIENT_VERSEMENT" and payment_type and payment_type != "VERSEMENT_LIBRE":
            return False
        return True

    @staticmethod
    def _source_key_from_parts(source_payment_id, source_free_versement_id):
        try:
            free_id = int(source_free_versement_id or 0)
        except (TypeError, ValueError):
            free_id = 0
        if free_id > 0:
            return ("free", free_id)
        try:
            payment_id = int(source_payment_id or 0)
        except (TypeError, ValueError):
            payment_id = 0
        return ("payment", payment_id)

    @classmethod
    def _source_key(cls, dep):
        source_free_versement_id = dep.get("source_free_versement_id")
        source_payment_id = None if source_free_versement_id else dep.get("id")
        return cls._source_key_from_parts(source_payment_id, source_free_versement_id)

    def _current_amounts(self):
        current = {}
        for entry in self.current_plan.get("entries", []) or []:
            key = self._source_key_from_parts(
                entry.get("source_payment_id"),
                entry.get("source_free_versement_id"),
            )
            current[key] = float(entry.get("amount") or 0.0)
        return current

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Choisir les sources du versement libre")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #243447;")
        layout.addWidget(title)

        self.summary = QLabel("")
        self.summary.setStyleSheet("font-size: 13px; color: #596275;")
        layout.addWidget(self.summary)

        self.table = QTableWidget(len(self.deposits), 6)
        self.table.setHorizontalHeaderLabels([
            "Source",
            "Type",
            "Disponible",
            "Poids dispo",
            "Montant",
            "Poids source",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        apply_touch_table_defaults(self.table)
        self.table.verticalHeader().setDefaultSectionSize(62)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self.table)

        self._populate_rows()

        actions = QHBoxLayout()
        btn_clear = QPushButton("Effacer")
        btn_clear.clicked.connect(self.clear_selection)
        btn_max = QPushButton("Remplir max")
        btn_max.clicked.connect(self.fill_maximum)
        actions.addWidget(btn_clear)
        actions.addWidget(btn_max)
        actions.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        layout.addLayout(actions)
        self._update_summary()

    def _text_item(self, text, align=Qt.AlignLeft | Qt.AlignVCenter):
        item = QTableWidgetItem(text)
        item.setTextAlignment(align)
        return item

    def _populate_rows(self):
        current_amounts = self._current_amounts()
        for row, dep in enumerate(self.deposits):
            available = self._remaining_amount(dep)
            rate = self._source_rate(dep)
            available_weight = self._available_weight(dep)
            is_weighted = available_weight > 0.0005 and rate > 0
            key = self._source_key(dep)
            selected_amount = min(available, current_amounts.get(key, 0.0))

            source_label = (
                dep.get("display_number")
                or dep.get("document_number")
                or dep.get("receipt_number")
                or f"#{dep.get('id')}"
            )
            self.table.setItem(row, 0, self._text_item(str(source_label)))
            self.table.setItem(row, 1, self._text_item("Poids" if is_weighted else "Montant", Qt.AlignCenter))
            self.table.setItem(row, 2, self._text_item(f"{available:,.2f} DA", Qt.AlignRight | Qt.AlignVCenter))
            self.table.setItem(
                row,
                3,
                self._text_item(f"{available_weight:.3f} g" if is_weighted else "-", Qt.AlignCenter),
            )

            amount_spin = QDoubleSpinBox()
            amount_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            amount_spin.setRange(0.0, available)
            amount_spin.setDecimals(2)
            amount_spin.setSuffix(" DA")
            amount_spin.setAlignment(Qt.AlignCenter)
            amount_spin.setMinimumWidth(150)
            apply_touch_input_defaults(amount_spin)

            weight_spin = QDoubleSpinBox()
            weight_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            weight_spin.setRange(0.0, available_weight if is_weighted else 0.0)
            weight_spin.setDecimals(3)
            weight_spin.setSuffix(" g")
            weight_spin.setAlignment(Qt.AlignCenter)
            weight_spin.setMinimumWidth(130)
            weight_spin.setEnabled(is_weighted)
            apply_touch_input_defaults(weight_spin)

            data = {
                "deposit": dep,
                "available": available,
                "available_weight": available_weight,
                "rate": rate,
                "is_weighted": is_weighted,
                "amount_spin": amount_spin,
                "weight_spin": weight_spin,
            }
            self.rows.append(data)

            amount_spin.valueChanged.connect(lambda _value, row_index=row: self._sync_from_amount(row_index))
            weight_spin.valueChanged.connect(lambda _value, row_index=row: self._sync_from_weight(row_index))

            amount_spin.setValue(selected_amount)
            self.table.setCellWidget(
                row,
                4,
                self._spin_action_cell(
                    amount_spin,
                    self._numpad_button(amount_spin, f"Montant {source_label}"),
                    self._row_fill_button(row, mode="amount"),
                ),
            )
            self.table.setCellWidget(
                row,
                5,
                self._spin_action_cell(
                    weight_spin,
                    self._numpad_button(weight_spin, f"Poids {source_label}", enabled=is_weighted),
                    self._row_fill_button(row, mode="weight", enabled=is_weighted),
                ),
            )
            self._sync_from_amount(row)

    def _open_numpad(self, spinbox, title):
        if not spinbox.isEnabled():
            return
        from ui.tools.virtual_numpad import VirtualNumpad

        pad = VirtualNumpad(
            title,
            mode="direct",
            target_widget=spinbox,
            allow_decimal=True,
            parent=self,
        )
        pad.exec()

    def _spin_action_cell(self, spinbox, numpad_button, fill_button):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(5)
        layout.addWidget(spinbox, 1)
        layout.addWidget(numpad_button)
        layout.addWidget(fill_button)
        return container

    @staticmethod
    def _style_compact_button(button):
        button.setFixedHeight(44)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet("""
            QPushButton {
                min-height: 44px;
                max-height: 44px;
                padding: 0;
                border-radius: 6px;
                border: 1px solid #cbd5df;
                background-color: #ffffff;
                color: #243447;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton:pressed { background-color: #e8eef5; }
            QPushButton:disabled {
                color: #a5adb8;
                background-color: #f4f6f8;
                border-color: #dfe4ea;
            }
        """)

    def _numpad_button(self, spinbox, title, enabled=True):
        button = QPushButton("123")
        button.setToolTip("Pave numerique")
        button.setEnabled(bool(enabled))
        button.setFixedWidth(52)
        self._style_compact_button(button)
        button.clicked.connect(lambda _checked=False, sb=spinbox, t=title: self._open_numpad(sb, t))
        return button

    def _row_fill_button(self, row, mode="amount", enabled=True):
        button = QPushButton("Tout")
        button.setToolTip("Utiliser tout le disponible de cette ligne")
        button.setEnabled(bool(enabled))
        button.setFixedWidth(58)
        self._style_compact_button(button)
        button.clicked.connect(lambda _checked=False, r=row, m=mode: self.fill_row_maximum(r, m))
        return button

    def _row_max_amount(self, row):
        data = self.rows[row]
        available = float(data["available"] or 0.0)
        if self.max_amount is None:
            return available
        current = float(data["amount_spin"].value() or 0.0)
        total, _weight = self._totals()
        remaining_capacity = max(0.0, float(self.max_amount or 0.0) - (total - current))
        return min(available, remaining_capacity)

    def fill_row_maximum(self, row, mode="amount"):
        if row < 0 or row >= len(self.rows):
            return
        data = self.rows[row]
        amount = self._row_max_amount(row)
        if mode == "weight" and data["is_weighted"] and data["rate"] > 0:
            data["weight_spin"].setValue(min(data["available_weight"], amount / data["rate"]))
            return
        data["amount_spin"].setValue(amount)

    def _sync_from_amount(self, row):
        if self._updating:
            return
        data = self.rows[row]
        if not data["is_weighted"] or data["rate"] <= 0:
            self._update_summary()
            return
        self._updating = True
        amount = float(data["amount_spin"].value() or 0.0)
        data["weight_spin"].setValue(min(data["available_weight"], amount / data["rate"]))
        self._updating = False
        self._update_summary()

    def _sync_from_weight(self, row):
        if self._updating:
            return
        data = self.rows[row]
        if not data["is_weighted"] or data["rate"] <= 0:
            self._update_summary()
            return
        self._updating = True
        weight = float(data["weight_spin"].value() or 0.0)
        data["amount_spin"].setValue(min(data["available"], weight * data["rate"]))
        self._updating = False
        self._update_summary()

    def _totals(self):
        amount = 0.0
        weight = 0.0
        for data in self.rows:
            amount += float(data["amount_spin"].value() or 0.0)
            if data["is_weighted"]:
                weight += float(data["weight_spin"].value() or 0.0)
        return round(amount, 2), round(weight, 3)

    def _update_summary(self):
        amount, weight = self._totals()
        limit_text = f" / limite {self.max_amount:,.2f} DA" if self.max_amount is not None else ""
        self.summary.setText(f"Selection: {amount:,.2f} DA{limit_text} | poids source: {weight:.3f} g")
        if self.max_amount is not None and amount > self.max_amount + 0.05:
            self.summary.setStyleSheet("font-size: 13px; color: #c0392b; font-weight: bold;")
        else:
            self.summary.setStyleSheet("font-size: 13px; color: #596275;")

    def clear_selection(self):
        self._updating = True
        for data in self.rows:
            data["amount_spin"].setValue(0.0)
            data["weight_spin"].setValue(0.0)
        self._updating = False
        self._update_summary()

    def fill_maximum(self):
        remaining = self.max_amount if self.max_amount is not None else sum(
            data["available"] for data in self.rows
        )
        self._updating = True
        for data in self.rows:
            amount = min(data["available"], max(0.0, remaining))
            data["amount_spin"].setValue(amount)
            if data["is_weighted"] and data["rate"] > 0:
                data["weight_spin"].setValue(min(data["available_weight"], amount / data["rate"]))
            remaining -= amount
        self._updating = False
        self._update_summary()

    def accept(self):
        amount, _weight = self._totals()
        if self.max_amount is not None and amount > self.max_amount + 0.05:
            QMessageBox.warning(
                self,
                "Versement libre",
                "La selection depasse le montant restant a payer.",
            )
            return
        super().accept()

    def get_plan(self):
        entries = []
        weighted_amount = 0.0
        weighted_weight = 0.0
        for data in self.rows:
            dep = data["deposit"]
            amount = round(float(data["amount_spin"].value() or 0.0), 2)
            if amount <= 0.005:
                continue
            source_free_versement_id = dep.get("source_free_versement_id")
            source_weight = round(float(data["weight_spin"].value() or 0.0), 3) if data["is_weighted"] else 0.0
            entry = {
                "source_payment_id": None if source_free_versement_id else dep.get("id"),
                "source_free_versement_id": source_free_versement_id,
                "amount": amount,
                "source_weight": source_weight,
                "source_amount": amount,
                "source_rate": float(data["rate"] or dep.get("metal_rate_at_payment") or 0.0),
                "source_purity": float(dep.get("metal_purity_at_payment") or 0.0),
                "is_weighted": source_weight > 0.0005,
            }
            entries.append(entry)
            if entry["is_weighted"]:
                weighted_amount += amount
                weighted_weight += source_weight
        return {
            "weighted_amount": round(weighted_amount, 2),
            "weighted_weight": round(weighted_weight, 3),
            "entries": entries,
        }
