# ui/widgets/inventory/_helpers.py
"""
مساعدات مشتركة تُستخدم في تبويبات المخزون.
لا تعتمد على أي كلاس آخر من هذه الحزمة.
"""

import os
import json

from PySide6.QtWidgets import (
    QTableWidgetItem, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt
import qtawesome as qta

from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults
from ui.tools.virtual_keyboard import VirtualKeyboardDialog


class SortableTableWidgetItem(QTableWidgetItem):
    """
    عنصر جدول يدعم الترتيب الرقمي والنصي تلقائياً.
    """

    def __init__(self, text: str, sort_value=None):
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else text

    def __lt__(self, other):
        try:
            if isinstance(self.sort_value, (int, float)) and isinstance(other.sort_value, (int, float)):
                return float(self.sort_value) < float(other.sort_value)
            return str(self.sort_value).lower() < str(other.sort_value).lower()
        except Exception:
            return super().__lt__(other)


class ProductNameSelectionDialog(QDialog):
    """
    نافذة اختيار تسمية المنتج من قائمة مسبقة الإعداد.
    """

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.vkb = None
        self.setWindowTitle("Sélectionner une Désignation")
        self.setMinimumSize(520, 620)
        self.resize(560, 680)
        self.setStyleSheet("QDialog { background-color: #f4f7fa; }")
        self.init_ui()
        self.load_names()

    def show_virtual_keyboard(self):
        if not self.vkb:
            self.vkb = VirtualKeyboardDialog(self)
        self.vkb.show()
        self.vkb.raise_()

    def close_keyboard(self):
        if self.vkb and self.vkb.isVisible():
            self.vkb.close()

    def accept(self):
        self.close_keyboard()
        super().accept()

    def reject(self):
        self.close_keyboard()
        super().reject()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Rechercher une désignation...")
        self.search_bar.setFixedHeight(50)
        apply_touch_input_defaults(self.search_bar)
        self.search_bar.setStyleSheet(
            "font-size: 14px; padding: 5px; border: 2px solid #bdc3c7; border-radius: 8px;"
        )
        self.search_bar.textChanged.connect(self.filter_names)
        layout.addWidget(self.search_bar)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                font-size: 16px; font-weight: bold;
                border: 2px solid #bdc3c7; border-radius: 8px; background-color: white;
            }
            QListWidget::item { padding: 15px; border-bottom: 1px solid #ecf0f1; min-height: 44px; }
            QListWidget::item:selected { background-color: #3498db; color: white; }
            QListWidget::item:hover { background-color: #ecf0f1; color: #2c3e50; }
        """)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()

        btn_cancel = QPushButton(" Annuler")
        btn_cancel.setIcon(qta.icon("fa5s.times", color="#c0392b"))
        btn_cancel.setStyleSheet("padding: 8px; font-weight: bold; font-size: 14px;")
        apply_touch_button_defaults(btn_cancel, danger=True)
        btn_cancel.clicked.connect(self.reject)

        btn_keyboard = QPushButton(" Clavier")
        btn_keyboard.setStyleSheet(
            "background-color: #34495e; color: white; padding: 8px;"
            "font-weight: bold; font-size: 14px;"
        )
        apply_touch_button_defaults(btn_keyboard)
        btn_keyboard.clicked.connect(self.show_virtual_keyboard)

        btn_select = QPushButton(" Sélectionner")
        btn_select.setIcon(qta.icon("fa5s.check", color="white"))
        btn_select.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 8px;"
            "font-weight: bold; font-size: 14px;"
        )
        apply_touch_button_defaults(btn_select, primary=True)
        btn_select.clicked.connect(self.accept)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_keyboard)
        btn_layout.addWidget(btn_select)
        layout.addLayout(btn_layout)

    def load_names(self):
        self.list_widget.clear()
        try:
            names = self.manager.product_names.get_all_product_names()
            for item in names:
                self.list_widget.addItem(QListWidgetItem(item['name']))
        except Exception:
            pass

    def filter_names(self, text: str):
        search = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(search not in item.text().lower())

    def get_selected_name(self):
        current = self.list_widget.currentItem()
        return current.text() if current else None


def load_label_config(parent_widget=None) -> dict | None:
    """
    تقرأ إعدادات الطباعة من config.json.
    تُعيد None وتعرض تحذيراً في حالة الخطأ.
    """
    config_file = "config.json"
    if not os.path.exists(config_file):
        if parent_widget:
            QMessageBox.warning(parent_widget, "Erreur", "Fichier de configuration introuvable.")
        return None
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("label_config", {})
    except Exception as e:
        if parent_widget:
            QMessageBox.warning(parent_widget, "Erreur", f"Erreur de lecture: {e}")
        return None
