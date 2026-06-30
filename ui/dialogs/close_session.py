# ui/dialogs/close_session_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QHBoxLayout,
    QMessageBox, QDoubleSpinBox, QLabel, QAbstractSpinBox,
    QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import qtawesome as qta

# 🟢 استدعاء لوحة المفاتيح الافتراضية
from ui.tools.virtual_keyboard import VirtualKeyboardDialog
from ui.tools.virtual_numpad import VirtualNumpad
from ui.touch_design import (
    TOUCH_BUTTON_HEIGHT,
    TOUCH_INPUT_HEIGHT,
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)
from ui.dialog_theme import apply_dialog_theme
from ui.widgets.finance.finance_touch_helpers import (
    build_close_session_summary,
    confirm_finance_summary,
)

CLOSE_SESSION_TABLE_ROW_HEIGHT = max(TOUCH_BUTTON_HEIGHT, TOUCH_INPUT_HEIGHT) + 14


class CloseSessionDialog(QDialog):
    def __init__(self, manager, session_id, current_user_role, parent=None):
        super().__init__(parent)
        self.setObjectName("closeSessionDialog")
        self.setWindowTitle("Cloture de Session (Remise de Caisse)")

        self.manager = manager
        self.session_id = session_id
        self.current_user_role = current_user_role
        self.vkb = None # متغير لحفظ نسخة الكيبورد

        # 🟢 جعل الحجم متجاوباً مع الشاشات الصغيرة (لا يتجاوز 50% من الارتفاع)
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(700, int(screen.width() * 0.95))
        h = max(360, min(600, int(screen.height() * 0.58)))
        self.resize(w, h)
        self.setMaximumHeight(h)

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

        self.count_spinboxes = {}
        self.count_numpad_buttons = []
        self.btn_numpad = None
        self.init_ui()
        apply_dialog_theme(self, parent=parent, object_name=self.objectName(), extra_stylesheet=self._dialog_stylesheet())

    # 🟢 إجبار النافذة على التموضع في أعلى الشاشة تماماً
    def showEvent(self, event):
        super().showEvent(event)
        self._fit_to_screen_top()

    def _fit_to_screen_top(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        screen_geom = screen.availableGeometry()
        x = screen_geom.x() + max(0, (screen_geom.width() - self.width()) // 2)
        y = screen_geom.y() + 8
        self.move(x, y)

    def _dialog_stylesheet(self):
        return """
        QDialog#closeSessionDialog QLabel#closeSessionTitle {
            font-size: 18px;
            font-weight: 800;
            color: #c0392b;
            margin-bottom: 4px;
        }
        QDialog#closeSessionDialog QTableWidget {
            font-size: 15px;
        }
        QDialog#closeSessionDialog QHeaderView::section {
            min-height: 38px;
            padding: 6px;
            border-bottom: 1px solid #cbd5df;
        }
        QDialog#closeSessionDialog QLineEdit#closeSessionNotes {
            font-size: 14px;
            padding: 5px 8px;
        }
        QDialog#closeSessionDialog QDoubleSpinBox#closeSessionCountSpin {
            font-weight: 800;
            font-size: 16px;
            margin: 2px;
        }
        QDialog#closeSessionDialog QPushButton#btn_close_session_count_numpad {
            min-width: 54px;
            max-width: 54px;
            padding: 0;
            background: #34495e;
            color: #ffffff;
            border-color: #34495e;
        }
        QDialog#closeSessionDialog QPushButton#btn_close_session_count_numpad:hover,
        QDialog#closeSessionDialog QPushButton#btn_close_session_keyboard:hover {
            background: #2c3e50;
            border-color: #2c3e50;
        }
        QDialog#closeSessionDialog QPushButton#btn_close_session_keyboard {
            background: #34495e;
            color: #ffffff;
            border-color: #34495e;
        }
        QDialog#closeSessionDialog QPushButton#btn_close_session_confirm {
            background: #27ae60;
            color: #ffffff;
            border-color: #27ae60;
        }
        QDialog#closeSessionDialog QPushButton#btn_close_session_confirm[warning="true"] {
            background: #e67e22;
            color: #ffffff;
            border-color: #e67e22;
        }
        """

    # 🟢 دوال التحكم في الكيبورد
    def show_virtual_keyboard(self):
        if not self.vkb:
            self.vkb = VirtualKeyboardDialog(self)
        self.vkb.show()
        self.vkb.raise_()

    def close_keyboard(self):
        if self.vkb and self.vkb.isVisible():
            self.vkb.close()

    def open_count_numpad(self, target_spin=None, title="Montant compte"):
        spin = target_spin
        if spin is None:
            row = self.table.currentRow()
            if row < 0 and self.table.rowCount() > 0:
                row = 0
                self.table.selectRow(row)
            spin = self.table.cellWidget(row, 2) if row >= 0 else None
        if spin is None:
            QMessageBox.information(
                self,
                "Pave numerique",
                "Selectionnez une ligne de devise, puis touchez le bouton du pave numerique.",
            )
            return
        self.close_keyboard()
        pad = VirtualNumpad(
            title,
            mode="direct",
            target_widget=spin,
            parent=self,
        )
        pad.exec()

    def _make_count_numpad_button(self, spin, currency_code):
        button = QPushButton()
        button.setObjectName("btn_close_session_count_numpad")
        button.setToolTip("Pave numerique")
        button.setAccessibleName(f"Pave numerique {currency_code}")
        button.setIcon(qta.icon("fa5s.calculator", color="white"))
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedWidth(58)
        apply_touch_button_defaults(button)
        button.clicked.connect(
            lambda _checked=False, target=spin, code=currency_code: self.open_count_numpad(
                target,
                f"Montant compte - {code}",
            )
        )
        return button

    def accept(self):
        self.close_keyboard()
        super().accept()

    def reject(self):
        self.close_keyboard()
        super().reject()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Titre ---
        lbl_title = QLabel("Journal de Caisse - Fermeture")
        lbl_title.setObjectName("closeSessionTitle")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        # --- Tableau des Devises ---
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Devise", "Théorique", "Réel (Compté)", "", "Écart"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.resizeSection(3, 64)
        self.table.verticalHeader().setVisible(False)

        # ارتفاع متناسب لتسهيل اللمس دون أخذ مساحة كبيرة جداً
        self.table.setAlternatingRowColors(True)
        apply_touch_table_defaults(self.table)
        self._apply_count_table_row_sizing()

        layout.addWidget(self.table, stretch=1)

        self.load_currencies()

        # --- Notes ---
        note_layout = QHBoxLayout()
        note_lbl = QLabel("Note :")

        self.txt_notes = QLineEdit()
        self.txt_notes.setObjectName("closeSessionNotes")
        self.txt_notes.setPlaceholderText("Justification des écarts...")
        self.txt_notes.setFixedHeight(40)

        apply_touch_input_defaults(self.txt_notes)

        note_layout.addWidget(note_lbl)
        note_layout.addWidget(self.txt_notes)
        layout.addLayout(note_layout)

        # --- Boutons de contrôle ---
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setObjectName("btn_close_session_cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setFixedHeight(45)
        self.btn_cancel.clicked.connect(self.reject)
        apply_touch_button_defaults(self.btn_cancel)

        # 🟢 زر فتح الكيبورد
        self.btn_kb = QPushButton("Clavier")
        self.btn_kb.setObjectName("btn_close_session_keyboard")
        self.btn_kb.setIcon(qta.icon("fa5s.keyboard", color="white"))
        self.btn_kb.setCursor(Qt.PointingHandCursor)
        self.btn_kb.setFixedHeight(45)
        self.btn_kb.clicked.connect(self.show_virtual_keyboard)
        apply_touch_button_defaults(self.btn_kb)

        self.btn_confirm = QPushButton("Valider Cloture")
        self.btn_confirm.setObjectName("btn_close_session_confirm")
        self.btn_confirm.setIcon(qta.icon("fa5s.check-circle", color="white"))
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setFixedHeight(45)
        self.btn_confirm.setProperty("warning", False)
        self.btn_confirm.clicked.connect(self.validate_and_accept)
        apply_touch_button_defaults(self.btn_confirm, primary=True)

        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_kb)
        btn_box.addWidget(self.btn_confirm, stretch=1)
        layout.addLayout(btn_box)

    def load_currencies(self):
        self.table.setRowCount(len(self.currencies))
        self.count_spinboxes.clear()
        self.count_numpad_buttons.clear()
        for i, curr in enumerate(self.currencies):
            c_id = curr['id']
            expected = self.expected_totals.get(c_id, 0.0)
            currency_code = str(curr.get('code') or "")

            # 1. Devise (Code)
            item_code = QTableWidgetItem(f"{currency_code}")
            item_code.setTextAlignment(Qt.AlignCenter)
            item_code.setFlags(Qt.ItemIsEnabled)
            font = QFont(); font.setBold(True); item_code.setFont(font)
            self.table.setItem(i, 0, item_code)

            # 2. Théorique (Lecture seule)
            item_exp = QTableWidgetItem(f"{expected:,.2f}")
            item_exp.setTextAlignment(Qt.AlignCenter)
            item_exp.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(i, 1, item_exp)

            # 3. Réel (SpinBox)
            spin = QDoubleSpinBox()
            spin.setRange(-1e9, 1e9)
            spin.setDecimals(2)
            spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spin.setValue(expected)
            spin.setAlignment(Qt.AlignCenter)
            spin.setObjectName("closeSessionCountSpin")

            spin.setProperty("expected", expected)
            spin.setProperty("curr_id", c_id)
            apply_touch_input_defaults(spin)
            spin.valueChanged.connect(self.update_diff)
            self.table.setCellWidget(i, 2, spin)
            self.count_spinboxes[c_id] = spin

            btn_numpad = self._make_count_numpad_button(spin, currency_code)
            self.count_numpad_buttons.append(btn_numpad)
            if self.btn_numpad is None:
                self.btn_numpad = btn_numpad
            self.table.setCellWidget(i, 3, btn_numpad)

            # 4. Écart (Label)
            lbl_diff = QLabel("0.00")
            lbl_diff.setObjectName("closeSessionDiff")
            lbl_diff.setAlignment(Qt.AlignCenter)
            lbl_diff.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 15px;")
            self.table.setCellWidget(i, 4, lbl_diff)
            self.table.setRowHeight(i, CLOSE_SESSION_TABLE_ROW_HEIGHT)

    def _apply_count_table_row_sizing(self):
        header = self.table.verticalHeader()
        header.setDefaultSectionSize(CLOSE_SESSION_TABLE_ROW_HEIGHT)
        header.setMinimumSectionSize(CLOSE_SESSION_TABLE_ROW_HEIGHT)

    def update_diff(self):
        has_alert = False
        for i in range(self.table.rowCount()):
            spin = self.table.cellWidget(i, 2)
            expected = spin.property("expected")
            val = spin.value()
            diff = val - expected

            lbl = self.table.cellWidget(i, 4)
            lbl.setText(f"{diff:+,.2f}")

            if abs(diff) > 0.01:
                color = "#c0392b" if diff < 0 else "#2980b9"
                lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 15px;")
                if abs(diff) > 100:
                    has_alert = True
            else:
                lbl.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 15px;")

        if has_alert:
            self.btn_confirm.setText("Cloturer avec Ecart")
            self.btn_confirm.setProperty("warning", True)
        else:
            self.btn_confirm.setText("Valider Cloture")
            self.btn_confirm.setProperty("warning", False)
        self.btn_confirm.style().unpolish(self.btn_confirm)
        self.btn_confirm.style().polish(self.btn_confirm)
        self.btn_confirm.update()

    def validate_and_accept(self):
        has_diff = False
        msg_details = ""

        for i in range(self.table.rowCount()):
            spin = self.table.cellWidget(i, 2)
            expected = spin.property("expected")
            val = spin.value()
            if abs(val - expected) > 10.0:
                curr_code = self.table.item(i, 0).text()
                diff = val - expected
                has_diff = True
                msg_details += f"- {curr_code} : {diff:+,.2f}\n"

        if has_diff:
            # إخفاء الكيبورد قبل ظهور رسالة التحذير لكي لا تغطي عليها
            self.close_keyboard()
            reply = QMessageBox.warning(self, "Confirmer l'écart",
                f"Attention ! Des écarts ont été détectés :\n{msg_details}\n"
                "Ces écarts seront enregistrés sous votre responsabilité.\n"
                "Voulez-vous continuer ?",
                QMessageBox.Yes | QMessageBox.No)

            if reply == QMessageBox.No:
                return

        if not confirm_finance_summary(
            self,
            "Confirmer la cloture",
            build_close_session_summary(self),
        ):
            return

        self.accept()

    def get_data(self):
        counts = {}
        for i in range(self.table.rowCount()):
            spin = self.table.cellWidget(i, 2)
            curr_id = spin.property("curr_id")
            counts[curr_id] = spin.value()

        return counts, self.txt_notes.text()
