

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QDialog,
    QApplication, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
import qtawesome as qta

from ui.tools.virtual_keyboard import VirtualKeyboardDialog

class ProductNameSelectionDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.vkb = None

        self.setWindowTitle("Sélectionner une Désignation")
        self.setFixedSize(450, 550)
        self.setStyleSheet("QDialog { background-color: #f4f7fa; }")
        self.init_ui()
        self.load_names()

    # 🟢 إجبار النافذة على التموضع في أعلى الشاشة تماماً
    def showEvent(self, event):
        super().showEvent(event)
        screen_geom = QApplication.primaryScreen().availableGeometry()
        x = (screen_geom.width() - self.width()) // 2
        y = 0  # الحافة العلوية تماماً
        self.move(x, y)

    # 🟢 دوال التحكم في الكيبورد الافتراضي
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
        layout.setSpacing(10)

        # --- شريط البحث ---
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Rechercher une désignation...")
        self.search_bar.setFixedHeight(50) # 🟢 تكبير الحقل ليناسب اللمس
        self.search_bar.setStyleSheet("""
            font-size: 16px; font-weight: bold; padding: 5px 15px;
            border: 2px solid #bdc3c7; border-radius: 8px; background-color: white;
        """)
        self.search_bar.textChanged.connect(self.filter_names)
        layout.addWidget(self.search_bar)

        # --- قائمة الأسماء ---
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                font-size: 18px; font-weight: bold; border: 2px solid #bdc3c7;
                border-radius: 8px; background-color: white;
            }
            QListWidget::item {
                padding: 15px; border-bottom: 1px solid #ecf0f1; /* 🟢 مساحة نصوص أكبر للمس */
            }
            QListWidget::item:selected { background-color: #3498db; color: white; }
            QListWidget::item:hover { background-color: #ecf0f1; color: #2c3e50; }
        """)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list_widget)

        # --- أزرار التحكم ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton(" Annuler")
        btn_cancel.setIcon(qta.icon("fa5s.times", color="#c0392b"))
        btn_cancel.setFixedHeight(50)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("background-color: #ecf0f1; color: #2c3e50; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_cancel.clicked.connect(self.reject)

        # 🟢 زر فتح الكيبورد
        btn_kb = QPushButton(" ⌨️ Clavier")
        btn_kb.setFixedHeight(50)
        btn_kb.setCursor(Qt.PointingHandCursor)
        btn_kb.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_kb.clicked.connect(self.show_virtual_keyboard)

        btn_select = QPushButton(" Sélectionner")
        btn_select.setIcon(qta.icon("fa5s.check", color="white"))
        btn_select.setFixedHeight(50)
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_select.clicked.connect(self.accept)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_kb) # 🟢 وضع الزر في المنتصف
        btn_layout.addWidget(btn_select)

        layout.addLayout(btn_layout)

    def load_names(self):
        self.list_widget.clear()
        try:
            names = self.manager.product_names.get_all_product_names()
            for item in names:
                list_item = QListWidgetItem(item['name'])
                self.list_widget.addItem(list_item)
        except Exception as e:
            pass

    def filter_names(self, text):
        search_text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(search_text not in item.text().lower())

    def get_selected_name(self):
        current_item = self.list_widget.currentItem()
        if current_item:
            return current_item.text()
        return None
