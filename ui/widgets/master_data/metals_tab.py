from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QDoubleSpinBox, 
    QFormLayout, QGroupBox, QMessageBox, QComboBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.deferred_loading import defer_initial_load


class MetalsTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # --- TABLE ---
        table_layout = QVBoxLayout()

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#2c3e50"))
        self.btn_refresh.clicked.connect(self.load_data)

        self.btn_delete = QPushButton("Supprimer la sélection")
        self.btn_delete.setIcon(qta.icon("fa5s.trash", color="#e74c3c"))
        self.btn_delete.setProperty("class", "btn_danger")
        self.btn_delete.clicked.connect(self.delete_metal)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)

        table_layout.addLayout(btn_layout)

        # ✅ زيادة عدد الأعمدة إلى 5 لإظهار اسم الفاتورة
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Nom", "Pureté (‰)", "Nom Facture", "Type"])

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self.on_table_click)

        table_layout.addWidget(self.table)

        # --- FORM ---
        form_container = QGroupBox("Détails du Métal")
        form_container.setFixedWidth(350)
        form_layout = QVBoxLayout(form_container)

        form = QFormLayout()
        form.setVerticalSpacing(15)

        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Ex: Or 18k")

        self.inp_purity = QDoubleSpinBox()
        self.inp_purity.setRange(0, 1000)
        self.inp_purity.setDecimals(1)
        self.inp_purity.setValue(750.0)
        self.inp_purity.setSuffix(" ‰")

        self.inp_category = QComboBox()
        self.inp_category.addItem("Or", "GOLD")
        self.inp_category.addItem("Argent", "SILVER")

        # ✅ الحقل الجديد الخاص باسم الفاتورة
        self.inp_invoice_name = QLineEdit()
        self.inp_invoice_name.setPlaceholderText("Nom affiché sur la facture...")

        self.inp_desc = QLineEdit()
        self.inp_desc.setPlaceholderText("Description optionnelle...")

        form.addRow("Nom:", self.inp_name)
        form.addRow("Pureté:", self.inp_purity)
        form.addRow("Type:", self.inp_category)
        form.addRow("Nom Facture:", self.inp_invoice_name) # إضافته للنموذج
        form.addRow("Description:", self.inp_desc)

        form_layout.addLayout(form)

        # Buttons
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.btn_save.setProperty("class", "btn_primary")
        self.btn_save.clicked.connect(self.save_metal)

        self.btn_clear = QPushButton("Nouveau / Annuler")
        self.btn_clear.clicked.connect(self.clear_form)

        self.current_edit_id = None

        form_layout.addSpacing(20)
        form_layout.addWidget(self.btn_save)
        form_layout.addWidget(self.btn_clear)
        form_layout.addStretch()

        layout.addLayout(table_layout, stretch=1)
        layout.addWidget(form_container)

        defer_initial_load(self, self.load_data)

    def load_data(self):
        self.table.setRowCount(0)
        metals = self.manager.metal_types.get_all_metal_types()

        for row_idx, metal in enumerate(metals):
            self.table.insertRow(row_idx)

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(metal['id'])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(metal['name']))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(metal['purity_value'])))
            
            # ✅ جلب وعرض اسم الفاتورة في الجدول
            invoice_name = metal.get('invoice_display_name') or ""
            self.table.setItem(row_idx, 3, QTableWidgetItem(invoice_name))

            category = metal.get("metal_category", "GOLD")
            display = "Or" if category == "GOLD" else "Argent"

            cat_item = QTableWidgetItem(display)
            cat_item.setTextAlignment(Qt.AlignCenter)
            cat_item.setData(Qt.UserRole, metal)

            # ✅ تغيير الفهرس إلى 4 بسبب إضافة عمود الفاتورة قبله
            self.table.setItem(row_idx, 4, cat_item)

    def save_metal(self):
        name = self.inp_name.text().strip()
        purity = self.inp_purity.value()
        category = self.inp_category.currentData()
        invoice_name = self.inp_invoice_name.text().strip() # ✅ جلب قيمة اسم الفاتورة
        desc = self.inp_desc.text().strip()

        if not name:
            QMessageBox.warning(self, "Attention", "Veuillez entrer une désignation.")
            return

        # إذا ترك المستخدم الحقل فارغاً، نرسل None لقاعدة البيانات
        invoice_display_val = invoice_name if invoice_name else None

        try:
            if self.current_edit_id:
                self.manager.metal_types.update_metal_type(
                    self.current_edit_id, name, purity, category, desc, invoice_display_val
                )
            else:
                self.manager.metal_types.add_metal_type(
                    name, purity, category, desc, invoice_display_val
                )

            self.clear_form()
            self.load_data()

        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def delete_metal(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Sélectionnez une ligne.")
            return

        metal_id = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()

        confirm = QMessageBox.question(
            self, "Confirmation",
            f"Supprimer '{name}' ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            if self.manager.metal_types.delete_metal_type(metal_id):
                self.load_data()
                self.clear_form()

    def on_table_click(self):
        row = self.table.currentRow()
        if row < 0:
            return

        # ✅ تغيير الفهرس هنا إلى 4 لسحب البيانات المخفية
        data = self.table.item(row, 4).data(Qt.UserRole)

        if data:
            self.current_edit_id = data['id']
            self.inp_name.setText(data['name'])
            self.inp_purity.setValue(float(data['purity_value']))
            self.inp_desc.setText(data.get('description', ''))
            
            # ✅ تعبئة حقل الفاتورة بالبيانات الموجودة
            self.inp_invoice_name.setText(data.get('invoice_display_name') or "")

            category = data.get("metal_category", "GOLD")
            index = self.inp_category.findData(category)
            if index >= 0:
                self.inp_category.setCurrentIndex(index)

            self.btn_save.setText("Modifier")

    def clear_form(self):
        self.current_edit_id = None
        self.inp_name.clear()
        self.inp_purity.setValue(750.0)
        self.inp_category.setCurrentIndex(0)
        self.inp_invoice_name.clear() # ✅ تفريغ حقل الفاتورة
        self.inp_desc.clear()
        self.btn_save.setText("Enregistrer")

    def refresh_data(self):
        self.load_data()
