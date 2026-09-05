from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox,
    QMessageBox, QSplitter, QSizePolicy, QApplication, QLabel
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

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
# InventoryFormTab — واجهة الإدخال السريع المتكيفة والمتجاوبة
# ============================================================
class InventoryFormTab(QWidget):
    """
    واجهة إدخال المنتجات بنظام تجاوب ذكي (Smart Responsive Dual-Mode):
    - وضع الشاشة العريضة (Width >= 1120px): تقسيم أفقي يخصص كامل التمدد للنموذج (Stretch 1)
      ويقفل جدول الجلسة عند العرض المثالي للقراءة (450px, Stretch 0) مع فرض setMinimumWidth(440).
    - وضع الشاشة المدمجة (Width < 1120px): تحويل فوري لتقسيم رأسي (Vertical Drawer) يمنح
      النموذج 100% من العرض الأفقي لمنع أي اقتصاص للحقول نهائياً.
    - دعم طي/فتح درج جدول الجلسة بنقرة واحدة (Drawer Toggle).
    """

    item_saved = Signal()
    BREAKPOINT_WIDTH = 1120

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self._vkb = None
        self._is_drawer_collapsed = False
        self._init_ui()

    # ----------------------------------------------------------
    # بناء الواجهة
    # ----------------------------------------------------------
    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e2e8f0;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal {
                width: 5px;
                margin: 4px 1px;
            }
            QSplitter::handle:vertical {
                height: 5px;
                margin: 1px 4px;
            }
            QSplitter::handle:hover {
                background-color: #3b82f6;
            }
        """)

        # ------------------------------------------------------
        # الجانب الأيسر: بطاقة نموذج الإدخال السريع
        # ------------------------------------------------------
        self.form_box = QGroupBox("📝 Ajouter un Nouvel Article — Saisie Rapide")
        self.form_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.form_box.setMinimumWidth(520)
        self.form_box.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                font-size: 13px;
                color: #1e293b;
                border: 1.5px solid #cbd5e1;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 14px;
                background-color: #ffffff;
            }
        """)
        form_layout = QVBoxLayout(self.form_box)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(8)

        self.form = FormInputSection(self.manager)
        self.form.recalculate_requested.connect(self._recalculate)
        self.form.combo_item_type.currentIndexChanged.connect(self._on_type_changed)
        self.form.submit_requested.connect(self._save_item)
        form_layout.addWidget(self.form, stretch=1)

        action_layout = self._build_action_buttons()
        form_layout.addLayout(action_layout)

        self.lbl_after_save_hint = QLabel("")
        self.lbl_after_save_hint.setVisible(False)
        self.lbl_after_save_hint.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #166534;
                background-color: #f0fdf4;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        form_layout.addWidget(self.lbl_after_save_hint)

        # ------------------------------------------------------
        # الجانب الأيمن / السفلي: جدول الجلسة
        # ------------------------------------------------------
        self.session_table = SessionTableSection(self.manager)
        self.session_table.setMinimumWidth(440)
        self.session_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.session_table._items = []
        self.session_table.item_edited.connect(lambda _: self.item_saved.emit())
        self.session_table.item_deleted.connect(lambda _: self.item_saved.emit())

        # تركيب العناصر داخل الـ Splitter
        self._splitter.addWidget(self.form_box)
        self._splitter.addWidget(self.session_table)

        # تخصيص التمدد: النموذج يمتص كامل التمدد الإضافي
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setSizes([650, 450])

        main_layout.addWidget(self._splitter)

        # ربط تسلسل Tab عبر النموذج وأزرار الحفظ
        self.form.setup_tab_order(self.btn_save)
        QWidget.setTabOrder(self.btn_save, self.btn_clear)
        QWidget.setTabOrder(self.btn_clear, self.btn_price)
        QWidget.setTabOrder(self.btn_price, self.btn_kb)
        QWidget.setTabOrder(self.btn_kb, self.form.inp_barcode)

        # تحميل البيانات الأولية
        self.form.restore_state(StateManager.load())
        self._on_type_changed()
        defer_initial_load(self, self.refresh_data)

    def _build_action_buttons(self) -> QHBoxLayout:
        box = QHBoxLayout()
        box.setSpacing(6)
        box.setContentsMargins(0, 2, 0, 0)

        # 1. زر المسح
        self.btn_clear = QPushButton(" Vider")
        self.btn_clear.setIcon(qta.icon("fa5s.eraser", color="#475569"))
        self.btn_clear.setFixedHeight(44)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: 700;
                font-size: 13px;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #cbd5e1;
            }
        """)
        apply_touch_button_defaults(self.btn_clear)
        self.btn_clear.clicked.connect(lambda: self.form.clear(full=True))

        # 2. زر تحديث سعر الذهب
        self.btn_price = QPushButton(" Maj Cours Or")
        self.btn_price.setFixedHeight(44)
        self.btn_price.setIcon(qta.icon("fa5s.chart-line", color="#d97706"))
        self.btn_price.setCursor(Qt.PointingHandCursor)
        self.btn_price.setStyleSheet("""
            QPushButton {
                background-color: #fffbeb;
                color: #b45309;
                font-weight: 700;
                font-size: 13px;
                border: 1.5px solid #f59e0b;
                border-radius: 6px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #fef3c7;
            }
            QPushButton:pressed {
                background-color: #fde68a;
            }
        """)
        apply_touch_button_defaults(self.btn_price)
        self.btn_price.clicked.connect(self._open_price_dialog)

        # 3. زر لوحة المفاتيح الافتراضية
        self.btn_kb = QPushButton(" ⌨️ Clavier")
        self.btn_kb.setFixedSize(110, 44)
        self.btn_kb.setCursor(Qt.PointingHandCursor)
        self.btn_kb.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: white;
                font-size: 12px;
                font-weight: 700;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QPushButton:pressed {
                background-color: #0f172a;
            }
        """)
        apply_touch_button_defaults(self.btn_kb)
        self.btn_kb.clicked.connect(self._show_virtual_keyboard)

        # 4. زر تبديل عرض جدول الجلسة (Drawer Toggle)
        self.btn_toggle_drawer = QPushButton(" 📦 Session")
        self.btn_toggle_drawer.setFixedHeight(44)
        self.btn_toggle_drawer.setToolTip("Afficher / Masquer le tableau de la session")
        self.btn_toggle_drawer.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_drawer.setFocusPolicy(Qt.NoFocus)
        self.btn_toggle_drawer.setStyleSheet("""
            QPushButton {
                background-color: #f8fafc;
                color: #475569;
                font-size: 12px;
                font-weight: 700;
                border: 1.5px solid #cbd5e1;
                border-radius: 6px;
                padding: 0 10px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        apply_touch_button_defaults(self.btn_toggle_drawer)
        self.btn_toggle_drawer.clicked.connect(self._toggle_session_drawer)

        # 5. زر الإضافة الرئيسي
        self.btn_save = QPushButton(" Ajouter le Produit")
        self.btn_save.setIcon(qta.icon("fa5s.plus-circle", color="white"))
        self.btn_save.setFixedHeight(44)
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: 700;
                font-size: 14px;
                border-radius: 6px;
                border: none;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
        """)
        apply_touch_button_defaults(self.btn_save, primary=True)
        self.btn_save.clicked.connect(self._save_item)

        box.addWidget(self.btn_clear)
        box.addWidget(self.btn_price)
        box.addWidget(self.btn_kb)
        box.addWidget(self.btn_toggle_drawer)
        box.addWidget(self.btn_save, stretch=2)
        return box

    # ----------------------------------------------------------
    # التجاوب الذكي وتبديل الأنماط حسب دقة الشاشة
    # ----------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        if w < self.BREAKPOINT_WIDTH:
            if self._splitter.orientation() != Qt.Vertical:
                self._apply_compact_vertical_mode()
        else:
            if self._splitter.orientation() != Qt.Horizontal:
                self._apply_standard_horizontal_mode()

    def _apply_compact_vertical_mode(self):
        """التبديل إلى الوضع الرأسي المدمج لمنح النموذج 100% من العرض."""
        self.form_box.setMinimumWidth(0)
        self.session_table.setMinimumWidth(0)
        self._splitter.setOrientation(Qt.Vertical)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        h = self.height()
        drawer_h = min(240, max(180, int(h * 0.35)))
        self._splitter.setSizes([h - drawer_h, drawer_h])

    def _apply_standard_horizontal_mode(self):
        """التبديل إلى الوضع الأفقي الجانبي مع تثبيت عرض الجدول عند 450px."""
        self.form_box.setMinimumWidth(520)
        self.session_table.setMinimumWidth(440)
        self._splitter.setOrientation(Qt.Horizontal)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        table_w = 450
        form_w = max(520, self.width() - table_w - 20)
        self._splitter.setSizes([form_w, table_w])

    def _toggle_session_drawer(self):
        """إظهار أو إخفاء جدول الجلسة يدوياً لمنح كامل الشاشة للنموذج."""
        is_visible = self.session_table.isVisible()
        self.session_table.setVisible(not is_visible)
        if not is_visible:
            self.btn_toggle_drawer.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    color: #475569;
                    font-size: 12px;
                    font-weight: 700;
                    border: 1.5px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 0 10px;
                }
            """)
        else:
            self.btn_toggle_drawer.setStyleSheet("""
                QPushButton {
                    background-color: #eff6ff;
                    color: #2563eb;
                    font-size: 12px;
                    font-weight: 700;
                    border: 1.5px solid #93c5fd;
                    border-radius: 6px;
                    padding: 0 10px;
                }
            """)

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
            QMessageBox.warning(self, "Erreur", "Le nom est obligatoire. Saisissez un nom ou utilisez le bouton de sélection.")
            self.form.inp_name.setFocus()
            return
        if data["category_id"] is None:
            QMessageBox.warning(self, "Erreur", "Sélectionnez une catégorie avant d'ajouter le produit.")
            self.form.combo_category.setFocus()
            return
        if data["item_type"] == "WEIGHT" and data["weight"] <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez un poids supérieur à 0 g pour un article au poids.")
            self.form.spin_weight.setFocus()
            self.form.spin_weight.selectAll()
            return
        if data["quantity"] <= 0:
            QMessageBox.warning(self, "Erreur", "Indiquez une quantité supérieure à 0.")
            self.form.spin_qty.setFocus()
            self.form.spin_qty.selectAll()
            return

        try:
            receipt = self.form.get_receipt_posting_data()
        except ValueError as exc:
            QMessageBox.warning(self, "Réception fournisseur", str(exc))
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
                QMessageBox.critical(self, "Réception fournisseur", message)
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
        self.form.inp_barcode.selectAll()
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
        self.layout().setContentsMargins(8, 8, 8, kh + 10)

    def _restore_layout(self):
        self.layout().setContentsMargins(8, 8, 8, 8)
        self.session_table.show()

    # ----------------------------------------------------------
    # API عام
    # ----------------------------------------------------------
    def refresh_data(self):
        self.form.load_combos()