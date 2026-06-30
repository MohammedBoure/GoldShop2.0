import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QGroupBox, QDialog,
    QMessageBox, QDoubleSpinBox, QLabel, QGridLayout, QDateEdit, QFormLayout
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QBrush
import qtawesome as qta


# ──────────────────────────────────────────────────────────
# 1. نافذة تعديل سطر محدد (Edit Dialog)
# ──────────────────────────────────────────────────────────
class EditAchatOCDialog(QDialog):
    def __init__(self, record_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modifier l'achat OC")
        self.setFixedSize(450, 350)
        self.record_data = record_data
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        s = "font-size: 16px; padding: 5px; font-weight: bold;"
        
        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        # تحويل التاريخ القادم من قاعدة البيانات إلى QDate
        try:
            date_obj = QDate.fromString(str(self.record_data.get('date_achat', '')), "yyyy-MM-dd")
            if date_obj.isValid():
                self.inp_date.setDate(date_obj)
            else:
                self.inp_date.setDate(QDate.currentDate())
        except Exception:
            self.inp_date.setDate(QDate.currentDate())
            
        self.inp_date.setStyleSheet(s)
        
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0, 999999)
        self.spin_weight.setDecimals(3)
        self.spin_weight.setSuffix(" g")
        self.spin_weight.setValue(float(self.record_data.get('weight_g', 0)))
        self.spin_weight.setStyleSheet(s)
        
        self.spin_unit_price = QDoubleSpinBox()
        self.spin_unit_price.setRange(0, 99999999)
        self.spin_unit_price.setSuffix(" DA")
        self.spin_unit_price.setValue(float(self.record_data.get('unit_price_da', 0)))
        self.spin_unit_price.setStyleSheet(s)
        
        self.spin_total = QDoubleSpinBox()
        self.spin_total.setRange(0, 999999999)
        self.spin_total.setSuffix(" DA")
        self.spin_total.setValue(float(self.record_data.get('total_amount_da', 0)))
        self.spin_total.setStyleSheet(s)
        
        self.inp_notes = QLineEdit(str(self.record_data.get('notes') or ''))
        self.inp_notes.setStyleSheet(s)
        
        # التحديث التلقائي للإجمالي عند تغيير الوزن أو السعر
        self.spin_weight.valueChanged.connect(self._auto_calc)
        self.spin_unit_price.valueChanged.connect(self._auto_calc)
        
        form.addRow("📅 Date :", self.inp_date)
        form.addRow("⚖️ Poids :", self.spin_weight)
        form.addRow("💰 Prix unitaire :", self.spin_unit_price)
        form.addRow("💵 Montant Total :", self.spin_total)
        form.addRow("📝 Observation :", self.inp_notes)
        layout.addLayout(form)
        
        btn_save = QPushButton(" Enregistrer les modifications")
        btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 15px; padding: 10px; border-radius: 5px;")
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

    def _auto_calc(self):
        self.spin_total.setValue(self.spin_weight.value() * self.spin_unit_price.value())

    def get_values(self):
        return {
            "date_achat": self.inp_date.date().toString("yyyy-MM-dd"),
            "weight_g": self.spin_weight.value(),
            "unit_price_da": self.spin_unit_price.value(),
            "total_amount_da": self.spin_total.value(),
            "notes": self.inp_notes.text().strip()
        }


