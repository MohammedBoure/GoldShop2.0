import random
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QGroupBox, QDialog,
    QMessageBox, QComboBox, QDoubleSpinBox, QLabel, QSpinBox,
    QScrollArea, QSplitter, QGridLayout, QSizePolicy, QAbstractSpinBox,
    QApplication
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults
from ui.widgets.inventory.touch_product_entry import wrap_with_numpad

# ============================================================
# 3. FormInputSection — قسم حقول الإدخال
# ============================================================
class FormInputSection(QWidget):
    """
    يحتوي على جميع حقول الإدخال (باركود، اسم، نوع، مورد…)
    والـ QScrollArea الخاص بها.
    يُصدر إشارة recalculate_requested عند تغيير أي قيمة مؤثرة.
    """

    recalculate_requested = Signal()

    _INPUT_STYLE = (
        "font-size: 16px; font-weight: bold; padding: 5px 10px;"
        " border: 2px solid #bdc3c7; border-radius: 8px; background-color: #f9f9f9;"
    )
    _FOCUS_STYLE = (
        "QLineEdit:focus, QDoubleSpinBox:focus,"
        " QSpinBox:focus, QComboBox:focus"
        " { border: 2px solid #3498db; background-color: white; }"
    )

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._build_ui()

    # ----------------------------------------------------------
    # بناء الواجهة
    # ----------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        content = QWidget()
        grid = QGridLayout(content)
        grid.setVerticalSpacing(15)
        grid.setHorizontalSpacing(25)

        s = self._INPUT_STYLE + self._FOCUS_STYLE

        # --- Barcode ---
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setFixedHeight(45)
        self.inp_barcode.setStyleSheet(s)

        btn_gen = QPushButton()
        btn_gen.setIcon(qta.icon("fa5s.magic", color="#d4af37"))
        btn_gen.setFixedSize(50, 45)
        btn_gen.setCursor(Qt.PointingHandCursor)
        apply_touch_button_defaults(btn_gen)
        btn_gen.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 8px;")
        btn_gen.clicked.connect(self._generate_barcode)
        bc_widget = self._hbox(self.inp_barcode, btn_gen)

        # --- Name ---
        self.inp_name = QLineEdit()
        self.inp_name.setFixedHeight(45)
        self.inp_name.setPlaceholderText("Saisir manuellement ou choisir...")
        self.inp_name.setStyleSheet(s)

        btn_name = QPushButton()
        btn_name.setIcon(qta.icon("fa5s.list-ul", color="#2980b9"))
        btn_name.setFixedSize(50, 45)
        btn_name.setCursor(Qt.PointingHandCursor)
        btn_name.setToolTip("Choisir depuis la liste pré-définie")
        btn_name.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 8px;")
        apply_touch_button_defaults(btn_name)
        btn_name.clicked.connect(self._open_name_dialog)
        name_widget = self._hbox(self.inp_name, btn_name)

        # --- Item type ---
        self.combo_item_type = QComboBox()
        self.combo_item_type.setFixedHeight(45)
        self.combo_item_type.setStyleSheet(s)
        self.combo_item_type.addItem("Au Poids (Or/Argent)", "WEIGHT")
        self.combo_item_type.addItem("À la Pièce (Montres, Accessoires)", "PIECE")

        # --- Category ---
        self.combo_category = QComboBox()
        self.combo_category.setFixedHeight(45)
        self.combo_category.setStyleSheet(s)

        btn_cat = QPushButton()
        btn_cat.setIcon(qta.icon("fa5s.list-ul", color="#2980b9"))
        btn_cat.setFixedSize(50, 45)
        btn_cat.setCursor(Qt.PointingHandCursor)
        btn_cat.setToolTip("Choisir une catégorie")
        btn_cat.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 8px;")
        apply_touch_button_defaults(btn_cat)
        btn_cat.clicked.connect(self._open_category_dialog)
        cat_widget = self._hbox(self.combo_category, btn_cat)

        # --- Metal / Location ---
        self.combo_metal = QComboBox()
        self.combo_metal.setFixedHeight(45)
        self.combo_metal.setStyleSheet(s)

        self.combo_location = QComboBox()
        self.combo_location.setFixedHeight(45)
        self.combo_location.setStyleSheet(s)

        # --- Supplier ---
        self.combo_supplier = QComboBox()
        self.combo_supplier.setFixedHeight(45)
        self.combo_supplier.setStyleSheet(s)

        self.combo_receipt_mode = QComboBox()
        self.combo_receipt_mode.setFixedHeight(45)
        self.combo_receipt_mode.setStyleSheet(s)
        self.combo_receipt_mode.addItem("Stock uniquement / dette deja enregistree", "INVENTORY_ONLY")
        self.combo_receipt_mode.addItem("Reception fournisseur a credit / creer un bon", "SUPPLIER_RECEIPT")

        self.combo_supplier_account = QComboBox()
        self.combo_supplier_account.setFixedHeight(45)
        self.combo_supplier_account.setStyleSheet(s)
        self.combo_supplier_account.setEnabled(False)

        btn_supp = QPushButton()
        btn_supp.setIcon(qta.icon("fa5s.list-ul", color="#2980b9"))
        btn_supp.setFixedSize(50, 45)
        btn_supp.setCursor(Qt.PointingHandCursor)
        btn_supp.setToolTip("Choisir un fournisseur")
        btn_supp.setStyleSheet("background-color: #ecf0f1; border: 2px solid #bdc3c7; border-radius: 8px;")
        apply_touch_button_defaults(btn_supp)
        btn_supp.clicked.connect(self._open_supplier_dialog)
        supp_widget = self._hbox(self.combo_supplier, btn_supp)

        # --- Spinboxes ---
        self.spin_weight      = self._dspin(suffix=" g",     max_val=10000,     decimals=3)
        self.spin_qty         = self._spin(suffix=" pcs",    max_val=10000,     default=1)
        self.spin_metal_cost  = self._dspin(suffix=" DA/g",  max_val=1_000_000)
        self.spin_labor_cost  = self._dspin(suffix=" DA/g",  max_val=1_000_000)
        self.spin_total_cost  = self._dspin(suffix=" DA",    max_val=100_000_000)
        self.spin_selling_price = self._dspin(suffix=" DA",  max_val=100_000_000)

        # --- Margin ---
        self.combo_margin_type = QComboBox()
        self.combo_margin_type.setFixedHeight(45)
        self.combo_margin_type.setStyleSheet(s)
        self.combo_margin_type.addItem("Fixe (DA)", "FIXED")
        self.combo_margin_type.addItem("Pourcentage (%)", "PERCENTAGE")

        self.spin_profit_margin = self._dspin(suffix=" DA/g", max_val=100_000_000)

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

        margin_row = QHBoxLayout()
        margin_row.setSpacing(5)
        margin_row.setContentsMargins(0, 0, 0, 0)
        margin_row.addWidget(self.combo_margin_type, 1)
        margin_row.addWidget(
            wrap_with_numpad(self, self.spin_profit_margin, "Marge benefice", allow_decimal=True),
            2,
        )
        margin_widget = QWidget()
        margin_widget.setLayout(margin_row)

        # --- Connect signals for recalculation ---
        for w in (self.spin_weight, self.spin_metal_cost,
                  self.spin_labor_cost, self.spin_profit_margin):
            w.valueChanged.connect(self.recalculate_requested)
        self.combo_margin_type.currentIndexChanged.connect(self._on_margin_type_changed)
        self.combo_supplier.currentIndexChanged.connect(self._refresh_supplier_accounts)
        self.combo_receipt_mode.currentIndexChanged.connect(self._refresh_supplier_accounts)

        # --- Layout grid ---
        def vbox(label, widget):
            lay = QVBoxLayout()
            lay.setSpacing(3)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #34495e;")
            lay.addWidget(lbl)
            lay.addWidget(widget) if isinstance(widget, QWidget) else lay.addLayout(widget)
            return lay

        grid.addLayout(vbox("Code-barres:",       bc_widget),           0, 0)
        grid.addLayout(vbox("Désignation:",        name_widget),         0, 1)
        grid.addLayout(vbox("Type d'Article:",     self.combo_item_type),0, 2)
        grid.addLayout(vbox("Catégorie:",          cat_widget),          1, 0)
        grid.addLayout(vbox("Métal:",              self.combo_metal),    1, 1)
        grid.addLayout(vbox("Emplacement:",        self.combo_location), 1, 2)
        grid.addLayout(vbox("Fournisseur:",        supp_widget),         2, 0)
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
        grid.addLayout(vbox("Marge Bénéfice:",     margin_widget),       3, 2)
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
        outer.addWidget(scroll)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    @staticmethod
    def _hbox(*widgets):
        lay = QHBoxLayout()
        lay.setSpacing(5)
        lay.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            lay.addWidget(w)
        container = QWidget()
        container.setLayout(lay)
        return container

    def _dspin(self, suffix="", max_val=10000, decimals=2):
        sp = QDoubleSpinBox()
        sp.setFixedHeight(45)
        sp.setRange(0, max_val)
        sp.setDecimals(decimals)
        sp.setSuffix(suffix)
        sp.setButtonSymbols(QAbstractSpinBox.NoButtons)
        sp.setStyleSheet(
            self._INPUT_STYLE + self._FOCUS_STYLE
        )
        return sp

    def _spin(self, suffix="", max_val=10000, default=0):
        sp = QSpinBox()
        sp.setFixedHeight(45)
        sp.setRange(0, max_val)
        sp.setValue(default)
        sp.setSuffix(suffix)
        sp.setButtonSymbols(QAbstractSpinBox.NoButtons)
        sp.setStyleSheet(
            self._INPUT_STYLE + self._FOCUS_STYLE
        )
        return sp

    # ----------------------------------------------------------
    # Slots — نوافذ الاختيار
    # ----------------------------------------------------------
    def _open_name_dialog(self):
        from ui.dialogs.product_name_selection import ProductNameSelectionDialog

        dialog = ProductNameSelectionDialog(self.manager, self)
        if dialog.exec() == QDialog.Accepted:
            name = dialog.get_selected_name()
            if name:
                self.inp_name.setText(name)
                self.combo_item_type.setFocus()

    def _open_category_dialog(self):
        from ui.dialogs.category_selection import CategorySelectionDialog

        dialog = CategorySelectionDialog(self.manager, self)
        if dialog.exec() == QDialog.Accepted:
            cid = dialog.get_selected_category_id()
            if cid is not None:
                idx = self.combo_category.findData(cid)
                if idx >= 0:
                    self.combo_category.setCurrentIndex(idx)
                    self.combo_metal.setFocus()

    def _open_supplier_dialog(self):
        from ui.dialogs.supplier_selection import SupplierSelectionDialog

        dialog = SupplierSelectionDialog(self.manager, self)
        if dialog.exec() == QDialog.Accepted:
            sid = dialog.get_selected_supplier_id()
            if sid is not None:
                idx = self.combo_supplier.findData(sid)
                if idx >= 0:
                    self.combo_supplier.setCurrentIndex(idx)
                    self.spin_weight.setFocus()

    def _generate_barcode(self):
        now = datetime.datetime.now()
        code12 = f"21{now.strftime('%y%j%H%M%S')}{random.randint(10, 99)}"[-12:]
        check = (10 - (
            (sum(int(code12[i]) for i in range(12) if i % 2 == 0) +
             sum(int(code12[i]) for i in range(12) if i % 2 != 0) * 3) % 10
        )) % 10
        self.inp_barcode.setText(f"{code12}{check}")

    def _on_margin_type_changed(self):
        if self.combo_margin_type.currentData() == "PERCENTAGE":
            self.spin_profit_margin.setSuffix(" %")
        else:
            self.spin_profit_margin.setSuffix(" DA/g")
        self.recalculate_requested.emit()

    # ----------------------------------------------------------
    # API عام
    # ----------------------------------------------------------
    def load_combos(self):
        try:
            self.combo_category.clear()
            for c in self.manager.categories.get_all_categories():
                self.combo_category.addItem(c["name"], c["id"])

            self.combo_metal.clear()
            for m in self.manager.metal_types.get_all_metal_types():
                self.combo_metal.addItem(f"{m['name']} ({m['purity_value']})", m["id"])

            self.combo_location.clear()
            for loc in self.manager.storage_locations.get_all_locations():
                self.combo_location.addItem(loc["name"], loc["id"])

            self.combo_supplier.clear()
            for s in self.manager.suppliers.get_all_suppliers():
                self.combo_supplier.addItem(s["name"], s["id"])
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

    def get_receipt_posting_data(self):
        if self.combo_receipt_mode.currentData() != "SUPPLIER_RECEIPT":
            return None
        if self.combo_item_type.currentData() != "WEIGHT":
            raise ValueError("La reception fournisseur a credit est reservee aux articles au poids.")
        supplier_id = self.combo_supplier.currentData()
        account_id = self.combo_supplier_account.currentData()
        if not supplier_id or not account_id:
            raise ValueError("Selectionnez un fournisseur et un compte LOCAL/IMPORT actif.")
        return {"supplier_id": supplier_id, "supplier_account_id": account_id}

    def toggle_weight_fields(self, is_weight: bool):
        """تفعيل/تعطيل الحقول المرتبطة بالوزن حسب نوع المنتج."""
        for w in (self.spin_weight, self.spin_metal_cost,
                  self.spin_labor_cost, self.spin_profit_margin,
                  self.combo_margin_type):
            w.setEnabled(is_weight)

        self.spin_total_cost.setReadOnly(is_weight)
        self.spin_selling_price.setReadOnly(is_weight)

        base = "font-size: 16px; font-weight: bold; padding: 5px; border-radius: 8px; border: 2px solid #bdc3c7;"
        if is_weight:
            self.spin_total_cost.setStyleSheet(base + "background-color: #ecf0f1; color: #7f8c8d;")
            self.spin_selling_price.setStyleSheet(base + "background-color: #d4efdf; color: #1e8449;")
        else:
            self.spin_total_cost.setStyleSheet(base + "background-color: #ffffff; color: #2c3e50;")
            self.spin_selling_price.setStyleSheet(base + "background-color: #ffffff; color: #27ae60;")

    def get_form_data(self) -> dict:
        """يُعيد dict بجميع قيم النموذج."""
        return {
            "barcode":            self.inp_barcode.text().strip() or None,
            "name":               self.inp_name.text().strip(),
            "item_type":          self.combo_item_type.currentData(),
            "category_id":        self.combo_category.currentData(),
            "metal_type_id":      self.combo_metal.currentData(),
            "weight":             self.spin_weight.value(),
            "quantity":           self.spin_qty.value(),
            "metal_cost_per_gram":self.spin_metal_cost.value(),
            "labor_cost_per_gram":self.spin_labor_cost.value(),
            "profit_margin":      self.spin_profit_margin.value(),
            "margin_type":        self.combo_margin_type.currentData(),
            "total_cost":         self.spin_total_cost.value(),
            "selling_price":      self.spin_selling_price.value(),
            "location_id":        self.combo_location.currentData(),
            "supplier_id":        self.combo_supplier.currentData(),
        }

    def clear(self, full: bool = True):
        self.inp_barcode.clear()
        self.spin_weight.setValue(0)
        self.spin_qty.setValue(1)
        self.combo_receipt_mode.setCurrentIndex(0)
        self._refresh_supplier_accounts()
        if full:
            self.inp_name.clear()
            self.spin_metal_cost.setValue(0)
            self.spin_labor_cost.setValue(0)
            self.spin_profit_margin.setValue(0)
            self.combo_metal.setCurrentIndex(0)
            self.combo_category.setCurrentIndex(0)

    def restore_state(self, state: dict):
        self.inp_name.setText(state.get("name", ""))
        self.spin_metal_cost.setValue(state.get("metal_cost", 0))
        self.spin_labor_cost.setValue(state.get("labor_cost", 0))
        self.spin_profit_margin.setValue(state.get("margin", 0))

        for combo, key in (
            (self.combo_metal,        "metal_type_id"),
            (self.combo_category,     "category_id"),
            (self.combo_supplier,     "supplier_id"),
            (self.combo_location,     "location_id"),
            (self.combo_item_type,    "item_type"),
            (self.combo_margin_type,  "margin_type"),
        ):
            idx = combo.findData(state.get(key))
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def build_state(self) -> dict:
        return {
            "name":         self.inp_name.text(),
            "category_id":  self.combo_category.currentData(),
            "metal_type_id":self.combo_metal.currentData(),
            "metal_cost":   self.spin_metal_cost.value(),
            "labor_cost":   self.spin_labor_cost.value(),
            "margin":       self.spin_profit_margin.value(),
            "margin_type":  self.combo_margin_type.currentData(),
            "location_id":  self.combo_location.currentData(),
            "supplier_id":  self.combo_supplier.currentData(),
            "item_type":    self.combo_item_type.currentData(),
        }
