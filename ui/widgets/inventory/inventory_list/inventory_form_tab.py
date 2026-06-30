# ui/widgets/inventory/inventory_form_tab.py

import datetime
import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QGroupBox, QDialog,
    QMessageBox, QComboBox, QDoubleSpinBox, QLabel, QSpinBox,
    QScrollArea, QSplitter, QGridLayout, QSizePolicy, QAbstractSpinBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
import qtawesome as qta

from database.system_logger import active_user_id
from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)
from ui.tools.virtual_keyboard import VirtualKeyboardDialog
from ui.dialogs.printer_label import LabelPrintPreviewDialog
from ui.dialogs.Product_edit import ProductEditDialog
from ui.deferred_loading import defer_initial_load
from ui.widgets.inventory.touch_product_entry import (
    after_save_options_text,
    confirm_product_entry,
    wrap_with_numpad,
)
from ._helpers import SortableTableWidgetItem, ProductNameSelectionDialog, load_label_config


class InventoryFormTab(QWidget):
    """
    تبويب الإضافة السريعة للمخزون.
    يحتوي على نموذج إدخال (أعلى) وجدول العناصر المضافة في الجلسة (أسفل).
    """

    item_saved = Signal()

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.session_added_items = []
        self.vkb = None
        self.init_ui()

    # ------------------------------------------------------------------
    # Virtual keyboard
    # ------------------------------------------------------------------

    def show_virtual_keyboard(self):
        if not self.vkb:
            self.vkb = VirtualKeyboardDialog(self.window())
            self.vkb.finished.connect(self._restore_layout)
        self.recent_wrapper.hide()
        self.vkb.show()
        self.vkb.raise_()

    def _restore_layout(self):
        self.recent_wrapper.show()

    def close_keyboard(self):
        if self.vkb and self.vkb.isVisible():
            self.vkb.close()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self._build_form_group())
        self.splitter.addWidget(self._build_recent_group())
        self.splitter.setSizes([700, 300])

        main_layout.addWidget(self.splitter)
        self.toggle_type_fields()
        defer_initial_load(self, self.refresh_data)

    def _build_form_group(self) -> QGroupBox:
        box = QGroupBox("📝 Ajouter un Nouvel Article (Saisie Rapide)")
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        box.setStyleSheet("""
            QGroupBox {
                font-weight: bold; font-size: 16px; color: #2980b9;
                border: 2px solid #bdc3c7; border-radius: 8px;
                margin-top: 10px; padding-top: 20px; background-color: white;
            }
        """)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        grid = QGridLayout(content)
        grid.setVerticalSpacing(15)
        grid.setHorizontalSpacing(25)

        S = "font-size: 16px; font-weight: bold; padding: 5px 10px; border: 2px solid #bdc3c7; border-radius: 8px; background-color: #f9f9f9;"
        F = "QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus { border: 2px solid #3498db; background-color: white; }"

        def vbox(label_text, widget):
            vl = QVBoxLayout()
            vl.setSpacing(3)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #34495e;")
            vl.addWidget(lbl)
            vl.addWidget(widget)
            return vl

        # Barcode
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setFixedHeight(45)
        self.inp_barcode.setStyleSheet(S + F)
        btn_gen = QPushButton()
        btn_gen.setIcon(qta.icon("fa5s.magic", color="#d4af37"))
        btn_gen.setFixedSize(50, 45)
        btn_gen.setCursor(Qt.PointingHandCursor)
        btn_gen.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 8px;")
        btn_gen.clicked.connect(self.generate_barcode)
        bc_lay = QHBoxLayout()
        bc_lay.setSpacing(5); bc_lay.setContentsMargins(0, 0, 0, 0)
        bc_lay.addWidget(self.inp_barcode); bc_lay.addWidget(btn_gen)
        bc_widget = QWidget(); bc_widget.setLayout(bc_lay)

        # Name
        self.inp_name = QLineEdit()
        self.inp_name.setFixedHeight(45)
        self.inp_name.setPlaceholderText("Saisir manuellement ou choisir...")
        self.inp_name.setStyleSheet(S + F)
        btn_choose = QPushButton()
        btn_choose.setIcon(qta.icon("fa5s.list-ul", color="#2980b9"))
        btn_choose.setFixedSize(50, 45)
        btn_choose.setCursor(Qt.PointingHandCursor)
        btn_choose.setToolTip("Choisir depuis la liste pré-définie")
        btn_choose.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 8px;")
        btn_choose.clicked.connect(self._open_name_selection_dialog)
        name_lay = QHBoxLayout()
        name_lay.setSpacing(5); name_lay.setContentsMargins(0, 0, 0, 0)
        name_lay.addWidget(self.inp_name); name_lay.addWidget(btn_choose)
        name_widget = QWidget(); name_widget.setLayout(name_lay)

        # Type
        self.combo_item_type = QComboBox()
        self.combo_item_type.setFixedHeight(45); self.combo_item_type.setStyleSheet(S + F)
        self.combo_item_type.addItem("Au Poids (Or/Argent)", "WEIGHT")
        self.combo_item_type.addItem("À la Pièce (Montres, Accessoires)", "PIECE")
        self.combo_item_type.currentIndexChanged.connect(self.toggle_type_fields)

        # Combos
        self.combo_category = QComboBox(); self.combo_category.setFixedHeight(45); self.combo_category.setStyleSheet(S + F)
        self.combo_metal    = QComboBox(); self.combo_metal.setFixedHeight(45);    self.combo_metal.setStyleSheet(S + F)
        self.combo_location = QComboBox(); self.combo_location.setFixedHeight(45); self.combo_location.setStyleSheet(S + F)
        self.combo_supplier = QComboBox(); self.combo_supplier.setFixedHeight(45); self.combo_supplier.setStyleSheet(S + F)
        self.combo_receipt_mode = QComboBox(); self.combo_receipt_mode.setFixedHeight(45); self.combo_receipt_mode.setStyleSheet(S + F)
        self.combo_receipt_mode.addItem("Stock uniquement / dette deja enregistree", "INVENTORY_ONLY")
        self.combo_receipt_mode.addItem("Reception fournisseur a credit / creer un bon", "SUPPLIER_RECEIPT")
        self.combo_supplier_account = QComboBox(); self.combo_supplier_account.setFixedHeight(45); self.combo_supplier_account.setStyleSheet(S + F)
        self.combo_supplier_account.setEnabled(False)

        # SpinBoxes
        def spin_double(suffix="", max_val=10000, decimals=3):
            s = QDoubleSpinBox()
            s.setFixedHeight(45); s.setRange(0, max_val); s.setDecimals(decimals)
            s.setButtonSymbols(QAbstractSpinBox.NoButtons); s.setStyleSheet(S + F)
            if suffix: s.setSuffix(suffix)
            return s

        self.spin_weight      = spin_double(" g", 10000, 3)
        self.spin_metal_cost  = spin_double(" DA/g", 1_000_000, 2)
        self.spin_labor_cost  = spin_double(" DA/g", 1_000_000, 2)
        self.spin_total_cost  = spin_double(" DA", 100_000_000, 2)
        self.spin_selling_price = spin_double(" DA", 100_000_000, 2)
        self.spin_profit_margin = spin_double(" DA/g", 100_000_000, 2)

        self.spin_qty = QSpinBox()
        self.spin_qty.setFixedHeight(45); self.spin_qty.setRange(0, 10000); self.spin_qty.setValue(1)
        self.spin_qty.setSuffix(" pcs"); self.spin_qty.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin_qty.setStyleSheet(S + F)

        self.combo_margin_type = QComboBox()
        self.combo_margin_type.setFixedHeight(45); self.combo_margin_type.setStyleSheet(S + F)
        self.combo_margin_type.addItem("Fixe (DA)", "FIXED")
        self.combo_margin_type.addItem("Pourcentage (%)", "PERCENTAGE")

        for input_widget in (
            self.inp_barcode,
            self.inp_name,
            self.combo_item_type,
            self.combo_category,
            self.combo_metal,
            self.combo_location,
            self.combo_supplier,
            self.combo_receipt_mode,
            self.combo_supplier_account,
            self.combo_margin_type,
            self.spin_weight,
            self.spin_qty,
            self.spin_metal_cost,
            self.spin_labor_cost,
            self.spin_total_cost,
            self.spin_selling_price,
            self.spin_profit_margin,
        ):
            apply_touch_input_defaults(input_widget)
        for button in (btn_gen, btn_choose):
            apply_touch_button_defaults(button)

        # Signals
        self.spin_weight.valueChanged.connect(self.calculate_totals)
        self.spin_metal_cost.valueChanged.connect(self.calculate_totals)
        self.spin_labor_cost.valueChanged.connect(self.calculate_totals)
        self.spin_profit_margin.valueChanged.connect(self.calculate_totals)
        self.combo_margin_type.currentIndexChanged.connect(self._update_margin_suffix)
        self.combo_supplier.currentIndexChanged.connect(self._refresh_supplier_accounts)
        self.combo_receipt_mode.currentIndexChanged.connect(self._refresh_supplier_accounts)

        margin_lay = QHBoxLayout()
        margin_lay.setSpacing(5); margin_lay.setContentsMargins(0, 0, 0, 0)
        margin_lay.addWidget(self.combo_margin_type, 1)
        margin_lay.addWidget(
            wrap_with_numpad(self, self.spin_profit_margin, "Marge benefice", allow_decimal=True),
            2,
        )
        margin_widget = QWidget(); margin_widget.setLayout(margin_lay)

        # Grid layout
        grid.addLayout(vbox("Code-barres:", bc_widget),         0, 0)
        grid.addLayout(vbox("Désignation:", name_widget),       0, 1)
        grid.addLayout(vbox("Type d'Article:", self.combo_item_type), 0, 2)
        grid.addLayout(vbox("Catégorie:", self.combo_category), 1, 0)
        grid.addLayout(vbox("Métal:", self.combo_metal),        1, 1)
        grid.addLayout(vbox("Emplacement:", self.combo_location), 1, 2)
        grid.addLayout(vbox("Fournisseur:", self.combo_supplier), 2, 0)
        grid.addLayout(
            vbox("Poids (g):", wrap_with_numpad(self, self.spin_weight, "Poids", allow_decimal=True)),
            2,
            1,
        )
        grid.addLayout(
            vbox("Quantité (pcs):", wrap_with_numpad(self, self.spin_qty, "Quantite", allow_decimal=False)),
            2,
            2,
        )
        grid.addLayout(
            vbox("Coût Métal (par g):", wrap_with_numpad(self, self.spin_metal_cost, "Cout metal", allow_decimal=True)),
            3,
            0,
        )
        grid.addLayout(
            vbox("Coût Façon (par g):", wrap_with_numpad(self, self.spin_labor_cost, "Cout facon", allow_decimal=True)),
            3,
            1,
        )
        grid.addLayout(vbox("Marge Bénéfice:", margin_widget),  3, 2)
        grid.addLayout(
            vbox("Coût Total / Achat:", wrap_with_numpad(self, self.spin_total_cost, "Cout total", allow_decimal=True)),
            4,
            0,
        )
        grid.addLayout(
            vbox("Prix Vente Fixe / Auto:", wrap_with_numpad(self, self.spin_selling_price, "Prix vente", allow_decimal=True)),
            4,
            1,
        )

        grid.addLayout(vbox("Traitement fournisseur:", self.combo_receipt_mode), 5, 0)
        grid.addLayout(vbox("Compte LOCAL / IMPORT:", self.combo_supplier_account), 5, 1)

        scroll.setWidget(content)
        box_layout.addWidget(scroll)
        box_layout.addLayout(self._build_form_buttons())
        return box

    def _build_form_buttons(self) -> QHBoxLayout:
        btn_box = QHBoxLayout()
        btn_box.setSpacing(15)

        btn_clear = QPushButton(" Vider")
        btn_clear.setIcon(qta.icon("fa5s.eraser", color="#2c3e50"))
        btn_clear.setFixedHeight(55)
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet(
            "background-color: #ecf0f1; color: #2c3e50; font-weight: bold; font-size: 16px; border-radius: 8px;"
        )
        apply_touch_button_defaults(btn_clear)
        btn_clear.clicked.connect(self.clear_form)

        btn_kb = QPushButton(" ⌨️ Clavier")
        btn_kb.setFixedSize(140, 55)
        btn_kb.setCursor(Qt.PointingHandCursor)
        btn_kb.setStyleSheet(
            "background-color: #34495e; color: white; font-size: 16px; font-weight: bold; border-radius: 8px;"
        )
        apply_touch_button_defaults(btn_kb)
        btn_kb.clicked.connect(self.show_virtual_keyboard)

        self.btn_save = QPushButton(" Ajouter le Produit")
        self.btn_save.setIcon(qta.icon("fa5s.plus-circle", color="white"))
        self.btn_save.setFixedHeight(55)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; font-size: 18px; border-radius: 8px;"
        )
        apply_touch_button_defaults(self.btn_save, primary=True)
        self.btn_save.clicked.connect(self.save_item)

        btn_box.addWidget(btn_clear)
        btn_box.addWidget(btn_kb)
        btn_box.addWidget(self.btn_save, stretch=1)
        return btn_box

    def _build_recent_group(self) -> QGroupBox:
        self.recent_wrapper = QGroupBox("📦 Articles ajoutés lors de cette session")
        self.recent_wrapper.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 16px; color: #2c3e50;"
            "border: 2px solid #bdc3c7; border-radius: 8px; margin-top: 10px; background-color: white; }"
        )
        recent_layout = QVBoxLayout(self.recent_wrapper)

        self.lbl_after_save_hint = QLabel("")
        self.lbl_after_save_hint.setVisible(False)
        self.lbl_after_save_hint.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1e8449;"
            " background-color: #eafaf1; border: 1px solid #82e0aa;"
            " border-radius: 8px; padding: 8px 12px;"
        )
        recent_layout.addWidget(self.lbl_after_save_hint)

        self.table_recent = QTableWidget()
        cols = ["Code", "Article", "Poids U.", "Pds Reste", "Coût Façon", "Type Marge", "Marge", "P.Vente", "Actions"]
        self.table_recent.setColumnCount(len(cols))
        self.table_recent.setHorizontalHeaderLabels(cols)

        header = self.table_recent.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        self.table_recent.setColumnWidth(8, 170)

        self.table_recent.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_recent.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_recent.setAlternatingRowColors(True)
        self.table_recent.verticalHeader().setVisible(False)
        self.table_recent.verticalHeader().setDefaultSectionSize(55)
        apply_touch_table_defaults(self.table_recent)
        self.table_recent.verticalHeader().setDefaultSectionSize(55)
        self.table_recent.setSortingEnabled(True)
        self.table_recent.setStyleSheet("""
            QTableWidget { font-size: 15px; background-color: white; border: none; }
            QHeaderView::section {
                font-weight: bold; background-color: #ecf0f1;
                padding: 10px; border-bottom: 2px solid #bdc3c7; color: #2c3e50; font-size: 14px;
            }
        """)
        recent_layout.addWidget(self.table_recent)
        return self.recent_wrapper

    # ------------------------------------------------------------------
    # Form logic
    # ------------------------------------------------------------------

    def load_combos(self):
        try:
            self.combo_category.clear()
            for c in self.manager.categories.get_all_categories():
                self.combo_category.addItem(c['name'], c['id'])
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
        except Exception:
            pass

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

    def toggle_type_fields(self):
        is_weight = self.combo_item_type.currentData() == "WEIGHT"
        for w in (self.spin_weight, self.spin_metal_cost, self.spin_labor_cost,
                  self.spin_profit_margin, self.combo_margin_type):
            w.setEnabled(is_weight)
        self.spin_total_cost.setReadOnly(is_weight)
        self.spin_selling_price.setReadOnly(is_weight)

        base = "font-size: 16px; font-weight: bold; padding: 5px; border-radius: 8px; border: 2px solid #bdc3c7;"
        if is_weight:
            self.spin_total_cost.setStyleSheet(base + "background-color: #ecf0f1; color: #7f8c8d;")
            self.spin_selling_price.setStyleSheet(base + "background-color: #d4efdf; color: #1e8449;")
            self.calculate_totals()
        else:
            self.spin_total_cost.setStyleSheet(base + "background-color: #ffffff; color: #2c3e50;")
            self.spin_selling_price.setStyleSheet(base + "background-color: #ffffff; color: #27ae60;")

    def _update_margin_suffix(self):
        if self.combo_margin_type.currentData() == "PERCENTAGE":
            self.spin_profit_margin.setSuffix(" %")
        else:
            self.spin_profit_margin.setSuffix(" DA/g")
        self.calculate_totals()

    def calculate_totals(self):
        if not hasattr(self, 'combo_item_type') or self.combo_item_type.currentData() == "PIECE":
            return
        w  = self.spin_weight.value()
        mc = self.spin_metal_cost.value()
        lc = self.spin_labor_cost.value()
        margin = self.spin_profit_margin.value()
        margin_type = self.combo_margin_type.currentData()

        total_cost = (mc + lc) * w
        profit_per_gram = (mc + lc) * (margin / 100.0) if margin_type == 'PERCENTAGE' else margin
        self.spin_total_cost.setValue(total_cost)
        self.spin_selling_price.setValue(total_cost + profit_per_gram * w)

    def generate_barcode(self):
        now = datetime.datetime.now()
        code_12 = f"21{now.strftime('%y%j%H%M%S')}{random.randint(10, 99)}"[-12:]
        check = (10 - ((
            sum(int(code_12[i]) for i in range(12) if i % 2 == 0) +
            sum(int(code_12[i]) for i in range(12) if i % 2 != 0) * 3
        ) % 10)) % 10
        self.inp_barcode.setText(f"{code_12}{check}")

    def clear_form(self):
        self.inp_barcode.clear()
        self.inp_name.clear()
        self.spin_weight.setValue(0)
        self.spin_qty.setValue(1)
        self.combo_receipt_mode.setCurrentIndex(0)
        self._refresh_supplier_accounts()
        self.spin_metal_cost.setValue(0)
        self.spin_labor_cost.setValue(0)
        self.combo_margin_type.setCurrentIndex(0)
        self.spin_profit_margin.setValue(0)
        if self.combo_item_type.currentData() == "PIECE":
            self.spin_total_cost.setValue(0)
            self.spin_selling_price.setValue(0)
        self.calculate_totals()

    def _open_name_selection_dialog(self):
        dialog = ProductNameSelectionDialog(self.manager, self)
        if dialog.exec() == QDialog.Accepted:
            name = dialog.get_selected_name()
            if name:
                self.inp_name.setText(name)
                self.combo_item_type.setFocus()

    def save_item(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom est obligatoire. Saisissez un nom ou utilisez le bouton de selection.")
            return
        if self.combo_category.currentData() is None:
            QMessageBox.warning(self, "Erreur", "Selectionnez une categorie avant d'ajouter le produit.")
            return
        if self.combo_item_type.currentData() == "WEIGHT" and self.spin_weight.value() <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez un poids superieur a 0 g pour un article au poids.")
            return
        if self.spin_qty.value() <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez une quantite superieure a 0.")
            return

        data = {
            "barcode":            self.inp_barcode.text().strip() or None,
            "name":               name,
            "item_type":          self.combo_item_type.currentData(),
            "category_id":        self.combo_category.currentData(),
            "metal_type_id":      self.combo_metal.currentData(),
            "weight":             self.spin_weight.value(),
            "quantity":           self.spin_qty.value(),
            "metal_cost_per_gram": self.spin_metal_cost.value(),
            "labor_cost_per_gram": self.spin_labor_cost.value(),
            "profit_margin":      self.spin_profit_margin.value(),
            "margin_type":        self.combo_margin_type.currentData(),
            "total_cost":         self.spin_total_cost.value(),
            "selling_price":      self.spin_selling_price.value(),
            "location_id":        self.combo_location.currentData(),
            "supplier_id":        self.combo_supplier.currentData(),
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
                    user_id=active_user_id.get(),
                    description=data["name"],
                )
                if not success:
                    QMessageBox.critical(self, "Reception fournisseur", message)
                    return
            else:
                new_id = self.manager.inventory.add_item(**data)
            if new_id:
                self.item_saved.emit()
                new_item_data = self.manager.inventory.get_item_by_id(new_id) or {
                    'id': new_id, **data
                }
                self.session_added_items.insert(0, new_item_data)
                self.update_recent_table()
                self.clear_form()
                self.inp_barcode.setFocus()
                if hasattr(self, "lbl_after_save_hint"):
                    self.lbl_after_save_hint.setText(after_save_options_text(new_item_data.get("name", name)))
                    self.lbl_after_save_hint.setVisible(True)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ajouter le produit : {e}")

    # ------------------------------------------------------------------
    # Recent table
    # ------------------------------------------------------------------

    def update_recent_table(self):
        self.table_recent.setSortingEnabled(False)
        self.table_recent.setRowCount(len(self.session_added_items))

        for row, item in enumerate(self.session_added_items):
            i_type = item.get('item_type', 'WEIGHT')

            self.table_recent.setItem(row, 0, QTableWidgetItem(str(item.get('barcode') or "-")))

            name_item = QTableWidgetItem(str(item.get('name') or ""))
            name_item.setData(Qt.UserRole, item)
            self.table_recent.setItem(row, 1, name_item)

            w_val = float(item.get('weight') or 0)
            w_item = SortableTableWidgetItem(f"{w_val:.2f} g" if i_type == 'WEIGHT' else "-", w_val)
            w_item.setTextAlignment(Qt.AlignCenter)
            self.table_recent.setItem(row, 2, w_item)

            rw_val = float(item.get('remaining_weight') or 0)
            rw_item = SortableTableWidgetItem(f"{rw_val:.2f} g" if i_type == 'WEIGHT' else "-", rw_val)
            rw_item.setTextAlignment(Qt.AlignCenter)
            rw_item.setForeground(QColor("#27ae60"))
            rw_item.setFont(QFont("", 11, QFont.Bold))
            self.table_recent.setItem(row, 3, rw_item)

            labor_val = float(item.get('labor_cost_per_gram') or 0)
            labor_item = SortableTableWidgetItem(f"{labor_val:,.2f} DA", labor_val)
            labor_item.setTextAlignment(Qt.AlignCenter)
            self.table_recent.setItem(row, 4, labor_item)

            margin_type = item.get('margin_type', 'FIXED')
            mt_item = QTableWidgetItem("%" if margin_type == "PERCENTAGE" else "Fixe")
            mt_item.setTextAlignment(Qt.AlignCenter)
            self.table_recent.setItem(row, 5, mt_item)

            margin_val = float(item.get('profit_margin') or 0)
            suffix = "%" if margin_type == "PERCENTAGE" else "DA"
            mg_item = SortableTableWidgetItem(f"{margin_val:,.2f} {suffix}", margin_val)
            mg_item.setTextAlignment(Qt.AlignCenter)
            mg_item.setForeground(QColor("#2980b9"))
            mg_item.setFont(QFont("", 11, QFont.Bold))
            self.table_recent.setItem(row, 6, mg_item)

            price_val = float(item.get('selling_price') or 0)
            p_item = SortableTableWidgetItem(f"{price_val:,.2f} DA", price_val)
            p_item.setForeground(QColor("#27ae60"))
            p_item.setFont(QFont("", 12, QFont.Bold))
            p_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table_recent.setItem(row, 7, p_item)

            # Buttons
            container = QWidget()
            bl = QHBoxLayout(container)
            bl.setContentsMargins(5, 5, 5, 5); bl.setSpacing(10)

            def make_btn(icon_name, color, bg, callback):
                btn = QPushButton()
                btn.setIcon(qta.icon(icon_name, color=color))
                btn.setFixedSize(48, 48)
                apply_touch_button_defaults(btn)
                btn.setStyleSheet(f"background-color: {bg}; border-radius: 8px;")
                btn.clicked.connect(callback)
                return btn

            bl.addWidget(make_btn("fa5s.print", "#34495e", "#ecf0f1", lambda _, d=item: self._print_recent_item(d)))
            bl.addWidget(make_btn("fa5s.edit",  "#f39c12", "#fdf2e9", lambda _, d=item: self._edit_recent_item(d)))
            bl.addWidget(make_btn("fa5s.trash", "#c0392b", "#fadbd8", lambda _, d=item: self._delete_recent_item(d)))
            self.table_recent.setCellWidget(row, 8, container)

        self.table_recent.setSortingEnabled(True)

    def _print_recent_item(self, item_data: dict):
        label_config = load_label_config(self)
        if label_config is None:
            return
        if not label_config.get("printer_name"):
            QMessageBox.warning(self, "Erreur", "Aucune imprimante sélectionnée.")
            return
        LabelPrintPreviewDialog(label_config, item_data, self).exec()

    def _edit_recent_item(self, item_data: dict):
        dialog = ProductEditDialog(self.manager, item_data, self)
        if dialog.exec():
            updated = self.manager.inventory.get_item_by_id(item_data['id'])
            if updated:
                for i, itm in enumerate(self.session_added_items):
                    if itm['id'] == item_data['id']:
                        self.session_added_items[i] = updated
                        break
                self.update_recent_table()
                self.item_saved.emit()

    def _delete_recent_item(self, item_data: dict):
        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous vraiment supprimer '{item_data['name']}' ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if self.manager.inventory.delete_item(item_data['id']):
                self.session_added_items = [
                    i for i in self.session_added_items if i['id'] != item_data['id']
                ]
                self.update_recent_table()
                self.item_saved.emit()

    def refresh_data(self):
        self.load_combos()
