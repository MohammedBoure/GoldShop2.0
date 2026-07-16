# ui/widgets/versements/versements_view.py

import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QLineEdit, QComboBox,
    QMenu, QMessageBox, QDialog, QAbstractScrollArea, QFormLayout,
    QDoubleSpinBox, QApplication, QGroupBox
)
from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QColor, QFont, QBrush, QDesktopServices
import qtawesome as qta

try:
    from ui.tools.invoice_generator import ReceiptGenerator
except ImportError:
    ReceiptGenerator = None



def _open_numpad(widget, allow_decimal=True, parent=None):
    try:
        widget.setFocus()
        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad(mode="direct", target_widget=widget, allow_decimal=allow_decimal, allow_negative=True, parent=parent)
        pad.exec()
    except Exception:
        pass

def _open_vkb(widget, parent=None):
    try:
        widget.setFocus()
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog
        kb = VirtualKeyboardDialog(parent)
        kb.show()
    except Exception:
        pass

def _wrap_with_numpad(widget, allow_decimal=True, parent=None):
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    lay.addWidget(widget, stretch=1)
    
    btn = QPushButton("🔢")
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setFixedSize(38, 38)
    btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 16px;")
    btn.setCursor(Qt.PointingHandCursor)
    btn.clicked.connect(lambda: _open_numpad(widget, allow_decimal, parent))
    lay.addWidget(btn)
    return container

def _wrap_with_keyboard(widget, parent=None):
    container = QWidget()
    lay = QHBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(5)
    lay.addWidget(widget, stretch=1)
    
    btn = QPushButton("⌨️")
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setFixedSize(38, 38)
    btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 16px;")
    btn.setCursor(Qt.PointingHandCursor)
    btn.clicked.connect(lambda: _open_vkb(widget, parent))
    lay.addWidget(btn)
    return container

def _move_dialog_to_top(dialog):
    """نقل النافذة المنبثقة إلى أعلى الشاشة لتوفير المساحة للوحة المفاتيح"""
    screen = QApplication.primaryScreen().availableGeometry()
    dialog.move(int((screen.width() - dialog.width()) / 2), 0)