# ──────────────────────────────────────────────────────────
# 2. الواجهة الرئيسية (Main View)
# ──────────────────────────────────────────────────────────
class AchatOCView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # --- القسم العلوي: إدخال البيانات ---
        form_box = QGroupBox("📥 Enregistrement Manuel - Achat Or Cassé (OC)")
        form_box.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 16px; color: #d35400; 
                        border: 2px solid #e67e22; border-radius: 8px; 
                        margin-top: 10px; padding-top: 20px; background-color: white; }
        """)
        grid = QGridLayout(form_box)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(15)

        s_input = "font-size: 16px; font-weight: bold; padding: 8px; border: 2px solid #bdc3c7; border-radius: 6px; background-color: #fdf2e9;"
        
        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setDate(QDate.currentDate())
        self.inp_date.setStyleSheet(s_input)
        
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0, 999999)
        self.spin_weight.setDecimals(3)
        self.spin_weight.setSuffix(" g")
        self.spin_weight.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin_weight.setStyleSheet(s_input)
        
        self.spin_unit_price = QDoubleSpinBox()
        self.spin_unit_price.setRange(0, 99999999)
        self.spin_unit_price.setSuffix(" DA/g")
        self.spin_unit_price.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin_unit_price.setStyleSheet(s_input)
        
        self.spin_total_amount = QDoubleSpinBox()
        self.spin_total_amount.setRange(0, 999999999)
        self.spin_total_amount.setSuffix(" DA")
        self.spin_total_amount.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin_total_amount.setStyleSheet(s_input)
        
        self.inp_notes = QLineEdit()
        self.inp_notes.setPlaceholderText("Ex: Achat chez Passager...")
        self.inp_notes.setStyleSheet(s_input)

        # الحساب التلقائي للإجمالي عند الإدخال
        self.spin_weight.valueChanged.connect(self._recalculate_total)
        self.spin_unit_price.valueChanged.connect(self._recalculate_total)

        # ترتيب الحقول في الشبكة
        def add_field(label, widget, r, c):
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
            grid.addWidget(lbl, r, c)
            grid.addWidget(widget, r+1, c)

        add_field("📅 Date d'Achat:", self.inp_date, 0, 0)
        add_field("⚖️ Poids (g):", self.spin_weight, 0, 1)
        add_field("💰 Prix du gramme (DA):", self.spin_unit_price, 0, 2)
        add_field("💵 Montant Total (DA):", self.spin_total_amount, 2, 0)
        add_field("📝 Observation / Note:", self.inp_notes, 2, 1)

        # أزرار الحفظ والإلغاء
        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton(" Vider")
        self.btn_clear.setIcon(qta.icon("fa5s.eraser", color="#7f8c8d"))
        self.btn_clear.setStyleSheet("background-color: #ecf0f1; font-weight: bold; font-size: 15px; padding: 12px; border-radius: 6px;")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_form)
        
        self.btn_add = QPushButton(" Ajouter au Registre")
        self.btn_add.setIcon(qta.icon("fa5s.plus-circle", color="white"))
        self.btn_add.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; font-size: 15px; padding: 12px; border-radius: 6px;")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.clicked.connect(self.add_record)
        
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_add, stretch=1)
        grid.addLayout(btn_layout, 3, 2)

        layout.addWidget(form_box)

        # --- القسم السفلي: جدول البيانات ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Poids (g)", "Prix Unitaire", "Montant Total", "Observations", "Actions"])
        
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; gridline-color: #bdc3c7; font-size: 15px; }
            QHeaderView::section { background-color: #f5cba7; color: #5e3717; font-weight: bold; font-size: 15px; padding: 10px; border: 1px solid #e59866; }
            QTableWidget::item:selected { background-color: #fedbb6; color: black; }
        """)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(50)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 120)
        
        layout.addWidget(self.table)

    # ──────────────────────────────────────────────────────────
    # الدوال التشغيلية (Methods)
    # ──────────────────────────────────────────────────────────
    def _recalculate_total(self):
        self.spin_total_amount.setValue(self.spin_weight.value() * self.spin_unit_price.value())

    def clear_form(self):
        self.spin_weight.setValue(0)
        self.spin_unit_price.setValue(0)
        self.spin_total_amount.setValue(0)
        self.inp_notes.clear()
        self.inp_date.setDate(QDate.currentDate())
        self.spin_weight.setFocus()

    def add_record(self):
        w = self.spin_weight.value()
        p = self.spin_unit_price.value()
        t = self.spin_total_amount.value()
        dt = self.inp_date.date().toString("yyyy-MM-dd")
        note = self.inp_notes.text().strip()

        if w <= 0 or t <= 0:
            QMessageBox.warning(self, "Erreur", "Le poids et le montant doivent être supérieurs à 0.")
            return

        # 🟢 استخدام المدير الجديد
        result = self.manager.achat_oc.add_record(dt, w, p, t, note)
        
        if result["success"]:
            self.clear_form()
            self.load_data()
        else:
            QMessageBox.critical(self, "Erreur DB", f"Impossible d'enregistrer: {result['message']}")

    def load_data(self):
        self.table.setRowCount(0)
        
        # 🟢 استخدام المدير الجديد لجلب البيانات
        records = self.manager.achat_oc.get_all_records()
                
        total_w = 0.0
        total_m = 0.0

        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            total_w += float(r['weight_g'])
            total_m += float(r['total_amount_da'])

            self.table.setItem(row, 0, self._create_item(str(r['date_achat'])))
            self.table.setItem(row, 1, self._create_item(f"{float(r['weight_g']):.3f} g", bold=True))
            self.table.setItem(row, 2, self._create_item(f"{float(r['unit_price_da']):,.2f} DA"))
            
            total_item = self._create_item(f"{float(r['total_amount_da']):,.2f} DA", bold=True)
            total_item.setForeground(QBrush(QColor("#c0392b")))
            self.table.setItem(row, 3, total_item)
            
            self.table.setItem(row, 4, self._create_item(str(r['notes'] or ''), align_left=True))
            self.table.setCellWidget(row, 5, self._create_action_buttons(r))

        if records:
            tot_row = self.table.rowCount()
            self.table.insertRow(tot_row)
            self.table.setItem(tot_row, 0, self._create_item("TOTAL", bold=True, bg="#f5cba7"))
            self.table.setItem(tot_row, 1, self._create_item(f"{total_w:.3f} g", bold=True, bg="#f5cba7"))
            self.table.setItem(tot_row, 2, self._create_item("", bg="#f5cba7"))
            self.table.setItem(tot_row, 3, self._create_item(f"{total_m:,.2f} DA", bold=True, bg="#f5cba7", color="#c0392b"))
            self.table.setItem(tot_row, 4, self._create_item("", bg="#f5cba7"))
            self.table.setItem(tot_row, 5, self._create_item("", bg="#f5cba7"))

    def _create_item(self, text, bold=False, align_left=False, bg=None, color=None):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if align_left else Qt.AlignCenter)
        if bold:
            item.setFont(QFont("", 12, QFont.Bold))
        if bg:
            item.setBackground(QBrush(QColor(bg)))
        if color:
            item.setForeground(QBrush(QColor(color)))
        return item

    def _create_action_buttons(self, record):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(6)

        btn_edit = QPushButton()
        btn_edit.setIcon(qta.icon("fa5s.edit", color="#f39c12"))
        btn_edit.setFixedSize(38, 38)
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setStyleSheet("background-color: #fdf2e9; border: 1px solid #f39c12; border-radius: 6px;")
        btn_edit.clicked.connect(lambda: self.edit_record(record))

        btn_del = QPushButton()
        btn_del.setIcon(qta.icon("fa5s.trash", color="#c0392b"))
        btn_del.setFixedSize(38, 38)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("background-color: #fadbd8; border: 1px solid #c0392b; border-radius: 6px;")
        btn_del.clicked.connect(lambda: self.delete_record(record['id']))

        lay.addWidget(btn_edit)
        lay.addWidget(btn_del)
        return container

    def edit_record(self, record):
        dlg = EditAchatOCDialog(record, self)
        if dlg.exec() == QDialog.Accepted:
            vals = dlg.get_values()
            
            # 🟢 استخدام المدير الجديد للتعديل
            success = self.manager.achat_oc.update_record(
                record['id'], vals['date_achat'], vals['weight_g'], 
                vals['unit_price_da'], vals['total_amount_da'], vals['notes']
            )
            
            if success:
                self.load_data()
            else:
                QMessageBox.critical(self, "Erreur", "Mise à jour échouée.")

    def delete_record(self, record_id):
        reply = QMessageBox.question(
            self, "Confirmation", 
            "Voulez-vous vraiment supprimer cet enregistrement d'Achat OC ?", 
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # 🟢 استخدام المدير الجديد للحذف
            success = self.manager.achat_oc.delete_record(record_id)
            if success:
                self.load_data()
            else:import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QGroupBox, QDialog,
    QMessageBox, QDoubleSpinBox, QLabel, QGridLayout, QDateEdit, QFormLayout,
    QComboBox, QFrame, QApplication
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QBrush
import qtawesome as qta

# 🟢 استيراد أدوات التحميل المؤجل واللوحات الافتراضية
from ui.deferred_loading import defer_initial_load
from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog


# ──────────────────────────────────────────────────────────
# 1. نافذة تعديل سطر محدد (Edit Dialog) مع دعم اللوحات الافتراضية
# ──────────────────────────────────────────────────────────
class EditAchatOCDialog(QDialog):
    def __init__(self, record_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modifier l'achat OC")
        self.setFixedSize(500, 400)
        self.record_data = record_data
        self.init_ui()

    def _wrap_numpad(self, widget, title, allow_decimal=True):
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        btn = QPushButton("🔢")
        btn.setFixedSize(38, 38)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: VirtualNumpad(title=title, mode="direct", target_widget=widget, allow_decimal=allow_decimal, parent=self).show())
        lay.addWidget(btn)
        w = QWidget()
        w.setLayout(lay)
        return w

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        s = "font-size: 16px; padding: 5px; font-weight: bold;"
        
        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        try:
            date_obj = QDate.fromString(str(self.record_data.get('date_achat', '')), "yyyy-MM-dd")
            self.inp_date.setDate(date_obj if date_obj.isValid() else QDate.currentDate())
        except Exception:
            self.inp_date.setDate(QDate.currentDate())
        self.inp_date.setStyleSheet(s)
        
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0, 999999)
        self.spin_weight.setDecimals(3)
        self.spin_weight.setSuffix(" g")
        self.spin_weight.setValue(float(self.record_data.get('weight_g', 0)))
        self.spin_weight.setStyleSheet(s)
        
        self.spin_unit_price = QDoubleSpinBox()
        self.spin_unit_price.setRange(0, 99999999)
        self.spin_unit_price.setSuffix(" DA")
        self.spin_unit_price.setValue(float(self.record_data.get('unit_price_da', 0)))
        self.spin_unit_price.setStyleSheet(s)
        
        self.spin_total = QDoubleSpinBox()
        self.spin_total.setRange(0, 999999999)
        self.spin_total.setSuffix(" DA")
        self.spin_total.setValue(float(self.record_data.get('total_amount_da', 0)))
        self.spin_total.setStyleSheet(s)
        
        self.inp_notes = QLineEdit(str(self.record_data.get('notes') or ''))
        self.inp_notes.setStyleSheet(s)
        
        # أزرار الكيبورد للملاحظة
        note_lay = QHBoxLayout()
        note_lay.setContentsMargins(0, 0, 0, 0)
        note_lay.addWidget(self.inp_notes)
        btn_kb = QPushButton("⌨️")
        btn_kb.setFixedSize(38, 38)
        btn_kb.clicked.connect(self._show_keyboard)
        note_lay.addWidget(btn_kb)
        note_widget = QWidget()
        note_widget.setLayout(note_lay)
        
        self.spin_weight.valueChanged.connect(self._auto_calc)
        self.spin_unit_price.valueChanged.connect(self._auto_calc)
        
        form.addRow("📅 Date :", self.inp_date)
        form.addRow("⚖️ Poids :", self._wrap_numpad(self.spin_weight, "Poids"))
        form.addRow("💰 Prix unitaire :", self._wrap_numpad(self.spin_unit_price, "Prix unitaire"))
        form.addRow("💵 Montant Total :", self._wrap_numpad(self.spin_total, "Montant Total"))
        form.addRow("📝 Observation :", note_widget)
        
        layout.addLayout(form)
        
        btn_save = QPushButton(" Enregistrer les modifications")
        btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 15px; padding: 10px; border-radius: 5px;")
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

    def _show_keyboard(self):
        if not hasattr(self, '_vkb') or not self._vkb:
            self._vkb = VirtualKeyboardDialog(self.window())
        self._vkb.show()
        self._vkb.raise_()

    def _auto_calc(self):
        self.spin_total.setValue(self.spin_weight.value() * self.spin_unit_price.value())

    def get_values(self):
        return {
            "date_achat": self.inp_date.date().toString("yyyy-MM-dd"),
            "weight_g": self.spin_weight.value(),
            "unit_price_da": self.spin_unit_price.value(),
            "total_amount_da": self.spin_total.value(),
            "notes": self.inp_notes.text().strip()
        }


