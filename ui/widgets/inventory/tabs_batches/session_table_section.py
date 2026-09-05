import os
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QGroupBox, QMessageBox, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
import qtawesome as qta

from ui.touch_design import apply_touch_button_defaults, apply_touch_table_defaults

# ============================================================
# SessionTableSection — جدول الجلسة المحسَّن والمضغوط
# ============================================================
class SessionTableSection(QGroupBox):
    """
    يعرض المنتجات المضافة خلال الجلسة الحالية بتصميم مدمج وسريع الاستجابة.
    - ارتفاع أسطر مصمم بعناية (36px) لتوفير أقصى مساحة رؤية.
    - أزرار إجراءات مدمجة ومريحة للمس والفأرة.
    - شريط إحصائيات واضح مع زر لتصفير عرض الجلسة.
    """

    item_edited  = Signal(dict)
    item_deleted = Signal(dict)

    def __init__(self, manager, parent=None):
        super().__init__("📦 Articles ajoutés lors de cette session", parent)
        self.manager = manager
        self._items = []
        self.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                font-size: 13px;
                color: #1e293b;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 14px;
                background-color: #ffffff;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 14, 8, 8)
        layout.setSpacing(8)

        # ------------------------------------------------------
        # 1. شريط الإحصائيات + زر مسح الجلسة
        # ------------------------------------------------------
        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        self.lbl_stats = QLabel("⚖️ Poids : <b>0.00 g</b>  |  📦 Articles : <b>0</b>")
        self.lbl_stats.setFixedHeight(32)
        self.lbl_stats.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #6b21a8;
                background-color: #faf5ff;
                padding: 4px 10px;
                border-radius: 6px;
                border: 1px solid #e9d5ff;
            }
        """)

        btn_clear = QPushButton(" Nouvelle Série")
        btn_clear.setIcon(qta.icon("fa5s.broom", color="#991b1b"))
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setFixedHeight(32)
        btn_clear.setFocusPolicy(Qt.NoFocus)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #991b1b;
                font-weight: 700;
                font-size: 11px;
                padding: 2px 10px;
                border-radius: 6px;
                border: 1px solid #fca5a5;
            }
            QPushButton:hover {
                background-color: #fecaca;
            }
            QPushButton:pressed {
                background-color: #f87171;
                color: white;
            }
        """)
        apply_touch_button_defaults(btn_clear, danger=True)
        btn_clear.clicked.connect(self._clear_session)

        info_row.addWidget(self.lbl_stats, stretch=1)
        info_row.addWidget(btn_clear)
        layout.addLayout(info_row)

        # ------------------------------------------------------
        # 2. الجدول + أزرار التمرير الجانبية المدمجة
        # ------------------------------------------------------
        table_row = QHBoxLayout()
        table_row.setSpacing(6)

        self.table = QTableWidget()
        cols = ["Code", "Article", "Type", "Poids/Qté", "P.Vente", "Actions"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 105)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        apply_touch_table_defaults(self.table)
        self.table.verticalHeader().setDefaultSectionSize(36)

        self.table.setStyleSheet("""
            QTableWidget {
                font-size: 12px;
                font-weight: 500;
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                gridline-color: #f1f5f9;
            }
            QTableWidget::item {
                padding: 2px 4px;
            }
            QTableWidget::item:selected {
                background-color: #eff6ff;
                color: #1e3a8a;
            }
            QHeaderView::section {
                font-weight: 700;
                background-color: #f1f5f9;
                padding: 6px 4px;
                border: none;
                border-bottom: 1.5px solid #cbd5e1;
                color: #475569;
                font-size: 11px;
            }
        """)

        # أزرار التمرير الجانبية
        scroll_col = QVBoxLayout()
        scroll_col.setSpacing(6)

        btn_up = QPushButton()
        btn_up.setIcon(qta.icon("fa5s.chevron-up", color="white"))
        btn_up.setFixedSize(28, 48)
        btn_up.setCursor(Qt.PointingHandCursor)
        btn_up.setFocusPolicy(Qt.NoFocus)
        apply_touch_button_defaults(btn_up)
        btn_up.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton:pressed {
                background-color: #1e293b;
            }
        """)
        btn_up.clicked.connect(lambda: self._scroll(-1))

        btn_down = QPushButton()
        btn_down.setIcon(qta.icon("fa5s.chevron-down", color="white"))
        btn_down.setFixedSize(28, 48)
        btn_down.setCursor(Qt.PointingHandCursor)
        btn_down.setFocusPolicy(Qt.NoFocus)
        apply_touch_button_defaults(btn_down)
        btn_down.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton:pressed {
                background-color: #1e293b;
            }
        """)
        btn_down.clicked.connect(lambda: self._scroll(1))

        scroll_col.addWidget(btn_up)
        scroll_col.addStretch()
        scroll_col.addWidget(btn_down)

        table_row.addWidget(self.table, stretch=1)
        table_row.addLayout(scroll_col)
        layout.addLayout(table_row)

    # ----------------------------------------------------------
    # Slots
    # ----------------------------------------------------------
    def _scroll(self, direction: int):
        sb = self.table.verticalScrollBar()
        sb.setValue(sb.value() + direction)

    def _clear_session(self):
        if not self._items:
            return

        reply = QMessageBox.question(
            self, "Confirmation",
            "Voulez-vous réinitialiser l'affichage de cette série ?\n\n"
            "(Les articles restent enregistrés dans la base de données.)",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._items.clear()
            self._refresh_table()

    # ----------------------------------------------------------
    # API عام
    # ----------------------------------------------------------
    def set_items(self, items: list):
        self._items = items
        self._refresh_table()

    def prepend(self, item: dict):
        self._items.insert(0, item)
        self._refresh_table()

    def update_item(self, item_id, new_data: dict):
        for i, it in enumerate(self._items):
            if it["id"] == item_id:
                self._items[i] = new_data
                break
        self._refresh_table()

    def remove_item(self, item_id):
        self._items = [it for it in self._items if it["id"] != item_id]
        self._refresh_table()

    # ----------------------------------------------------------
    # رسم الجدول
    # ----------------------------------------------------------
    def _refresh_table(self):
        self.table.setRowCount(len(self._items))
        total_weight = 0.0
        total_qty = 0

        for row, item in enumerate(self._items):
            # 0. Barcode
            bc_cell = self._cell(str(item.get("barcode") or "-"), bold=True)
            bc_cell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, bc_cell)

            # 1. Article Name
            name_cell = QTableWidgetItem(str(item.get("name") or ""))
            name_cell.setData(Qt.UserRole, item)
            name_cell.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 1, name_cell)

            # 2. Type
            i_type = item.get("item_type", "WEIGHT")
            type_cell = QTableWidgetItem("Poids" if i_type == "WEIGHT" else "Pièce")
            type_cell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, type_cell)

            # 3. Poids / Quantité
            if i_type == "WEIGHT":
                w = float(item.get("weight") or 0)
                qty_str = f"{w:.2f} g"
                total_weight += w
                total_qty += 1
            else:
                q = int(item.get("quantity") or 0)
                qty_str = f"{q} pcs"
                total_qty += q

            qty_cell = QTableWidgetItem(qty_str)
            qty_cell.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, qty_cell)

            # 4. Prix de Vente
            price_val = float(item.get("selling_price") or 0)
            price_cell = QTableWidgetItem(f"{price_val:,.2f} DA")
            price_cell.setForeground(QColor("#15803d"))
            price_cell.setFont(QFont("", 10, QFont.Bold))
            price_cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 4, price_cell)

            # 5. Action buttons
            self.table.setCellWidget(row, 5, self._action_buttons(item))

        self.lbl_stats.setText(
            f"⚖️ Poids : <b>{total_weight:.2f} g</b>  |  📦 Articles : <b>{total_qty}</b>"
        )

    def _cell(self, text: str, bold: bool = False) -> QTableWidgetItem:
        cell = QTableWidgetItem(text)
        if bold:
            cell.setFont(QFont("", 9, QFont.Bold))
        return cell

    def _action_buttons(self, item: dict) -> QWidget:
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)

        def btn(icon_name, color, bg, border, tooltip):
            b = QPushButton()
            b.setIcon(qta.icon(icon_name, color=color))
            b.setFixedSize(28, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tooltip)
            b.setFocusPolicy(Qt.NoFocus)
            apply_touch_button_defaults(b)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    border: 1.5px solid {color};
                }}
            """)
            return b

        b_print = btn("fa5s.print",    "#2563eb", "#eff6ff", "#bfdbfe", "Imprimer l'étiquette")
        b_edit  = btn("fa5s.pen",      "#d97706", "#fffbeb", "#fde68a", "Modifier l'article")
        b_del   = btn("fa5s.trash-alt","#dc2626", "#fef2f2", "#fecaca", "Supprimer l'article")

        b_print.clicked.connect(lambda _, d=item: self._print(d))
        b_edit.clicked.connect(lambda _, d=item: self._edit(d))
        b_del.clicked.connect(lambda _, d=item: self._delete(d))

        lay.addWidget(b_print)
        lay.addWidget(b_edit)
        lay.addWidget(b_del)
        return container

    def _print(self, item: dict):
        config_file = "config.json"
        if not os.path.exists(config_file):
            return
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            return
        lc = config.get("label_config", {})
        if not lc.get("printer_name"):
            QMessageBox.warning(self, "Erreur", "Aucune imprimante sélectionnée dans la configuration.")
            return
        from ui.dialogs.printer_label import LabelPrintPreviewDialog

        LabelPrintPreviewDialog(lc, item, self).exec()

    def _edit(self, item: dict):
        from ui.dialogs.Product_edit import ProductEditDialog

        dialog = ProductEditDialog(self.manager, item, self)
        if dialog.exec():
            updated = self.manager.inventory.get_item_by_id(item["id"])
            if updated:
                self.update_item(item["id"], updated)
                self.item_edited.emit(updated)

    def _delete(self, item: dict):
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous vraiment supprimer '{item.get('name')}' ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes and self.manager.inventory.delete_item(item["id"]):
            self.remove_item(item["id"])
            self.item_deleted.emit(item)