# ========================================================
# نافذة قراءة الباركود وإضافة منتج إضافي للملف
# ========================================================
class AddItemToVersementDialog(QDialog):
    def __init__(self, manager, versement_id, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.versement_id = versement_id
        self.inventory_id = None
        self.designation = ""
        self.setWindowTitle("Ajouter un article au dossier")
        self.setMinimumWidth(450)
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        _move_dialog_to_top(self)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        title = QLabel("Scanner le code-barres de l'article")
        title.setFont(QFont("", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setPlaceholderText("Code-barres...")
        self.inp_barcode.setStyleSheet("font-size: 16px; padding: 10px; border: 2px solid #3498db; border-radius: 6px;")
        self.inp_barcode.returnPressed.connect(self.search_item)
        self.inp_barcode.installEventFilter(self)
        
        # إضافة زر الكيبورد للباركود
        layout.addWidget(_wrap_with_keyboard(self.inp_barcode, self))
        
        self.lbl_result = QLabel("")
        self.lbl_result.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_result)
        
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton(" Ajouter au dossier")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_add.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold; font-size: 14px; border-radius: 6px;")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self.add_item)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.inp_barcode and event.type() == QEvent.Type.KeyPress:
            text = event.text()
            if text:
                azerty_map = str.maketrans("&é\"'(-è_çà", "1234567890")
                corrected_text = text.translate(azerty_map).upper()
                if text != corrected_text:
                    self.inp_barcode.insert(corrected_text)
                    return True
        return super().eventFilter(obj, event)

    def search_item(self):
        barcode = self.inp_barcode.text().strip().upper()
        if not barcode: return
        
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM Inventory WHERE barcode = %s", (barcode,))
                item = cursor.fetchone()
                
                if not item:
                    self.lbl_result.setText("❌ Article introuvable.")
                    self.lbl_result.setStyleSheet("color: #e74c3c; font-weight: bold;")
                    self.btn_add.setEnabled(False)
                    self.inp_barcode.selectAll()
                    return
                    
                if item['status'] != 'Available':
                    self.lbl_result.setText(f"⚠️ Cet article n'est pas disponible (Statut: {item['status']}).")
                    self.lbl_result.setStyleSheet("color: #e67e22; font-weight: bold;")
                    self.btn_add.setEnabled(False)
                    self.inp_barcode.selectAll()
                    return
                    
                self.inventory_id = item['id']
                name = item.get('name') or item.get('item_name') or 'Article sans nom'
                weight = float(item.get('weight') or 0)
                self.designation = f"{name} ({weight:.2f}g)" if (weight > 0 and f"({weight:.2f}g)" not in name and not name.strip().endswith("g)")) else name
                
                self.lbl_result.setText(f"✅ Trouvé : {self.designation}")
                self.lbl_result.setStyleSheet("color: #27ae60; font-weight: bold;")
                self.btn_add.setEnabled(True)
                self.btn_add.setFocus()
        except Exception as e:
            self.lbl_result.setText(f"Erreur de recherche : {e}")

    def add_item(self):
        if self.inventory_id and self.designation:
            if self.manager.versements.add_item_to_versement(self.versement_id, self.inventory_id, self.designation):
                self.accept()
            else:
                QMessageBox.warning(self, "Erreur", "Impossible d'ajouter l'article au dossier.")


# ========================================================
# نافذة التعديل (Edit Payment)
# ========================================================
class EditPaymentDialog(QDialog):
    def __init__(self, manager, p_data, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.p_data = p_data
        self.v_data = None
        self.item_prices = {}
        self.item_weights = {}
        
        self.setWindowTitle("Modifier le Paiement (Acompte & Déduction)")
        self.setMinimumWidth(880)
        
        self._load_versement_data()
        self.init_ui()
        self.update_dynamic_summary()

    def _load_versement_data(self):
        try:
            versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
            self.v_data = next((v for v in versements if v['id'] == self.p_data.get('v_id')), None)
            if self.v_data:
                for item in self.v_data.get('items', []):
                    self.item_prices[item['item_id']] = float(item.get('selling_price') or 0)
                    self.item_weights[item['item_id']] = float(item.get('weight') or 0)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        _move_dialog_to_top(self)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 12, 15, 12)

        title = QLabel("Corriger les détails du paiement (Paiement & Déduction)")
        title.setFont(QFont("", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # 1. قائمة تحديد المنتج الهدف
        top_layout = QHBoxLayout()
        lbl_dest = QLabel("Paiement destiné à :")
        lbl_dest.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.combo_target = QComboBox()
        self.combo_target.setStyleSheet("padding: 6px; font-size: 14px; font-weight: bold; border: 1px solid #bdc3c7; border-radius: 4px;")
        self.combo_target.addItem("📦 Dossier Global (Aucun article spécifique)", None)
        self._populate_target_combo()
        self.combo_target.currentIndexChanged.connect(self.update_dynamic_summary)
        
        btn_details = QPushButton("ℹ️ Détails Produit")
        btn_details.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; font-size: 14px; padding: 6px 12px; border-radius: 4px;")
        btn_details.setCursor(Qt.PointingHandCursor)
        btn_details.clicked.connect(self.show_product_details)
        
        top_layout.addWidget(lbl_dest)
        top_layout.addWidget(self.combo_target, stretch=1)
        top_layout.addWidget(btn_details)
        main_layout.addLayout(top_layout)
        
        # ========================================================
        # تقسيم النماذج إلى عمودين (استغلال العرض وتقليل الارتفاع)
        # ========================================================
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)

        # ─── العمود الأول: المبالغ والعملات ───
        col1_box = QGroupBox("💵 Montants & Devises")
        col1_box.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        form1 = QFormLayout(col1_box)
        form1.setSpacing(6)
        form1.setContentsMargins(10, 14, 10, 10)

        self.inp_da = QDoubleSpinBox()
        self.inp_da.setRange(-99999999, 99999999)
        self.inp_da.setSuffix(" DA")
        self.inp_da.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold;")
        self.inp_da.setValue(self.p_data.get("montant_da", 0))
        self.inp_da.valueChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_tpe = QDoubleSpinBox()
        self.inp_tpe.setRange(-99999999, 99999999)
        self.inp_tpe.setSuffix(" TPE (DA)")
        self.inp_tpe.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold; color: #2980b9;")
        self.inp_tpe.setValue(self.p_data.get("tpe_da", 0))
        self.inp_tpe.valueChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_euro = QDoubleSpinBox()
        self.inp_euro.setRange(-999999, 999999)
        self.inp_euro.setSuffix(" €")
        self.inp_euro.setStyleSheet("padding: 5px; font-size: 13px; font-weight: bold;")
        self.inp_euro.setValue(self.p_data.get("montant_euro", 0))

        self.inp_taux = QDoubleSpinBox()
        self.inp_taux.setRange(-99999, 99999)
        self.inp_taux.setStyleSheet("padding: 5px; font-size: 13px;")
        self.inp_taux.setValue(self.p_data.get("taux_change_euro", 0))

        self.inp_dollar = QDoubleSpinBox()
        self.inp_dollar.setRange(-999999, 999999)
        self.inp_dollar.setSuffix(" $")
        self.inp_dollar.setStyleSheet("padding: 5px; font-size: 13px; font-weight: bold;")
        self.inp_dollar.setValue(self.p_data.get("montant_dollar", 0))

        self.inp_taux_dollar = QDoubleSpinBox()
        self.inp_taux_dollar.setRange(-99999, 99999)
        self.inp_taux_dollar.setStyleSheet("padding: 5px; font-size: 13px;")
        self.inp_taux_dollar.setValue(self.p_data.get("taux_change_dollar", 0))

        # ربط الحقول بالمساعد الحسابي التلقائي
        self.inp_euro.valueChanged.connect(lambda _: self.calc_da_eq())
        self.inp_taux.valueChanged.connect(lambda _: self.calc_da_eq())
        self.inp_dollar.valueChanged.connect(lambda _: self.calc_da_eq())
        self.inp_taux_dollar.valueChanged.connect(lambda _: self.calc_da_eq())

        form1.addRow("Montant (DA):", _wrap_with_numpad(self.inp_da, parent=self))
        form1.addRow("TPE (DA):", _wrap_with_numpad(self.inp_tpe, parent=self))
        form1.addRow("Montant (€):", _wrap_with_numpad(self.inp_euro, parent=self))
        form1.addRow("Taux de change (€):", _wrap_with_numpad(self.inp_taux, parent=self))
        form1.addRow("Montant ($):", _wrap_with_numpad(self.inp_dollar, parent=self))
        form1.addRow("Taux de change ($):", _wrap_with_numpad(self.inp_taux_dollar, parent=self))
        
        columns_layout.addWidget(col1_box, stretch=1)

        # ─── العمود الثاني: الذهب المكسر، الخصم والملاحظات ───
        col2_layout = QVBoxLayout()
        col2_layout.setSpacing(8)
        
        col2_box = QGroupBox("🎁 Or Cassé & Déductions (Poids)")
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
        btn_ppg = QPushButton("Prix/g Target")
        btn_ppg.setStyleSheet("background-color: #8e44ad; color: white; padding: 5px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_ppg.setCursor(Qt.PointingHandCursor)
        btn_ppg.clicked.connect(self.open_discount_price_per_gram)
        
        remise_buttons_layout.addWidget(btn_pct)
        remise_buttons_layout.addWidget(btn_arrondi)
        remise_buttons_layout.addWidget(btn_ppg)
        form2.addRow(lbl_remise_tools, remise_buttons_layout)

        self.inp_oc = QDoubleSpinBox()
        self.inp_oc.setRange(-10000, 10000)
        self.inp_oc.setDecimals(3)
        self.inp_oc.setSuffix(" g")
        self.inp_oc.setStyleSheet("padding: 5px; font-size: 13px; font-weight: bold; color: #d35400;")
        self.inp_oc.setValue(self.p_data.get("or_casse_g", 0))

        self.inp_remise = QDoubleSpinBox()
        self.inp_remise.setRange(0, 99999999)
        self.inp_remise.setSuffix(" DA")
        self.inp_remise.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold; color: #8e44ad;")
        self.inp_remise.setValue(self.p_data.get("remise_da", 0))
        self.inp_remise.valueChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_deduit = QDoubleSpinBox()
        self.inp_deduit.setRange(-10000, 10000)
        self.inp_deduit.setDecimals(3)
        self.inp_deduit.setSuffix(" g")
        self.inp_deduit.setStyleSheet("padding: 5px; font-size: 14px; font-weight: bold; color: white; background-color: #2c3e50;")
        self.inp_deduit.setValue(self.p_data.get("poids_deduit_g", 0))
        self.inp_deduit.valueChanged.connect(lambda _: self.update_dynamic_summary())

        self.inp_notes = QLineEdit()
        self.inp_notes.setStyleSheet("padding: 5px; font-size: 13px;")
        self.inp_notes.setText(self.p_data.get("notes", ""))

        form2.addRow("Or Cassé (g):", _wrap_with_numpad(self.inp_oc, parent=self))
        form2.addRow("Remise accordée (DA):", _wrap_with_numpad(self.inp_remise, parent=self))
        form2.addRow("Poids à Déduire (g):", _wrap_with_numpad(self.inp_deduit, parent=self))
        form2.addRow("Notes:", _wrap_with_keyboard(self.inp_notes, self))
        col2_layout.addWidget(col2_box)

        # العرض الديناميكي للصافي المباشر بالجرام والدينار والنسبة المئوية
        self.summary_box = QGroupBox("📊 Impact du Paiement sur le Dossier (Reste en Grammes)")
        self.summary_box.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; background-color: #f8f9fa; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        sum_layout = QFormLayout(self.summary_box)
        sum_layout.setContentsMargins(10, 10, 10, 10)
        sum_layout.setSpacing(6)
        
        self.lbl_summary_reste = QLabel("0.00 g (0.00 DA)")
        self.lbl_summary_reste.setStyleSheet("font-size: 13px; font-weight: bold; color: #c0392b;")
        
        self.lbl_summary_current = QLabel("0.00 DA")
        self.lbl_summary_current.setStyleSheet("font-size: 13px; font-weight: bold; color: #27ae60;")
        
        self.lbl_summary_nouveau = QLabel("0.00 g")
        self.lbl_summary_nouveau.setStyleSheet("font-size: 16px; font-weight: bold; color: #c0392b;")
        
        sum_layout.addRow(QLabel("Reste Initial (Sans ce paiement) :"), self.lbl_summary_reste)
        sum_layout.addRow(QLabel("Paiement + Remise Modifiés :"), self.lbl_summary_current)
        sum_layout.addRow(QLabel("Nouveau Reste Final :"), self.lbl_summary_nouveau)
        col2_layout.addWidget(self.summary_box)
        col2_layout.addStretch()

        columns_layout.addLayout(col2_layout, stretch=1)
        main_layout.addLayout(columns_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px 25px; font-weight: bold; border-radius: 4px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_save = QPushButton("Enregistrer les modifications")
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 25px; font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self.save_data)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

    def calc_da_eq(self):
        """مساعد في الحساب: يكتب تلقائياً القيمة المقابلة بالدينار ويسمح للمستخدم بالتعديل كأداة مساعدة فقط"""
        try:
            euro = self.inp_euro.value()
            taux = self.inp_taux.value()
            dollar = self.inp_dollar.value()
            taux_dollar = self.inp_taux_dollar.value()
            total_da = (euro * taux) + (dollar * taux_dollar)
            if total_da != 0:
                self.inp_da.blockSignals(True)
                self.inp_da.setValue(total_da)
                self.inp_da.blockSignals(False)
                self.auto_calculate_poids_deduit()
        except Exception:
            pass

    def _get_active_base_amount(self):
        selected_item_id = self.combo_target.currentData()
        if selected_item_id and selected_item_id in self.item_prices:
            item_amount = float(self.item_prices[selected_item_id] or 0)
            current_payment_id = self.p_data.get('payment_id')
            item_paid = sum(
                float(p.get('montant_da') or 0) +
                float(p.get('tpe_da') or 0) +
                float(p.get('remise_da') or 0)
                for p in (self.v_data.get('payments', []) if self.v_data else [])
                if p.get('versement_item_id') == selected_item_id and p.get('id') != current_payment_id
            )
            return max(0.0, item_amount - item_paid)
        elif self.v_data:
            total_est = self.v_data.get('total_estimated_price_da', 0)
            total_paid = self.v_data.get('total_paid_money_da', 0) + self.v_data.get('total_remise_da', 0)
            # إرجاع المبلغ المدفوع القديم للحصول على الأساس الحقيقي قبل هذه الدفعة
            old_pay = float(self.p_data.get('montant_da', 0)) + float(self.p_data.get('tpe_da', 0)) + float(self.p_data.get('remise_da', 0))
            return max(0.0, (total_est - total_paid) + old_pay)
        return 0.0

    def _get_active_base_weight(self):
        selected_item_id = self.combo_target.currentData()
        if selected_item_id and selected_item_id in self.item_weights:
            w = self.item_weights[selected_item_id]
            deductions = sum(float(p.get('poids_deduit_g') or 0) for p in self.v_data.get('payments', []) if p.get('versement_item_id') == selected_item_id)
            old_deduction = float(self.p_data.get('poids_deduit_g', 0)) if self.p_data.get('versement_item_id') == selected_item_id else 0.0
            return max(0.0, (w - deductions) + old_deduction)
        elif self.v_data:
            old_deduction = float(self.p_data.get('poids_deduit_g', 0))
            return float(self.v_data.get('reste_poids_g', 0)) + old_deduction
        return 0.0

    def open_discount_pct(self):
        base_amount = self._get_active_base_amount()
        if base_amount <= 0:
            QMessageBox.warning(self, "Erreur", "Aucune base de prix estimé disponible pour calculer la remise.")
            return
        
        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad(title="Saisir la Remise (%)", mode="dialog", allow_decimal=True, allow_negative=False, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                pct = float(val)
                if 0 <= pct <= 100:
                    remise_val = base_amount * (pct / 100.0)
                    self.inp_remise.setValue(remise_val)
                else:
                    QMessageBox.warning(self, "Erreur", "Le pourcentage doit être entre 0 et 100.")

    def open_discount_arrondi(self):
        base_amount = self._get_active_base_amount()
        if base_amount <= 0:
            QMessageBox.warning(self, "Erreur", "Aucun reste estimé disponible à solder ou arrondir.")
            return
        
        current_pay = self.inp_da.value() + self.inp_tpe.value()
        reste_actuel = max(0.0, base_amount - current_pay)
        
        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad(title="Saisir le Nouveau Reste Cible (DA)", mode="dialog", allow_decimal=True, allow_negative=False, initial_value=reste_actuel, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                cible = float(val)
                if 0 <= cible <= base_amount:
                    remise_needed = base_amount - current_pay - cible
                    if remise_needed >= 0:
                        self.inp_remise.setValue(remise_needed)
                    else:
                        QMessageBox.warning(self, "Erreur", "Le paiement actuel dépasse déjà le montant cible.")
                else:
                    QMessageBox.warning(self, "Erreur", f"Le reste cible doit être entre 0 et {base_amount:,.2f} DA.")

    def _get_price_per_gram_context(self):
        selected_item_id = self.combo_target.currentData()
        if selected_item_id is None:
            selected_item_id = getattr(self, "preselected_item_id", None)
        if selected_item_id is None:
            selected_item_id = getattr(self, "p_data", {}).get("versement_item_id")

        current_payment = getattr(self, "p_data", {})
        current_payment_id = current_payment.get("payment_id")
        if selected_item_id in self.item_prices and selected_item_id in self.item_weights:
            item_amount = float(self.item_prices[selected_item_id] or 0)
            item_weight = float(self.item_weights[selected_item_id] or 0)
            if item_amount > 0 and item_weight > 0:
                deducted_weight = sum(
                    float(p.get("poids_deduit_g") or 0)
                    for p in (self.v_data.get("payments", []) if self.v_data else [])
                    if p.get("versement_item_id") == selected_item_id
                )
                if current_payment_id and current_payment.get("versement_item_id") == selected_item_id:
                    deducted_weight -= float(current_payment.get("poids_deduit_g") or 0)
                return item_amount / item_weight, max(0.0, item_weight - deducted_weight)

        if self.v_data:
            total_amount = float(self.v_data.get("total_estimated_price_da") or 0)
            total_weight = float(self.v_data.get("total_weight_g") or 0)
            if total_amount > 0 and total_weight > 0:
                remaining_weight = float(self.v_data.get("reste_poids_g") or 0)
                if current_payment_id:
                    remaining_weight += float(current_payment.get("poids_deduit_g") or 0)
                return total_amount / total_weight, max(0.0, remaining_weight)

        return 0.0, 0.0

    def _get_price_per_gram_context(self):
        selected_item_id = self.combo_target.currentData()
        if selected_item_id is None:
            selected_item_id = getattr(self, "preselected_item_id", None)
        if selected_item_id is None:
            selected_item_id = getattr(self, "p_data", {}).get("versement_item_id")

        current_payment = getattr(self, "p_data", {})
        current_payment_id = current_payment.get("payment_id")
        if selected_item_id in self.item_prices and selected_item_id in self.item_weights:
            item_amount = float(self.item_prices[selected_item_id] or 0)
            item_weight = float(self.item_weights[selected_item_id] or 0)
            if item_amount > 0 and item_weight > 0:
                deducted_weight = sum(
                    float(p.get("poids_deduit_g") or 0)
                    for p in (self.v_data.get("payments", []) if self.v_data else [])
                    if p.get("versement_item_id") == selected_item_id
                )
                if current_payment_id and current_payment.get("versement_item_id") == selected_item_id:
                    deducted_weight -= float(current_payment.get("poids_deduit_g") or 0)
                return item_amount / item_weight, max(0.0, item_weight - deducted_weight)

        if self.v_data:
            total_amount = float(self.v_data.get("total_estimated_price_da") or 0)
            total_weight = float(self.v_data.get("total_weight_g") or 0)
            if total_amount > 0 and total_weight > 0:
                remaining_weight = float(self.v_data.get("reste_poids_g") or 0)
                if current_payment_id:
                    remaining_weight += float(current_payment.get("poids_deduit_g") or 0)
                return total_amount / total_weight, max(0.0, remaining_weight)

        return 0.0, 0.0

    def open_discount_price_per_gram(self):
        current_ppg, available_weight = self._get_price_per_gram_context()
        if current_ppg <= 0 or available_weight <= 0:
            QMessageBox.warning(self, "Erreur", "Aucun article actif avec prix et poids restants n'est disponible pour calculer la remise.")
            return

        payment_value_da = max(0.0, self.inp_montant_da.value() + self.inp_tpe.value())
        if payment_value_da <= 0:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir d'abord la valeur du versement Ã  calculer.")
            return

        from ui.tools.virtual_numpad import VirtualNumpad
        pad = VirtualNumpad(
            title=f"Saisir le prix/g (actuel: {current_ppg:,.2f} DA/g)",
            mode="dialog",
            allow_decimal=True,
            allow_negative=False,
            initial_value=current_ppg,
            parent=self
        )
        if pad.exec() == QDialog.Accepted:
            value = pad.get_value()
            if value:
                target_ppg = min(max(0.0, float(value)), current_ppg)
                payment_weight = min(available_weight, payment_value_da / current_ppg)
                remise_value = max(0.0, (current_ppg - target_ppg) * payment_weight)
                self.inp_remise.setValue(remise_value)
    def auto_calculate_poids_deduit(self):
        """مساعد في الحساب: يكتب تلقائياً الوزن المقتنى بالجرام ويسمح للمستخدم بالتعديل اليدوي كأداة مساعدة"""
        base_amount = self._get_active_base_amount()
        base_weight = self._get_active_base_weight()
        
        current_pay = self.inp_da.value() + self.inp_tpe.value()
        remise = self.inp_remise.value()
        
        if base_amount > 0 and base_weight > 0:
            prix_g_moyen = base_amount / base_weight
            poids_auto = (current_pay + remise) / prix_g_moyen
            if poids_auto > base_weight: poids_auto = base_weight
            
            self.inp_deduit.blockSignals(True)
            self.inp_deduit.setValue(poids_auto)
            self.inp_deduit.blockSignals(False)
            
        self.update_dynamic_summary()

    def update_dynamic_summary(self):
        base_amount = self._get_active_base_amount()
        base_weight = self._get_active_base_weight()
        
        current_pay = self.inp_da.value() + self.inp_tpe.value()
        remise = self.inp_remise.value()
        poids_deduit = self.inp_deduit.value()
        
        remise_pct = (remise / base_amount * 100.0) if base_amount > 0 else 0.0
        nouveau_reste_da = max(0.0, base_amount - (current_pay + remise))
        nouveau_reste_g = max(0.0, base_weight - poids_deduit)
        
        self.lbl_summary_reste.setText(f"{base_weight:,.2f} g  (Estimé: {base_amount:,.2f} DA)")
        self.lbl_summary_current.setText(f"{(current_pay + remise):,.2f} DA  [Remise: {remise:,.2f} DA ({remise_pct:.1f}%)]")
        self.lbl_summary_nouveau.setText(f"{nouveau_reste_g:,.2f} g  (Estimé: {nouveau_reste_da:,.2f} DA)")


    def _populate_target_combo(self):
        try:
            versement_id = self.p_data.get('v_id')
            current_item_id = self.p_data.get('versement_item_id')
            self.target_to_inventory = {}
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT vi.id, vi.inventory_id, vi.designation, i.weight, cat.name as category_name, sup.name as supplier_name
                    FROM Versement_Items vi
                    LEFT JOIN Inventory i ON vi.inventory_id = i.id
                    LEFT JOIN Categories cat ON i.category_id = cat.id
                    LEFT JOIN Suppliers sup ON i.supplier_id = sup.id
                    WHERE vi.versement_id = %s AND vi.item_status != 'ANNULE'
                """, (versement_id,))
                items = cursor.fetchall()
                
                for item in items:
                    self.target_to_inventory[item['id']] = item['inventory_id']
                    w = float(item['weight'] or 0)
                    desig = item['designation']
                    display_name = f"{desig} ({w:.2f}g)" if (w > 0 and f"({w:.2f}g)" not in desig and not desig.strip().endswith("g)")) else desig
                    if item.get('category_name'):
                        display_name += f" | Cat: {item['category_name']}"
                    if item.get('supplier_name'):
                        display_name += f" | Fourn: {item['supplier_name']}"
                    self.combo_target.addItem(f"💍 {display_name}", item['id'])
                    
                    if current_item_id and item['id'] == current_item_id:
                        idx = self.combo_target.count() - 1
                        self.combo_target.setCurrentIndex(idx)
        except Exception as e:
            print(f"Erreur chargement articles combo (Edit): {e}")

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

    def save_data(self):
        try:
            success = self.manager.versements.update_payment(
                payment_id=self.p_data['payment_id'],
                montant_da=self.inp_da.value(),
                tpe_da=self.inp_tpe.value(),
                montant_euro=self.inp_euro.value(),
                taux_change_euro=self.inp_taux.value(),
                or_casse_g=self.inp_oc.value(),
                poids_deduit_g=self.inp_deduit.value(),
                notes=self.inp_notes.text(),
                versement_item_id=self.combo_target.currentData(),
                montant_dollar=self.inp_dollar.value(),
                taux_change_dollar=self.inp_taux_dollar.value(),
                remise_da=self.inp_remise.value()
            )
        except TypeError:
            success = self.manager.versements.update_payment(
                payment_id=self.p_data['payment_id'],
                montant_da=self.inp_da.value(),
                tpe_da=self.inp_tpe.value(),
                montant_euro=self.inp_euro.value(),
                taux_change_euro=self.inp_taux.value(),
                or_casse_g=self.inp_oc.value(),
                poids_deduit_g=self.inp_deduit.value(),
                notes=self.inp_notes.text(),
                versement_item_id=self.combo_target.currentData()
            )

        if success:
            self.accept()
        else:
            QMessageBox.critical(self, "Erreur", "Échec de la modification.")



class FacturationVersementDialog(QDialog):
    def __init__(self, manager, data, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.data = data
        self.setWindowTitle("Facturation d'un article livré")
        self.setFixedSize(450, 400)
        self.v_data = None
        self.client_id = None
        self._load_v_data()
        self._init_ui()
        
    def _load_v_data(self):
        versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
        self.v_data = next((v for v in versements if v['id'] == self.data.get("v_id")), None)
        self.client_id = self.v_data.get('client_id') if self.v_data else 1
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        lbl_info = QLabel("<b>Article :</b> " + str(self.data.get("designation", "")))
        lbl_info.setStyleSheet("font-size: 16px; color: #2c3e50;")
        layout.addWidget(lbl_info)
        
        lbl_desc = QLabel("La facturation de cet article générera une facture de vente (Journal Excel).")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #7f8c8d; font-size: 13px;")
        layout.addWidget(lbl_desc)
        
        form = QFormLayout()
        self.inp_price = QLineEdit("0")
        self.inp_price.setStyleSheet("font-size: 18px; font-weight: bold; color: #27ae60; padding: 5px;")
        self.inp_price.setFocusPolicy(Qt.ClickFocus)
        self.inp_price.mousePressEvent = lambda e: _open_numpad(self.inp_price, allow_decimal=True, parent=self)
        form.addRow("Prix de Vente Final (DA):", self.inp_price)
        
        self.inp_cash = QLineEdit("0")
        self.inp_cash.setStyleSheet("font-size: 18px; font-weight: bold; color: #2980b9; padding: 5px;")
        self.inp_cash.setFocusPolicy(Qt.ClickFocus)
        self.inp_cash.mousePressEvent = lambda e: _open_numpad(self.inp_cash, allow_decimal=True, parent=self)
        form.addRow("Cash Payé Aujourd'hui (DA):", self.inp_cash)
        
        self.combo_vendeur = QComboBox()
        self.combo_vendeur.setStyleSheet("font-size: 16px; padding: 5px;")
        self._load_sellers()
        form.addRow("Vendeur :", self.combo_vendeur)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        
        btn_confirm = QPushButton("Facturer et Livrer")
        btn_confirm.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        btn_confirm.clicked.connect(self.accept)
        
        for btn in [btn_cancel, btn_confirm]:
            btn.setFixedHeight(45)
            btn_layout.addWidget(btn)
            
        layout.addLayout(btn_layout)
        
    def _load_sellers(self):
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, username FROM Users WHERE is_active = 1")
                for u in cursor.fetchall():
                    self.combo_vendeur.addItem(u['username'], u['id'])
        except Exception:
            pass

# ========================================================
# الواجهة الرئيسية (Versements View)
# ========================================================
class VersementsView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        lbl_main_title = QLabel("SUIVI DES VERSEMENTS & ACOMPTES CLIENTS")
        lbl_main_title.setAlignment(Qt.AlignCenter)
        lbl_main_title.setStyleSheet("""
            font-size: 20px; font-weight: 900; color: white;
            background-color: #0f8f83; padding: 10px; border-radius: 4px; letter-spacing: 1px;
        """)
        layout.addWidget(lbl_main_title)

        tools_layout = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Rechercher par nom ou téléphone...")
        self.inp_search.setStyleSheet("font-size: 13px; padding: 5px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        self.inp_search.textChanged.connect(self.load_data)
        tools_layout.addWidget(self.inp_search)

        self.combo_status = QComboBox()
        self.combo_status.addItems(["En Cours", "Clôturé", "Annulé", "Tous"])
        self.combo_status.setStyleSheet("font-size: 13px; padding: 5px 8px; border: 1px solid #cbd5df; border-radius: 4px; background-color: white;")
        self.combo_status.currentTextChanged.connect(self.load_data)
        tools_layout.addWidget(self.combo_status)

        self.btn_new = QPushButton(" + Nouveau Versement")
        self.btn_new.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_new.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 13px; padding: 5px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_new.clicked.connect(self.open_new_versement_dialog)
        tools_layout.addWidget(self.btn_new)

        self.toolbar_actions_widget = QWidget()
        self.toolbar_actions_layout = QHBoxLayout(self.toolbar_actions_widget)
        self.toolbar_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_actions_layout.setSpacing(5)
        tools_layout.addWidget(self.toolbar_actions_widget)
        tools_layout.addStretch()

        layout.addLayout(tools_layout)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Date / Opération", "Cash (DA)", "TPE (DA)", "Montant (€/$)", "Taux (DA/€/$)", "Or Cassé (g)", "Poids Déduit", "Statut", "Observation"
        ])
        
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #ffffff; font-size: 14px; gridline-color: #dcdde1; border: 1px solid #cbd5df; }
            QHeaderView::section { background-color: #0f8f83; color: white; font-weight: bold; font-size: 14px; padding: 6px; border: 1px solid #0b776d; }
            QTableWidget::item { padding: 6px 10px; background-color: transparent; color: unset; }
            QTableWidget::item:selected { background-color: #d1d8e0; color: black; }
        """)
        
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 8): header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Stretch)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        layout.addWidget(self.table)

    # ──────────────────────────────────────────────────────────────
    # قراءة أسماء الطابعات من الإعدادات
    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _read_config_json():
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @classmethod
    def _get_pdf_printer_name(cls):
        cfg = cls._read_config_json()
        return str(cfg.get("pdf_config", {}).get("printer_name", "") or "").strip()

    @classmethod
    def _get_thermal_printer_name(cls):
        cfg = cls._read_config_json()
        return str(cfg.get("thermal_config", {}).get("printer_name", "") or "").strip()

    # ──────────────────────────────────────────────────────────────
    # تجهيز بيانات Versement (مشتركة بين PDF و الحرارية)
    # ──────────────────────────────────────────────────────────────
    def _prepare_versement_data(self, versement_id):
        versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
        v_data = next((v for v in versements if v['id'] == versement_id), None)
        
        if not v_data:
            return None, None

        v_num = f"VRS-{v_data['id']:05d}"
        
        pdf_data = {
            "customer_name": v_data.get('client_name', 'Client Inconnu'),
            "phone": v_data.get('phone', ''),
            "sale_id": v_data['id'],
            "operation_number": v_num,
            "versement_operation_number": v_num,
            "versements": [],
            "items": [],
            "currency": "DA"
        }

        total_active_w = sum(float(i['weight'] or 0) for i in v_data.get('items', []) if i['item_status'] != 'ANNULE')
        global_deductions = sum(float(p.get('poids_deduit_g') or 0) for p in v_data.get('payments', []) if p.get('versement_item_id') is None)

        for item in v_data.get('items', []):
            if item.get('item_status') != 'ANNULE':
                desig = item.get('designation', '')
                w = float(item.get('weight') or 0)
                full_name = f"{desig} ({w:.2f}g)" if (w > 0 and f"({w:.2f}g)" not in desig and not desig.strip().endswith("g)")) else desig
                
                item_specific_deduction = sum(float(p.get('poids_deduit_g') or 0) for p in v_data.get('payments', []) if p.get('versement_item_id') == item.get('item_id'))
                item_global_share = global_deductions * (w / total_active_w) if total_active_w > 0 else 0
                item_remaining_w = max(0.0, w - (item_specific_deduction + item_global_share))

                pdf_data['items'].append({
                    "name": full_name,
                    "item_name": full_name,
                    "description": desig,
                    "barcode": item.get('barcode', ''),
                    "weight": w,
                    "total_weight": w,
                    "remaining_weight": item_remaining_w,
                    "total_amount": 0.0,
                })

        for p in v_data.get('payments', []):
            montant_da = float(p.get('montant_da') or 0)
            montant_tpe = float(p.get('tpe_da') or 0)
            montant_euro = float(p.get('montant_euro') or 0)
            taux = float(p.get('taux_change_euro') or 0)
            montant_dollar = float(p.get('montant_dollar') or 0)
            taux_dollar = float(p.get('taux_change_dollar') or 0)
            remise_da = float(p.get('remise_da') or 0)
            
            poids_casse = float(p.get('or_casse_g') or 0)
            poids_deduit = float(p.get('poids_deduit_g') or 0)
            
            total_money = montant_da + montant_tpe
            total_weight_pay = poids_casse + poids_deduit

            item_desig = p.get('item_designation', '')
            if item_desig:
                for it in v_data.get('items', []):
                    if it.get('designation') == item_desig:
                        w = float(it.get('weight') or 0)
                        if w > 0 and f"({w:.2f}g)" not in item_desig and not item_desig.strip().endswith("g)"):
                            item_desig = f"{item_desig} ({w:.2f}g)"
                        break

            pdf_data['versements'].append({
                "id": p.get('id', ''),
                "payment_date": p.get('payment_date'),
                "amount": total_money,
                "tpe_da": montant_tpe,
                "montant_euro": montant_euro,
                "taux_change_euro": taux,
                "montant_dollar": montant_dollar,
                "taux_change_dollar": taux_dollar,
                "remise_da": remise_da,
                "weight": total_weight_pay,
                "product_name": item_desig,
                "item_name": item_desig,
                "operation_number": v_num
            })

        pdf_data['total_weight'] = float(v_data.get('total_weight_g', 0))
        pdf_data['exact_paid_weight'] = float(v_data.get('total_paid_weight_g', 0))
        pdf_data['remaining_weight'] = float(v_data.get('reste_poids_g', 0))
        pdf_data['total_paid'] = float(v_data.get('total_paid_money_da', 0))
        pdf_data['total_remise_da'] = float(v_data.get('total_remise_da', 0))
        pdf_data['total_dollar'] = float(v_data.get('total_dollar', 0))
        pdf_data['total_amount'] = pdf_data['total_paid']
        pdf_data['total_quantity'] = len(pdf_data['items'])

        return pdf_data, v_data

    # ──────────────────────────────────────────────────────────────
    # القائمة المنبثقة (كليك يمين)
    # ──────────────────────────────────────────────────────────────
    def show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0: return
        item = self.table.item(row, 0)
        if not item: return
        
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict): return
        
        row_type = data.get("type")
        v_id = data.get("v_id")
        v_statut = data.get("statut")

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { font-size: 15px; background-color: white; border: 1px solid #ccc; }
            QMenu::item { padding: 10px 30px; }
            QMenu::item:selected { background-color: #3498db; color: white; }
            QMenu::separator { height: 1px; background: #ddd; margin: 4px 10px; }
        """)
        
        act_print_pdf = act_print_direct = act_print_thermal = None
        act_pay_global = act_close = act_cancel = act_add_item = act_show_details = None
        act_reopen_versement = None
        act_pay_item = act_retirer_item = act_cancel_item = act_delete_item = None
        act_change_item_status = None
        act_edit_pay = act_delete_pay = None

        if row_type == "HEADER":
            act_show_details = menu.addAction("ℹ️ Afficher les spécifications détaillées des articles")
            menu.addSeparator()
            pdf_printer = self._get_pdf_printer_name()
            thermal_printer = self._get_thermal_printer_name()

            act_print_pdf = menu.addAction("📄 Télécharger Bon (Aperçu PDF)")

            if pdf_printer:
                act_print_direct = menu.addAction(f"🖨️ Imprimer directement → {pdf_printer}")
            else:
                act_print_direct = menu.addAction("🖨️ Imprimer directement (non configurée)")
                act_print_direct.setEnabled(False)

            if thermal_printer:
                act_print_thermal = menu.addAction(f"🧾 Imprimer sur thermique → {thermal_printer}")
            else:
                act_print_thermal = menu.addAction("🧾 Imprimer sur thermique (non configurée)")
                act_print_thermal.setEnabled(False)

            if v_statut == 'EN_COURS':
                menu.addSeparator()
                act_add_item = menu.addAction("➕ Ajouter un nouvel article à ce dossier")
                menu.addSeparator()
                act_pay_global = menu.addAction("💵 Ajouter un paiement (Dossier Global)")
                act_close = menu.addAction("✅ Clôturer tout le dossier")
                menu.addSeparator()
                act_cancel = menu.addAction("❌ Annuler tout le dossier")
            elif v_statut in ('CLOTURE', 'ANNULE'):
                menu.addSeparator()
                act_reopen_versement = menu.addAction("🔄 Changer état : remettre le dossier En Cours")
            
        elif row_type == "ITEM":
            act_show_details = menu.addAction("ℹ️ Afficher les spécifications détaillées du produit")
            menu.addSeparator()
            item_status = data.get("item_status")
            if item_status == 'EN_COURS' and v_statut == 'EN_COURS':
                act_pay_item = menu.addAction("💵 Ajouter un paiement pour CET ARTICLE")
                act_retirer_item = menu.addAction("📦 Marquer cet article comme RETIRÉ (Livré)")
                menu.addSeparator()
                act_cancel_item = menu.addAction("❌ Annuler l'article (Retour vitrine)")
                act_delete_item = menu.addAction("🗑️ Supprimer du dossier (Erreur d'ajout)")
            elif item_status == 'RETIRE':
                act_change_item_status = menu.addAction("🔄 Changer état : remettre l'article En Cours")
            elif item_status == 'ANNULE':
                act_change_item_status = menu.addAction("🔄 Changer état : remettre l'article En Cours")
            else:
                menu.addAction("ℹ️ Le dossier est " + v_statut.lower())

        elif row_type == "PAYMENT" and v_statut == 'EN_COURS':
            act_edit_pay = menu.addAction("✏️ Modifier ce paiement")
            act_delete_pay = menu.addAction("🗑️ Supprimer ce paiement (Erreur de saisie)")

        if menu.isEmpty(): return
        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if not action: return
        
        if action == act_show_details:
            self.show_product_specs(data)
        elif action == act_print_pdf:
            self.print_versement_pdf(v_id, open_pdf=True, direct=False)
        elif action == act_print_direct:
            self.print_versement_pdf(v_id, open_pdf=False, direct=True)
        elif action == act_print_thermal:
            self.print_versement_thermal(v_id)
        elif action == act_add_item:
            self.open_add_item_dialog(v_id)
        elif action == act_pay_global:
            self.open_add_payment_dialog(v_id)
        elif action == act_pay_item:
            self.open_add_payment_dialog(v_id, preselected_item_id=data.get("item_id"))
        elif action == act_retirer_item:
            self._handle_retirer_item(data)
        elif action == act_cancel_item:
            self._handle_cancel_item(data)
        elif action == act_delete_item:
            self._handle_delete_item(data)
        elif action == act_change_item_status:
            self._handle_change_item_status(data)
        elif action == act_close:
            self._handle_close_versement(v_id)
        elif action == act_cancel:
            self._handle_cancel_versement(v_id)
        elif action == act_reopen_versement:
            self._handle_change_versement_status(v_id, 'EN_COURS')
        elif action == act_delete_pay:
            self._handle_delete_payment(data)
        elif action == act_edit_pay:
            self._handle_edit_payment(data)

    def _handle_retirer_item(self, data):
        dlg = FacturationVersementDialog(self.manager, data, self)
        if dlg.exec() == QDialog.Accepted:
            try: price = float(dlg.inp_price.text() or 0)
            except: price = 0.0
            try: cash = float(dlg.inp_cash.text() or 0)
            except: cash = 0.0
            vendeur_id = dlg.combo_vendeur.currentData() or 1
            
            success = self.manager.versements.retirer_versement_item(data.get("item_id"))
            if success:
                journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
                if cash > 0 and journee:
                    self.manager.versements.add_payment(
                        versement_id=data.get("v_id"),
                        journee_id=journee['id'],
                        montant_da=cash,
                        or_casse_g=0, prix_gramme_jour_da=0,
                        notes=f"Cash de livraison {data.get('designation', '')}",
                        versement_item_id=data.get("item_id")
                    )
                
                if journee:
                    cart_items = [{
                        'id': data.get("inventory_id"),
                        'item_type': 'WEIGHT',
                        'barcode': '',
                        'name': data.get("designation", "Article Versement"),
                        'cart_sold_weight': data.get("weight", 0),
                        'cart_sold_qty': 1,
                        'cart_unit_price': price,
                        'cart_line_total': price,
                        'custom_note': f"Vendu via Versement N°VRS-{data.get('v_id'):05d}"
                    }]
                    self.manager.sales.create_sale(
                        journee_id=journee['id'],
                        client_id=dlg.client_id,
                        user_id=vendeur_id,
                        cart_items=cart_items,
                        total_amount=price,
                        discount=0,
                        net_to_pay=price,
                        cash_paid=0,
                        tpe_paid=0, old_gold_weight=0, impos_weight=0,
                        notes=f"Facturé depuis Versement N°VRS-{data.get('v_id'):05d} (Cash payé: {cash} DA)"
                    )
                self.load_data()
            else:
                QMessageBox.warning(self, "Erreur", "Impossible de livrer l'article.")

    def _handle_cancel_item(self, data):
        if QMessageBox.question(self, "Annuler", "Annuler cet article ? (Retour en vitrine)", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.manager.versements.cancel_versement_item(data.get("item_id")): self.load_data()

    def _handle_delete_item(self, data):
        if QMessageBox.question(self, "Supprimer", "Voulez-vous supprimer définitivement cet article du dossier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            success, msg = self.manager.versements.delete_versement_item(data.get("item_id"))
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_change_item_status(self, data):
        if QMessageBox.question(self, "Changer état", "Remettre cet article en cours dans le dossier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            success, msg = self.manager.versements.revert_versement_item_status(data.get("item_id"))
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_close_versement(self, v_id):
        if QMessageBox.question(self, "Clôturer", "Confirmer la clôture de ce versement ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
            journee_id = journee['id'] if journee else 1
            success, msg = self.manager.versements.change_versement_status(v_id, 'CLOTURE', journee_id)
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_cancel_versement(self, v_id):
        if QMessageBox.question(self, "Annuler", "Voulez-vous vraiment annuler tout le dossier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            success, msg = self.manager.versements.change_versement_status(v_id, 'ANNULE')
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_change_versement_status(self, v_id, target_status):
        labels = {
            'EN_COURS': 'remettre ce dossier En Cours',
            'CLOTURE': 'cloturer ce dossier',
            'ANNULE': 'annuler ce dossier',
        }
        message = f"Confirmer: {labels.get(target_status, 'changer le statut de ce dossier')} ?"
        if QMessageBox.question(self, "Changer état", message, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
            journee_id = journee['id'] if journee else 1
            success, msg = self.manager.versements.change_versement_status(v_id, target_status, journee_id)
            if success: self.load_data()
            else: QMessageBox.warning(self, "Erreur", msg)

    def _handle_delete_payment(self, data):
        if QMessageBox.question(self, "Supprimer", "Voulez-vous vraiment annuler et supprimer ce paiement ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.manager.versements.delete_payment(data.get("payment_id")): self.load_data()
            else: QMessageBox.critical(self, "Erreur", "Impossible de supprimer ce paiement.")

    def _handle_edit_payment(self, data):
        dlg = EditPaymentDialog(self.manager, data, self)
        if dlg.exec() == QDialog.Accepted: self.load_data()

    def _add_action_btn(self, icon_name, tooltip, bg_color, hover_color, callback, enabled=True):
        btn = QPushButton()
        btn.setIcon(qta.icon(icon_name, color="white"))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        btn.setEnabled(enabled)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg_color}; border: none; padding: 5px 10px; border-radius: 4px; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
            QPushButton:disabled {{ background-color: #bdc3c7; }}
        """)
        btn.clicked.connect(callback)
        self.toolbar_actions_layout.addWidget(btn)
        return btn

    def on_table_selection_changed(self):
        while self.toolbar_actions_layout.count():
            child = self.toolbar_actions_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        selected_rows = self.table.selectedItems()
        if not selected_rows: return
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if not item: return
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict): return

        row_type = data.get("type")
        v_id = data.get("v_id")
        v_statut = data.get("statut")

        if row_type == "HEADER":
            self._add_action_btn("fa5s.info-circle", "Spécifications détaillées", "#3498db", "#2980b9", lambda: self.show_product_specs(data))
            self._add_action_btn("fa5s.file-pdf", "Télécharger Bon (PDF)", "#e74c3c", "#c0392b", lambda: self.print_versement_pdf(v_id, open_pdf=True, direct=False))
            pdf_printer = self._get_pdf_printer_name()
            self._add_action_btn("fa5s.print", f"Imprimer direct → {pdf_printer}" if pdf_printer else "Imprimer direct (non configurée)", "#9b59b6", "#8e44ad", lambda: self.print_versement_pdf(v_id, open_pdf=False, direct=True), enabled=bool(pdf_printer))
            thermal_printer = self._get_thermal_printer_name()
            self._add_action_btn("fa5s.receipt", f"Imprimer thermique → {thermal_printer}" if thermal_printer else "Imprimer thermique (non config)", "#e67e22", "#d35400", lambda: self.print_versement_thermal(v_id), enabled=bool(thermal_printer))
            if v_statut == 'EN_COURS':
                self._add_action_btn("fa5s.cart-plus", "Ajouter un nouvel article", "#27ae60", "#2ecc71", lambda: self.open_add_item_dialog(v_id))
                self._add_action_btn("fa5s.money-bill-wave", "Ajouter un paiement (Global)", "#f1c40f", "#f39c12", lambda: self.open_add_payment_dialog(v_id))
                self._add_action_btn("fa5s.check-circle", "Clôturer tout le dossier", "#2ecc71", "#27ae60", lambda: self._handle_close_versement(v_id))
                self._add_action_btn("fa5s.times-circle", "Annuler tout le dossier", "#c0392b", "#962d2d", lambda: self._handle_cancel_versement(v_id))
            elif v_statut in ('CLOTURE', 'ANNULE'):
                self._add_action_btn("fa5s.exchange-alt", "Changer état: remettre le dossier En Cours", "#e67e22", "#d35400", lambda: self._handle_change_versement_status(v_id, 'EN_COURS'))

        elif row_type == "ITEM":
            self._add_action_btn("fa5s.info-circle", "Spécifications détaillées du produit", "#3498db", "#2980b9", lambda: self.show_product_specs(data))
            item_status = data.get("item_status")
            if item_status == 'EN_COURS' and v_statut == 'EN_COURS':
                self._add_action_btn("fa5s.hand-holding-usd", "Ajouter un paiement pour CET ARTICLE", "#f1c40f", "#f39c12", lambda: self.open_add_payment_dialog(v_id, preselected_item_id=data.get("item_id")))
                self._add_action_btn("fa5s.box-open", "Marquer comme RETIRÉ (Livré)", "#27ae60", "#2ecc71", lambda: self._handle_retirer_item(data))
                self._add_action_btn("fa5s.store-slash", "Annuler l'article (Retour vitrine)", "#e74c3c", "#c0392b", lambda: self._handle_cancel_item(data))
                self._add_action_btn("fa5s.trash-alt", "Supprimer du dossier", "#7f8c8d", "#95a5a6", lambda: self._handle_delete_item(data))
            elif item_status == 'RETIRE' or item_status == 'ANNULE':
                self._add_action_btn("fa5s.exchange-alt", "Changer état: remettre l'article En Cours", "#e67e22", "#d35400", lambda: self._handle_change_item_status(data))

        elif row_type == "PAYMENT" and v_statut == 'EN_COURS':
            self._add_action_btn("fa5s.edit", "Modifier ce paiement", "#3498db", "#2980b9", lambda: self._handle_edit_payment(data))
            self._add_action_btn("fa5s.trash", "Supprimer ce paiement", "#e74c3c", "#c0392b", lambda: self._handle_delete_payment(data))

    def show_product_specs(self, data):
        try:
            inventory_ids = []
            if data.get("type") == "ITEM" and data.get("inventory_id"):
                inventory_ids.append(data.get("inventory_id"))
            elif data.get("type") == "HEADER" and data.get("v_id"):
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT inventory_id FROM Versement_Items WHERE versement_id = %s AND item_status != 'ANNULE'", (data.get("v_id"),))
                    for row in cursor.fetchall():
                        if row.get('inventory_id'):
                            inventory_ids.append(row['inventory_id'])

            if not inventory_ids:
                QMessageBox.information(self, "Détails Produit", "Aucun article spécifique en base n'est associé à cette sélection.")
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
                dlg.setWindowTitle("📋 Spécifications Techniques")
                dlg.setText("Voici les spécifications détaillées :")
                dlg.setInformativeText(details_text.strip())
                dlg.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #2c3e50; }")
                dlg.exec()
            else:
                QMessageBox.information(self, "Détails Produit", "Détails introuvables en base de données.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des détails : {e}")

    # ──────────────────────────────────────────────────────────────
    # طباعة PDF (تحميل أو مباشرة)
    # ──────────────────────────────────────────────────────────────
    def print_versement_pdf(self, versement_id, open_pdf=True, direct=False):
        if not ReceiptGenerator:
            QMessageBox.warning(self, "Erreur", "Le module d'impression (invoice_generator) est introuvable.")
            return

        pdf_data, v_data = self._prepare_versement_data(versement_id)
        if not v_data:
            QMessageBox.warning(self, "Erreur", "Données du versement introuvables.")
            return

        output_dir = os.path.abspath("factures/versements")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"Bon_Versement_{v_data['id']}.pdf")

        try:
            direct_printer = self._get_pdf_printer_name() if direct else ""
            if direct and not direct_printer:
                QMessageBox.warning(self, "Aucune imprimante PDF", "Aucune imprimante PDF configurée dans les paramètres.")
                return

            if not pdf_data['items'] or v_data.get('type_versement') == 'A_VIDE':
                ReceiptGenerator.generate_global_versement_receipt(pdf_data, output_path=output_path, direct_printer_name=direct_printer)
            else:
                ReceiptGenerator.generate_product_versement_receipt(pdf_data, output_path=output_path, direct_printer_name=direct_printer)
            
            if open_pdf:
                QDesktopServices.openUrl(QUrl.fromLocalFile(output_path))
            else:
                QMessageBox.information(self, "Impression PDF envoyée", f"Le Bon a été envoyé à :\n{direct_printer}")

        except ValueError as e:
            QMessageBox.critical(self, "Erreur d'impression PDF", f"Impossible d'imprimer :\n\n{e}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erreur d'impression", f"Impossible de générer le PDF: {e}")

    # ──────────────────────────────────────────────────────────────
    # طباعة حرارية مباشرة
    # ──────────────────────────────────────────────────────────────
    def print_versement_thermal(self, versement_id):
        thermal_printer = self._get_thermal_printer_name()
        if not thermal_printer:
            QMessageBox.warning(self, "Aucune imprimante thermique", "Aucune imprimante thermique n'est configurée.\n\nVeuillez aller dans Paramètres → Impression Thermique.")
            return

        pdf_data, v_data = self._prepare_versement_data(versement_id)
        if not v_data:
            QMessageBox.warning(self, "Erreur", "Données du versement introuvables.")
            return

        try:
            from ui.tools.print_functions import print_thermal_bon_versement
            print_thermal_bon_versement(pdf_data, calculate_only=False, printer_name=thermal_printer)
            QMessageBox.information(self, "Impression thermique envoyée", f"Le ticket de versement a été envoyé à :\n{thermal_printer}")
        except ValueError as e:
            QMessageBox.critical(self, "Erreur imprimante thermique", f"Impossible d'imprimer sur la thermique :\n\n{e}\n\nVérifiez que l'imprimante est allumée et connectée.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erreur thermique", f"Erreur lors de l'impression thermique :\n{e}")

    # ──────────────────────────────────────────────────────────────
    # باقي الدوال
    # ──────────────────────────────────────────────────────────────
    def add_group_header_row(self, data_dict, text1, span1, text2=None, span2=None, bg_color="#C00080", text_color="white", text_color2=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        item1 = QTableWidgetItem(text1)
        item1.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        item1.setFont(QFont("", 11, QFont.Bold))
        item1.setBackground(QBrush(QColor(bg_color)))
        item1.setForeground(QBrush(QColor(text_color)))
        item1.setData(Qt.UserRole, data_dict)
        self.table.setItem(row, 0, item1)
        self.table.setSpan(row, 0, 1, span1)
        
        if text2 and span2:
            item2 = QTableWidgetItem(text2)
            item2.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item2.setFont(QFont("", 11, QFont.Bold))
            item2.setBackground(QBrush(QColor(bg_color)))
            item2.setForeground(QBrush(QColor(text_color2 or text_color)))
            item2.setData(Qt.UserRole, data_dict)
            self.table.setItem(row, span1, item2)
            self.table.setSpan(row, span1, 1, span2)
        self.table.setRowHeight(row, 35)

    def create_and_set_item(self, row, col, text, data_dict, bold=False, align_center=True, color_red=False, bg_color=None, text_color=None):
        item = QTableWidgetItem(text)
        item.setFont(QFont("", 11, QFont.Bold if bold else QFont.Normal))
        item.setData(Qt.UserRole, data_dict)
        item.setTextAlignment((Qt.AlignCenter if align_center else Qt.AlignLeft) | Qt.AlignVCenter)
        if color_red: item.setForeground(QBrush(QColor("#c0392b")))
        if bg_color: item.setBackground(QBrush(QColor(bg_color)))
        if text_color: item.setForeground(QBrush(QColor(text_color)))
        self.table.setItem(row, col, item)

    def _calculate_item_weight_balance(self, item, payments, total_active_weight):
        item_id = item.get('item_id') or item.get('id')
        item_weight = float(item.get('weight') or 0)

        direct_payments = [p for p in payments if p.get('versement_item_id') == item_id]
        global_payments = [p for p in payments if p.get('versement_item_id') is None]

        direct_deducted_g = sum(float(p.get('poids_deduit_g') or 0) for p in direct_payments)
        global_deducted_g = sum(float(p.get('poids_deduit_g') or 0) for p in global_payments)
        shared_deducted_g = global_deducted_g * (item_weight / total_active_weight) if total_active_weight > 0 else 0.0

        deducted_g = direct_deducted_g + shared_deducted_g
        return {
            "deducted_g": deducted_g,
            "remaining_g": max(0.0, item_weight - deducted_g),
            "has_shared": bool(global_payments),
        }

    def load_data(self):
        self.table.setRowCount(0)
        status_map = {"En Cours": "EN_COURS", "Clôturé": "CLOTURE", "Annulé": "ANNULE", "Tous": None}
        selected_status = status_map[self.combo_status.currentText()]
        search_text = self.inp_search.text().lower().strip()
        
        try:
            versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=selected_status)
            
            for v in versements:
                client_name = v.get('client_name', 'Inconnu')
                client_phone = str(v.get('phone') or '')
                statut = v.get('status', '')
                v_id = v['id']
                is_annule = (statut == 'ANNULE')

                if search_text:
                    if not (search_text in client_name.lower() or search_text in client_phone): continue

                header_data = {"type": "HEADER", "v_id": v_id, "statut": statut}
                header_title = f" 📦 VRS-{v_id} | Client: {client_name} {f'(Tel: {client_phone})' if client_phone else ''}"
                header_details = f"Poids Total Actif: {v.get('total_weight_g', 0):.2f} g "
                self.add_group_header_row(header_data, header_title, 4, header_details, 5, bg_color="#0f8f83", text_color="white")

                payments = v.get('payments', [])
                items = v.get('items', [])
                active_items = [it for it in items if it.get('item_status') != 'ANNULE']
                total_active_weight = sum(float(it.get('weight') or 0) for it in active_items)
                if items:
                    for item in items:
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        i_statut = item.get('item_status', 'EN_COURS')
                        weight = float(item.get('weight') or 0)
                        balance = self._calculate_item_weight_balance(item, payments, total_active_weight)
                        i_data = {
                            "type": "ITEM", "v_id": v_id, "statut": statut, "item_id": item['item_id'],
                            "item_status": i_statut, "inventory_id": item.get('inventory_id'),
                            "designation": item.get('designation', 'Inconnu'),
                            "weight": weight,
                            "deducted_g": balance["deducted_g"],
                            "remaining_g": balance["remaining_g"]
                        }
                        designation = f"   💍 Article: {item.get('designation', 'Inconnu')}"
                        weight_str = f"Poids: {weight:.2f} g"
                        remain_g_str = f"Déduit: {balance['deducted_g']:.3f} g | Reste: {balance['remaining_g']:.3f} g"
                        obs_str = f"Reste poids produit: {balance['remaining_g']:.3f} g"
                        if balance["has_shared"]:
                            obs_str += " (avec part poids globale)"
                        
                        bg_c = None; fg_c = None
                        if i_statut == 'ANNULE': bg_c = "#fff5f3"; fg_c = "#be3528"
                        elif i_statut == 'RETIRE': bg_c = "#eafaf1"; fg_c = "#27ae60"
                        else: bg_c = "#eef7f5"; fg_c = "#075f58"
                        
                        self.create_and_set_item(row, 0, designation, i_data, bold=True, align_center=False, bg_color=bg_c, text_color=fg_c)
                        for col in range(1, 5): self.create_and_set_item(row, col, "-", i_data, bg_color=bg_c)
                        self.create_and_set_item(row, 5, weight_str, i_data, bold=True, bg_color=bg_c, text_color=fg_c)
                        self.create_and_set_item(row, 6, remain_g_str, i_data, bold=True, color_red=(balance["remaining_g"] > 0), bg_color=bg_c, text_color="#c0392b" if balance["remaining_g"] > 0 else "#27ae60")
                        self.create_and_set_item(row, 7, i_statut, i_data, bold=True, bg_color=bg_c, text_color=fg_c)
                        self.create_and_set_item(row, 8, obs_str, i_data, align_center=False, bg_color=bg_c, text_color=fg_c)
                        self.table.setRowHeight(row, 38)

                if is_annule and not payments:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    dummy_data = {"type": "INFO"}
                    self.create_and_set_item(row, 0, "Dossier Annulé", dummy_data, bold=True, align_center=False, bg_color="#fff5f3", text_color="#be3528")
                    for col in range(1, 9): self.create_and_set_item(row, col, "-", dummy_data, bg_color="#fff5f3")
                elif not payments and not is_annule:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    dummy_data = {"type": "INFO"}
                    date_init = v['created_at'].strftime("%d/%m/%Y") if hasattr(v['created_at'], 'strftime') else str(v['created_at'])
                    self.create_and_set_item(row, 0, f"   ↳ {date_init} - Création à vide", dummy_data, align_center=False, bg_color="#edf2f6", text_color="#526170")
                    for col in range(1, 9): self.create_and_set_item(row, col, "-", dummy_data, bg_color="#edf2f6")
                else:
                    for idx, p in enumerate(payments):
                        row = self.table.rowCount()
                        self.table.insertRow(row)
                        d = p.get('payment_date', v['created_at'])
                        date_str = d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
                        
                        m_da = float(p.get('montant_da') or 0); m_tpe = float(p.get('tpe_da') or 0); m_eu = float(p.get('montant_euro') or 0)
                        taux = float(p.get('taux_change_euro') or 0); o_c = float(p.get('or_casse_g') or 0)
                        deduit = float(p.get('poids_deduit_g') or 0); p_notes = p.get('notes') or ""
                        m_dl = float(p.get('montant_dollar') or 0); taux_dl = float(p.get('taux_change_dollar') or 0)
                        remise = float(p.get('remise_da') or 0)
                        
                        op_label = f"   💵 {date_str} - Versement #{idx+1}"
                        if p.get('item_designation'): op_label += f" [{p['item_designation']}]"
                        
                        p_data = {
                            "type": "PAYMENT", "v_id": v_id, "statut": statut, "payment_id": p.get('id'),
                            "versement_item_id": p.get('versement_item_id'),
                            "montant_da": m_da, "tpe_da": m_tpe, "montant_euro": m_eu, "taux_change_euro": taux,
                            "montant_dollar": m_dl, "taux_change_dollar": taux_dl, "remise_da": remise,
                            "or_casse_g": o_c, "poids_deduit_g": deduit, "notes": p_notes
                        }
                        self.create_and_set_item(row, 0, op_label, p_data, bold=True, align_center=False, bg_color="#fff8e8", text_color="#7a4d08")
                        self.create_and_set_item(row, 1, f"{m_da:,.0f} DA" if m_da != 0 else "-", p_data, color_red=(m_da < 0), bg_color="#fff8e8", text_color="#27ae60" if m_da >= 0 else None)
                        self.create_and_set_item(row, 2, f"{m_tpe:,.0f} DA" if m_tpe != 0 else "-", p_data, color_red=(m_tpe < 0), bg_color="#fff8e8", text_color="#27ae60" if m_tpe >= 0 else None)
                        devise_str = []
                        if m_eu != 0: devise_str.append(f"{m_eu:,.0f} €")
                        if m_dl != 0: devise_str.append(f"{m_dl:,.0f} $")
                        self.create_and_set_item(row, 3, " | ".join(devise_str) if devise_str else "-", p_data, color_red=(m_eu < 0 or m_dl < 0), bg_color="#fff8e8", text_color="#27ae60" if (m_eu >= 0 and m_dl >= 0) else None)
                        
                        taux_str = []
                        if taux != 0: taux_str.append(f"{taux:,.2f} €")
                        if taux_dl != 0: taux_str.append(f"{taux_dl:,.2f} $")
                        self.create_and_set_item(row, 4, " | ".join(taux_str) if taux_str else "-", p_data, color_red=(taux < 0 or taux_dl < 0), bg_color="#fff8e8", text_color="#27ae60" if (taux >= 0 and taux_dl >= 0) else None)
                        
                        self.create_and_set_item(row, 5, f"{o_c:.2f} g" if o_c != 0 else "-", p_data, color_red=(o_c < 0), bg_color="#fff8e8", text_color="#27ae60" if o_c >= 0 else None)
                        
                        deduit_str = f"{deduit:.2f} g" if deduit != 0 else "-"
                        self.create_and_set_item(row, 6, deduit_str, p_data, bold=(deduit!=0), color_red=(deduit>0), bg_color="#fff8e8", text_color="#7a4d08" if deduit <= 0 else None)
                        
                        self.create_and_set_item(row, 7, "Paiement", p_data, bg_color="#fff8e8", text_color="#27ae60")
                        
                        obs_str = ""
                        if remise > 0: obs_str += f"[Remise: {remise:,.0f} DA] "
                        obs_str += p_notes
                        self.create_and_set_item(row, 8, obs_str if obs_str.strip() else "-", p_data, align_center=False, bg_color="#fff8e8", text_color="#7a4d08")
                        self.table.setRowHeight(row, 28)

                if not is_annule:
                    total_paid_da = v.get('total_paid_money_da', 0)
                    total_tpe = v.get('total_tpe_da', 0)
                    total_dollar = v.get('total_dollar', 0)
                    total_remise = v.get('total_remise_da', 0)
                    total_deducted = v.get('total_paid_weight_g', 0)
                    reste_poids = v.get('reste_poids_g', 0)
                    
                    sum_text_1 = f"💰 Payé: {total_paid_da:,.0f} DA"
                    if total_tpe != 0: sum_text_1 += f"  |  TPE: {total_tpe:,.0f} DA"
                    if total_dollar > 0: sum_text_1 += f"  |  💵 {total_dollar:,.0f} $"
                    if total_remise > 0: sum_text_1 += f"  |  🎁 Remise: {total_remise:,.0f} DA"
                    sum_text_1 += f"  |  ⚖️ Déduit: - {total_deducted:.2f} g"
                    
                    sum_text_2 = f"STATUT: {statut}  |  ⚖️ RESTE: {reste_poids:.3f} g"
                    is_complete = (reste_poids <= 0) or (statut == 'CLOTURE')
                    bg_summary = "#dff5f1" if is_complete else "#ffedea"
                    payment_summary_color = "#27ae60" if total_paid_da >= 0 else "#c0392b"
                    self.add_group_header_row({"type": "SUMMARY"}, sum_text_1, 4, sum_text_2, 5, bg_color=bg_summary, text_color=payment_summary_color, text_color2="#c0392b")
                    
                    row_space = self.table.rowCount()
                    self.table.insertRow(row_space)
                    self.table.setRowHeight(row_space, 8)
                    for col in range(9):
                        empty_item = QTableWidgetItem("")
                        empty_item.setFlags(Qt.NoItemFlags)
                        self.table.setItem(row_space, col, empty_item)
        except Exception as e:
            import traceback
            print(f"Erreur load_data: {e}\n{traceback.format_exc()}")

    # ========================================================
    # فتح النوافذ المنبثقة
    # ========================================================
    def open_new_versement_dialog(self):
        from ui.widgets.versements.new_versement_dialog import NewVersementDialog
        try:
            app = QApplication.instance()
            current_user = app.current_main_window.current_user if hasattr(app, 'current_main_window') else {}
        except: current_user = {}

        dlg = NewVersementDialog(self.manager, current_user, self)
        if dlg.exec() == QDialog.Accepted: self.load_data()
        
    def open_add_payment_dialog(self, versement_id, preselected_item_id=None):
        from ui.widgets.versements.add_payment_dialog import AddPaymentDialog
        journee = self.manager.cash_box.get_or_create_today_session(user_id=1)
        current_journee_id = journee['id'] if journee else 1
            
        dlg = AddPaymentDialog(self.manager, versement_id, current_journee_id, preselected_item_id, self)
        if dlg.exec() == QDialog.Accepted: self.load_data()

    def open_add_item_dialog(self, versement_id):
        dlg = AddItemToVersementDialog(self.manager, versement_id, self)
        if dlg.exec() == QDialog.Accepted:
            self.load_data()
