# ui/dialogs/audit_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QLabel, QMessageBox, QDoubleSpinBox,
    QFrame, QAbstractSpinBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
import qtawesome as qta

# 🟢 استدعاء لوحة المفاتيح الافتراضية
from ui.tools.virtual_keyboard import VirtualKeyboardDialog

class AuditDialog(QDialog):
    """
    Fenêtre d'Audit (Multi-Devises).
    Affiche toutes les devises avec leurs soldes théoriques et permet la saisie du comptage réel.
    """
    def __init__(self, manager, session_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audit de Caisse (Multi-Devises)")

        self.manager = manager
        self.session_id = session_id
        self.vkb = None # 🟢 متغير لحفظ نسخة الكيبورد

        # 🟢 جعل الحجم متجاوباً مع الشاشات الصغيرة (لا يتجاوز 50% من الارتفاع)
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(650, int(screen.width() * 0.95))
        h = min(500, int(screen.height() * 0.50))
        self.resize(w, h)

        self.setStyleSheet("QDialog { background-color: #f8f9fa; }")

        # استخراج رقم الصندوق (Location ID) من الواجهة الأم (POS)
        self.location_id = 1
        if hasattr(parent, 'session_info'):
            self.location_id = parent.session_info.get('location_id', 1)

        self.currencies = self.manager.currencies.get_all_currencies()

        # جلب الرصيد الفعلي للصندوق من قسم المالية لكل عملة
        self.expected_totals = {}
        for c in self.currencies:
            try:
                bal = self.manager.cash_box.get_balance(location_id=self.location_id, currency_id=c['id'])
                self.expected_totals[c['id']] = float(bal)
            except:
                self.expected_totals[c['id']] = 0.0

        self.init_ui()
        self.load_data()

    # 🟢 إجبار النافذة على التموضع في أعلى الشاشة تماماً
    def showEvent(self, event):
        super().showEvent(event)
        screen_geom = QApplication.primaryScreen().availableGeometry()
        x = (screen_geom.width() - self.width()) // 2
        y = 0  # الحافة العلوية
        self.move(x, y)

    # 🟢 دوال التحكم في الكيبورد
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
        layout.setSpacing(15)

        # --- العنوان ---
        lbl_icon = QLabel()
        lbl_icon.setPixmap(qta.icon("fa5s.clipboard-list", color="#e67e22").pixmap(40, 40))
        lbl_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_icon)

        lbl_title = QLabel("Vérification Instantanée (Spot Check)")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #d35400;")
        layout.addWidget(lbl_title)

        # --- جدول العملات ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Devise", "Théorique (Finance)", "Réel (Physique)", "Écart"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)

        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setAlternatingRowColors(True)

        self.table.setStyleSheet("""
            QTableWidget { border: 1px solid #ccc; font-size: 14px; background-color: white; border-radius: 5px; }
            QHeaderView::section { background-color: #ecf0f1; font-weight: bold; padding: 8px; border-bottom: 2px solid #e67e22; color: #2c3e50; }
            QTableWidget::item { padding: 5px; }
        """)
        layout.addWidget(self.table)

        # --- حقل الملاحظات ---
        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Notes / Justification (Optionnel)...")
        self.txt_notes.setFixedHeight(40)
        self.txt_notes.setStyleSheet("border: 1px solid #bdc3c7; border-radius: 4px; padding: 5px; background-color: white; font-size: 14px;")

        note_layout = QVBoxLayout()
        note_lbl = QLabel("Note:")
        note_lbl.setStyleSheet("font-weight: bold; color: #2c3e50;")
        note_layout.addWidget(note_lbl)
        note_layout.addWidget(self.txt_notes)
        layout.addLayout(note_layout)

        # --- الأزرار ---
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(45)
        btn_cancel.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 14px;")
        btn_cancel.clicked.connect(self.reject)

        # 🟢 زر فتح الكيبورد
        btn_kb = QPushButton("⌨️ Clavier")
        btn_kb.setCursor(Qt.PointingHandCursor)
        btn_kb.setFixedHeight(45)
        btn_kb.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 14px;")
        btn_kb.clicked.connect(self.show_virtual_keyboard)

        btn_save = QPushButton(" Enregistrer l'Audit")
        btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(45)
        btn_save.setStyleSheet("""
            QPushButton { background-color: #e67e22; color: white; font-weight: bold; padding: 10px; border-radius: 5px; font-size: 14px; }
            QPushButton:hover { background-color: #d35400; }
        """)
        btn_save.clicked.connect(self.save_audit)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_kb)
        btn_box.addWidget(btn_save, stretch=1)
        layout.addLayout(btn_box)

    def load_data(self):
        self.table.setRowCount(len(self.currencies))

        for i, curr in enumerate(self.currencies):
            curr_id = curr['id']
            symbol = curr['symbol']

            # 1. اسم العملة
            item_name = QTableWidgetItem(f"{curr['code']} ({symbol})")
            item_name.setFlags(Qt.ItemIsEnabled)
            font = QFont(); font.setBold(True); item_name.setFont(font)
            item_name.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, item_name)

            # 2. الرصيد المتوقع (من النظام المالي المباشر)
            expected_val = self.expected_totals.get(curr_id, 0.0)
            item_expected = QTableWidgetItem(f"{expected_val:,.2f}")
            item_expected.setTextAlignment(Qt.AlignCenter)
            item_expected.setFlags(Qt.ItemIsEnabled)
            item_expected.setBackground(QColor("#f8f9fa"))
            self.table.setItem(i, 1, item_expected)

            # 3. الرصيد الفعلي
            spin = QDoubleSpinBox()
            spin.setRange(-100000000, 100000000)
            spin.setDecimals(2)
            spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spin.setValue(expected_val)
            spin.setAlignment(Qt.AlignCenter)

            spin.setStyleSheet("""
                QDoubleSpinBox {
                    font-weight: bold;
                    font-size: 15px;
                    color: #2980b9;
                    background-color: #ffffff;
                    border: 2px solid #bdc3c7;
                    border-radius: 6px;
                    margin: 4px;
                }
                QDoubleSpinBox:focus {
                    border: 2px solid #e67e22;
                    background-color: #fdf5e6;
                }
            """)

            spin.setProperty("row", i)
            spin.setProperty("curr_id", curr_id)
            spin.setProperty("expected", expected_val)
            spin.valueChanged.connect(self.update_diff)

            self.table.setCellWidget(i, 2, spin)

            # 4. الفرق (Label)
            lbl_diff = QLabel("0.00")
            lbl_diff.setAlignment(Qt.AlignCenter)
            lbl_diff.setStyleSheet("font-weight: bold; font-size: 15px;")
            self.table.setCellWidget(i, 3, lbl_diff)

            self.update_row_diff(i, expected_val, expected_val)

    def update_diff(self):
        sender = self.sender()
        if not sender: return

        row = sender.property("row")
        expected = sender.property("expected")
        counted = sender.value()

        self.update_row_diff(row, expected, counted)

    def update_row_diff(self, row, expected, counted):
        diff = counted - expected
        lbl_diff = self.table.cellWidget(row, 3)

        lbl_diff.setText(f"{diff:+,.2f}")

        if diff < -0.01:
            lbl_diff.setStyleSheet("color: #c0392b; font-weight: bold; font-size: 15px;") # عجز (أحمر)
        elif diff > 0.01:
            lbl_diff.setStyleSheet("color: #2980b9; font-weight: bold; font-size: 15px;") # فائض (أزرق)
        else:
            lbl_diff.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 15px;") # مطابق (أخضر)

    def save_audit(self):
        counts = {}
        has_major_diff = False

        for i in range(self.table.rowCount()):
            spin = self.table.cellWidget(i, 2)
            curr_id = spin.property("curr_id")
            val = spin.value()
            expected = spin.property("expected")

            counts[curr_id] = val

            if abs(val - expected) > 10.0:
                has_major_diff = True

        notes = self.txt_notes.text().strip()
        if not notes:
            notes = "Audit rapide (Spot Check)"

        if has_major_diff:
            # 🟢 إخفاء الكيبورد قبل إظهار رسالة التحذير حتى لا يغطي عليها
            self.close_keyboard()

            reply = QMessageBox.warning(self, "Écarts détectés",
                "Il y a des écarts importants entre le système et le comptage physique.\n"
                "Voulez-vous vraiment enregistrer cet audit ?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return

        auditor_id = getattr(self.parent(), 'current_user_id', None)
        if not auditor_id and hasattr(self.manager, 'current_user'):
             auditor_id = self.manager.current_user.get('id')

        if not auditor_id: auditor_id = 1

        success = self.manager.sessions.perform_multi_currency_audit(
            self.session_id,
            auditor_id,
            counts,
            notes
        )

        if success:
            self.accept()
        else:
            QMessageBox.critical(self, "Erreur", "Erreur lors de l'enregistrement de l'audit.")