# ui/widgets/versements/add_payment_dialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout, 
    QPushButton, QDoubleSpinBox, QLineEdit, QMessageBox, 
    QLabel, QWidget, QComboBox, QApplication, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

try:
    from ui.tools.virtual_numpad import VirtualNumpad
    from ui.tools.virtual_keyboard import VirtualKeyboardDialog
except ImportError:
    pass

class AddPaymentDialog(QDialog):
    def __init__(self, manager, versement_id, journee_id, preselected_item_id=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.versement_id = versement_id
        self.journee_id = journee_id
        self.preselected_item_id = preselected_item_id
        
        self.is_versement_libre = False
        self.v_data = None
        self.item_prices = {}
        self.item_weights = {}
        self._poids_deduit_manual = False
        self._updating_poids_deduit = False
        self._last_suggested_poids_deduit = 0.0
        
        self.setWindowTitle("Ajouter un nouveau versement (Paiement)")
        self.setMinimumWidth(880) 
        
        self._load_versement_data()
        self.init_ui()
        self.auto_calculate_poids_deduit()

    def _load_versement_data(self):
        try:
            versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
            self.v_data = next((v for v in versements if v['id'] == self.versement_id), None)
            if self.v_data:
                if self.v_data.get('type_versement') == 'A_VIDE':
                    self.is_versement_libre = True
                for item in self.v_data.get('items', []):
                    versement_item_id = item.get('item_id') or item.get('id')
                    if versement_item_id:
                        self.item_prices[versement_item_id] = float(item.get('selling_price') or 0)
                        self.item_weights[versement_item_id] = float(item.get('weight') or 0)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(int((screen.width() - self.width()) / 2), 0)

    def _wrap_with_numpad(self, widget):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("🔢")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(34, widget.sizeHint().height() or 34)
        btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 14px;")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._open_numpad(widget))
        lay.addWidget(btn)
        return container

    def _wrap_with_keyboard(self, widget):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("⌨️")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(34, widget.sizeHint().height() or 34)
        btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 14px;")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._open_vkb(widget))
        lay.addWidget(btn)
        return container

    def _open_numpad(self, widget):
        widget.setFocus()
        pad = VirtualNumpad(mode="direct", target_widget=widget, allow_decimal=True, allow_negative=True, parent=self)
        pad.exec()

    def _open_vkb(self, widget):
        widget.setFocus()
        kb = VirtualKeyboardDialog(self)
        kb.show()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 12, 15, 12)

        title = QLabel("Détails de la transaction (Paiement & Déduction)")
        title.setFont(QFont("", 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        top_layout = QHBoxLayout()
        lbl_dest = QLabel("Paiement destiné à :")
        lbl_dest.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.combo_target = QComboBox()
        self.combo_target.setStyleSheet("padding: 6px; font-size: 14px; font-weight: bold; border: 1px solid #bdc3c7; border-radius: 4px;")
        self.combo_target.addItem("📦 Dossier Global (Aucun article spécifique)", None)
        self._populate_target_combo()
        self.combo_target.currentIndexChanged.connect(lambda _: self.auto_calculate_poids_deduit())
        
        btn_details = QPushButton("ℹ️ Détails Produit")
        btn_details.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; font-size: 14px; padding: 6px 12px; border-radius: 4px;")
        btn_details.setCursor(Qt.PointingHandCursor)
        btn_details.clicked.connect(self.show_product_details)
        
        top_layout.addWidget(lbl_dest)
        top_layout.addWidget(self.combo_target, stretch=1)
        top_layout.addWidget(btn_details)
        main_layout.addLayout(top_layout)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)

        col1_box = QGroupBox("💵 Montants & Financement")
        col1_box.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        form1 = QFormLayout(col1_box)
        form1.setSpacing(6)
        form1.setContentsMargins(10, 14, 10, 10)

        self.inp_montant_da = QDoubleSpinBox()
        self.inp_montant_da.setRange(-99999999, 99999999)
        self.inp_montant_da.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold; color: #c0392b; border: 1px solid #c0392b;" if self.is_versement_libre else "padding: 5px; font-size: 14px; font-weight: bold;")
        self.inp_montant_da.setSuffix(" DA")
        self.inp_montant_da.setGroupSeparatorShown(True)
        self.inp_montant_da.valueChanged.connect(lambda _: self.auto_calculate_poids_deduit())
        
        self.inp_tpe = QDoubleSpinBox()
        self.inp_tpe.setRange(-99999999, 99999999)
        self.inp_tpe.setSuffix(" TPE (DA)")
        self.inp_tpe.setGroupSeparatorShown(True)
        self.inp_tpe.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold; color: #2980b9;")
        self.inp_tpe.valueChanged.connect(lambda _: self.auto_calculate_poids_deduit())
        self.inp_montant_euro = QDoubleSpinBox()
        self.inp_montant_euro.setRange(-999999, 999999)
        self.inp_montant_euro.setSuffix(" €")
        self.inp_montant_euro.setGroupSeparatorShown(True)
        self.inp_montant_euro.setStyleSheet("padding: 5px; font-size: 13px; font-weight: bold;")

        self.inp_taux_change = QDoubleSpinBox()
        self.inp_taux_change.setRange(0, 99999)
        self.inp_taux_change.setDecimals(2)
        self.inp_taux_change.setSuffix(" DA/€")
        self.inp_taux_change.setStyleSheet("padding: 5px; font-size: 13px;")

        self.inp_montant_dollar = QDoubleSpinBox()
        self.inp_montant_dollar.setRange(-999999, 999999)
        self.inp_montant_dollar.setSuffix(" $")
        self.inp_montant_dollar.setGroupSeparatorShown(True)
        self.inp_montant_dollar.setStyleSheet("padding: 5px; font-size: 13px; font-weight: bold;")

        self.inp_taux_change_dollar = QDoubleSpinBox()
        self.inp_taux_change_dollar.setRange(0, 99999)
        self.inp_taux_change_dollar.setDecimals(2)
        self.inp_taux_change_dollar.setSuffix(" DA/$")
        self.inp_taux_change_dollar.setStyleSheet("padding: 5px; font-size: 13px;")

        self.inp_or_casse = QDoubleSpinBox()
        self.inp_or_casse.setRange(-10000, 10000)
        self.inp_or_casse.setSuffix(" g")
        self.inp_or_casse.setDecimals(3)
        self.inp_or_casse.setStyleSheet("padding: 5px; font-size: 13px; font-weight: bold; color: #d35400;")

        self.inp_prix_gramme = QDoubleSpinBox()
        self.inp_prix_gramme.setRange(0, 99999)
        self.inp_prix_gramme.setSuffix(" DA/g")
        self.inp_prix_gramme.setGroupSeparatorShown(True)
        self.inp_prix_gramme.setStyleSheet("padding: 5px; font-size: 13px;")

        # ربط الحقول بالمساعد الحسابي التلقائي
        self.inp_montant_euro.valueChanged.connect(lambda _: self.calc_montant_da_eq())
        self.inp_taux_change.valueChanged.connect(lambda _: self.calc_montant_da_eq())
        self.inp_montant_dollar.valueChanged.connect(lambda _: self.calc_montant_da_eq())
        self.inp_taux_change_dollar.valueChanged.connect(lambda _: self.calc_montant_da_eq())
        self.inp_or_casse.valueChanged.connect(lambda _: self.calc_montant_da_eq())
        self.inp_prix_gramme.valueChanged.connect(lambda _: self.calc_montant_da_eq())

        form1.addRow("Montant payé (DA) :", self._wrap_with_numpad(self.inp_montant_da))
        form1.addRow("TPE (DA) :", self._wrap_with_numpad(self.inp_tpe))
        form1.addRow("Montant payé (€) :", self._wrap_with_numpad(self.inp_montant_euro))
        form1.addRow("Taux de change (€) :", self._wrap_with_numpad(self.inp_taux_change))
        form1.addRow("Montant payé ($) :", self._wrap_with_numpad(self.inp_montant_dollar))
        form1.addRow("Taux de change ($) :", self._wrap_with_numpad(self.inp_taux_change_dollar))
        form1.addRow("Or cassé reçu (Casse) :", self._wrap_with_numpad(self.inp_or_casse))
        form1.addRow("Prix du gramme du jour :", self._wrap_with_numpad(self.inp_prix_gramme))
        
        columns_layout.addWidget(col1_box, stretch=1)

        # ─── العمود الثاني: التخفيضات، الخصم، الملاحظات والملخص ───
        col2_layout = QVBoxLayout()
        col2_layout.setSpacing(8)
        
        col2_box = QGroupBox("🎁 Remise & Déductions (Poids)")
        col2_box.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: #075f58; border: 1px solid #bdc3c7; border-radius: 6px; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        form2 = QFormLayout(col2_box)
        form2.setSpacing(6)
        form2.setContentsMargins(10, 14, 10, 10)

        # أزرار المساعدة الذكية للتخفيضات (Discount Assistant Tools)
        lbl_remise_tools = QLabel("🛠️ Outils d'aide Remise :")
        lbl_remise_tools.setStyleSheet("font-size: 12px; font-weight: bold; color: #7f8c8d;")
        
        remise_buttons_layout = QHBoxLayout()
        btn_pct = QPushButton("🧮 Remise (%)")
        btn_pct.setStyleSheet("background-color: #34495e; color: white; padding: 5px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_pct.setCursor(Qt.PointingHandCursor)
        btn_pct.clicked.connect(self.open_discount_pct)
        
        btn_arrondi = QPushButton("🏷️ Arrondi / Solde")
        btn_arrondi.setStyleSheet("background-color: #8e44ad; color: white; padding: 5px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_arrondi.setCursor(Qt.PointingHandCursor)
        btn_arrondi.clicked.connect(self.open_discount_arrondi)
        
        remise_buttons_layout.addWidget(btn_pct)
        remise_buttons_layout.addWidget(btn_arrondi)
        form2.addRow(lbl_remise_tools, remise_buttons_layout)

        self.inp_remise_da = QDoubleSpinBox()
        self.inp_remise_da.setRange(0, 99999999)
        self.inp_remise_da.setSuffix(" DA")
        self.inp_remise_da.setGroupSeparatorShown(True)
        self.inp_remise_da.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold; color: #8e44ad;")
        self.inp_remise_da.valueChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_poids_deduit = QDoubleSpinBox()
        self.inp_poids_deduit.setRange(-10000, 10000)
        self.inp_poids_deduit.setSuffix(" g")
        self.inp_poids_deduit.setDecimals(3)
        self.inp_poids_deduit.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold; color: white; background-color: #2c3e50;")
        self.inp_poids_deduit.valueChanged.connect(self._on_poids_deduit_changed)

        self.lbl_poids_suggestion = QLabel("Suggestion: 0.000 g")
        self.lbl_poids_suggestion.setStyleSheet("font-size: 12px; font-weight: bold; color: #075f58;")
        self.btn_apply_poids_suggestion = QPushButton("Appliquer")
        self.btn_apply_poids_suggestion.setCursor(Qt.PointingHandCursor)
        self.btn_apply_poids_suggestion.setStyleSheet("background-color: #0f8f83; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        self.btn_apply_poids_suggestion.clicked.connect(self.apply_poids_suggestion)
        poids_suggestion_layout = QHBoxLayout()
        poids_suggestion_layout.setContentsMargins(0, 0, 0, 0)
        poids_suggestion_layout.setSpacing(6)
        poids_suggestion_layout.addWidget(self.lbl_poids_suggestion, stretch=1)
        poids_suggestion_layout.addWidget(self.btn_apply_poids_suggestion)

        self.inp_notes = QLineEdit()
        self.inp_notes.setPlaceholderText("Notes ou observations...")
        self.inp_notes.setStyleSheet("padding: 5px; font-size: 13px;")

        form2.addRow("Remise accordée (DA) :", self._wrap_with_numpad(self.inp_remise_da))
        form2.addRow("Poids à DÉDUIRE (g) :", self._wrap_with_numpad(self.inp_poids_deduit))
        form2.addRow("", poids_suggestion_layout)
        form2.addRow("Notes :", self._wrap_with_keyboard(self.inp_notes))
        col2_layout.addWidget(col2_box)

        # العرض الديناميكي للصافي المباشر بالجرام والدينار والنسبة المئوية
        self.summary_box = QGroupBox("📊 Impact du Paiement sur le Dossier (Reste en Grammes)")
        self.summary_box.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; background-color: #f8f9fa; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        sum_layout = QFormLayout(self.summary_box)
        sum_layout.setContentsMargins(10, 10, 10, 10)
        sum_layout.setSpacing(6)
        
        self.lbl_summary_reste = QLabel("0.00 g (0.00 DA)")
        self.lbl_summary_reste.setStyleSheet("font-size: 13px; font-weight: bold; color: #7f8c8d;")
        
        self.lbl_summary_current = QLabel("0.00 DA")
        self.lbl_summary_current.setStyleSheet("font-size: 13px; font-weight: bold; color: #27ae60;")
        
        self.lbl_summary_nouveau = QLabel("0.00 g")
        self.lbl_summary_nouveau.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980b9;")
        
        sum_layout.addRow(QLabel("Reste Actuel (Avant) :"), self.lbl_summary_reste)
        sum_layout.addRow(QLabel("Paiement + Remise :"), self.lbl_summary_current)
        sum_layout.addRow(QLabel("Nouveau Reste Final :"), self.lbl_summary_nouveau)
        col2_layout.addWidget(self.summary_box)
        col2_layout.addStretch()

        columns_layout.addLayout(col2_layout, stretch=1)
        main_layout.addLayout(columns_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px 25px; font-size: 14px; font-weight: bold; border-radius: 4px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_save = QPushButton("Enregistrer le versement")
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; padding: 8px 25px; font-size: 14px; font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self.save_payment)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

    def calc_montant_da_eq(self):
        try:
            euro = self.inp_montant_euro.value()
            taux_euro = self.inp_taux_change.value()
            dollar = self.inp_montant_dollar.value()
            taux_dollar = self.inp_taux_change_dollar.value()
            oc = self.inp_or_casse.value()
            prix_g = self.inp_prix_gramme.value()
            
            total_da = (euro * taux_euro) + (dollar * taux_dollar) + (oc * prix_g)
            if total_da != 0:
                self.inp_montant_da.blockSignals(True)
                self.inp_montant_da.setValue(total_da)
                self.inp_montant_da.blockSignals(False)
                self.auto_calculate_poids_deduit()
        except Exception:
            pass

    def _get_active_base_amount(self):
        selected_item_id = self.combo_target.currentData()
        if selected_item_id and selected_item_id in self.item_prices:
            return self.item_prices[selected_item_id]
        elif self.v_data:
            total_est = self.v_data.get('total_estimated_price_da', 0)
            total_paid = self.v_data.get('total_paid_money_da', 0) + self.v_data.get('total_remise_da', 0)
            return max(0.0, total_est - total_paid)
        return 0.0

    def _get_active_base_weight(self):
        selected_item_id = self.combo_target.currentData()
        if selected_item_id and selected_item_id in self.item_weights:
            w = self.item_weights[selected_item_id]
            # خصم الدفعات السابقة الموجهة لهذه القطعة
            deductions = sum(float(p.get('poids_deduit_g') or 0) for p in self.v_data.get('payments', []) if p.get('versement_item_id') == selected_item_id)
            return max(0.0, w - deductions)
        elif self.v_data:
            return float(self.v_data.get('reste_poids_g', 0))
        return 0.0

    def open_discount_pct(self):
        base_amount = self._get_active_base_amount()
        if base_amount <= 0:
            QMessageBox.warning(self, "Erreur", "Aucune base de prix estimé disponible pour calculer la remise.")
            return
        
        pad = VirtualNumpad(title="Saisir la Remise (%)", mode="dialog", allow_decimal=True, allow_negative=False, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                pct = float(val)
                if 0 <= pct <= 100:
                    remise_val = base_amount * (pct / 100.0)
                    self.inp_remise_da.setValue(remise_val)
                else:
                    QMessageBox.warning(self, "Erreur", "Le pourcentage doit être entre 0 et 100.")

    def open_discount_arrondi(self):
        base_amount = self._get_active_base_amount()
        if base_amount <= 0:
            QMessageBox.warning(self, "Erreur", "Aucun reste estimé disponible à solder ou arrondir.")
            return
        
        current_pay = self.inp_montant_da.value() + self.inp_tpe.value()
        reste_actuel = max(0.0, base_amount - current_pay)
        
        pad = VirtualNumpad(title="Saisir le Nouveau Reste Cible (DA)", mode="dialog", allow_decimal=True, allow_negative=False, initial_value=reste_actuel, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                cible = float(val)
                if 0 <= cible <= base_amount:
                    remise_needed = base_amount - current_pay - cible
                    if remise_needed >= 0:
                        self.inp_remise_da.setValue(remise_needed)
                    else:
                        QMessageBox.warning(self, "Erreur", "Le paiement actuel dépasse déjà le montant cible.")
                else:
                    QMessageBox.warning(self, "Erreur", f"Le reste cible doit être entre 0 et {base_amount:,.2f} DA.")

    def _calculate_poids_suggestion(self):
        base_amount = self._get_active_base_amount()
        base_weight = self._get_active_base_weight()
        if base_amount <= 0 or base_weight <= 0:
            return 0.0

        current_pay = self.inp_montant_da.value() + self.inp_tpe.value()
        remise = self.inp_remise_da.value()
        prix_g_moyen = base_amount / base_weight
        poids_suggested = (current_pay + remise) / prix_g_moyen
        if poids_suggested > base_weight:
            return base_weight
        return poids_suggested

    def _set_poids_deduit_value(self, value):
        self._updating_poids_deduit = True
        self.inp_poids_deduit.blockSignals(True)
        self.inp_poids_deduit.setValue(value)
        self.inp_poids_deduit.blockSignals(False)
        self._updating_poids_deduit = False

    def _on_poids_deduit_changed(self, _value):
        if not self._updating_poids_deduit:
            self._poids_deduit_manual = True
        self.update_dynamic_summary()

    def apply_poids_suggestion(self):
        self._poids_deduit_manual = False
        self._set_poids_deduit_value(self._last_suggested_poids_deduit)
        self.btn_apply_poids_suggestion.setEnabled(False)
        self.update_dynamic_summary()

    def auto_calculate_poids_deduit(self):
        """مساعد في الحساب: يكتب تلقائياً الوزن المقتنى بالجرام ويسمح للمستخدم بالتعديل اليدوي كأداة مساعدة"""
        suggested = self._calculate_poids_suggestion()
        self._last_suggested_poids_deduit = suggested
        self.lbl_poids_suggestion.setText(f"Suggestion: {suggested:,.3f} g")
        self.btn_apply_poids_suggestion.setEnabled(abs(suggested - self.inp_poids_deduit.value()) > 0.0005)
        if not self._poids_deduit_manual:
            self._set_poids_deduit_value(suggested)
        self.update_dynamic_summary()

    def update_dynamic_summary(self):
        base_amount = self._get_active_base_amount()
        base_weight = self._get_active_base_weight()
        
        current_pay = self.inp_montant_da.value() + self.inp_tpe.value()
        remise = self.inp_remise_da.value()
        poids_deduit = self.inp_poids_deduit.value()
        
        remise_pct = (remise / base_amount * 100.0) if base_amount > 0 else 0.0
        nouveau_reste_da = max(0.0, base_amount - (current_pay + remise))
        nouveau_reste_g = max(0.0, base_weight - poids_deduit)
        
        self.lbl_summary_reste.setText(f"{base_weight:,.2f} g  (Estimé: {base_amount:,.2f} DA)")
        self.lbl_summary_current.setText(f"{(current_pay + remise):,.2f} DA  [Remise: {remise:,.2f} DA ({remise_pct:.1f}%)]")
        self.lbl_summary_nouveau.setText(f"{nouveau_reste_g:,.2f} g  (Estimé: {nouveau_reste_da:,.2f} DA)")

    def _populate_target_combo(self):
        try:
            self.target_to_inventory = {}
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT vi.id, vi.inventory_id, vi.designation, i.weight, i.selling_price, cat.name as category_name, sup.name as supplier_name
                    FROM Versement_Items vi
                    LEFT JOIN Inventory i ON vi.inventory_id = i.id
                    LEFT JOIN Categories cat ON i.category_id = cat.id
                    LEFT JOIN Suppliers sup ON i.supplier_id = sup.id
                    WHERE vi.versement_id = %s AND vi.item_status = 'EN_COURS'
                """, (self.versement_id,))
                items = cursor.fetchall()
                
                for item in items:
                    self.target_to_inventory[item['id']] = item['inventory_id']
                    w = float(item['weight'] or 0)
                    self.item_weights[item['id']] = w
                    self.item_prices[item['id']] = float(item.get('selling_price') or 0)
                    desig = item['designation']
                    display_name = f"{desig} ({w:.2f}g)" if (w > 0 and f"({w:.2f}g)" not in desig and not desig.strip().endswith("g)")) else desig
                    if item.get('category_name'):
                        display_name += f" | Cat: {item['category_name']}"
                    if item.get('supplier_name'):
                        display_name += f" | Fourn: {item['supplier_name']}"
                    self.combo_target.addItem(f"💍 {display_name}", item['id'])
                    
                    if self.preselected_item_id and item['id'] == self.preselected_item_id:
                        idx = self.combo_target.count() - 1
                        self.combo_target.setCurrentIndex(idx)
        except Exception as e:
            print(f"Erreur chargement articles combo: {e}")

    def show_product_details(self):
        try:
            target_id = self.combo_target.currentData()
            inventory_ids = []
            if target_id and hasattr(self, 'target_to_inventory') and self.target_to_inventory.get(target_id):
                inventory_ids.append(self.target_to_inventory[target_id])
            elif self.v_data and self.v_data.get('items'):
                inventory_ids = [it['item_id'] for it in self.v_data.get('items', []) if it.get('item_id')]
            
            if not inventory_ids:
                QMessageBox.information(self, "Détails Produit", "Aucun article en base n'est spécifiquement associé à ce versement ou dossier à vide.")
                return

            details_text = ""
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                for inv_id in inventory_ids:
                    if not inv_id: continue
                    cursor.execute("""
                        SELECT i.barcode, i.name, i.weight, i.remaining_weight, i.selling_price, i.status, i.entry_date, i.item_type,
                               c.name as category_name, m.name as metal_name, m.purity_value, s.name as supplier_name, l.name as location_name
                        FROM Inventory i
                        LEFT JOIN Categories c ON i.category_id = c.id
                        LEFT JOIN MetalTypes m ON i.metal_type_id = m.id
                        LEFT JOIN Suppliers s ON i.supplier_id = s.id
                        LEFT JOIN StorageLocations l ON i.location_id = l.id
                        WHERE i.id = %s
                    """, (inv_id,))
                    row = cursor.fetchone()
                    if row:
                        details_text += f"🏷️ Article : {row['name']}\n"
                        details_text += f"▪️ Code-barres : {row['barcode'] or 'N/A'}\n"
                        details_text += f"▪️ Catégorie : {row['category_name'] or 'N/A'}\n"
                        details_text += f"▪️ Métal / Titre : {row['metal_name'] or 'N/A'} ({row['purity_value'] or ''})\n"
                        details_text += f"▪️ Fournisseur : {row['supplier_name'] or 'N/A'}\n"
                        details_text += f"▪️ Poids Initial : {float(row['weight'] or 0):.2f} g\n"
                        details_text += f"▪️ Prix de Vente Estimé : {float(row['selling_price'] or 0):,.2f} DA\n"
                        details_text += f"▪️ Emplacement : {row['location_name'] or 'N/A'}\n"
                        details_text += f"▪️ Date d'entrée : {row['entry_date'] or 'N/A'}\n"
                        details_text += "────────────────────────────\n"
            
            if details_text:
                dlg = QMessageBox(self)
                dlg.setWindowTitle("📋 Détails Techniques du Produit")
                dlg.setText("Voici les spécifications détaillées de l'article :")
                dlg.setInformativeText(details_text.strip())
                dlg.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #2c3e50; }")
                dlg.exec()
            else:
                QMessageBox.information(self, "Détails Produit", "Détails introuvables en base de données pour l'article sélectionné.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des détails : {e}")

    def save_payment(self):
        try:
            montant_da = self.inp_montant_da.value()
            tpe_da = self.inp_tpe.value()
            montant_euro = self.inp_montant_euro.value()
            taux_change = self.inp_taux_change.value()
            montant_dollar = self.inp_montant_dollar.value()
            taux_change_dollar = self.inp_taux_change_dollar.value()
            remise_da = self.inp_remise_da.value()
            or_casse = self.inp_or_casse.value()
            poids_deduit = self.inp_poids_deduit.value()
            prix_gramme = self.inp_prix_gramme.value()
            notes = self.inp_notes.text().strip()
            
            selected_item_id = self.combo_target.currentData()

            if montant_da < 0 or tpe_da < 0 or montant_euro < 0 or montant_dollar < 0 or or_casse < 0 or poids_deduit < 0:
                if not notes:
                    QMessageBox.warning(
                        self, "Note Obligatoire", 
                        "Vous saisissez une valeur négative (Sortie/Correction du dossier).\n\n"
                        "Veuillez obligatoirement écrire une note explicative dans le champ 'Notes'.\n\n"
                        "Exemples :\n"
                        "- Remis en espèces au client\n"
                        "- Transféré vers VRS-XXXXX\n"
                        "- Erreur de saisie corrigée"
                    )
                    self.inp_notes.setFocus()
                    return

            if montant_da == 0 and tpe_da == 0 and montant_euro == 0 and montant_dollar == 0 and or_casse == 0 and remise_da == 0:
                QMessageBox.warning(self, "Erreur", "Veuillez entrer au moins un montant (DA/Euro/Dollar), de l'or cassé ou une remise.")
                return

            if poids_deduit == 0:
                reply = QMessageBox.question(
                    self, "Attention", "Le poids à déduire est 0g. Êtes-vous sûr de ne rien déduire du reste ?", 
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No: return

            try:
                success = self.manager.versements.add_payment(
                    versement_id=self.versement_id,
                    journee_id=self.journee_id,
                    montant_da=montant_da,
                    tpe_da=tpe_da,
                    montant_euro=montant_euro,
                    taux_change_euro=taux_change,
                    or_casse_g=or_casse,
                    poids_deduit_g=poids_deduit,
                    prix_gramme_jour_da=prix_gramme,
                    notes=notes,
                    versement_item_id=selected_item_id,
                    montant_dollar=montant_dollar,
                    taux_change_dollar=taux_change_dollar,
                    remise_da=remise_da
                )
            except TypeError:
                success = self.manager.versements.add_payment(
                    versement_id=self.versement_id, journee_id=self.journee_id, montant_da=montant_da,
                    or_casse_g=or_casse, prix_gramme_jour_da=prix_gramme, notes=notes
                )

            if success:
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", "Une erreur est survenue lors de l'enregistrement.")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
