# ui/widgets/inventory/Product_edit.py

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QDialog, QMessageBox, QComboBox, QDoubleSpinBox, QLabel, QSpinBox,
    QScrollArea, QApplication, QGridLayout, QAbstractSpinBox
)
from PySide6.QtCore import Qt
import qtawesome as qta

from ui.tools.virtual_keyboard import VirtualKeyboardDialog

# استيراد نوافذ الاختيار
try:
    from ui.dialogs.product_name_selection import ProductNameSelectionDialog
except ImportError:
    pass
try:
    from ui.dialogs.category_selection import CategorySelectionDialog
except ImportError:
    pass
try:
    from ui.dialogs.supplier_selection import SupplierSelectionDialog
except ImportError:
    pass
try:
    from ui.dialogs.client_selection_dialog import ClientSelectionDialog
except ImportError:
    pass

class ProductEditDialog(QDialog):
    def __init__(self, manager, item_data, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.item_data = item_data
        self.current_edit_id = item_data.get('id')
        self.vkb = None

        self.selected_item_name = ""
        self.selected_category_id = None
        self.selected_supplier_id = None
        self.selected_client_id = None

        self.setWindowTitle(f"📝 Modifier Produit: {item_data.get('name', '')}")

        # 🟢 العرض عريض والارتفاع مدروس لترك مساحة للكيبورد
        self.setFixedSize(1100, 600)
        self.setStyleSheet("QDialog { background-color: #f4f7fa; }")

        self.init_ui()
        self.load_combos()
        self.populate_data()

    def showEvent(self, event):
        super().showEvent(event)
        screen_geom = QApplication.primaryScreen().availableGeometry()
        x = (screen_geom.width() - self.width()) // 2
        y = 0 # 🟢 دفع النافذة لأعلى الشاشة تماماً
        self.move(x, y)

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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(10)

        header_lbl = QLabel(f"✏️ Modification: {self.item_data.get('barcode', '')}")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        header_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header_lbl)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        grid.setVerticalSpacing(8) # 🟢 تقليل الفراغ العمودي بين الأسطر
        grid.setHorizontalSpacing(15)

        # 🟢 ستايل مدمج للحقول مع ارتفاع مناسب لللمس (38px)
        scroll_content.setStyleSheet("""
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                font-size: 15px; font-weight: bold; padding: 2px 8px;
                border: 2px solid #bdc3c7; border-radius: 6px; background-color: #f9f9f9;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
                border: 2px solid #3498db; background-color: white;
            }
        """)

        display_style = "font-size: 14px; font-weight: bold; padding: 2px 8px; border: 2px solid #bdc3c7; border-radius: 6px; background-color: #ecf0f1; color: #2c3e50;"
        button_select_style = "QPushButton { background-color: #34495e; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; } QPushButton:pressed { background-color: #2c3e50; }"
        widget_height = 38 # 🟢 ارتفاع مدروس لتقليل المساحة الكلية مع بقائه سهل اللمس

        # 🟢 دالة لإنشاء تخطيط أفقي (Label بجانب Input) بدلاً من عمودي
        def create_hbox(label_text, widget):
            hlay = QHBoxLayout()
            hlay.setContentsMargins(0, 0, 0, 0)
            hlay.setSpacing(5)

            lbl = QLabel(label_text)
            lbl.setFixedWidth(110) # 🟢 عرض ثابت للعناوين لتكون جميع الحقول متساوية
            lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #34495e;")
            lbl.setWordWrap(True)

            hlay.addWidget(lbl)
            hlay.addWidget(widget, 1)

            container = QWidget()
            container.setLayout(hlay)
            return container

        # --- 1. Code-barres ---
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setFixedHeight(widget_height)

        # --- 2. Désignation ---
        self.inp_name_display = QLineEdit(); self.inp_name_display.setReadOnly(True)
        self.inp_name_display.setFixedHeight(widget_height); self.inp_name_display.setStyleSheet(display_style)
        self.btn_select_name = QPushButton(" Choisir"); self.btn_select_name.setIcon(qta.icon("fa5s.search", color="white"))
        self.btn_select_name.setFixedSize(90, widget_height); self.btn_select_name.setStyleSheet(button_select_style)
        self.btn_select_name.clicked.connect(self.open_name_selector)
        name_lay = QHBoxLayout(); name_lay.setContentsMargins(0,0,0,0); name_lay.addWidget(self.inp_name_display); name_lay.addWidget(self.btn_select_name)
        name_widget = QWidget(); name_widget.setLayout(name_lay)

        # --- 3. Type ---
        self.combo_item_type = QComboBox()
        self.combo_item_type.setFixedHeight(widget_height)
        self.combo_item_type.addItem("Au Poids (Or/Argent)", "WEIGHT")
        self.combo_item_type.addItem("À la Pièce", "PIECE")
        self.combo_item_type.currentIndexChanged.connect(self.toggle_type_fields)

        # --- 4. Catégorie ---
        self.inp_category_display = QLineEdit(); self.inp_category_display.setReadOnly(True)
        self.inp_category_display.setFixedHeight(widget_height); self.inp_category_display.setStyleSheet(display_style)
        self.btn_select_category = QPushButton(" Choisir"); self.btn_select_category.setIcon(qta.icon("fa5s.list", color="white"))
        self.btn_select_category.setFixedSize(90, widget_height); self.btn_select_category.setStyleSheet(button_select_style)
        self.btn_select_category.clicked.connect(self.open_category_selector)
        cat_lay = QHBoxLayout(); cat_lay.setContentsMargins(0,0,0,0); cat_lay.addWidget(self.inp_category_display); cat_lay.addWidget(self.btn_select_category)
        cat_widget = QWidget(); cat_widget.setLayout(cat_lay)

        # --- 5. Fournisseur ---
        self.inp_supplier_display = QLineEdit(); self.inp_supplier_display.setReadOnly(True)
        self.inp_supplier_display.setFixedHeight(widget_height); self.inp_supplier_display.setStyleSheet(display_style)
        self.btn_select_supplier = QPushButton(" Choisir"); self.btn_select_supplier.setIcon(qta.icon("fa5s.truck", color="white"))
        self.btn_select_supplier.setFixedSize(90, widget_height); self.btn_select_supplier.setStyleSheet(button_select_style)
        self.btn_select_supplier.clicked.connect(self.open_supplier_selector)
        supp_lay = QHBoxLayout(); supp_lay.setContentsMargins(0,0,0,0); supp_lay.addWidget(self.inp_supplier_display); supp_lay.addWidget(self.btn_select_supplier)
        supp_widget = QWidget(); supp_widget.setLayout(supp_lay)

        # --- 6. Client (Réservé pour) ---
        self.inp_client_display = QLineEdit(); self.inp_client_display.setReadOnly(True)
        self.inp_client_display.setFixedHeight(widget_height); self.inp_client_display.setPlaceholderText("Libre")
        self.inp_client_display.setStyleSheet(display_style)
        self.btn_select_client = QPushButton(" Choisir"); self.btn_select_client.setFixedHeight(widget_height); self.btn_select_client.setStyleSheet(button_select_style)
        self.btn_select_client.clicked.connect(self.open_client_selector)
        self.btn_clear_client = QPushButton(); self.btn_clear_client.setIcon(qta.icon("fa5s.times", color="white"))
        self.btn_clear_client.setFixedSize(widget_height, widget_height); self.btn_clear_client.setStyleSheet("background-color: #e74c3c; border-radius: 6px;")
        self.btn_clear_client.clicked.connect(self.clear_client_selection)
        client_lay = QHBoxLayout(); client_lay.setContentsMargins(0,0,0,0); client_lay.setSpacing(2); client_lay.addWidget(self.inp_client_display); client_lay.addWidget(self.btn_select_client); client_lay.addWidget(self.btn_clear_client)
        client_widget = QWidget(); client_widget.setLayout(client_lay)

        # --- 7. Combos (Métal, Emplacement, Statut) ---
        self.combo_metal = QComboBox(); self.combo_metal.setFixedHeight(widget_height)
        self.combo_location = QComboBox(); self.combo_location.setFixedHeight(widget_height)
        self.combo_status = QComboBox(); self.combo_status.setFixedHeight(widget_height)
        for label, val in [("Disponible", "Available"), ("Vendu (Totalement)", "Sold"), ("Partiellement Vendu", "Partially_Sold"), ("Réservé", "Reserved"), ("Casse / Débris", "Scrap"), ("En Réparation", "Repair"), ("Perdu", "Lost")]:
            self.combo_status.addItem(label, val)

        # --- 8. الأوزان والكميات ---
        self.spin_weight = QDoubleSpinBox(); self.spin_weight.setFixedHeight(widget_height)
        self.spin_weight.setRange(0, 10000); self.spin_weight.setDecimals(3); self.spin_weight.setSuffix(" g"); self.spin_weight.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.spin_remaining_weight = QDoubleSpinBox(); self.spin_remaining_weight.setFixedHeight(widget_height)
        self.spin_remaining_weight.setRange(0, 10000); self.spin_remaining_weight.setDecimals(3); self.spin_remaining_weight.setSuffix(" g"); self.spin_remaining_weight.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_remaining_weight.setStyleSheet("font-size: 15px; font-weight: bold; border: 2px solid #e67e22; color: #d35400; background-color: #fef9e7;")

        self.spin_qty = QSpinBox(); self.spin_qty.setFixedHeight(widget_height)
        self.spin_qty.setRange(0, 10000); self.spin_qty.setSuffix(" pcs"); self.spin_qty.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.spin_remaining_qty = QSpinBox(); self.spin_remaining_qty.setFixedHeight(widget_height)
        self.spin_remaining_qty.setRange(0, 10000); self.spin_remaining_qty.setSuffix(" pcs"); self.spin_remaining_qty.setButtonSymbols(QAbstractSpinBox.NoButtons)

        # --- 9. التكاليف والأسعار ---
        self.spin_metal_cost = QDoubleSpinBox(); self.spin_metal_cost.setFixedHeight(widget_height); self.spin_metal_cost.setRange(0, 1000000); self.spin_metal_cost.setSuffix(" DA/g"); self.spin_metal_cost.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_labor_cost = QDoubleSpinBox(); self.spin_labor_cost.setFixedHeight(widget_height); self.spin_labor_cost.setRange(0, 1000000); self.spin_labor_cost.setSuffix(" DA/g"); self.spin_labor_cost.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.combo_margin_type = QComboBox(); self.combo_margin_type.setFixedHeight(widget_height)
        self.combo_margin_type.addItem("Fixe", "FIXED"); self.combo_margin_type.addItem("En %", "PERCENTAGE")
        self.spin_profit_margin = QDoubleSpinBox(); self.spin_profit_margin.setFixedHeight(widget_height); self.spin_profit_margin.setRange(0, 100000000); self.spin_profit_margin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        margin_lay = QHBoxLayout(); margin_lay.setContentsMargins(0,0,0,0); margin_lay.addWidget(self.combo_margin_type, 1); margin_lay.addWidget(self.spin_profit_margin, 2)
        margin_widget = QWidget(); margin_widget.setLayout(margin_lay)

        self.spin_total_cost = QDoubleSpinBox(); self.spin_total_cost.setFixedHeight(widget_height); self.spin_total_cost.setRange(0, 100000000); self.spin_total_cost.setSuffix(" DA"); self.spin_total_cost.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_selling_price = QDoubleSpinBox(); self.spin_selling_price.setFixedHeight(widget_height); self.spin_selling_price.setRange(0, 100000000); self.spin_selling_price.setSuffix(" DA"); self.spin_selling_price.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_selling_price.setStyleSheet("font-size: 15px; font-weight: bold; border: 2px solid #27ae60; color: #27ae60; background-color: #eafaf1;")

        # --- Signals ---
        self.spin_weight.valueChanged.connect(self.calculate_totals)
        self.spin_metal_cost.valueChanged.connect(self.calculate_totals)
        self.spin_labor_cost.valueChanged.connect(self.calculate_totals)
        self.spin_profit_margin.valueChanged.connect(self.calculate_totals)
        self.combo_margin_type.currentIndexChanged.connect(self.update_margin_suffix)

        # 🟢 بناء الشبكة (Grid) بشكل أفقي لتقليل الارتفاع العمودي
        grid.addWidget(create_hbox("Code-barres:", self.inp_barcode), 0, 0)
        grid.addWidget(create_hbox("Désignation:", name_widget), 0, 1)
        grid.addWidget(create_hbox("Type Article:", self.combo_item_type), 0, 2)

        grid.addWidget(create_hbox("Catégorie:", cat_widget), 1, 0)
        grid.addWidget(create_hbox("Métal:", self.combo_metal), 1, 1)
        grid.addWidget(create_hbox("Emplacement:", self.combo_location), 1, 2)

        grid.addWidget(create_hbox("Fournisseur:", supp_widget), 2, 0)
        grid.addWidget(create_hbox("Statut:", self.combo_status), 2, 1)
        grid.addWidget(create_hbox("Réservé Pour:", client_widget), 2, 2)

        grid.addWidget(create_hbox("Poids Total:", self.spin_weight), 3, 0)
        grid.addWidget(create_hbox("Poids Restant:", self.spin_remaining_weight), 3, 1)
        grid.addWidget(create_hbox("Coût Métal (g):", self.spin_metal_cost), 3, 2)

        grid.addWidget(create_hbox("Qté Totale:", self.spin_qty), 4, 0)
        grid.addWidget(create_hbox("Qté Restante:", self.spin_remaining_qty), 4, 1)
        grid.addWidget(create_hbox("Coût Façon (g):", self.spin_labor_cost), 4, 2)

        grid.addWidget(create_hbox("Marge Bénéfice:", margin_widget), 5, 0)
        grid.addWidget(create_hbox("Coût Global:", self.spin_total_cost), 5, 1)
        grid.addWidget(create_hbox("Prix de Vente:", self.spin_selling_price), 5, 2)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # --- Bottom Buttons ---
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_height = 45 # 🟢 تصغير ارتفاع الأزرار السفلية قليلاً للحفاظ على مساحة الكيبورد

        self.btn_delete = QPushButton(" Supprimer")
        self.btn_delete.setIcon(qta.icon("fa5s.trash", color="white"))
        self.btn_delete.setFixedHeight(btn_height)
        self.btn_delete.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        self.btn_delete.clicked.connect(self.delete_item)

        btn_cancel = QPushButton(" Annuler")
        btn_cancel.setFixedHeight(btn_height)
        btn_cancel.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_cancel.clicked.connect(self.reject)

        btn_kb = QPushButton(" ⌨️ Clavier")
        btn_kb.setFixedHeight(btn_height)
        btn_kb.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_kb.clicked.connect(self.show_virtual_keyboard)

        btn_save = QPushButton(" Enregistrer les Modifications")
        btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        btn_save.setFixedHeight(btn_height)
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_save.clicked.connect(self.save_changes)

        btn_box.addWidget(self.btn_delete)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_kb)
        btn_box.addWidget(btn_save, stretch=1)

        main_layout.addLayout(btn_box)

    # ---------------------------------------------------------
    # Dialog Selectors Methods
    # ---------------------------------------------------------
    def open_name_selector(self):
        try:
            dlg = ProductNameSelectionDialog(self.manager, self)
            if dlg.exec() == QDialog.Accepted:
                selected_name = dlg.get_selected_name()
                if selected_name:
                    self.selected_item_name = selected_name
                    self.inp_name_display.setText(self.selected_item_name)
                    self.inp_name_display.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px 8px; border: 2px solid #27ae60; border-radius: 6px; background-color: #eafaf1; color: #2c3e50;")
        except NameError: pass

    def open_category_selector(self):
        try:
            dlg = CategorySelectionDialog(self.manager, self)
            if dlg.exec() == QDialog.Accepted:
                selected_item = dlg.list_widget.currentItem()
                if selected_item:
                    self.selected_category_id = selected_item.data(Qt.UserRole)
                    self.inp_category_display.setText(selected_item.text())
                    self.inp_category_display.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px 8px; border: 2px solid #27ae60; border-radius: 6px; background-color: #eafaf1; color: #2c3e50;")
        except NameError: pass

    def open_supplier_selector(self):
        try:
            dlg = SupplierSelectionDialog(self.manager, self)
            if dlg.exec() == QDialog.Accepted:
                selected_item = dlg.list_widget.currentItem()
                if selected_item:
                    self.selected_supplier_id = selected_item.data(Qt.UserRole)
                    self.inp_supplier_display.setText(selected_item.text())
                    self.inp_supplier_display.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px 8px; border: 2px solid #27ae60; border-radius: 6px; background-color: #eafaf1; color: #2c3e50;")
        except NameError: pass

    def open_client_selector(self):
        try:
            dlg = ClientSelectionDialog(self.manager, self)
            if dlg.exec() == QDialog.Accepted:
                if dlg.selected_client_id:
                    self.selected_client_id = dlg.selected_client_id
                    client_info = self.manager.customers.get_customer_by_id(self.selected_client_id)
                    if client_info:
                        self.inp_client_display.setText(client_info['name'])
                        self.inp_client_display.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px 8px; border: 2px solid #8e44ad; border-radius: 6px; background-color: #f4ecf7; color: #8e44ad;")
        except NameError: pass

    def clear_client_selection(self):
        self.selected_client_id = None
        self.inp_client_display.clear()
        self.inp_client_display.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px 8px; border: 2px solid #bdc3c7; border-radius: 6px; background-color: #ecf0f1; color: #2c3e50;")

    # ---------------------------------------------------------
    # Core Logic
    # ---------------------------------------------------------
    def load_combos(self):
        try:
            for m in self.manager.metal_types.get_all_metal_types():
                self.combo_metal.addItem(f"{m['name']} ({m['purity_value']})", m['id'])
            for l in self.manager.storage_locations.get_all_locations():
                self.combo_location.addItem(l['name'], l['id'])
        except: pass

    def populate_data(self):
        self.inp_barcode.setText(str(self.item_data.get('barcode') or ''))

        self.selected_item_name = str(self.item_data.get('name') or '')
        if self.selected_item_name:
            self.inp_name_display.setText(self.selected_item_name)

        cat_id = self.item_data.get('category_id')
        if cat_id:
            self.selected_category_id = cat_id
            self.inp_category_display.setText(str(self.item_data.get('category_name') or 'Sélectionné'))

        sup_id = self.item_data.get('supplier_id')
        if sup_id:
            self.selected_supplier_id = sup_id
            self.inp_supplier_display.setText(str(self.item_data.get('supplier_name') or 'Sélectionné'))

        cl_id = self.item_data.get('reserved_for_client_id')
        if cl_id:
            self.selected_client_id = cl_id
            self.inp_client_display.setText(str(self.item_data.get('reserved_client_name') or 'Client Réservé'))
            self.inp_client_display.setStyleSheet("font-size: 14px; font-weight: bold; padding: 2px 8px; border: 2px solid #8e44ad; border-radius: 6px; background-color: #f4ecf7; color: #8e44ad;")

        i_type = self.item_data.get('item_type', 'WEIGHT')
        idx = self.combo_item_type.findData(i_type)
        if idx >= 0: self.combo_item_type.setCurrentIndex(idx)

        self.set_combo(self.combo_metal, self.item_data.get('metal_type_id'))
        self.set_combo(self.combo_location, self.item_data.get('location_id'))
        self.set_combo(self.combo_status, self.item_data.get('status'))

        m_type = self.item_data.get('margin_type', 'FIXED')
        m_idx = self.combo_margin_type.findData(m_type)
        if m_idx >= 0: self.combo_margin_type.setCurrentIndex(m_idx)
        self.update_margin_suffix()

        self.spin_weight.setValue(float(self.item_data.get('weight') or 0))
        self.spin_remaining_weight.setValue(float(self.item_data.get('remaining_weight') or self.item_data.get('weight') or 0))
        self.spin_qty.setValue(int(self.item_data.get('quantity') or 1))
        self.spin_remaining_qty.setValue(int(self.item_data.get('remaining_quantity') or self.item_data.get('quantity') or 1))

        self.spin_metal_cost.setValue(float(self.item_data.get('metal_cost_per_gram') or 0))
        self.spin_labor_cost.setValue(float(self.item_data.get('labor_cost_per_gram') or 0))
        self.spin_profit_margin.setValue(float(self.item_data.get('profit_margin') or 0))

        if i_type == 'PIECE':
            self.spin_total_cost.setValue(float(self.item_data.get('total_cost') or 0))
            self.spin_selling_price.setValue(float(self.item_data.get('selling_price') or 0))
        else:
            self.calculate_totals()

        self.toggle_type_fields()

    def set_combo(self, combo, val):
        if val is None: return
        idx = combo.findData(val)
        if idx >= 0: combo.setCurrentIndex(idx)

    def update_margin_suffix(self):
        if self.combo_margin_type.currentData() == "PERCENTAGE":
            self.spin_profit_margin.setSuffix(" %")
        else:
            self.spin_profit_margin.setSuffix(" DA/g")
        self.calculate_totals()

    def toggle_type_fields(self):
        is_weight = self.combo_item_type.currentData() == "WEIGHT"
        self.spin_weight.setEnabled(is_weight)
        self.spin_remaining_weight.setEnabled(is_weight)
        self.spin_metal_cost.setEnabled(is_weight)
        self.spin_labor_cost.setEnabled(is_weight)
        self.spin_profit_margin.setEnabled(is_weight)
        self.combo_margin_type.setEnabled(is_weight)

        base_style = "font-size: 14px; font-weight: bold; padding: 2px 8px; border-radius: 6px; border: 1px solid #bdc3c7;"
        if is_weight:
            self.spin_total_cost.setReadOnly(True)
            self.spin_selling_price.setReadOnly(True)
            self.spin_total_cost.setStyleSheet(base_style + "background-color: #ecf0f1; color: #7f8c8d;")
            self.spin_selling_price.setStyleSheet(base_style + "background-color: #d4efdf; color: #1e8449;")
            self.calculate_totals()
        else:
            self.spin_total_cost.setReadOnly(False)
            self.spin_selling_price.setReadOnly(False)
            self.spin_total_cost.setStyleSheet(base_style + "background-color: #ffffff; color: #2c3e50;")
            self.spin_selling_price.setStyleSheet(base_style + "border: 2px solid #27ae60; color: #27ae60; background-color: #eafaf1;")

    def calculate_totals(self):
        if not hasattr(self, 'combo_item_type') or self.combo_item_type.currentData() == "PIECE":
            return

        w = self.spin_weight.value()
        mc = self.spin_metal_cost.value()
        lc = self.spin_labor_cost.value()
        margin = self.spin_profit_margin.value()
        margin_type = self.combo_margin_type.currentData()

        total_cost = (mc + lc) * w

        if margin_type == 'PERCENTAGE':
            profit_per_gram = (mc + lc) * (margin / 100.0)
        else:
            profit_per_gram = margin

        selling_price = total_cost + (profit_per_gram * w)

        self.spin_total_cost.setValue(total_cost)
        self.spin_selling_price.setValue(selling_price)

    def save_changes(self):
        if not self.selected_item_name:
            QMessageBox.warning(self, "Erreur", "Veuillez choisir un nom d'article.")
            return

        # 🟢 استدعاء الدالة المدمجة الجديدة من الـ Backend
        ok = self.manager.inventory.update_item_extended(
            item_id=self.current_edit_id,
            barcode=self.inp_barcode.text().strip() or None,
            name=self.selected_item_name,
            item_type=self.combo_item_type.currentData(),
            category_id=self.selected_category_id,
            metal_type_id=self.combo_metal.currentData(),
            weight=self.spin_weight.value(),
            quantity=self.spin_qty.value(),
            metal_cost_per_gram=self.spin_metal_cost.value(),
            labor_cost_per_gram=self.spin_labor_cost.value(),
            profit_margin=self.spin_profit_margin.value(),
            margin_type=self.combo_margin_type.currentData(),
            total_cost=self.spin_total_cost.value(),
            selling_price=self.spin_selling_price.value(),
            location_id=self.combo_location.currentData(),
            supplier_id=self.selected_supplier_id,
            remaining_weight=self.spin_remaining_weight.value(),
            remaining_quantity=self.spin_remaining_qty.value(),
            status=self.combo_status.currentData(),
            reserved_for_client_id=self.selected_client_id
        )

        if ok:
            self.accept()
        else:
            QMessageBox.critical(self, "Erreur", "Impossible de sauvegarder les modifications.")

    def delete_item(self):
        if QMessageBox.question(self, "Confirmation", "Supprimer définitivement cet article ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.manager.inventory.delete_item(self.current_edit_id):
                self.accept()