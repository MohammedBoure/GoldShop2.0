# ui/dialogs/quick_add_droduct_dialog.py

import os
import json
import datetime
import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, QSpinBox,
    QMessageBox, QLabel, QFrame, QGridLayout, QDialog, QAbstractItemView, QScrollArea,
    QSizePolicy, QCompleter, QDoubleSpinBox, QComboBox, QScroller, QAbstractSpinBox,
    QApplication
)
from PySide6.QtCore import Qt
import qtawesome as qta

from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults
from ui.widgets.inventory.touch_product_entry import (
    confirm_product_entry,
    wrap_with_numpad,
)
from .product_name_selection import ProductNameSelectionDialog
from .category_selection import CategorySelectionDialog

RUNTIME_DIR = "runtime"
INVENTORY_STATE_FILE = os.path.join(RUNTIME_DIR, "inventory_last_state.json")
LEGACY_INVENTORY_STATE_FILE = "inventory_last_state.json"

class QuickAddProductDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.added_item_id = None
        self.vkb = None

        # تخزين القيم المختارة من النوافذ المنبثقة
        self.selected_item_name = ""
        self.selected_category_id = None

        self.setWindowTitle("Ajout Rapide & Vente")
        self.setMinimumSize(720, 480)
        self.resize(960, 580)
        self.setStyleSheet("QDialog { background-color: #f4f7fa; }")

        self.init_ui()
        self.load_combos()
        # 🟢 تحميل آخر إعدادات محفوظة
        self.load_last_state()
        self.toggle_type_fields()

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        screen_geom = screen.availableGeometry()
        width = min(980, max(720, screen_geom.width() - 40))
        height = min(620, max(480, screen_geom.height() - 320))
        self.resize(width, height)
        x = screen_geom.x() + (screen_geom.width() - self.width()) // 2
        y = screen_geom.y()
        self.move(x, y)

    def show_virtual_keyboard(self):
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog
        if not self.vkb:
            self.vkb = VirtualKeyboardDialog(self)
        self.vkb.show()
        self.vkb.raise_()
    def init_ui(self):
        main_layout = QVBoxLayout(self)

        header_lbl = QLabel("🛍️ Ajouter un Nouvel Article pour Vente Directe")
        header_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50; margin-bottom: 5px;")
        header_lbl.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header_lbl)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        grid.setVerticalSpacing(15)
        grid.setHorizontalSpacing(20)

        scroll_content.setStyleSheet("""
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
                font-size: 16px; font-weight: bold; padding: 5px 10px;
                border: 2px solid #bdc3c7; border-radius: 8px; background-color: #f9f9f9;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {
                border: 2px solid #3498db; background-color: white;
            }
        """)

        display_style = "font-size: 16px; font-weight: bold; padding: 5px 10px; border: 2px solid #bdc3c7; border-radius: 8px; background-color: #ecf0f1; color: #2c3e50;"
        button_select_style = "QPushButton { background-color: #34495e; color: white; border-radius: 8px; font-weight: bold; font-size: 14px; } QPushButton:pressed { background-color: #2c3e50; }"

        def create_vbox(label_text, widget):
            vlay = QVBoxLayout()
            vlay.setSpacing(3)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #34495e;")
            vlay.addWidget(lbl)
            vlay.addWidget(widget)
            
            w = QWidget()
            w.setLayout(vlay)
            w.lbl = lbl
            return w

        # --- Code-barres ---
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setFixedHeight(45)

        self.btn_gen_barcode = QPushButton()
        self.btn_gen_barcode.setIcon(qta.icon("fa5s.magic", color="#d4af37"))
        self.btn_gen_barcode.setFixedSize(50, 45)
        self.btn_gen_barcode.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 8px;")
        self.btn_gen_barcode.clicked.connect(self.generate_barcode)

        bc_lay = QHBoxLayout()
        bc_lay.setContentsMargins(0,0,0,0)
        bc_lay.addWidget(self.inp_barcode)
        bc_lay.addWidget(self.btn_gen_barcode)
        bc_widget = QWidget()
        bc_widget.setLayout(bc_lay)

        # --- Désignation (Selector) ---
        self.inp_name_display = QLineEdit()
        self.inp_name_display.setReadOnly(True)
        self.inp_name_display.setFixedHeight(45)
        self.inp_name_display.setPlaceholderText("Choisir un nom...")
        self.inp_name_display.setStyleSheet(display_style)

        self.btn_select_name = QPushButton(" Choisir")
        self.btn_select_name.setIcon(qta.icon("fa5s.search", color="white"))
        self.btn_select_name.setFixedSize(100, 45)
        self.btn_select_name.setStyleSheet(button_select_style)
        self.btn_select_name.clicked.connect(self.open_name_selector)

        name_lay = QHBoxLayout()
        name_lay.setContentsMargins(0,0,0,0)
        name_lay.addWidget(self.inp_name_display)
        name_lay.addWidget(self.btn_select_name)
        name_widget = QWidget()
        name_widget.setLayout(name_lay)

        # --- Type ---
        self.combo_item_type = QComboBox()
        self.combo_item_type.setFixedHeight(45)
        self.combo_item_type.addItem("Au Poids (Or/Argent)", "WEIGHT")
        self.combo_item_type.addItem("À la Pièce (Accessoires)", "PIECE")
        self.combo_item_type.currentIndexChanged.connect(self.toggle_type_fields)

        # --- Catégorie (Selector) ---
        self.inp_category_display = QLineEdit()
        self.inp_category_display.setReadOnly(True)
        self.inp_category_display.setFixedHeight(45)
        self.inp_category_display.setPlaceholderText("Choisir une catégorie...")
        self.inp_category_display.setStyleSheet(display_style)

        self.btn_select_category = QPushButton(" Choisir")
        self.btn_select_category.setIcon(qta.icon("fa5s.list", color="white"))
        self.btn_select_category.setFixedSize(100, 45)
        self.btn_select_category.setStyleSheet(button_select_style)
        self.btn_select_category.clicked.connect(self.open_category_selector)

        cat_lay = QHBoxLayout()
        cat_lay.setContentsMargins(0,0,0,0)
        cat_lay.addWidget(self.inp_category_display)
        cat_lay.addWidget(self.btn_select_category)
        cat_widget = QWidget()
        cat_widget.setLayout(cat_lay)

        # --- القوائم الإضافية ---
        self.combo_metal = QComboBox()
        self.combo_metal.setFixedHeight(45)

        self.combo_location = QComboBox()
        self.combo_location.setFixedHeight(45)

        self.combo_supplier = QComboBox()
        self.combo_supplier.setFixedHeight(45)

        self.combo_receipt_mode = QComboBox()
        self.combo_receipt_mode.setFixedHeight(45)
        self.combo_receipt_mode.addItem("Stock uniquement / dette deja enregistree", "INVENTORY_ONLY")
        self.combo_receipt_mode.addItem("Reception fournisseur a credit / creer un bon", "SUPPLIER_RECEIPT")

        self.combo_supplier_account = QComboBox()
        self.combo_supplier_account.setFixedHeight(45)
        self.combo_supplier_account.setEnabled(False)

        # --- Spinboxes ---
        self.spin_qty = QSpinBox()
        self.spin_qty.setFixedHeight(45)
        self.spin_qty.setRange(1, 10000)
        self.spin_qty.setSuffix(" pcs")
        self.spin_qty.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.spin_weight = QDoubleSpinBox()
        self.spin_weight.setFixedHeight(45)
        self.spin_weight.setRange(0, 10000)
        self.spin_weight.setDecimals(3)
        self.spin_weight.setSuffix(" g")
        self.spin_weight.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.spin_metal_cost = QDoubleSpinBox()
        self.spin_metal_cost.setFixedHeight(45)
        self.spin_metal_cost.setRange(0, 1000000)
        self.spin_metal_cost.setSuffix(" DA/g")
        self.spin_metal_cost.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.spin_labor_cost = QDoubleSpinBox()
        self.spin_labor_cost.setFixedHeight(45)
        self.spin_labor_cost.setRange(0, 1000000)
        self.spin_labor_cost.setSuffix(" DA/g")
        self.spin_labor_cost.setButtonSymbols(QAbstractSpinBox.NoButtons)

        self.combo_margin_type = QComboBox()
        self.combo_margin_type.setFixedHeight(45)
        self.combo_margin_type.addItem("Fixe (DA)", "FIXED")
        self.combo_margin_type.addItem("Pourcentage (%)", "PERCENTAGE")

        self.spin_profit_margin = QDoubleSpinBox()
        self.spin_profit_margin.setFixedHeight(45)
        self.spin_profit_margin.setRange(0, 1000000)
        self.spin_profit_margin.setButtonSymbols(QAbstractSpinBox.NoButtons)

        for input_widget in (
            self.inp_barcode,
            self.inp_name_display,
            self.inp_category_display,
            self.combo_item_type,
            self.combo_metal,
            self.combo_location,
            self.combo_supplier,
            self.combo_receipt_mode,
            self.combo_supplier_account,
            self.combo_margin_type,
            self.spin_qty,
            self.spin_weight,
            self.spin_metal_cost,
            self.spin_labor_cost,
            self.spin_profit_margin,
        ):
            apply_touch_input_defaults(input_widget)

        for button in (self.btn_gen_barcode, self.btn_select_name, self.btn_select_category):
            apply_touch_button_defaults(button)

        margin_lay = QHBoxLayout()
        margin_lay.setContentsMargins(0,0,0,0)
        margin_lay.addWidget(self.combo_margin_type, 1)
        margin_lay.addWidget(
            wrap_with_numpad(self, self.spin_profit_margin, "Marge benefice", allow_decimal=True),
            2,
        )
        margin_widget = QWidget()
        margin_widget.setLayout(margin_lay)

        # Signals
        self.spin_weight.valueChanged.connect(self.calculate_totals)
        self.spin_metal_cost.valueChanged.connect(self.calculate_totals)
        self.spin_labor_cost.valueChanged.connect(self.calculate_totals)
        self.spin_profit_margin.valueChanged.connect(self.calculate_totals)
        self.combo_margin_type.currentIndexChanged.connect(self.calculate_totals)
        self.combo_supplier.currentIndexChanged.connect(self._refresh_supplier_accounts)
        self.combo_receipt_mode.currentIndexChanged.connect(self._refresh_supplier_accounts)
        self.combo_metal.currentIndexChanged.connect(self._refresh_product_name_display)
        self.combo_supplier.currentIndexChanged.connect(self._refresh_product_name_display)

        # Grid
        grid.addWidget(create_vbox("Code-barres:", bc_widget), 0, 0)
        grid.addWidget(create_vbox("Désignation:", name_widget), 0, 1)
        grid.addWidget(create_vbox("Type d'Article:", self.combo_item_type), 0, 2)

        grid.addWidget(create_vbox("Catégorie:", cat_widget), 1, 0)
        
        self.wg_metal = create_vbox("Métal:", self.combo_metal)
        grid.addWidget(self.wg_metal, 1, 1)
        
        grid.addWidget(create_vbox("Emplacement:", self.combo_location), 1, 2)

        grid.addWidget(create_vbox("Fournisseur:", self.combo_supplier), 2, 0)
        
        self.wg_weight = create_vbox("Poids (g):", wrap_with_numpad(self, self.spin_weight, "Poids", allow_decimal=True))
        grid.addWidget(self.wg_weight, 2, 1)
        
        grid.addWidget(
            create_vbox("Quantité (pcs):", wrap_with_numpad(self, self.spin_qty, "Quantite", allow_decimal=False)),
            2,
            2,
        )

        self.wg_metal_cost = create_vbox("Coût Métal (par g):", wrap_with_numpad(self, self.spin_metal_cost, "Cout metal", allow_decimal=True))
        grid.addWidget(self.wg_metal_cost, 3, 0)
        
        self.wg_labor_cost = create_vbox("Coût Façon (par g):", wrap_with_numpad(self, self.spin_labor_cost, "Cout facon", allow_decimal=True))
        grid.addWidget(self.wg_labor_cost, 3, 1)
        
        self.wg_margin = create_vbox("Marge Bénéfice:", margin_widget)
        grid.addWidget(self.wg_margin, 3, 2)

        grid.addWidget(create_vbox("Traitement fournisseur:", self.combo_receipt_mode), 4, 0)
        grid.addWidget(create_vbox("Compte LOCAL / IMPORT:", self.combo_supplier_account), 4, 1)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # --- Buttons ---
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        btn_cancel = QPushButton(" Annuler")
        btn_cancel.setIcon(qta.icon("fa5s.times", color="white"))
        btn_cancel.setFixedHeight(55)
        btn_cancel.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; font-size: 16px; border-radius: 8px;")
        btn_cancel.clicked.connect(self.reject)

        btn_kb = QPushButton(" ⌨️ Clavier")
        self.btn_keyboard = btn_kb
        btn_kb.setFixedHeight(55)
        btn_kb.setStyleSheet("background-color: #34495e; color: white; font-weight: bold; font-size: 16px; border-radius: 8px;")
        btn_kb.clicked.connect(self.show_virtual_keyboard)

        btn_save = QPushButton(" Ajouter & Vendre")
        btn_save.setIcon(qta.icon("fa5s.cart-plus", color="white"))
        btn_save.setFixedHeight(55)
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 16px; border-radius: 8px;")
        btn_save.clicked.connect(self.save_and_sell)

        apply_touch_button_defaults(btn_cancel, danger=True)
        apply_touch_button_defaults(btn_kb)
        apply_touch_button_defaults(btn_save, primary=True)

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_kb)
        btn_box.addWidget(btn_save, stretch=1)

        main_layout.addLayout(btn_box)

    def open_name_selector(self):
        dlg = ProductNameSelectionDialog(self.manager, self)
        if dlg.exec() == QDialog.Accepted:
            selected_name = dlg.get_selected_name()
            if selected_name:
                self.selected_item_name = selected_name
                self._refresh_product_name_display()

    def open_category_selector(self):
        dlg = CategorySelectionDialog(self.manager, self)
        if dlg.exec() == QDialog.Accepted:
            selected_item = dlg.list_widget.currentItem()
            if selected_item:
                self.selected_category_id = selected_item.data(Qt.UserRole)
                self.inp_category_display.setText(selected_item.text())
                self.inp_category_display.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px 10px; border: 2px solid #27ae60; border-radius: 8px; background-color: #eafaf1; color: #2c3e50;")
                self._refresh_product_name_display()

    @staticmethod
    def _selected_display_style():
        return (
            "font-size: 16px; font-weight: bold; padding: 5px 10px; "
            "border: 2px solid #27ae60; border-radius: 8px; "
            "background-color: #eafaf1; color: #2c3e50;"
        )

    @staticmethod
    def _combo_text(combo):
        try:
            text = combo.currentText()
        except Exception:
            return ""
        return text.strip() if isinstance(text, str) else ""

    @staticmethod
    def _line_text(line_edit):
        try:
            text = line_edit.text()
        except Exception:
            return ""
        return text.strip() if isinstance(text, str) else ""

    def _product_name_summary(self):
        name = str(self.selected_item_name or "").strip()
        if not name:
            return ""

        parts = [name]
        category = self._line_text(self.inp_category_display)
        metal = self._combo_text(self.combo_metal)
        supplier = self._combo_text(self.combo_supplier)

        if category:
            parts.append(f"Catégorie: {category}")
        if metal:
            parts.append(f"Métal/Titre: {metal}")
        if supplier:
            parts.append(f"Fournisseur: {supplier}")
        return " | ".join(parts)

    def _refresh_product_name_display(self, *_):
        summary = self._product_name_summary()
        if not summary:
            return
        self.inp_name_display.setText(summary)
        self.inp_name_display.setToolTip(summary)
        self.inp_name_display.setStyleSheet(self._selected_display_style())

    def generate_barcode(self):
        now = datetime.datetime.now()
        code_12 = f"21{now.strftime('%y%j%H%M%S')}{random.randint(10, 99)}"[-12:]
        check = (10 - ((sum(int(code_12[i]) for i in range(12) if i%2==0) + sum(int(code_12[i]) for i in range(12) if i%2!=0)*3) % 10)) % 10
        self.inp_barcode.setText(f"{code_12}{check}")

    def load_combos(self):
        try:
            self.combo_metal.clear()
            for m in self.manager.metal_types.get_all_metal_types():
                self.combo_metal.addItem(f"{m['name']} ({m['purity_value']})", m['id'])

            self.combo_location.clear()
            for l in self.manager.storage_locations.get_all_locations():
                self.combo_location.addItem(l['name'], l['id'])

            self.combo_supplier.clear()
            for s in self.manager.suppliers.get_all_suppliers():
                self.combo_supplier.addItem(s['name'], s['id'])
            self._refresh_supplier_accounts()
            self._refresh_product_name_display()
        except Exception as e:
            print(f"Error loading combos: {e}")

    def _refresh_supplier_accounts(self):
        self.combo_supplier_account.clear()
        is_receipt = self.combo_receipt_mode.currentData() == "SUPPLIER_RECEIPT"
        supplier_id = self.combo_supplier.currentData()
        self.combo_supplier_account.setEnabled(bool(is_receipt and supplier_id))
        if not is_receipt or not supplier_id:
            return
        for account in self.manager.supplier_operations.get_supplier_accounts(
            supplier_id, include_inactive=False
        ):
            code = account.get("code") or account.get("name") or "Compte"
            self.combo_supplier_account.addItem(str(code), account.get("id"))

    def _receipt_posting_data(self):
        if self.combo_receipt_mode.currentData() != "SUPPLIER_RECEIPT":
            return None
        if self.combo_item_type.currentData() != "WEIGHT":
            raise ValueError("La reception fournisseur a credit est reservee aux articles au poids.")
        supplier_id = self.combo_supplier.currentData()
        account_id = self.combo_supplier_account.currentData()
        if not supplier_id or not account_id:
            raise ValueError("Selectionnez un fournisseur et un compte LOCAL/IMPORT actif.")
        return {"supplier_id": supplier_id, "supplier_account_id": account_id}

    # 🟢 1. دالة حفظ الحالة
    def save_last_state(self):
        state = {
            "name": self.selected_item_name,
            "category_id": self.selected_category_id,
            "metal_type_id": self.combo_metal.currentData(),
            "metal_cost": self.spin_metal_cost.value(),
            "labor_cost": self.spin_labor_cost.value(),
            "margin": self.spin_profit_margin.value(),
            "margin_type": self.combo_margin_type.currentData(),
            "location_id": self.combo_location.currentData(),
            "supplier_id": self.combo_supplier.currentData(),
            "item_type": self.combo_item_type.currentData()
        }
        try:
            os.makedirs(RUNTIME_DIR, exist_ok=True)
            with open(INVENTORY_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
        except Exception as e:
            pass # Ignore errors on save

    # 🟢 2. دالة استرجاع الحالة
    def load_last_state(self):
        state_file = INVENTORY_STATE_FILE if os.path.exists(INVENTORY_STATE_FILE) else LEGACY_INVENTORY_STATE_FILE
        if not os.path.exists(state_file):
            return
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            # 1. استعادة الاسم
            saved_name = state.get("name", "")
            if saved_name:
                self.selected_item_name = saved_name

            # 2. استعادة الفئة والبحث عن اسمها لعرضه
            saved_cat_id = state.get("category_id")
            if saved_cat_id is not None:
                self.selected_category_id = saved_cat_id
                try:
                    cats = self.manager.categories.get_all_categories()
                    for c in cats:
                        if c['id'] == saved_cat_id:
                            self.inp_category_display.setText(c['name'])
                            self.inp_category_display.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px 10px; border: 2px solid #27ae60; border-radius: 8px; background-color: #eafaf1; color: #2c3e50;")
                            break
                except Exception:
                    pass

            # 3. الأرقام
            self.spin_metal_cost.setValue(state.get("metal_cost", 0))
            self.spin_labor_cost.setValue(state.get("labor_cost", 0))
            self.spin_profit_margin.setValue(state.get("margin", 0))

            # 4. القوائم
            idx_metal = self.combo_metal.findData(state.get("metal_type_id"))
            if idx_metal >= 0: self.combo_metal.setCurrentIndex(idx_metal)

            idx_supp = self.combo_supplier.findData(state.get("supplier_id"))
            if idx_supp >= 0: self.combo_supplier.setCurrentIndex(idx_supp)

            idx_loc = self.combo_location.findData(state.get("location_id"))
            if idx_loc >= 0: self.combo_location.setCurrentIndex(idx_loc)

            idx_type = self.combo_item_type.findData(state.get("item_type"))
            if idx_type >= 0: self.combo_item_type.setCurrentIndex(idx_type)

            idx_margin = self.combo_margin_type.findData(state.get("margin_type"))
            if idx_margin >= 0: self.combo_margin_type.setCurrentIndex(idx_margin)

            self._refresh_product_name_display()

        except Exception as e:
            print(f"Error loading state: {e}")

    def toggle_type_fields(self):
        is_weight = self.combo_item_type.currentData() == "WEIGHT"
        
        self.wg_weight.setVisible(is_weight)
        self.wg_labor_cost.setVisible(is_weight)
        self.wg_metal.setVisible(is_weight)

        if is_weight:
            self.wg_metal_cost.lbl.setText("Coût Métal (par g):")
            self.spin_metal_cost.setSuffix(" DA/g")
            self.wg_margin.lbl.setText("Marge Bénéfice:")
        else:
            self.wg_metal_cost.lbl.setText("Prix d'Achat (Pièce):")
            self.spin_metal_cost.setSuffix(" DA")
            self.wg_margin.lbl.setText("Marge Bénéfice (Pièce):")

        self.calculate_totals()

    def calculate_totals(self):
        if self.combo_margin_type.currentData() == "PERCENTAGE":
            self.spin_profit_margin.setSuffix(" %")
        else:
            is_weight = self.combo_item_type.currentData() == "WEIGHT"
            self.spin_profit_margin.setSuffix(" DA/g" if is_weight else " DA")

    def save_and_sell(self):
        if not self.selected_item_name:
            QMessageBox.warning(self, "Erreur", "Veuillez choisir une désignation (Nom).")
            return

        if not self.selected_category_id:
            QMessageBox.warning(self, "Erreur", "Veuillez choisir une catégorie.")
            return

        is_weight = self.combo_item_type.currentData() == "WEIGHT"
        w = self.spin_weight.value() if is_weight else 1.0
        
        if is_weight and w <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez un poids superieur a 0 g pour un article au poids.")
            return
        if self.spin_qty.value() <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez une quantite superieure a 0.")
            return
            
        mc = self.spin_metal_cost.value()
        lc = self.spin_labor_cost.value() if is_weight else 0.0
        margin = self.spin_profit_margin.value()
        margin_type = self.combo_margin_type.currentData()

        total_cost = (mc + lc) * w
        if margin_type == 'PERCENTAGE':
            profit_per_unit = total_cost * (margin / 100.0)
        else:
            profit_per_unit = margin
            
        selling_price = total_cost + (profit_per_unit * w)

        data = {
            "barcode": self.inp_barcode.text().strip() or None,
            "name": self.selected_item_name,
            "item_type": self.combo_item_type.currentData(),
            "category_id": self.selected_category_id,
            "metal_type_id": self.combo_metal.currentData() if is_weight else None,
            "weight": w,
            "quantity": self.spin_qty.value(),
            "metal_cost_per_gram": mc,
            "labor_cost_per_gram": lc,
            "profit_margin": margin,
            "margin_type": margin_type,
            "total_cost": total_cost,
            "selling_price": selling_price,
            "location_id": self.combo_location.currentData(),
            "supplier_id": self.combo_supplier.currentData()
        }

        try:
            receipt = self._receipt_posting_data()
        except ValueError as e:
            QMessageBox.warning(self, "Reception fournisseur", str(e))
            return

        supplier_label = self.combo_supplier.currentText() if hasattr(self.combo_supplier, "currentText") else ""
        account_label = (
            self.combo_supplier_account.currentText()
            if hasattr(self.combo_supplier_account, "currentText")
            else ""
        )
        if not confirm_product_entry(
            self,
            data,
            receipt,
            supplier_label=supplier_label,
            account_label=account_label,
        ):
            return

        try:
            if receipt:
                success, message, _operation_id, new_id = self.manager.supplier_operations.post_stocked_goods_receipt(
                    supplier_id=receipt["supplier_id"],
                    supplier_account_id=receipt["supplier_account_id"],
                    item_data=data,
                    description=data["name"],
                )
                if not success:
                    QMessageBox.critical(self, "Reception fournisseur", message)
                    return
            else:
                new_id = self.manager.inventory.add_item(**data)
            if new_id:
                # 🟢 3. حفظ الحالة قبل الإغلاق مباشرة
                self.save_last_state()
                self.added_item_id = new_id
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ajouter : {e}")
