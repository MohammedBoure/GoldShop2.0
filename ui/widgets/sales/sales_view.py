# ui/widgets/sales/sales_view.py

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QLabel
)
from ui.deferred_loading import defer_initial_load

class SalesView(QWidget):
    def __init__(self, manager, current_user):
        super().__init__()
        self.manager = manager
        self.current_user = current_user
        self.pos_widget = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        self.loading_widget = QLabel("Chargement du point de vente...")
        self.loading_widget.setStyleSheet("font-size: 18px; color: #7f8c8d;")
        self.loading_widget.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(self.loading_widget)
        
        # تحميل واجهة البيع مباشرة بعد فتح التطبيق
        defer_initial_load(self, self.load_pos_directly, 100)

    def load_pos_directly(self):
        """تحميل واجهة نقطة البيع مباشرة ببيانات وهمية لتجاوز نظام الجلسات"""
        if self.pos_widget is not None:
            self.stack.removeWidget(self.pos_widget)
            self.pos_widget.deleteLater()

        # بيانات وهمية (Dummy Info) لكي لا تنهار واجهة البيع التي تتوقع وجود جلسة
        info = {
            'id': 0, 
            'location_id': 1, 
            'location_name': 'Caisse Principale',
            'user_id': self.current_user.get('id', 0)
        }

        from .POS.pos_interface_widget import POSInterfaceWidget

        self.pos_widget = POSInterfaceWidget(self.manager, info, self.on_close)
        self.stack.addWidget(self.pos_widget)
        self.stack.setCurrentWidget(self.pos_widget)

    def on_close(self, sess_id=None, counts_dict=None, notes=""):
        """بما أنه لا يوجد نظام جلسات، النقر على إغلاق سيقوم بتصفير/إعادة تحميل واجهة البيع فقط"""
        self.load_pos_directly()

    def refresh_data(self):
        if self.pos_widget is not None and self.stack.currentWidget() is self.pos_widget:
            if hasattr(self.pos_widget, 'inp_barcode'):
                self.pos_widget.inp_barcode.setFocus()
            QTimer.singleShot(0, self._refresh_product_search)
        else:
            self.load_pos_directly()

    def _refresh_product_search(self):
        if self.pos_widget is not None and self.stack.currentWidget() is self.pos_widget:
            if hasattr(self.pos_widget, 'load_inventory_cache'):
                self.pos_widget.load_inventory_cache()