from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox,
    QMessageBox, QSplitter, QSizePolicy, QApplication, QLabel
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

# تم تصحيح مسار الاستدعاء هنا
from database import active_user_id
from ui.deferred_loading import defer_initial_load
from ui.touch_design import apply_touch_button_defaults
from ui.widgets.inventory.touch_product_entry import (
    after_save_options_text,
    confirm_product_entry,
)

from .state_manager import StateManager
from .session_table_section import SessionTableSection
from .formInput_section import FormInputSection
from .price_calculator import PriceCalculator



# ============================================================
# 5. InventoryFormTab — الكلاس الرئيسي (يجمع كل شيء)
# ============================================================
class InventoryFormTab(QWidget):
    """
    الواجهة الرئيسية لإضافة المنتجات.
    يتفوض على الكلاسات الفرعية ويُنسق بينها.
    """

    item_saved = Signal()

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._vkb = None
        self._init_ui()

    # ----------------------------------------------------------
    # بناء الواجهة
    # ----------------------------------------------------------
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Vertical)

        # --- القسم العلوي: نموذج الإدخال ---
        form_box = QGroupBox("📝 Ajouter un Nouvel Article (Saisie Rapide)")
        form_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        form_box.setStyleSheet(
            "QGroupBox { font-weight: bold; font-size: 16px; color: #2980b9;"
            " border: 2px solid #bdc3c7; border-radius: 8px;"
            " margin-top: 10px; padding-top: 20px; background-color: white; }"
        )
        form_layout = QVBoxLayout(form_box)
        form_layout.setContentsMargins(10, 10, 10, 10)

        self.form = FormInputSection(self.manager)
        self.form.recalculate_requested.connect(self._recalculate)
        self.form.combo_item_type.currentIndexChanged.connect(self._on_type_changed)
        form_layout.addWidget(self.form)
        form_layout.addLayout(self._build_action_buttons())
        self.lbl_after_save_hint = QLabel("")
        self.lbl_after_save_hint.setVisible(False)
        self.lbl_after_save_hint.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1e8449;"
            " background-color: #eafaf1; border: 1px solid #82e0aa;"
            " border-radius: 8px; padding: 8px 12px;"
        )
        form_layout.addWidget(self.lbl_after_save_hint)

        # --- القسم السفلي: جدول الجلسة ---
        self.session_table = SessionTableSection(self.manager)
        self.session_table._items = []   # تهيئة القائمة
        self.session_table.item_edited.connect(lambda _: self.item_saved.emit())
        self.session_table.item_deleted.connect(lambda _: self.item_saved.emit())

        splitter.addWidget(form_box)
        splitter.addWidget(self.session_table)
        splitter.setSizes([550, 450])

        layout.addWidget(splitter)
        self._splitter = splitter

        # تحميل البيانات الأولية
        self.form.restore_state(StateManager.load())
        self._on_type_changed()
        defer_initial_load(self, self.refresh_data)

    def _build_action_buttons(self) -> QHBoxLayout:
        box = QHBoxLayout()
        box.setSpacing(10)

        btn_clear = QPushButton(" Vider")
        btn_clear.setIcon(qta.icon("fa5s.eraser", color="#2c3e50"))
        btn_clear.setFixedHeight(55)
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet(
            "background-color: #ecf0f1; color: #2c3e50; font-weight: bold;"
            " font-size: 15px; border-radius: 8px;"
        )
        apply_touch_button_defaults(btn_clear)
        btn_clear.clicked.connect(lambda: self.form.clear(full=True))

        btn_price = QPushButton(" Maj Cours Or")
        btn_price.setFixedHeight(55)
        btn_price.setIcon(qta.icon("fa5s.chart-line", color="#d35400"))
        btn_price.setCursor(Qt.PointingHandCursor)
        btn_price.setStyleSheet(
            "background-color: #fdf2e9; color: #d35400; font-weight: bold;"
            " font-size: 15px; border: 2px solid #d35400; border-radius: 8px;"
        )
        apply_touch_button_defaults(btn_price)
        btn_price.clicked.connect(self._open_price_dialog)

        btn_kb = QPushButton(" ⌨️ Clavier")
        btn_kb.setFixedSize(130, 55)
        btn_kb.setCursor(Qt.PointingHandCursor)
        btn_kb.setStyleSheet(
            "background-color: #34495e; color: white; font-size: 15px;"
            " font-weight: bold; border-radius: 8px;"
        )
        apply_touch_button_defaults(btn_kb)
        btn_kb.clicked.connect(self._show_virtual_keyboard)

        btn_save = QPushButton(" Ajouter le Produit")
        btn_save.setIcon(qta.icon("fa5s.plus-circle", color="white"))
        btn_save.setFixedHeight(55)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold;"
            " font-size: 17px; border-radius: 8px;"
        )
        apply_touch_button_defaults(btn_save, primary=True)
        btn_save.clicked.connect(self._save_item)

        box.addWidget(btn_clear)
        box.addWidget(btn_price)
        box.addWidget(btn_kb)
        box.addWidget(btn_save, stretch=1)
        return box

    # ----------------------------------------------------------
    # Slots
    # ----------------------------------------------------------
    def _on_type_changed(self):
        is_weight = self.form.combo_item_type.currentData() == "WEIGHT"
        self.form.toggle_weight_fields(is_weight)
        if is_weight:
            self._recalculate()

    def _recalculate(self):
        if self.form.combo_item_type.currentData() != "WEIGHT":
            return
        tc, sp = PriceCalculator.compute(
            weight      = self.form.spin_weight.value(),
            metal_cost  = self.form.spin_metal_cost.value(),
            labor_cost  = self.form.spin_labor_cost.value(),
            margin      = self.form.spin_profit_margin.value(),
            margin_type = self.form.combo_margin_type.currentData(),
        )
        self.form.spin_total_cost.setValue(tc)
        self.form.spin_selling_price.setValue(sp)

    def _save_item(self):
        data = self.form.get_form_data()
        if not data["name"]:
            QMessageBox.warning(self, "Erreur", "Le nom est obligatoire. Saisissez un nom ou utilisez le bouton de selection.")
            return
        if data["category_id"] is None:
            QMessageBox.warning(self, "Erreur", "Selectionnez une categorie avant d'ajouter le produit.")
            return
        if data["item_type"] == "WEIGHT" and data["weight"] <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez un poids superieur a 0 g pour un article au poids.")
            return
        if data["quantity"] <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez une quantite superieure a 0.")
            return

        try:
            receipt = self.form.get_receipt_posting_data()
        except ValueError as exc:
            QMessageBox.warning(self, "Reception fournisseur", str(exc))
            return

        if not confirm_product_entry(
            self,
            data,
            receipt,
            supplier_label=self.form.combo_supplier.currentText(),
            account_label=self.form.combo_supplier_account.currentText(),
        ):
            return

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
        if not new_id:
            return

        self.item_saved.emit()

        new_item = self.manager.inventory.get_item_by_id(new_id) or {
            "id": new_id, **data,
            "barcode": data["barcode"] or "-",
        }

        self.session_table.prepend(new_item)
        StateManager.save(self.form.build_state())
        self.form.clear(full=False)
        self.form.inp_barcode.setFocus()
        self.lbl_after_save_hint.setText(after_save_options_text(new_item.get("name", data["name"])))
        self.lbl_after_save_hint.setVisible(True)

    def _open_price_dialog(self):
        from ui.dialogs.price_update import PriceUpdateDialog

        dialog = PriceUpdateDialog(self.manager, self)
        if dialog.exec():
            self.refresh_data()
            self.item_saved.emit()

    def _show_virtual_keyboard(self):
        if not self._vkb:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog

            self._vkb = VirtualKeyboardDialog(self.window())
            self._vkb.finished.connect(self._restore_layout)

        self.session_table.hide()
        self._vkb.show()
        self._vkb.raise_()

        geom = QApplication.primaryScreen().availableGeometry()
        kh = self._vkb.height() if self._vkb.height() > 100 else 450
        self._vkb.move((geom.width() - self._vkb.width()) // 2, geom.height() - kh)
        self.layout().setContentsMargins(10, 10, 10, kh + 20)

    def _restore_layout(self):
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.session_table.show()

    # ----------------------------------------------------------
    # API عام
    # ----------------------------------------------------------
    def refresh_data(self):
        self.form.load_combos()