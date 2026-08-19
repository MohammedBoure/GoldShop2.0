# ui/widgets/versements/add_payment_dialog.py

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QFormLayout, QMessageBox, QApplication, QFrame, QTextEdit, QGroupBox,
    QComboBox, QStackedWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QBrush

from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog
from database.versement import (
    payment_value_da as calculate_payment_value_da,
    shop_price_per_gram,
)


class AddPaymentDialog(QDialog):
    """
    نافذة إضافة دفعة مالية جديدة لملف عربون مفتوح (Versement / Acompte)
    مصممة بنظام العرض المنقسم (Split View) المتطابق 100% مع واجهة إنشاء العربون (NewVersementDialog).
    """
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
        self._target_price_per_gram = None

        self.setWindowTitle(f"Ajouter un Paiement - Dossier VRS-{self.versement_id:05d}")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)
        self.setWindowState(Qt.WindowMaximized)

        self._load_versement_data()
        self.init_ui()
        self.auto_calculate_poids_deduit()

    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowState(Qt.WindowMaximized)

    def _load_versement_data(self):
        try:
            versements = getattr(self.manager.versements, 'get_versements', lambda **k: [])(status_filter=None)
            self.v_data = next((v for v in versements if v['id'] == self.versement_id), None)
            if self.v_data:
                if self.v_data.get('type_versement') == 'A_VIDE':
                    self.is_versement_libre = True
                for item in self.v_data.get('items', []):
                    item_id = item.get('item_id') or item.get('id')
                    if item_id:
                        self.item_prices[item_id] = float(item.get('display_price') or item.get('selling_price') or 0)
                        self.item_weights[item_id] = float(item.get('display_weight') or item.get('weight') or 0)
        except Exception as e:
            logging.error(f"[AddPaymentDialog] Erreur chargement versement: {e}")

    # ==========================================
    # دوال مساعدة لإنشاء أزرار لوحات المفاتيح
    # ==========================================
    def _wrap_with_numpad(self, widget, allow_decimal=True):
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)

        btn = QPushButton("🔢")
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(34, 34)
        btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 15px;")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._open_numpad(widget, allow_decimal))

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
        btn.setFixedSize(34, 34)
        if isinstance(widget, QTextEdit):
            lay.setAlignment(btn, Qt.AlignTop)

        btn.setStyleSheet("background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; font-size: 15px;")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._open_vkb(widget))

        lay.addWidget(btn)
        return container

    def _open_numpad(self, widget, allow_decimal):
        widget.setFocus()
        pad = VirtualNumpad(mode="direct", target_widget=widget, allow_decimal=allow_decimal, allow_negative=True, parent=self)
        pad.exec()

    def _open_vkb(self, widget):
        widget.setFocus()
        kb = VirtualKeyboardDialog(self)
        kb.show()

    def _styled_lbl(self, text, color="#24313f"):
        l = QLabel(text)
        l.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")
        return l

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ==========================================
        # الجانب الأيسر: معلومات الملف، القطع والسجل (52%)
        # ==========================================
        left_panel = QFrame()
        left_panel.setObjectName("left_panel")
        left_panel.setStyleSheet("background-color: white; border-radius: 6px; border: 1px solid #dcdde1;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        # 1. بطاقة معلومات الزبون والملف
        client_name = self.v_data.get('client_name', 'Inconnu') if self.v_data else 'Inconnu'
        client_phone = str(self.v_data.get('phone') or 'Non renseigné') if self.v_data else ''
        statut = self.v_data.get('status', 'EN_COURS') if self.v_data else 'EN_COURS'
        created_at = str(self.v_data.get('created_at', ''))[:10] if self.v_data else ''

        card_info = QFrame()
        card_info.setStyleSheet("background-color: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 6px;")
        card_layout = QVBoxLayout(card_info)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)

        lbl_header = QLabel(f"📦 <b>Dossier N° VRS-{self.versement_id:05d}</b> &nbsp;|&nbsp; Date : {created_at} &nbsp;|&nbsp; Statut : <span style='color: #0f8f83;'><b>{statut}</b></span>")
        lbl_header.setStyleSheet("font-size: 14px; color: #166534;")
        lbl_client = QLabel(f"👤 <b>Client :</b> {client_name} &nbsp;&nbsp; 📞 <b>Tél :</b> {client_phone}")
        lbl_client.setStyleSheet("font-size: 13px; color: #1f2937;")
        card_layout.addWidget(lbl_header)
        card_layout.addWidget(lbl_client)
        left_layout.addWidget(card_info)

        # 2. جدول قطع الملف المحجوزة
        lbl_items = QLabel("💍 Articles du Dossier (Articles réservés)")
        lbl_items.setStyleSheet("font-size: 14px; font-weight: bold; color: #075f58;")
        left_layout.addWidget(lbl_items)

        self.table_items = QTableWidget(0, 5)
        self.table_items.setHorizontalHeaderLabels(["Désignation", "Poids Initial", "Déduit", "Reste", "Prix Estimé"])
        self.table_items.setStyleSheet("""
            QTableWidget { background-color: white; font-size: 13px; gridline-color: #eef2f6; }
            QHeaderView::section { background-color: #0f8f83; color: white; font-weight: bold; padding: 5px; font-size: 12px; border: none; }
            QTableWidget::item { border-bottom: 1px solid #eef2f6; }
        """)
        self.table_items.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_items.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_items.verticalHeader().setVisible(False)

        header_it = self.table_items.horizontalHeader()
        header_it.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 5):
            header_it.setSectionResizeMode(c, QHeaderView.ResizeToContents)

        left_layout.addWidget(self.table_items, stretch=3)

        # 3. سجل الدفعات السابقة
        lbl_hist = QLabel("📜 Historique des Paiements Enregistrés")
        lbl_hist.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50; margin-top: 4px;")
        left_layout.addWidget(lbl_hist)

        self.table_history = QTableWidget(0, 5)
        self.table_history.setHorizontalHeaderLabels(["Date", "Montant (DA)", "Devise/Casse", "Remise", "Poids Déduit"])
        self.table_history.setStyleSheet("""
            QTableWidget { background-color: white; font-size: 12px; gridline-color: #eef2f6; }
            QHeaderView::section { background-color: #475569; color: white; font-weight: bold; padding: 4px; font-size: 12px; border: none; }
            QTableWidget::item { border-bottom: 1px solid #eef2f6; }
        """)
        self.table_history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_history.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_history.verticalHeader().setVisible(False)

        header_hist = self.table_history.horizontalHeader()
        header_hist.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_hist.setSectionResizeMode(1, QHeaderView.Stretch)
        header_hist.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header_hist.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_hist.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        left_layout.addWidget(self.table_history, stretch=2)

        self._populate_left_panel_tables()

        # ==========================================
        # الجانب الأيمن: بيانات الدفع والخصم (48%)
        # ==========================================
        right_panel = QFrame()
        right_panel.setFixedWidth(560)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 1. تحديد القطعة الهدف
        group_target = QGroupBox("🎯 Destination du Paiement")
        group_target.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: #075f58; border: 1px solid #cbd5df; border-radius: 6px; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        lay_target = QHBoxLayout(group_target)
        lay_target.setContentsMargins(10, 12, 10, 10)

        self.combo_target = QComboBox()
        self.combo_target.setStyleSheet("font-size: 14px; font-weight: bold; padding: 6px; border: 1px solid #cbd5df; border-radius: 6px;")
        self.combo_target.addItem("📦 Dossier Global (Aucun article spécifique)", None)
        self._populate_target_combo()
        self.combo_target.currentIndexChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        btn_details = QPushButton("ℹ️ Détails")
        btn_details.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; font-size: 13px; padding: 6px 12px; border-radius: 6px;")
        btn_details.setCursor(Qt.PointingHandCursor)
        btn_details.clicked.connect(self.show_product_details)

        lay_target.addWidget(self.combo_target, stretch=1)
        lay_target.addWidget(btn_details)
        right_layout.addWidget(group_target)

        # 2. صندوق الدفع والخصومات (المتطابق تماماً مع NewVersementDialog)
        group_pay = QGroupBox("💵 Financement, Remise et Acompte")
        group_pay.setStyleSheet(group_target.styleSheet())
        pay_layout = QVBoxLayout(group_pay)
        pay_layout.setContentsMargins(10, 14, 10, 10)
        pay_layout.setSpacing(10)

        # اختيار طريقة الدفع
        self.combo_method = QComboBox()
        self.combo_method.addItems([
            "1 - Paiement en Dinar (Espèces / TPE)",
            "2 - Paiement en Devise (Euro €)",
            "3 - Paiement par Or Cassé",
            "4 - Paiement en Devise (Dollar $)"
        ])
        self.combo_method.setStyleSheet("font-size: 14px; font-weight: bold; padding: 6px; border: 2px solid #0f8f83; border-radius: 6px; color: #075f58; background-color: #e8f7f4;")
        self.combo_method.currentIndexChanged.connect(self.on_payment_method_changed)
        pay_layout.addWidget(self.combo_method)

        self.stacked_pay = QStackedWidget()
        inp_style = "font-size: 14px; font-weight: bold; padding: 5px; border: 1px solid #cbd5df; border-radius: 6px;"

        # --- الصفحة 0: الدينار ---
        self.page_dinar = QWidget()
        form_dinar = QFormLayout(self.page_dinar)
        form_dinar.setContentsMargins(0, 0, 0, 0)
        form_dinar.setSpacing(6)
        self.inp_cash = QLineEdit()
        self.inp_cash.setPlaceholderText("0.00")
        self.inp_cash.setStyleSheet(inp_style + "color: #27ae60;")
        self.inp_cash.textChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_tpe = QLineEdit()
        self.inp_tpe.setPlaceholderText("0.00")
        self.inp_tpe.setStyleSheet(inp_style + "color: #2980b9;")
        self.inp_tpe.textChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        form_dinar.addRow(self._styled_lbl("Espèces (Cash) :"), self._wrap_with_numpad(self.inp_cash))
        form_dinar.addRow(self._styled_lbl("Carte (TPE) :"), self._wrap_with_numpad(self.inp_tpe))

        self.stacked_pay.addWidget(self.page_dinar)

        # --- الصفحة 1: الأورو ---
        self.page_euro = QWidget()
        form_euro = QFormLayout(self.page_euro)
        form_euro.setContentsMargins(0, 0, 0, 0)
        form_euro.setSpacing(6)
        self.inp_euro = QLineEdit()
        self.inp_euro.setPlaceholderText("Montant €")
        self.inp_euro.setStyleSheet(inp_style + "color: #d35400;")
        self.inp_taux_change = QLineEdit()
        self.inp_taux_change.setPlaceholderText("Ex: 240")
        self.inp_taux_change.setStyleSheet(inp_style + "color: #7f8c8d;")
        self.inp_euro_da = QLineEdit()
        self.inp_euro_da.setPlaceholderText("Valeur en DA")
        self.inp_euro_da.setStyleSheet(inp_style + "color: white; background-color: #27ae60;")
        self.inp_euro_da.textChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_euro.textChanged.connect(self.calc_euro_eq)
        self.inp_taux_change.textChanged.connect(self.calc_euro_eq)

        form_euro.addRow(self._styled_lbl("Montant (€) :"), self._wrap_with_numpad(self.inp_euro))
        form_euro.addRow(self._styled_lbl("Taux (DA/€) :"), self._wrap_with_numpad(self.inp_taux_change))
        form_euro.addRow(self._styled_lbl("Équiv (DA) :", color="#27ae60"), self._wrap_with_numpad(self.inp_euro_da))
        self.stacked_pay.addWidget(self.page_euro)

        # --- الصفحة 2: الذهب المكسر ---
        self.page_casse = QWidget()
        form_casse = QFormLayout(self.page_casse)
        form_casse.setContentsMargins(0, 0, 0, 0)
        form_casse.setSpacing(6)
        self.inp_oc = QLineEdit()
        self.inp_oc.setPlaceholderText("Poids (g)")
        self.inp_oc.setStyleSheet(inp_style + "color: #8e44ad;")
        self.inp_prix_g_casse = QLineEdit()
        self.inp_prix_g_casse.setPlaceholderText("Prix/g")
        self.inp_prix_g_casse.setStyleSheet(inp_style + "color: #7f8c8d;")
        self.inp_casse_da = QLineEdit()
        self.inp_casse_da.setPlaceholderText("Valeur en DA")
        self.inp_casse_da.setStyleSheet(inp_style + "color: white; background-color: #27ae60;")
        self.inp_casse_da.textChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_oc.textChanged.connect(self.calc_casse_eq)
        self.inp_prix_g_casse.textChanged.connect(self.calc_casse_eq)

        form_casse.addRow(self._styled_lbl("Poids Cassé :"), self._wrap_with_numpad(self.inp_oc))
        form_casse.addRow(self._styled_lbl("Prix (DA/g) :"), self._wrap_with_numpad(self.inp_prix_g_casse))
        form_casse.addRow(self._styled_lbl("Équiv (DA) :", color="#27ae60"), self._wrap_with_numpad(self.inp_casse_da))
        self.stacked_pay.addWidget(self.page_casse)

        # --- الصفحة 3: الدولار ---
        self.page_dollar = QWidget()
        form_dollar = QFormLayout(self.page_dollar)
        form_dollar.setContentsMargins(0, 0, 0, 0)
        form_dollar.setSpacing(6)
        self.inp_dollar = QLineEdit()
        self.inp_dollar.setPlaceholderText("Montant $")
        self.inp_dollar.setStyleSheet(inp_style + "color: #16a085;")
        self.inp_taux_change_dollar = QLineEdit()
        self.inp_taux_change_dollar.setPlaceholderText("Ex: 220")
        self.inp_taux_change_dollar.setStyleSheet(inp_style + "color: #7f8c8d;")
        self.inp_dollar_da = QLineEdit()
        self.inp_dollar_da.setPlaceholderText("Valeur en DA")
        self.inp_dollar_da.setStyleSheet(inp_style + "color: white; background-color: #27ae60;")
        self.inp_dollar_da.textChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_dollar.textChanged.connect(self.calc_dollar_eq)
        self.inp_taux_change_dollar.textChanged.connect(self.calc_dollar_eq)

        form_dollar.addRow(self._styled_lbl("Montant ($) :"), self._wrap_with_numpad(self.inp_dollar))
        form_dollar.addRow(self._styled_lbl("Taux (DA/$) :"), self._wrap_with_numpad(self.inp_taux_change_dollar))
        form_dollar.addRow(self._styled_lbl("Équiv (DA) :", color="#27ae60"), self._wrap_with_numpad(self.inp_dollar_da))
        self.stacked_pay.addWidget(self.page_dollar)

        pay_layout.addWidget(self.stacked_pay)

        # أزرار المساعدة في التخفيضات (Discount Tools)
        lbl_remise_tools = QLabel("🛠️ Outils d'aide Remise :")
        lbl_remise_tools.setStyleSheet("font-size: 12px; font-weight: bold; color: #7f8c8d;")
        pay_layout.addWidget(lbl_remise_tools)

        remise_btns_layout = QHBoxLayout()
        remise_btns_layout.setSpacing(6)

        btn_pct = QPushButton("🧮 Remise (%)")
        btn_pct.setStyleSheet("background-color: #34495e; color: white; padding: 6px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_pct.setCursor(Qt.PointingHandCursor)
        btn_pct.clicked.connect(self.open_discount_pct)

        btn_final = QPushButton("🏷️ Prix Final")
        btn_final.setStyleSheet("background-color: #2980b9; color: white; padding: 6px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_final.setCursor(Qt.PointingHandCursor)
        btn_final.clicked.connect(self.open_discount_final_price)

        btn_ppg = QPushButton("⚖️ Prix/g Target")
        btn_ppg.setStyleSheet("background-color: #8e44ad; color: white; padding: 6px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_ppg.setCursor(Qt.PointingHandCursor)
        btn_ppg.clicked.connect(self.open_discount_price_per_gram)

        remise_btns_layout.addWidget(btn_pct)
        remise_btns_layout.addWidget(btn_final)
        remise_btns_layout.addWidget(btn_ppg)
        pay_layout.addLayout(remise_btns_layout)

        form_deduct = QFormLayout()
        form_deduct.setSpacing(6)

        self.inp_remise_da = QLineEdit()
        self.inp_remise_da.setPlaceholderText("Ex: 5000.00")
        self.inp_remise_da.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px; color: #8e44ad; border: 1px solid #8e44ad; border-radius: 6px;")
        self.inp_remise_da.textChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_poids_deduit = QLineEdit()
        self.inp_poids_deduit.setPlaceholderText("Ex: 5.200")
        self.inp_poids_deduit.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px; color: white; background-color: #c0392b; border-radius: 6px;")
        self.inp_poids_deduit.textChanged.connect(self.update_dynamic_summary)

        self.inp_notes = QLineEdit()
        self.inp_notes.setPlaceholderText("Notes ou observations...")
        self.inp_notes.setStyleSheet("font-size: 13px; padding: 5px; border: 1px solid #cbd5df; border-radius: 6px;")

        form_deduct.addRow(self._styled_lbl("🎁 Remise (DA) :", color="#8e44ad"), self._wrap_with_numpad(self.inp_remise_da))
        form_deduct.addRow(self._styled_lbl("⚖️ Poids DÉDUIT (g):", color="#c0392b"), self._wrap_with_numpad(self.inp_poids_deduit))
        form_deduct.addRow(self._styled_lbl("Notes :"), self._wrap_with_keyboard(self.inp_notes))
        pay_layout.addLayout(form_deduct)

        # العرض الديناميكي للصافي المباشر
        self.summary_box = QGroupBox("📊 Aperçu Instantané (Reste en Grammes)")
        self.summary_box.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; background-color: #f8f9fa; margin-top: 14px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        sum_layout = QFormLayout(self.summary_box)
        sum_layout.setContentsMargins(8, 8, 8, 8)
        sum_layout.setSpacing(4)

        self.lbl_summary_brut = QLabel("0.00 DA (0.00 g)")
        self.lbl_summary_brut.setStyleSheet("font-size: 13px; font-weight: bold; color: #7f8c8d;")

        self.lbl_summary_remise = QLabel("0.00 DA")
        self.lbl_summary_remise.setStyleSheet("font-size: 13px; font-weight: bold; color: #c0392b;")

        self.lbl_summary_paye = QLabel("0.00 DA")
        self.lbl_summary_paye.setStyleSheet("font-size: 13px; font-weight: bold; color: #27ae60;")

        self.lbl_summary_reste = QLabel("0.00 g")
        self.lbl_summary_reste.setStyleSheet("font-size: 16px; font-weight: bold; color: #c0392b;")

        sum_layout.addRow(self._styled_lbl("Total Initial Média :"), self.lbl_summary_brut)
        sum_layout.addRow(self._styled_lbl("Remise Appliquée :"), self.lbl_summary_remise)
        sum_layout.addRow(self._styled_lbl("Acompte Versé :", color="#27ae60"), self.lbl_summary_paye)
        sum_layout.addRow(self._styled_lbl("Reste Final :", color="#c0392b"), self.lbl_summary_reste)

        pay_layout.addWidget(self.summary_box)
        right_layout.addWidget(group_pay)
        right_layout.addStretch()

        # أزرار الحفظ والإلغاء
        buttons_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Fermer")
        self.btn_cancel.setStyleSheet("background-color: #fff5f3; border: 1px solid #e66f61; color: #be3528; font-weight: bold; font-size: 14px; padding: 10px 20px; border-radius: 6px;")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton("🔒 Enregistrer le Paiement")
        self.btn_confirm.setStyleSheet("background-color: #0f8f83; color: white; font-weight: bold; font-size: 15px; padding: 10px 20px; border-radius: 6px; border: none;")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.clicked.connect(self.save_payment)

        buttons_row.addWidget(self.btn_cancel)
        buttons_row.addWidget(self.btn_confirm, stretch=1)
        right_layout.addLayout(buttons_row)

        main_layout.addWidget(left_panel, stretch=52)
        main_layout.addWidget(right_panel, stretch=48)

        self.on_payment_method_changed(0)
        self.inp_cash.setFocus()

    def on_payment_method_changed(self, index):
        self.stacked_pay.setCurrentIndex(index)
        self.auto_calculate_poids_deduit()

    # ========================================================
    # أدوات المساعدة في التخفيضات (Discount Tools - نفس طريقة NewVersementDialog)
    # ========================================================
    def _get_price_per_gram_context(self):
        """إرجاع سعر الغرام والوزن المتاح للهدف المحدد (سواء ملف ككل أو قطعة محددة)"""
        selected_item_id = self.combo_target.currentData()
        if selected_item_id and selected_item_id in self.item_prices and selected_item_id in self.item_weights:
            item_price = float(self.item_prices[selected_item_id] or 0)
            item_weight = float(self.item_weights[selected_item_id] or 0)
            if item_price > 0 and item_weight > 0:
                unit_ppg = item_price / item_weight
                deductions = sum(
                    float(p.get('poids_deduit_g') or 0)
                    for p in (self.v_data.get('payments', []) if self.v_data else [])
                    if p.get('versement_item_id') == selected_item_id
                )
                rem_weight = max(0.0, item_weight - deductions)
                return unit_ppg, rem_weight

        if self.v_data:
            total_est = float(self.v_data.get('total_estimated_price_da') or 0)
            total_weight = float(self.v_data.get('total_weight_g') or 0)
            if total_est > 0 and total_weight > 0:
                unit_ppg = total_est / total_weight
                rem_weight = float(self.v_data.get('reste_poids_g') or 0)
                return unit_ppg, rem_weight
        return 0.0, 0.0

    def _get_active_base_amount(self):
        unit_ppg, rem_weight = self._get_price_per_gram_context()
        return rem_weight * unit_ppg

    def _get_current_payment_da(self):
        method_idx = self.combo_method.currentIndex()
        if method_idx == 0:
            try: cash = float(self.inp_cash.text() or 0)
            except Exception: cash = 0.0
            try: tpe = float(self.inp_tpe.text() or 0)
            except Exception: tpe = 0.0
            return cash + tpe
        elif method_idx == 1:
            try: return float(self.inp_euro_da.text() or 0)
            except Exception: return 0.0
        elif method_idx == 2:
            try: return float(self.inp_casse_da.text() or 0)
            except Exception: return 0.0
        elif method_idx == 3:
            try: return float(self.inp_dollar_da.text() or 0)
            except Exception: return 0.0
        return 0.0

    def open_discount_pct(self):
        unit_ppg, base_weight = self._get_price_per_gram_context()
        base_amount = self._get_active_base_amount()
        if base_amount <= 0 or base_weight <= 0:
            QMessageBox.warning(self, "Erreur", "Aucune base de prix estimé disponible pour calculer la remise.")
            return

        pad = VirtualNumpad(title="Saisir la Remise (%)", mode="dialog", allow_decimal=True, allow_negative=False, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                pct = float(val)
                if 0 <= pct <= 100:
                    remise_val = base_amount * (pct / 100.0)
                    self.inp_remise_da.setText(f"{remise_val:.2f}")
                    self.auto_calculate_poids_deduit()
                else:
                    QMessageBox.warning(self, "Erreur", "Le pourcentage doit être entre 0 et 100.")

    def open_discount_final_price(self):
        unit_ppg, base_weight = self._get_price_per_gram_context()
        base_amount = self._get_active_base_amount()
        if base_amount <= 0 or base_weight <= 0:
            QMessageBox.warning(self, "Erreur", "Aucune base de prix estimé disponible pour calculer la remise.")
            return

        pad = VirtualNumpad(title="Saisir le Prix Final (DA)", mode="dialog", allow_decimal=True, allow_negative=False, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                final_price = float(val)
                if 0 <= final_price <= base_amount:
                    remise_val = max(0.0, base_amount - final_price)
                    self.inp_remise_da.setText(f"{remise_val:.2f}")
                    self.auto_calculate_poids_deduit()
                else:
                    QMessageBox.warning(self, "Erreur", f"Le prix final doit être entre 0 et {base_amount:,.2f} DA.")

    def open_discount_price_per_gram(self):
        current_ppg, base_weight = self._get_price_per_gram_context()
        if current_ppg <= 0 or base_weight <= 0:
            QMessageBox.warning(self, "Erreur", "Aucun prix/poids disponible pour calculer la remise.")
            return

        pad = VirtualNumpad(
            title=f"Saisir le prix/g cible (actuel: {current_ppg:,.2f} DA/g)",
            mode="dialog",
            allow_decimal=True,
            allow_negative=False,
            initial_value=current_ppg,
            parent=self
        )
        if pad.exec() == QDialog.Accepted:
            value = pad.get_value()
            if value:
                target_ppg = float(value)
                if target_ppg <= 0:
                    QMessageBox.warning(self, "Erreur", "Le prix/g cible doit être supérieur à 0.")
                    return
                target_ppg = min(target_ppg, current_ppg)
                remise_value = max(0.0, (current_ppg - target_ppg) * base_weight)
                self.inp_remise_da.setText(f"{remise_value:.2f}")
                self.auto_calculate_poids_deduit()

    def auto_calculate_poids_deduit(self):
        """الحساب التلقائي اللحظي للوزن المقتنى بناءً على الدفعة المدفوعة وسعر الغرام المخفض الصافي"""
        unit_ppg, base_weight = self._get_price_per_gram_context()
        base_amount = base_weight * unit_ppg

        try:
            remise = float(self.inp_remise_da.text() or 0)
        except Exception:
            remise = 0.0
        remise = max(0.0, min(remise, base_amount))

        acompte_da = self._get_current_payment_da()

        if unit_ppg > 0 and base_weight > 0:
            net_amount = max(0.0, base_amount - remise)
            effective_ppg = net_amount / base_weight if base_weight > 0 else 0.0

            if effective_ppg > 0 and acompte_da > 0:
                poids_auto = min(base_weight, acompte_da / effective_ppg)
            else:
                poids_auto = 0.0

            self.inp_poids_deduit.blockSignals(True)
            self.inp_poids_deduit.setText(f"{poids_auto:.3f}")
            self.inp_poids_deduit.blockSignals(False)
        else:
            self.inp_poids_deduit.blockSignals(True)
            self.inp_poids_deduit.setText("0.000")
            self.inp_poids_deduit.blockSignals(False)

        self.update_dynamic_summary()


    def update_dynamic_summary(self):
        unit_ppg, base_weight = self._get_price_per_gram_context()
        total_brut = base_weight * unit_ppg

        try:
            remise = float(self.inp_remise_da.text() or 0)
        except Exception:
            remise = 0.0
        remise = max(0.0, min(remise, total_brut))

        try:
            poids_deduit = float(self.inp_poids_deduit.text() or 0)
        except Exception:
            poids_deduit = 0.0

        remise_pct = (remise / total_brut * 100.0) if total_brut > 0 else 0.0
        net = max(0.0, total_brut - remise)
        effective_ppg = (net / base_weight) if base_weight > 0 else 0.0

        acompte_da = self._get_current_payment_da()

        reste_g = max(0.0, base_weight - poids_deduit)
        montant_reste = reste_g * effective_ppg

        self.lbl_summary_brut.setText(f"{total_brut:,.2f} DA  (Base: {base_weight:,.2f} g)")
        self.lbl_summary_remise.setText(f"- {remise:,.2f} DA ({remise_pct:.1f}%)" if remise > 0 else "0.00 DA")
        self.lbl_summary_paye.setText(f"{acompte_da:,.2f} DA  (Poids déduit: {poids_deduit:,.3f} g)")
        self.lbl_summary_reste.setText(f"{reste_g:,.3f} g  (≈ {montant_reste:,.0f} DA)")

    # ========================================================
    # الحسابات الخاصة بطرق الدفع
    # ========================================================
    def calc_euro_eq(self):
        try:
            euro = float(self.inp_euro.text() or 0)
            taux = float(self.inp_taux_change.text() or 0)
            if euro != 0 and taux > 0:
                self.inp_euro_da.blockSignals(True)
                self.inp_euro_da.setText(f"{euro * taux:.2f}")
                self.inp_euro_da.blockSignals(False)
                self.auto_calculate_poids_deduit()
        except Exception:
            pass

    def calc_dollar_eq(self):
        try:
            dollar = float(self.inp_dollar.text() or 0)
            taux = float(self.inp_taux_change_dollar.text() or 0)
            if dollar != 0 and taux > 0:
                self.inp_dollar_da.blockSignals(True)
                self.inp_dollar_da.setText(f"{dollar * taux:.2f}")
                self.inp_dollar_da.blockSignals(False)
                self.auto_calculate_poids_deduit()
        except Exception:
            pass

    def calc_casse_eq(self):
        try:
            oc = float(self.inp_oc.text() or 0)
            prix = float(self.inp_prix_g_casse.text() or 0)
            if oc != 0 and prix > 0:
                self.inp_casse_da.blockSignals(True)
                self.inp_casse_da.setText(f"{oc * prix:.2f}")
                self.inp_casse_da.blockSignals(False)
                self.auto_calculate_poids_deduit()
        except Exception:
            pass

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
            logging.error(f"[AddPaymentDialog] Erreur chargement combo articles: {e}")

    def _populate_left_panel_tables(self):
        if not self.v_data:
            return

        # جدول القطع
        items = self.v_data.get('items', [])
        payments = self.v_data.get('payments', [])
        self.table_items.setRowCount(0)

        for i, item in enumerate(items):
            self.table_items.insertRow(i)
            desig = item.get('designation', 'Article')
            w = float(item.get('display_weight') or item.get('weight') or 0)
            item_id = item.get('item_id') or item.get('id')

            deductions = sum(float(p.get('poids_deduit_g') or 0) for p in payments if p.get('versement_item_id') == item_id)
            reste = max(0.0, w - deductions)
            price = float(item.get('display_price') or item.get('selling_price') or 0)

            it_desig = QTableWidgetItem(desig)
            it_w = QTableWidgetItem(f"{w:.2f} g")
            it_ded = QTableWidgetItem(f"{deductions:.2f} g")
            it_reste = QTableWidgetItem(f"{reste:.2f} g")
            it_price = QTableWidgetItem(f"{price:,.0f} DA")

            for it in [it_w, it_ded, it_reste, it_price]:
                it.setTextAlignment(Qt.AlignCenter)

            if reste == 0:
                it_reste.setForeground(QBrush(QColor("#27ae60")))
            else:
                it_reste.setForeground(QBrush(QColor("#c0392b")))

            self.table_items.setItem(i, 0, it_desig)
            self.table_items.setItem(i, 1, it_w)
            self.table_items.setItem(i, 2, it_ded)
            self.table_items.setItem(i, 3, it_reste)
            self.table_items.setItem(i, 4, it_price)
            self.table_items.setRowHeight(i, 28)

        # جدول سجل الدفعات السابقة
        self.table_history.setRowCount(0)
        for i, p in enumerate(payments):
            self.table_history.insertRow(i)
            d = p.get('payment_date', '')
            date_str = d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)[:10]

            m_da = float(p.get('montant_da') or 0)
            m_tpe = float(p.get('tpe_da') or 0)
            total_da = m_da + m_tpe
            remise = float(p.get('remise_da') or 0)
            deduit = float(p.get('poids_deduit_g') or 0)

            devise_parts = []
            if float(p.get('montant_euro') or 0) > 0:
                devise_parts.append(f"{float(p.get('montant_euro') or 0):,.0f} €")
            if float(p.get('montant_dollar') or 0) > 0:
                devise_parts.append(f"{float(p.get('montant_dollar') or 0):,.0f} $")
            if float(p.get('or_casse_g') or 0) > 0:
                devise_parts.append(f"{float(p.get('or_casse_g') or 0):.2f}g casse")
            devise_str = " | ".join(devise_parts) if devise_parts else "-"

            it_date = QTableWidgetItem(date_str)
            it_da = QTableWidgetItem(f"{total_da:,.0f} DA" if total_da > 0 else "-")
            it_dev = QTableWidgetItem(devise_str)
            it_rem = QTableWidgetItem(f"{remise:,.0f} DA" if remise > 0 else "-")
            it_ded = QTableWidgetItem(f"{deduit:.2f} g" if deduit > 0 else "-")

            for it in [it_date, it_da, it_dev, it_rem, it_ded]:
                it.setTextAlignment(Qt.AlignCenter)

            self.table_history.setItem(i, 0, it_date)
            self.table_history.setItem(i, 1, it_da)
            self.table_history.setItem(i, 2, it_dev)
            self.table_history.setItem(i, 3, it_rem)
            self.table_history.setItem(i, 4, it_ded)
            self.table_history.setRowHeight(i, 26)

    def show_product_details(self):
        try:
            target_id = self.combo_target.currentData()
            inventory_ids = []
            if target_id and hasattr(self, 'target_to_inventory') and self.target_to_inventory.get(target_id):
                inventory_ids.append(self.target_to_inventory[target_id])
            elif self.v_data and self.v_data.get('items'):
                inventory_ids = [it['item_id'] for it in self.v_data.get('items', []) if it.get('item_id')]

            if not inventory_ids:
                QMessageBox.information(self, "Détails Produit", "Aucun article associé.")
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
                QMessageBox.information(self, "Détails Produit", "Détails introuvables en base de données.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des détails : {e}")

    def save_payment(self):
        try:
            method_idx = self.combo_method.currentIndex()

            cash = 0.0; tpe = 0.0; euro = 0.0; taux = 0.0; oc = 0.0; prix_g = 0.0
            dollar = 0.0; taux_dollar = 0.0; remise_da = 0.0
            montant_total_da = 0.0
            poids_deduit = 0.0

            if method_idx == 0:  # Dinar
                cash = float(self.inp_cash.text() or 0)
                tpe = float(self.inp_tpe.text() or 0)
                montant_total_da = cash + tpe

            elif method_idx == 1:  # Euro
                euro = float(self.inp_euro.text() or 0)
                taux = float(self.inp_taux_change.text() or 0)
                montant_total_da = float(self.inp_euro_da.text() or 0)
                if euro == 0 or montant_total_da == 0:
                    QMessageBox.warning(self, "Erreur", "Le montant Euro et son équivalent en Dinar sont obligatoires.")
                    return

            elif method_idx == 2:  # Or cassé
                oc = float(self.inp_oc.text() or 0)
                prix_g = float(self.inp_prix_g_casse.text() or 0)
                montant_total_da = float(self.inp_casse_da.text() or 0)
                if oc == 0 or montant_total_da == 0:
                    QMessageBox.warning(self, "Erreur", "Le poids d'Or Cassé et son équivalent en Dinar sont obligatoires.")
                    return

            elif method_idx == 3:  # Dollar
                dollar = float(self.inp_dollar.text() or 0)
                taux_dollar = float(self.inp_taux_change_dollar.text() or 0)
                montant_total_da = float(self.inp_dollar_da.text() or 0)
                if dollar == 0 or montant_total_da == 0:
                    QMessageBox.warning(self, "Erreur", "Le montant Dollar et son équivalent en Dinar sont obligatoires.")
                    return

            try: remise_da = float(self.inp_remise_da.text() or 0)
            except Exception: remise_da = 0.0

            try: poids_deduit = float(self.inp_poids_deduit.text() or 0)
            except Exception: poids_deduit = 0.0

            if montant_total_da == 0 and remise_da == 0 and oc == 0:
                QMessageBox.warning(self, "Erreur", "Veuillez entrer un montant payé, de l'or cassé ou une remise.")
                return

            notes = self.inp_notes.text().strip()
            if remise_da > 0:
                remise_tag = f"[Remise: {remise_da:,.2f} DA]"
                if remise_tag not in notes:
                    notes = f"{notes} | {remise_tag}".strip(" |")

            selected_item_id = self.combo_target.currentData()
            montant_da_for_storage = cash if method_idx == 0 else montant_total_da

            if any(value < 0 for value in (cash, tpe, euro, dollar, oc, poids_deduit, montant_total_da)):
                if not notes:
                    notes = "Remboursement / Rendu espèces au client"
                    self.inp_notes.setText(notes)

            if poids_deduit == 0 and not self.is_versement_libre and montant_total_da > 0:
                reply = QMessageBox.question(
                    self, "Attention", "Le poids à déduire est 0g. Êtes-vous sûr de ne rien déduire du reste ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            success = self.manager.versements.add_payment(
                versement_id=self.versement_id,
                journee_id=self.journee_id,
                montant_da=montant_da_for_storage,
                tpe_da=tpe,
                montant_euro=euro,
                taux_change_euro=taux,
                or_casse_g=oc,
                poids_deduit_g=poids_deduit,
                prix_gramme_jour_da=prix_g,
                notes=notes,
                versement_item_id=selected_item_id,
                montant_dollar=dollar,
                taux_change_dollar=taux_dollar,
                remise_da=remise_da
            )

            if success:
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", "Une erreur est survenue lors de l'enregistrement.")

        except Exception as e:
            logging.error(f"[AddPaymentDialog] Erreur save_payment: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erreur", f"Une exception s'est produite: {e}")
