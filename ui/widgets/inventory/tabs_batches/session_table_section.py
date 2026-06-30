import os
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QGroupBox,
    QMessageBox,QLabel,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
import qtawesome as qta

from ui.touch_design import apply_touch_button_defaults, apply_touch_table_defaults






# ============================================================
# 4. SessionTableSection — جدول الجلسة
# ============================================================
class SessionTableSection(QGroupBox):
    """
    يعرض المنتجات المضافة خلال الجلسة الحالية،
    ويوفر أزرار الطباعة/التعديل/الحذف والتمرير.
    """

    item_edited  = Signal(dict)   # بيانات العنصر المعدَّل
    item_deleted = Signal(dict)   # بيانات العنصر المحذوف

    def __init__(self, manager, parent=None):
        super().__init__("📦 Articles ajoutés lors de cette session", parent)
        self.manager = manager
        self._items = []
        self.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 16px; color: #2c3e50;"
            " border: 2px solid #bdc3c7; border-radius: 8px;"
            " margin-top: 10px; background-color: white; }"
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 10)

        # --- شريط الإحصائيات + زر مسح الجلسة ---
        info_row = QHBoxLayout()

        self.lbl_stats = QLabel("⚖️ Poids Total : 0.00 g  |  📦 Total Articles : 0")
        self.lbl_stats.setFixedHeight(35)
        self.lbl_stats.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #8e44ad;"
            " background-color: #f4ecf7; padding: 5px 15px;"
            " border-radius: 6px; border: 1px solid #d2b4de;"
        )

        btn_clear = QPushButton(" Nouvelle Série (Vider l'affichage)")
        btn_clear.setIcon(qta.icon("fa5s.broom", color="white"))
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setFixedHeight(35)
        btn_clear.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold;"
            " font-size: 14px; padding: 5px 15px; border-radius: 6px;"
        )
        apply_touch_button_defaults(btn_clear, danger=True)
        btn_clear.clicked.connect(self._clear_session)

        # تحديد المسافة بين النص والزر (مثلا 15 بيكسل)
        info_row.setSpacing(15) 

        # إضافة العناصر مع فرض المحاذاة في المنتصف عمودياً
        info_row.addWidget(self.lbl_stats, alignment=Qt.AlignVCenter)
        info_row.addWidget(btn_clear, alignment=Qt.AlignVCenter)
        info_row.addStretch()
        
        layout.addLayout(info_row)

        # --- الجدول + أزرار التمرير ---
        table_row = QHBoxLayout()

        self.table = QTableWidget()
        cols = ["Code", "Article", "Type", "Poids/Qté", "P.Vente", "Actions"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Stretch)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 170)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(60)
        apply_touch_table_defaults(self.table)
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.table.setStyleSheet("""
            QTableWidget { font-size: 15px; background-color: white; border: none; }
            QHeaderView::section { font-weight: bold; background-color: #ecf0f1;
                padding: 10px; border-bottom: 2px solid #bdc3c7;
                color: #2c3e50; font-size: 14px; }
        """)

        # أزرار التمرير
        scroll_col = QVBoxLayout()
        scroll_col.setSpacing(10)

        btn_up = QPushButton()
        btn_up.setIcon(qta.icon("fa5s.chevron-up", color="white"))
        btn_up.setFixedSize(60, 80)
        btn_up.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(btn_up)
        btn_up.setStyleSheet("background-color: #34495e; border-radius: 8px;")
        btn_up.clicked.connect(lambda: self._scroll(-1))

        btn_down = QPushButton()
        btn_down.setIcon(qta.icon("fa5s.chevron-down", color="white"))
        btn_down.setFixedSize(60, 80)
        btn_down.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(btn_down)
        btn_down.setStyleSheet("background-color: #34495e; border-radius: 8px;")
        btn_down.clicked.connect(lambda: self._scroll(1))

        scroll_col.addWidget(btn_up)
        scroll_col.addStretch()
        scroll_col.addWidget(btn_down)

        table_row.addWidget(self.table)
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
            
        # This creates the confirmation dialog
        reply = QMessageBox.question(
            self, "Confirmation",
            "Are you sure you want to clear the display for this session?\n\n"
            "(This does not delete the items from the database.)",
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
            self.table.setItem(row, 0, self._cell(str(item.get("barcode") or "-"), bold=True))

            name_cell = QTableWidgetItem(str(item.get("name") or ""))
            name_cell.setData(Qt.UserRole, item)
            self.table.setItem(row, 1, name_cell)

            i_type = item.get("item_type", "WEIGHT")
            self.table.setItem(row, 2, QTableWidgetItem("Poids" if i_type == "WEIGHT" else "Pièce"))

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

            price_cell = QTableWidgetItem(f"{float(item.get('selling_price') or 0):,.2f} DA")
            price_cell.setForeground(QColor("#27ae60"))
            price_cell.setFont(QFont("", 12, QFont.Bold))
            price_cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 4, price_cell)

            self.table.setCellWidget(row, 5, self._action_buttons(item))

        self.lbl_stats.setText(
            f"⚖️ Poids Total : {total_weight:.2f} g  |  📦 Total Articles : {total_qty}"
        )

    def _cell(self, text: str, bold: bool = False) -> QTableWidgetItem:
        cell = QTableWidgetItem(text)
        if bold:
            cell.setFont(QFont("", 11, QFont.Bold))
        return cell

    def _action_buttons(self, item: dict) -> QWidget:
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(8)

        def btn(icon_name, color, bg):
            b = QPushButton()
            b.setIcon(qta.icon(icon_name, color=color))
            b.setFixedSize(48, 48)
            apply_touch_button_defaults(b)
            b.setStyleSheet(f"background-color: {bg}; border-radius: 6px;")
            return b

        b_print = btn("fa5s.print",  "#34495e", "#ecf0f1")
        b_edit  = btn("fa5s.edit",   "#f39c12", "#fdf2e9")
        b_del   = btn("fa5s.trash",  "#c0392b", "#fadbd8")

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
            QMessageBox.warning(self, "Erreur", "Aucune imprimante sélectionnée.")
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
            f"Voulez-vous vraiment supprimer '{item['name']}' ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes and self.manager.inventory.delete_item(item["id"]):
            self.remove_item(item["id"])
            self.item_deleted.emit(item)