# ──────────────────────────────────────────────────────────
# 2. الواجهة الرئيسية (Main View)
# ──────────────────────────────────────────────────────────
class AchatOCView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._vkb = None
        self.init_ui()
        
        # 🟢 تفعيل التحميل المؤجل للبيانات (Lazy Loading)
        defer_initial_load(self, self.load_data)

    def _wrap_numpad(self, widget, title, allow_decimal=True):
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        btn = QPushButton("🔢")
        btn.setFixedSize(40, 40)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 6px;")
        btn.clicked.connect(lambda: VirtualNumpad(title=title, mode="direct", target_widget=widget, allow_decimal=allow_decimal, parent=self).show())
        lay.addWidget(btn)
        w = QWidget()
        w.setLayout(lay)
        return w

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # 🟢 --- القسم 1: فلتر السنة والشهر ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dcdde1; border-radius: 8px; padding: 10px;")
        filter_layout = QHBoxLayout(filter_frame)
        
        filter_layout.addWidget(QLabel("<b>📅 Année :</b>"))
        self.combo_year = QComboBox()
        self.combo_year.setStyleSheet("font-size: 14px; padding: 5px;")
        filter_layout.addWidget(self.combo_year)
        
        filter_layout.addSpacing(15)
        filter_layout.addWidget(QLabel("<b>Mois :</b>"))
        self.combo_month = QComboBox()
        self.combo_month.setStyleSheet("font-size: 14px; padding: 5px;")
        filter_layout.addWidget(self.combo_month)
        
        filter_layout.addSpacing(20)
        self.btn_search = QPushButton(" Afficher le Registre")
        self.btn_search.setIcon(qta.icon("fa5s.search", color="white"))
        self.btn_search.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 15px; border-radius: 6px; font-weight: bold;")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.clicked.connect(self.load_data)
        filter_layout.addWidget(self.btn_search)
        filter_layout.addStretch()
        
        layout.addWidget(filter_frame)
        self._populate_filters()

        # 🟢 --- القسم 2: إدخال البيانات ---
        form_box = QGroupBox("📥 Enregistrement Manuel - Achat Or Cassé (OC)")
        form_box.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 16px; color: #d35400; 
                        border: 2px solid #e67e22; border-radius: 8px; 
                        margin-top: 10px; padding-top: 20px; background-color: white; }
        """)
        grid = QGridLayout(form_box)
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(15)

        s_input = "font-size: 16px; font-weight: bold; padding: 8px; border: 2px solid #bdc3c7; border-radius: 6px; background-color: #fdf2e9;"
        
        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setDate(QDate.currentDate())
        self.inp_date.setStyleSheet(s_input)
        
        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setRange(0, 999999)
        self.spin_weight.setDecimals(3)
        self.spin_weight.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin_weight.setStyleSheet(s_input)
        
        self.spin_unit_price = QDoubleSpinBox()
        self.spin_unit_price.setRange(0, 99999999)
        self.spin_unit_price.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin_unit_price.setStyleSheet(s_input)
        
        self.spin_total_amount = QDoubleSpinBox()
        self.spin_total_amount.setRange(0, 999999999)
        self.spin_total_amount.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin_total_amount.setStyleSheet(s_input)
        
        self.inp_notes = QLineEdit()
        self.inp_notes.setPlaceholderText("Observation...")
        self.inp_notes.setStyleSheet(s_input)
        
        note_lay = QHBoxLayout()
        note_lay.setContentsMargins(0, 0, 0, 0)
        note_lay.addWidget(self.inp_notes)
        btn_kb = QPushButton("⌨️")
        btn_kb.setFixedSize(40, 40)
        btn_kb.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 6px;")
        btn_kb.clicked.connect(self._show_keyboard)
        note_lay.addWidget(btn_kb)
        note_widget = QWidget()
        note_widget.setLayout(note_lay)

        self.spin_weight.valueChanged.connect(self._recalculate_total)
        self.spin_unit_price.valueChanged.connect(self._recalculate_total)

        def add_field(label, widget, r, c):
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
            grid.addWidget(lbl, r, c)
            grid.addWidget(widget, r+1, c)

        add_field("📅 Date d'Achat:", self.inp_date, 0, 0)
        add_field("⚖️ Poids (g):", self._wrap_numpad(self.spin_weight, "Poids (g)"), 0, 1)
        add_field("💰 Prix du gramme (DA):", self._wrap_numpad(self.spin_unit_price, "Prix unitaire"), 0, 2)
        add_field("💵 Montant Total (DA):", self._wrap_numpad(self.spin_total_amount, "Montant Total"), 2, 0)
        add_field("📝 Observation / Note:", note_widget, 2, 1)

        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton(" Vider")
        self.btn_clear.setIcon(qta.icon("fa5s.eraser", color="#7f8c8d"))
        self.btn_clear.setStyleSheet("background-color: #ecf0f1; font-weight: bold; font-size: 15px; padding: 12px; border-radius: 6px;")
        self.btn_clear.clicked.connect(self.clear_form)
        
        self.btn_add = QPushButton(" Ajouter au Registre")
        self.btn_add.setIcon(qta.icon("fa5s.plus-circle", color="white"))
        self.btn_add.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; font-size: 15px; padding: 12px; border-radius: 6px;")
        self.btn_add.clicked.connect(self.add_record)
        
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_add, stretch=1)
        grid.addLayout(btn_layout, 3, 2)

        layout.addWidget(form_box)

        # 🟢 --- القسم 3: جدول البيانات ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Poids (g)", "Prix Unitaire", "Montant Total", "Observations", "Actions"])
        
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; gridline-color: #bdc3c7; font-size: 15px; }
            QHeaderView::section { background-color: #f5cba7; color: #5e3717; font-weight: bold; font-size: 15px; padding: 10px; border: 1px solid #e59866; }
            QTableWidget::item:selected { background-color: #fedbb6; color: black; }
        """)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(50)
        
        header = self.table.horizontalHeader()
        for i in range(4): header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 120)
        
        layout.addWidget(self.table)

    # ──────────────────────────────────────────────────────────
    # الدوال التشغيلية
    # ──────────────────────────────────────────────────────────
    def _populate_filters(self):
        current_date = datetime.datetime.now()
        for y in range(current_date.year - 2, current_date.year + 4):
            self.combo_year.addItem(str(y), y)
        self.combo_year.setCurrentText(str(current_date.year))
        
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        for i, m in enumerate(months, 1): 
            self.combo_month.addItem(m, i)
        self.combo_month.setCurrentIndex(current_date.month - 1)

    def _show_keyboard(self):
        if not self._vkb:
            self._vkb = VirtualKeyboardDialog(self.window())
        self._vkb.show()
        self._vkb.raise_()

    def _recalculate_total(self):
        self.spin_total_amount.setValue(self.spin_weight.value() * self.spin_unit_price.value())

    def clear_form(self):
        self.spin_weight.setValue(0)
        self.spin_unit_price.setValue(0)
        self.spin_total_amount.setValue(0)
        self.inp_notes.clear()
        self.inp_date.setDate(QDate.currentDate())
        self.spin_weight.setFocus()

    def add_record(self):
        w = self.spin_weight.value()
        p = self.spin_unit_price.value()
        t = self.spin_total_amount.value()
        dt = self.inp_date.date().toString("yyyy-MM-dd")
        note = self.inp_notes.text().strip()

        if w <= 0 or t <= 0:
            QMessageBox.warning(self, "Erreur", "Le poids et le montant doivent être supérieurs à 0.")
            return

        result = self.manager.achat_oc.add_record(dt, w, p, t, note)
        if result.get("success"):
            self.clear_form()
            self.load_data()
        else:
            QMessageBox.critical(self, "Erreur DB", f"Impossible d'enregistrer: {result.get('message')}")

    def load_data(self):
        self.table.setRowCount(0)
        year = self.combo_year.currentData()
        month = self.combo_month.currentData()
        
        # الاعتماد على الدالة الجديدة في المدير
        records = self.manager.achat_oc.get_records_by_month(year, month)
                
        total_w = 0.0
        total_m = 0.0

        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            total_w += float(r['weight_g'])
            total_m += float(r['total_amount_da'])

            self.table.setItem(row, 0, self._create_item(str(r['date_achat'])))
            self.table.setItem(row, 1, self._create_item(f"{float(r['weight_g']):.3f} g", bold=True))
            self.table.setItem(row, 2, self._create_item(f"{float(r['unit_price_da']):,.2f} DA"))
            
            total_item = self._create_item(f"{float(r['total_amount_da']):,.2f} DA", bold=True)
            total_item.setForeground(QBrush(QColor("#c0392b"))) 
            self.table.setItem(row, 3, total_item)
            
            self.table.setItem(row, 4, self._create_item(str(r['notes'] or ''), align_left=True))
            self.table.setCellWidget(row, 5, self._create_action_buttons(r))

        if records:
            tot_row = self.table.rowCount()
            self.table.insertRow(tot_row)
            
            self.table.setItem(tot_row, 0, self._create_item("TOTAL", bold=True, bg="#f5cba7"))
            self.table.setItem(tot_row, 1, self._create_item(f"{total_w:.3f} g", bold=True, bg="#f5cba7"))
            self.table.setItem(tot_row, 2, self._create_item("", bg="#f5cba7"))
            self.table.setItem(tot_row, 3, self._create_item(f"{total_m:,.2f} DA", bold=True, bg="#f5cba7", color="#c0392b"))
            self.table.setItem(tot_row, 4, self._create_item("", bg="#f5cba7"))
            self.table.setItem(tot_row, 5, self._create_item("", bg="#f5cba7"))

    def _create_item(self, text, bold=False, align_left=False, bg=None, color=None):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter if align_left else Qt.AlignCenter)
        if bold:
            item.setFont(QFont("", 12, QFont.Bold))
        if bg:
            item.setBackground(QBrush(QColor(bg)))
        if color:
            item.setForeground(QBrush(QColor(color)))
        return item

    def _create_action_buttons(self, record):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(6)

        btn_edit = QPushButton()
        btn_edit.setIcon(qta.icon("fa5s.edit", color="#f39c12"))
        btn_edit.setFixedSize(38, 38)
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setStyleSheet("background-color: #fdf2e9; border: 1px solid #f39c12; border-radius: 6px;")
        btn_edit.clicked.connect(lambda: self.edit_record(record))

        btn_del = QPushButton()
        btn_del.setIcon(qta.icon("fa5s.trash", color="#c0392b"))
        btn_del.setFixedSize(38, 38)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("background-color: #fadbd8; border: 1px solid #c0392b; border-radius: 6px;")
        btn_del.clicked.connect(lambda: self.delete_record(record['id']))

        lay.addWidget(btn_edit)
        lay.addWidget(btn_del)
        return container

    def edit_record(self, record):
        dlg = EditAchatOCDialog(record, self)
        if dlg.exec() == QDialog.Accepted:
            vals = dlg.get_values()
            success = self.manager.achat_oc.update_record(
                record['id'], vals['date_achat'], vals['weight_g'], 
                vals['unit_price_da'], vals['total_amount_da'], vals['notes']
            )
            if success:
                self.load_data()
            else:
                QMessageBox.critical(self, "Erreur", "Mise à jour échouée.")

    def delete_record(self, record_id):
        reply = QMessageBox.question(
            self, "Confirmation", 
            "Voulez-vous vraiment supprimer cet enregistrement d'Achat OC ?", 
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.manager.achat_oc.delete_record(record_id)
            if success:
                self.load_data()
            else:
                QMessageBox.critical(self, "Erreur", "Suppression échouée.")
                QMessageBox.critical(self, "Erreur", "Suppression échouée.")