import random
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QComboBox, QDoubleSpinBox, QLabel, QSpinBox,
    QScrollArea, QGridLayout, QAbstractSpinBox, QFrame,
    QSizePolicy, QDialog
)
from PySide6.QtCore import Qt, Signal, QEvent
import qtawesome as qta

from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults
from ui.widgets.inventory.touch_product_entry import wrap_with_numpad

# ============================================================
# FormInputSection — قسم حقول الإدخال عالي السرعة والكفاءة
# ============================================================
class FormInputSection(QWidget):
    """
    نموذج إدخال سريع عالي الإنتاجية وشديد المرونة والتجاوب (Fully Fluid Subgrid):
    - سياسات حجم توسعية (QSizePolicy.Expanding) لجميع الحقول لمنع اقتصاص النصوص.
    - أبعاد ثابتة وصغيرة (34px) للأزرار المساعدة بدون حجز تركيز (Qt.NoFocus).
    - توزيع أعمدة متوازن بنسب متساوية (Column Stretch) يمتد بسلاسة مع الشاشة.
    - بطاقات حسابات مميزة بصرياً مع دعم الإدخال السريع عبر ماسح الباركود وزر Enter.
    """

    recalculate_requested = Signal()
    submit_requested = Signal()

    _INPUT_STYLE = (
        "QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {"
        "  font-size: 13px; font-weight: 600; color: #111827;"
        "  background-color: #ffffff; border: 1.5px solid #cbd5e1;"
        "  border-radius: 6px; padding: 2px 6px; min-height: 32px; max-height: 36px;"
        "}"
        "QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {"
        "  border: 2px solid #2563eb; background-color: #ffffff;"
        "}"
        "QComboBox::drop-down {"
        "  subcontrol-origin: padding; subcontrol-position: top right;"
        "  width: 20px; border-left: 1px solid #e2e8f0;"
        "}"
    )

    _BUTTON_HELPER_STYLE = (
        "QPushButton {"
        "  background-color: #f1f5f9; border: 1.5px solid #cbd5e1;"
        "  border-radius: 6px; min-height: 32px; max-height: 34px;"
        "}"
        "QPushButton:hover {"
        "  background-color: #e2e8f0; border-color: #94a3b8;"
        "}"
        "QPushButton:pressed {"
        "  background-color: #cbd5e1;"
        "}"
    )

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_ui()

    # ----------------------------------------------------------
    # بناء الواجهة
    # ----------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet(self._INPUT_STYLE)
        grid = QGridLayout(content)
        grid.setVerticalSpacing(6)
        grid.setHorizontalSpacing(10)
        grid.setContentsMargins(4, 4, 4, 4)

        # Equal column stretching for fluid resizing
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        # ------------------------------------------------------
        # 1. Barcode
        # ------------------------------------------------------
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.inp_barcode.setPlaceholderText("Scanner ou générer...")
        self.inp_barcode.returnPressed.connect(self._on_barcode_return)

        btn_gen = QPushButton()
        btn_gen.setIcon(qta.icon("fa5s.magic", color="#d97706"))
        btn_gen.setFixedSize(34, 34)
        btn_gen.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_gen.setCursor(Qt.PointingHandCursor)
        btn_gen.setToolTip("Générer un code-barres aléatoire sécurisé")
        btn_gen.setFocusPolicy(Qt.NoFocus)
        btn_gen.setStyleSheet(self._BUTTON_HELPER_STYLE)
        apply_touch_button_defaults(btn_gen)
        btn_gen.clicked.connect(self._generate_barcode)
        bc_widget = self._hbox(self.inp_barcode, btn_gen)

        # ------------------------------------------------------
        # 2. Designation (Name)
        # ------------------------------------------------------
        self.inp_name = QLineEdit()
        self.inp_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.inp_name.setPlaceholderText("Désignation du bijou...")
        self.inp_name.returnPressed.connect(self._on_name_return)

        btn_name = QPushButton()
        btn_name.setIcon(qta.icon("fa5s.list-ul", color="#2563eb"))
        btn_name.setFixedSize(34, 34)
        btn_name.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_name.setCursor(Qt.PointingHandCursor)
        btn_name.setToolTip("Sélectionner un nom prédéfini")
        btn_name.setFocusPolicy(Qt.NoFocus)
        btn_name.setStyleSheet(self._BUTTON_HELPER_STYLE)
        apply_touch_button_defaults(btn_name)
        btn_name.clicked.connect(self._open_name_dialog)
        name_widget = self._hbox(self.inp_name, btn_name)

        # ------------------------------------------------------
        # 3. Type d'article
        # ------------------------------------------------------
        self.combo_item_type = QComboBox()
        self.combo_item_type.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_item_type.addItem("Au Poids (Or/Argent)", "WEIGHT")
        self.combo_item_type.addItem("À la Pièce (Montres, Accessoires)", "PIECE")

        # ------------------------------------------------------
        # 4. Catégorie
        # ------------------------------------------------------
        self.combo_category = QComboBox()
        self.combo_category.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn_cat = QPushButton()
        btn_cat.setIcon(qta.icon("fa5s.th-list", color="#2563eb"))
        btn_cat.setFixedSize(34, 34)
        btn_cat.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_cat.setCursor(Qt.PointingHandCursor)
        btn_cat.setToolTip("Choisir la catégorie")
        btn_cat.setFocusPolicy(Qt.NoFocus)
        btn_cat.setStyleSheet(self._BUTTON_HELPER_STYLE)
        apply_touch_button_defaults(btn_cat)
        btn_cat.clicked.connect(self._open_category_dialog)
        cat_widget = self._hbox(self.combo_category, btn_cat)

        # ------------------------------------------------------
        # 5. Métal & Emplacement
        # ------------------------------------------------------
        self.combo_metal = QComboBox()
        self.combo_metal.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.combo_location = QComboBox()
        self.combo_location.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # ------------------------------------------------------
        # 6. Fournisseur & Réception
        # ------------------------------------------------------
        self.combo_supplier = QComboBox()
        self.combo_supplier.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        btn_supp = QPushButton()
        btn_supp.setIcon(qta.icon("fa5s.user-tag", color="#2563eb"))
        btn_supp.setFixedSize(34, 34)
        btn_supp.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_supp.setCursor(Qt.PointingHandCursor)
        btn_supp.setToolTip("Choisir le fournisseur")
        btn_supp.setFocusPolicy(Qt.NoFocus)
        btn_supp.setStyleSheet(self._BUTTON_HELPER_STYLE)
        apply_touch_button_defaults(btn_supp)
        btn_supp.clicked.connect(self._open_supplier_dialog)
        supp_widget = self._hbox(self.combo_supplier, btn_supp)

        self.combo_receipt_mode = QComboBox()
        self.combo_receipt_mode.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_receipt_mode.addItem("Stock uniquement (Sans dette)", "INVENTORY_ONLY")
        self.combo_receipt_mode.addItem("Réception à crédit (Bon Fournisseur)", "SUPPLIER_RECEIPT")

        self.combo_supplier_account = QComboBox()
        self.combo_supplier_account.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_supplier_account.setEnabled(False)

        # ------------------------------------------------------
        # 7. Spinboxes (Valeurs numériques)
        # ------------------------------------------------------
        self.spin_weight       = self._dspin(suffix=" g",    max_val=10000,     decimals=3)
        self.spin_qty          = self._spin(suffix=" pcs",   max_val=10000,     default=1)
        self.spin_metal_cost   = self._dspin(suffix=" DA/g", max_val=1_000_000)
        self.spin_labor_cost   = self._dspin(suffix=" DA/g", max_val=1_000_000)
        self.spin_total_cost   = self._dspin(suffix=" DA",   max_val=100_000_000)
        self.spin_selling_price= self._dspin(suffix=" DA",   max_val=100_000_000)

        # Enter key filter on numeric inputs
        for spin in (
            self.spin_weight, self.spin_qty, self.spin_metal_cost,
            self.spin_labor_cost, self.spin_total_cost, self.spin_selling_price
        ):
            spin.installEventFilter(self)

        # ------------------------------------------------------
        # 8. Marge Bénéfice
        # ------------------------------------------------------
        self.combo_margin_type = QComboBox()
        self.combo_margin_type.addItem("Fixe (DA)", "FIXED")
        self.combo_margin_type.addItem("Pourcentage (%)", "PERCENTAGE")
        self.combo_margin_type.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.combo_margin_type.setMinimumWidth(90)
        self.combo_margin_type.setMaximumWidth(125)

        self.spin_profit_margin = self._dspin(suffix=" DA/g", max_val=100_000_000)
        self.spin_profit_margin.installEventFilter(self)

        margin_row = QHBoxLayout()
        margin_row.setSpacing(4)
        margin_row.setContentsMargins(0, 0, 0, 0)
        margin_row.addWidget(self.combo_margin_type, 1)
        margin_row.addWidget(
            wrap_with_numpad(self, self.spin_profit_margin, "Marge bénéfice", allow_decimal=True),
            2
        )
        margin_widget = QWidget()
        margin_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        margin_widget.setLayout(margin_row)

        # ------------------------------------------------------
        # 9. Touch input defaults
        # ------------------------------------------------------
        for widget in (
            self.inp_barcode, self.inp_name, self.combo_item_type,
            self.combo_category, self.combo_metal, self.combo_location,
            self.combo_supplier, self.combo_receipt_mode, self.combo_supplier_account,
            self.combo_margin_type, self.spin_weight, self.spin_qty,
            self.spin_metal_cost, self.spin_labor_cost, self.spin_total_cost,
            self.spin_selling_price, self.spin_profit_margin,
        ):
            apply_touch_input_defaults(widget)

        # ------------------------------------------------------
        # 10. Signals for live recalculation
        # ------------------------------------------------------
        for w in (self.spin_weight, self.spin_metal_cost,
                  self.spin_labor_cost, self.spin_profit_margin):
            w.valueChanged.connect(self.recalculate_requested)
        self.combo_margin_type.currentIndexChanged.connect(self._on_margin_type_changed)
        self.combo_supplier.currentIndexChanged.connect(self._refresh_supplier_accounts)
        self.combo_receipt_mode.currentIndexChanged.connect(self._refresh_supplier_accounts)

        # ------------------------------------------------------
        # 11. Distinct Calculation Badges (Row 5)
        # ------------------------------------------------------
        self.card_cost, self.lbl_card_cost = self._build_calc_badge(
            title="💰 Coût Total (Achat)",
            spin_widget=self.spin_total_cost,
            is_emerald=False
        )
        self.card_price, self.lbl_card_price = self._build_calc_badge(
            title="🏷️ Prix de Vente (Calculé)",
            spin_widget=self.spin_selling_price,
            is_emerald=True
        )

        # ------------------------------------------------------
        # 12. Dense Grid Placement (3 Columns)
        # ------------------------------------------------------
        # Row 0: Identification
        grid.addWidget(self._field("Code-barres:", bc_widget), 0, 0)
        grid.addWidget(self._field("Désignation:", name_widget), 0, 1)
        grid.addWidget(self._field("Type d'Article:", self.combo_item_type), 0, 2)

        # Row 1: Classification & Location
        grid.addWidget(self._field("Catégorie:", cat_widget), 1, 0)
        grid.addWidget(self._field("Métal / Titre:", self.combo_metal), 1, 1)
        grid.addWidget(self._field("Emplacement:", self.combo_location), 1, 2)

        # Row 2: Supplier & Receipt Mode
        grid.addWidget(self._field("Fournisseur:", supp_widget), 2, 0)
        grid.addWidget(self._field("Traitement:", self.combo_receipt_mode), 2, 1)
        grid.addWidget(self._field("Compte Fournisseur:", self.combo_supplier_account), 2, 2)

        # Row 3: Quantities & Metal Cost
        grid.addWidget(
            self._field("Poids (g):", wrap_with_numpad(self, self.spin_weight, "Poids", allow_decimal=True)),
            3, 0
        )
        grid.addWidget(
            self._field("Quantité (pcs):", wrap_with_numpad(self, self.spin_qty, "Quantité", allow_decimal=False)),
            3, 1
        )
        grid.addWidget(
            self._field("Coût Métal (DA/g):", wrap_with_numpad(self, self.spin_metal_cost, "Coût métal", allow_decimal=True)),
            3, 2
        )

        # Row 4: Labor Cost & Margin
        grid.addWidget(
            self._field("Coût Façon (DA/g):", wrap_with_numpad(self, self.spin_labor_cost, "Coût façon", allow_decimal=True)),
            4, 0
        )
        grid.addWidget(self._field("Marge Bénéfice:", margin_widget), 4, 1, 1, 2)

        # Row 5: Calculation Badges (Spans all columns)
        badges_row = QHBoxLayout()
        badges_row.setSpacing(10)
        badges_row.setContentsMargins(0, 2, 0, 2)
        badges_row.addWidget(self.card_cost, 1)
        badges_row.addWidget(self.card_price, 1)
        badges_container = QWidget()
        badges_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        badges_container.setLayout(badges_row)
        grid.addWidget(badges_container, 5, 0, 1, 3)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        # Establish default tab sequence
        self.setup_tab_order()

    # ----------------------------------------------------------
    # Event Filter for Enter key submission
    # ----------------------------------------------------------
    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.submit_requested.emit()
            return True
        return super().eventFilter(watched, event)

    def _on_barcode_return(self):
        barcode = self.inp_barcode.text().strip()
        if not barcode:
            return
        if not self.inp_name.text().strip():
            self.inp_name.setFocus()
            self.inp_name.selectAll()
        elif self.spin_weight.isEnabled() and self.spin_weight.value() <= 0:
            self.spin_weight.setFocus()
            self.spin_weight.selectAll()
        else:
            self.submit_requested.emit()

    def _on_name_return(self):
        if self.spin_weight.isEnabled() and self.spin_weight.value() <= 0:
            self.spin_weight.setFocus()
            self.spin_weight.selectAll()
        else:
            self.submit_requested.emit()

    # ----------------------------------------------------------
    # Strict Tab Order
    # ----------------------------------------------------------
    def setup_tab_order(self, next_widget=None):
        """Builds an uninterrupted, linear Tab navigation chain."""
        order = [
            self.inp_barcode,
            self.inp_name,
            self.combo_item_type,
            self.combo_category,
            self.combo_metal,
            self.combo_location,
            self.combo_supplier,
            self.combo_receipt_mode,
        ]
        if self.combo_supplier_account.isEnabled():
            order.append(self.combo_supplier_account)

        order.extend([
            self.spin_weight,
            self.spin_qty,
            self.spin_metal_cost,
            self.spin_labor_cost,
            self.combo_margin_type,
            self.spin_profit_margin,
        ])

        for i in range(len(order) - 1):
            QWidget.setTabOrder(order[i], order[i + 1])

        if next_widget:
            QWidget.setTabOrder(order[-1], next_widget)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    @staticmethod
    def _field(label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #1f2937; margin: 0px; padding: 0px 2px;"
        )
        lay.addWidget(lbl)
        lay.addWidget(widget)
        return container

    @staticmethod
    def _hbox(main_widget: QWidget, helper_btn: QWidget) -> QWidget:
        lay = QHBoxLayout()
        lay.setSpacing(4)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(main_widget, 1)
        lay.addWidget(helper_btn, 0)
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        container.setLayout(lay)
        return container

    def _build_calc_badge(self, title: str, spin_widget: QWidget, is_emerald: bool = False) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("card_emerald" if is_emerald else "card_neutral")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; "
            f"color: {'#166534' if is_emerald else '#475569'}; background: transparent;"
        )
        lay.addWidget(lbl)
        lay.addWidget(spin_widget)

        theme_style = (
            "QFrame#card_emerald {"
            "  background-color: #f0fdf4; border: 1.5px solid #86efac; border-radius: 8px;"
            "}"
            if is_emerald else
            "QFrame#card_neutral {"
            "  background-color: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 8px;"
            "}"
        )
        card.setStyleSheet(theme_style)
        return card, lbl

    def _dspin(self, suffix="", max_val=10000, decimals=2):
        sp = QDoubleSpinBox()
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sp.setRange(0, max_val)
        sp.setDecimals(decimals)
        sp.setSuffix(suffix)
        sp.setButtonSymbols(QAbstractSpinBox.NoButtons)
        return sp

    def _spin(self, suffix="", max_val=10000, default=0):
        sp = QSpinBox()
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sp.setRange(0, max_val)
        sp.setValue(default)
        sp.setSuffix(suffix)
        sp.setButtonSymbols(QAbstractSpinBox.NoButtons)
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
                self.spin_weight.setFocus()
                self.spin_weight.selectAll()

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
                    self.spin_weight.selectAll()

    def _generate_barcode(self):
        now = datetime.datetime.now()
        code12 = f"21{now.strftime('%y%j%H%M%S')}{random.randint(10, 99)}"[-12:]
        check = (10 - (
            (sum(int(code12[i]) for i in range(12) if i % 2 == 0) +
             sum(int(code12[i]) for i in range(12) if i % 2 != 0) * 3) % 10
        )) % 10
        self.inp_barcode.setText(f"{code12}{check}")
        self.inp_barcode.setFocus()
        self.inp_barcode.selectAll()

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
        enabled = bool(is_receipt and supplier_id)
        self.combo_supplier_account.setEnabled(enabled)
        self.setup_tab_order()
        if not enabled:
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
            raise ValueError("La réception fournisseur à crédit est réservée aux articles au poids.")
        supplier_id = self.combo_supplier.currentData()
        account_id = self.combo_supplier_account.currentData()
        if not supplier_id or not account_id:
            raise ValueError("Sélectionnez un fournisseur et un compte LOCAL/IMPORT actif.")
        return {"supplier_id": supplier_id, "supplier_account_id": account_id}

    def toggle_weight_fields(self, is_weight: bool):
        """تفعيل/تعطيل الحقول المرتبطة بالوزن حسب نوع المنتج."""
        for w in (self.spin_weight, self.spin_metal_cost,
                  self.spin_labor_cost, self.spin_profit_margin,
                  self.combo_margin_type):
            w.setEnabled(is_weight)

        self.spin_total_cost.setReadOnly(is_weight)
        self.spin_selling_price.setReadOnly(is_weight)

        if is_weight:
            self.card_cost.setStyleSheet(
                "QFrame#card_neutral { background-color: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 8px; }"
            )
            self.card_price.setStyleSheet(
                "QFrame#card_emerald { background-color: #f0fdf4; border: 1.5px solid #86efac; border-radius: 8px; }"
            )
            self.spin_total_cost.setStyleSheet(
                "border: none; background: transparent; font-size: 15px; font-weight: bold; color: #334155;"
            )
            self.spin_selling_price.setStyleSheet(
                "border: none; background: transparent; font-size: 17px; font-weight: 800; color: #15803d;"
            )
        else:
            self.card_cost.setStyleSheet(
                "QFrame#card_neutral { background-color: #ffffff; border: 1.5px solid #94a3b8; border-radius: 8px; }"
            )
            self.card_price.setStyleSheet(
                "QFrame#card_emerald { background-color: #ffffff; border: 1.5px solid #22c55e; border-radius: 8px; }"
            )
            self.spin_total_cost.setStyleSheet(
                "border: none; background: transparent; font-size: 15px; font-weight: bold; color: #0f172a;"
            )
            self.spin_selling_price.setStyleSheet(
                "border: none; background: transparent; font-size: 17px; font-weight: 800; color: #15803d;"
            )

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
