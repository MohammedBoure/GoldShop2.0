# ui/widgets/versements/new_versement_dialog.py

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QFormLayout, QMessageBox, QApplication, QFrame, QTextEdit, QGroupBox,
    QCompleter, QComboBox, QStackedWidget
)
from PySide6.QtCore import Qt, QStringListModel, QEvent, QTimer
from PySide6.QtGui import QFont

from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog

import qtawesome as qta
from ui.dialogs.client_selection_dialog import ClientSelectionDialog

import time

class NewVersementDialog(QDialog):
    def __init__(self, manager, current_user, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.current_user = current_user
        
        self.cart_items = []
        self.selected_client_id = None
        self.products_autocomplete_map = {}
        self.is_processing = False
        
        self._last_key_time = 0.0                    
        self._scan_timer = QTimer(self)             
        self._scan_timer.setSingleShot(True)        
        self._scan_timer.setInterval(100)           
        self._scan_timer.timeout.connect(self._on_scan_complete)  

        self.setWindowTitle("Nouveau Versement (Acompte)")
        
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)
        self.setWindowState(Qt.WindowMaximized)
        
        self.init_ui()
        self.setup_product_completer()

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

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # ==========================================
        # الجانب الأيسر: سلة المنتجات والبحث (55%)
        # ==========================================
        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_panel.setStyleSheet("background-color: white; border-radius: 6px; border: 1px solid #dcdde1;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)

        lbl_scan = QLabel("🛒 Rechercher un article (Par Nom ou Code-barres)")
        lbl_scan.setStyleSheet("font-size: 15px; font-weight: bold; color: #2c3e50; border: none;")
        left_layout.addWidget(lbl_scan)

        barcode_layout = QHBoxLayout()
        self.inp_barcode = QLineEdit()
        self.inp_barcode.setPlaceholderText("🔍 Tapez le nom ou scannez le code-barres...")
        self.inp_barcode.setStyleSheet("font-size: 16px; padding: 8px; border: 2px solid #0f8f83; border-radius: 6px; background-color: #f8fffd;")
        
        self.inp_barcode.installEventFilter(self)
        self.inp_barcode.returnPressed.connect(self.on_barcode_entered)
        self.inp_barcode.textChanged.connect(self._on_barcode_text_changed)
        
        btn_clear_cart = QPushButton(" Vider")
        btn_clear_cart.setIcon(qta.icon("fa5s.trash", color="white"))
        btn_clear_cart.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; font-size: 14px; padding: 8px 12px; border-radius: 6px;")
        btn_clear_cart.setAutoDefault(False)
        btn_clear_cart.setDefault(False)
        btn_clear_cart.clicked.connect(self.clear_cart)
        
        btn_details = QPushButton("ℹ️ Détails Panier")
        btn_details.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; font-size: 14px; padding: 8px 12px; border-radius: 6px;")
        btn_details.setAutoDefault(False)
        btn_details.setDefault(False)
        btn_details.setCursor(Qt.PointingHandCursor)
        btn_details.clicked.connect(self.show_product_details)
        
        barcode_layout.addWidget(self._wrap_with_keyboard(self.inp_barcode))
        barcode_layout.addWidget(btn_details)
        barcode_layout.addWidget(btn_clear_cart)
        left_layout.addLayout(barcode_layout)

        self.cart_table = QTableWidget(0, 5)
        self.cart_table.setHorizontalHeaderLabels(["Code", "Désignation", "Poids (g)", "Prix Estimé", "Action"])
        self.cart_table.setStyleSheet("""
            QTableWidget { background-color: white; font-size: 14px; gridline-color: #eef2f6; }
            QHeaderView::section { background-color: #0f8f83; color: white; font-weight: bold; padding: 6px; font-size: 13px; border: none; }
            QTableWidget::item { border-bottom: 1px solid #eef2f6; }
        """)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cart_table.setSelectionMode(QTableWidget.NoSelection)
        self.cart_table.verticalHeader().setVisible(False)
        
        header = self.cart_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        left_layout.addWidget(self.cart_table)

        # ==========================================
        # الجانب الأيمن: البيانات المالية والزبون (45% - عريض ومقسم لعمودين)
        # ==========================================
        right_panel = QFrame()
        right_panel.setFixedWidth(680) 
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 1. تحديد الزبون (الجزء العلوي)
        group_client = QGroupBox("👤 Client (Obligatoire)")
        group_client.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; color: #075f58; border: 1px solid #cbd5df; border-radius: 6px; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        lay_client = QVBoxLayout(group_client)
        lay_client.setContentsMargins(10, 12, 10, 10)
        
        self.btn_select_client = QPushButton("🔍 Sélectionner un client")
        self.btn_select_client.setStyleSheet("background-color: #fff8e8; color: #7a4d08; border: 1px solid #e3b762; font-weight: bold; font-size: 15px; padding: 10px; border-radius: 6px;")
        self.btn_select_client.setCursor(Qt.PointingHandCursor)
        self.btn_select_client.clicked.connect(self.open_client_selection)
        lay_client.addWidget(self.btn_select_client)
        right_layout.addWidget(group_client)

        # 2. صندوق التمويل والخصومات (مقسم لعمودين أفقياً لاستغلال العرض)
        group_pay = QGroupBox("💵 Financement, Remise et Acompte")
        group_pay.setStyleSheet(group_client.styleSheet())
        pay_cols_layout = QHBoxLayout(group_pay)
        pay_cols_layout.setContentsMargins(10, 14, 10, 10)
        pay_cols_layout.setSpacing(15)

        # ─── العمود الأيمن الداخلي (اليسار): طرق الدفع والملخص ───
        inner_col1 = QVBoxLayout()
        inner_col1.setSpacing(8)

        self.combo_method = QComboBox()
        self.combo_method.addItems([
            "0 - Aucun acompte (Dossier à vide)",
            "1 - Paiement en Dinar (Espèces / TPE)",
            "2 - Paiement en Devise (Euro €)",
            "3 - Paiement par Or Cassé",
            "4 - Paiement en Devise (Dollar $)"
        ])
        self.combo_method.setStyleSheet("font-size: 14px; font-weight: bold; padding: 6px; border: 2px solid #0f8f83; border-radius: 6px; color: #075f58; background-color: #e8f7f4;")
        self.combo_method.currentIndexChanged.connect(self.on_payment_method_changed)
        inner_col1.addWidget(self.combo_method)

        self.stacked_pay = QStackedWidget()
        inp_style = "font-size: 14px; font-weight: bold; padding: 5px; border: 1px solid #cbd5df; border-radius: 6px;"
        
        # --- الصفحة 0 ---
        self.page_aucun = QWidget()
        self.stacked_pay.addWidget(self.page_aucun)

        # --- الصفحة 1: الدينار ---
        self.page_dinar = QWidget()
        form_dinar = QFormLayout(self.page_dinar)
        form_dinar.setContentsMargins(0,0,0,0)
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

        # --- الصفحة 2: الأورو ---
        self.page_euro = QWidget()
        form_euro = QFormLayout(self.page_euro)
        form_euro.setContentsMargins(0,0,0,0)
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

        # --- الصفحة 3: الذهب المكسر ---
        self.page_casse = QWidget()
        form_casse = QFormLayout(self.page_casse)
        form_casse.setContentsMargins(0,0,0,0)
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

        # --- الصفحة 4: الدولار ---
        self.page_dollar = QWidget()
        form_dollar = QFormLayout(self.page_dollar)
        form_dollar.setContentsMargins(0,0,0,0)
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

        inner_col1.addWidget(self.stacked_pay)

        # العرض الديناميكي للصافي المباشر (مدمج في أسفل العمود الأيسر - التركيز على الجرام)
        self.summary_box = QGroupBox("📊 Aperçu Instantané (Reste en Grammes)")
        self.summary_box.setStyleSheet("QGroupBox { font-size: 13px; font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; background-color: #f8f9fa; margin-top: 18px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 12px; top: 0px; padding: 0 5px; }")
        sum_layout = QFormLayout(self.summary_box)
        sum_layout.setContentsMargins(8, 8, 8, 8)
        sum_layout.setSpacing(4)
        
        self.lbl_summary_brut = QLabel("0.00 DA (0.00 g)")
        self.lbl_summary_brut.setStyleSheet("font-size: 13px; font-weight: bold; color: #7f8c8d;")
        
        self.lbl_summary_remise = QLabel("0.00 DA")
        self.lbl_summary_remise.setStyleSheet("font-size: 13px; font-weight: bold; color: #c0392b;")
        
        self.lbl_summary_paye = QLabel("0.00 DA")
        self.lbl_summary_paye.setStyleSheet("font-size: 13px; font-weight: bold; color: #27ae60;")
        
        self.lbl_summary_reste = QLabel("0.00 g (0.00 DA)")
        self.lbl_summary_reste.setStyleSheet("font-size: 16px; font-weight: bold; color: #2980b9;")
        
        sum_layout.addRow(self._styled_lbl("Total Brut Initial :"), self.lbl_summary_brut)
        sum_layout.addRow(self._styled_lbl("Remise Appliquée :"), self.lbl_summary_remise)
        sum_layout.addRow(self._styled_lbl("Acompte Versé :", color="#27ae60"), self.lbl_summary_paye)
        sum_layout.addRow(self._styled_lbl("Reste Final :", color="#2980b9"), self.lbl_summary_reste)
        
        inner_col1.addWidget(self.summary_box)
        inner_col1.addStretch()
        pay_cols_layout.addLayout(inner_col1, stretch=1)

        # ─── العمود الأيمن الداخلي (اليمين): الخصم، أدوات المساعدة، والملاحظات ───
        self.widget_deduction = QWidget()
        form_deduction = QFormLayout(self.widget_deduction)
        form_deduction.setContentsMargins(0,0,0,0)
        form_deduction.setSpacing(6)
        
        lbl_remise_tools = QLabel("🛠️ Outils d'aide Remise :")
        lbl_remise_tools.setStyleSheet("font-size: 12px; font-weight: bold; color: #7f8c8d;")
        form_deduction.addRow(lbl_remise_tools)
        
        remise_buttons_layout = QHBoxLayout()
        btn_pct = QPushButton("🧮 Remise (%)")
        btn_pct.setStyleSheet("background-color: #34495e; color: white; padding: 5px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_pct.setCursor(Qt.PointingHandCursor)
        btn_pct.clicked.connect(self.open_discount_pct)
        
        btn_final = QPushButton("🏷️ Prix Final")
        btn_final.setStyleSheet("background-color: #2980b9; color: white; padding: 5px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_final.setCursor(Qt.PointingHandCursor)
        btn_final.clicked.connect(self.open_discount_final_price)
        
        btn_ppg = QPushButton("⚖️ Prix/g Target")
        btn_ppg.setStyleSheet("background-color: #8e44ad; color: white; padding: 5px; font-weight: bold; border-radius: 4px; font-size: 12px;")
        btn_ppg.setCursor(Qt.PointingHandCursor)
        btn_ppg.clicked.connect(self.open_discount_price_per_gram)
        
        remise_buttons_layout.addWidget(btn_pct)
        remise_buttons_layout.addWidget(btn_final)
        remise_buttons_layout.addWidget(btn_ppg)
        form_deduction.addRow(remise_buttons_layout)
        
        self.inp_remise_da = QLineEdit()
        self.inp_remise_da.setPlaceholderText("Ex: 5000.00")
        self.inp_remise_da.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px; color: #8e44ad; border: 1px solid #8e44ad; border-radius: 6px;")
        self.inp_remise_da.textChanged.connect(lambda _: self.auto_calculate_poids_deduit())

        self.inp_poids_deduit = QLineEdit()
        self.inp_poids_deduit.setPlaceholderText("Ex: 5.20")
        self.inp_poids_deduit.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px; color: white; background-color: #c0392b; border-radius: 6px;")
        self.inp_poids_deduit.textChanged.connect(self.update_dynamic_summary)
        
        self.inp_notes = QTextEdit()
        self.inp_notes.setFixedHeight(45)
        self.inp_notes.setPlaceholderText("Notes ou observations...")
        
        form_deduction.addRow(self._styled_lbl("🎁 Remise (DA) :", color="#8e44ad"), self._wrap_with_numpad(self.inp_remise_da))
        form_deduction.addRow(self._styled_lbl("⚖️ Poids DÉDUIT (g):", color="#c0392b"), self._wrap_with_numpad(self.inp_poids_deduit))
        form_deduction.addRow(self._styled_lbl("Notes :"), self._wrap_with_keyboard(self.inp_notes))
        
        pay_cols_layout.addWidget(self.widget_deduction, stretch=1)
        right_layout.addWidget(group_pay)
        right_layout.addStretch()

        # 3. أزرار الحفظ والإغلاق (في صف واحد سفلي لتوفير المساحة)
        buttons_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Fermer")
        self.btn_cancel.setStyleSheet("background-color: #fff5f3; border: 1px solid #e66f61; color: #be3528; font-weight: bold; font-size: 14px; padding: 10px 20px; border-radius: 6px;")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_confirm = QPushButton("🔒 Enregistrer le Versement")
        self.btn_confirm.setStyleSheet("background-color: #0f8f83; color: white; font-weight: bold; font-size: 15px; padding: 10px 20px; border-radius: 6px; border: none;")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.clicked.connect(self.save_versement)
        
        buttons_row.addWidget(self.btn_cancel)
        buttons_row.addWidget(self.btn_confirm, stretch=1)
        right_layout.addLayout(buttons_row)

        main_layout.addWidget(left_panel, stretch=55)
        main_layout.addWidget(right_panel, stretch=45)
        
        self.on_payment_method_changed(0) 
        self.inp_barcode.setFocus()

    def _styled_lbl(self, text, color="#24313f"):
        l = QLabel(text)
        l.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")
        return l

    def on_payment_method_changed(self, index):
        self.stacked_pay.setCurrentIndex(index)
        self.widget_deduction.setVisible(index > 0)
        self.auto_calculate_poids_deduit()

    # ========================================================
    # أدوات المساعدة في التخفيضات (Discount Assistant Tools)
    # ========================================================
    def open_discount_pct(self):
        total_brut = sum(float(item.get('selling_price') or 0) for item in self.cart_items)
        if total_brut <= 0:
            QMessageBox.warning(self, "Erreur", "Le panier est vide ou n'a pas de prix estimé initial.")
            return
        
        pad = VirtualNumpad(title="Saisir la Remise (%)", mode="dialog", allow_decimal=True, allow_negative=False, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                pct = float(val)
                if 0 <= pct <= 100:
                    remise_val = total_brut * (pct / 100.0)
                    self.inp_remise_da.setText(f"{remise_val:.2f}")
                else:
                    QMessageBox.warning(self, "Erreur", "Le pourcentage doit être entre 0 et 100.")

    def open_discount_final_price(self):
        total_brut = sum(float(item.get('selling_price') or 0) for item in self.cart_items)
        if total_brut <= 0:
            QMessageBox.warning(self, "Erreur", "Le panier est vide ou n'a pas de prix estimé initial.")
            return
        
        pad = VirtualNumpad(title="Saisir le Prix Final (DA)", mode="dialog", allow_decimal=True, allow_negative=False, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                final_price = float(val)
                if 0 <= final_price <= total_brut:
                    remise_val = total_brut - final_price
                    self.inp_remise_da.setText(f"{remise_val:.2f}")
                else:
                    QMessageBox.warning(self, "Erreur", f"Le prix final doit être entre 0 et {total_brut:,.2f} DA.")

    def open_discount_price_per_gram(self):
        total_weight = sum(float(item.get('remaining_weight') or item.get('weight') or 0.0) for item in self.cart_items)
        if total_weight <= 0:
            QMessageBox.warning(self, "Erreur", "Aucun article avec poids dans le panier.")
            return

        total_brut = sum(float(item.get('selling_price') or 0) for item in self.cart_items)
        current_avg = total_brut / total_weight if total_weight > 0 else 0

        pad = VirtualNumpad(title="Saisir le Nouveau Prix par Gramme", mode="dialog", allow_decimal=True, allow_negative=False, initial_value=current_avg, parent=self)
        if pad.exec() == QDialog.Accepted:
            val = pad.get_value()
            if val:
                new_ppg = float(val)
                if new_ppg >= 0:
                    expected_final = new_ppg * total_weight
                    if expected_final > total_brut: expected_final = total_brut
                    remise_val = total_brut - expected_final
                    self.inp_remise_da.setText(f"{remise_val:.2f}")
                else:
                    QMessageBox.warning(self, "Erreur", "Le prix par gramme doit être positif.")

    def auto_calculate_poids_deduit(self):
        """مساعد في الحساب: يكتب تلقائياً الوزن المقتنى بالجرام ويسمح للمستخدم بالتعديل اليدوي كأداة مساعدة"""
        total_brut = sum(float(item.get('selling_price') or 0) for item in self.cart_items)
        total_weight = sum(float(item.get('remaining_weight') or item.get('weight') or 0.0) for item in self.cart_items)
        
        try: remise = float(self.inp_remise_da.text() or 0)
        except: remise = 0.0
        
        method_idx = self.combo_method.currentIndex()
        acompte_da = 0.0
        if method_idx == 1:
            try: cash = float(self.inp_cash.text() or 0)
            except: cash = 0.0
            try: tpe = float(self.inp_tpe.text() or 0)
            except: tpe = 0.0
            acompte_da = cash + tpe
        elif method_idx == 2:
            try: acompte_da = float(self.inp_euro_da.text() or 0)
            except: acompte_da = 0.0
        elif method_idx == 3:
            try: acompte_da = float(self.inp_casse_da.text() or 0)
            except: acompte_da = 0.0
        elif method_idx == 4:
            try: acompte_da = float(self.inp_dollar_da.text() or 0)
            except: acompte_da = 0.0

        if total_brut > 0 and total_weight > 0:
            prix_g_moyen = total_brut / total_weight
            poids_auto = (acompte_da + remise) / prix_g_moyen
            if poids_auto > total_weight: poids_auto = total_weight
            
            self.inp_poids_deduit.blockSignals(True)
            self.inp_poids_deduit.setText(f"{poids_auto:.3f}")
            self.inp_poids_deduit.blockSignals(False)
            
        self.update_dynamic_summary()

    def update_dynamic_summary(self):
        total_brut = sum(float(item.get('selling_price') or 0) for item in self.cart_items)
        total_weight = sum(float(item.get('remaining_weight') or item.get('weight') or 0.0) for item in self.cart_items)
        try: remise = float(self.inp_remise_da.text() or 0)
        except: remise = 0.0
        try: poids_deduit = float(self.inp_poids_deduit.text() or 0)
        except: poids_deduit = 0.0
        
        remise_pct = (remise / total_brut * 100.0) if total_brut > 0 else 0.0
        net = max(0.0, total_brut - remise)
        
        method_idx = self.combo_method.currentIndex()
        acompte_da = 0.0
        if method_idx == 1:
            try: cash = float(self.inp_cash.text() or 0)
            except: cash = 0.0
            try: tpe = float(self.inp_tpe.text() or 0)
            except: tpe = 0.0
            acompte_da = cash + tpe
        elif method_idx == 2:
            try: acompte_da = float(self.inp_euro_da.text() or 0)
            except: acompte_da = 0.0
        elif method_idx == 3:
            try: acompte_da = float(self.inp_casse_da.text() or 0)
            except: acompte_da = 0.0
        elif method_idx == 4:
            try: acompte_da = float(self.inp_dollar_da.text() or 0)
            except: acompte_da = 0.0

        reste_da = max(0.0, net - acompte_da)
        reste_g = max(0.0, total_weight - poids_deduit)
        
        self.lbl_summary_brut.setText(f"{total_brut:,.2f} DA  (Poids: {total_weight:,.2f} g)")
        self.lbl_summary_remise.setText(f"- {remise:,.2f} DA ({remise_pct:.1f}%)" if remise > 0 else "0.00 DA")
        self.lbl_summary_paye.setText(f"{acompte_da:,.2f} DA  (Poids déduit: {poids_deduit:,.2f} g)")
        self.lbl_summary_reste.setText(f"{reste_g:,.2f} g  (Estimé: {reste_da:,.2f} DA)")

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
        except: pass

    def calc_dollar_eq(self):
        try:
            dollar = float(self.inp_dollar.text() or 0)
            taux = float(self.inp_taux_change_dollar.text() or 0)
            if dollar != 0 and taux > 0:
                self.inp_dollar_da.blockSignals(True)
                self.inp_dollar_da.setText(f"{dollar * taux:.2f}")
                self.inp_dollar_da.blockSignals(False)
                self.auto_calculate_poids_deduit()
        except: pass

    def calc_casse_eq(self):
        try:
            oc = float(self.inp_oc.text() or 0)
            prix = float(self.inp_prix_g_casse.text() or 0)
            if oc != 0 and prix > 0:
                self.inp_casse_da.blockSignals(True)
                self.inp_casse_da.setText(f"{oc * prix:.2f}")
                self.inp_casse_da.blockSignals(False)
                self.auto_calculate_poids_deduit()
        except: pass

    def eventFilter(self, obj, event):
        if obj == self.inp_barcode and event.type() == QEvent.Type.KeyPress:
            text = event.text()
            if text:
                azerty_map = str.maketrans("&é\"'(-è_çà", "1234567890")
                corrected_text = text.translate(azerty_map).upper()
                
                now = time.time()
                delta = now - self._last_key_time
                self._last_key_time = now
                
                is_scanner = (self._last_key_time > 0 and delta < 0.05)
                
                if is_scanner:
                    if self._completer_instance:
                        self._completer_instance.setWidget(None)
                    self._scan_timer.start()
                else:
                    if self._completer_instance:
                        self._completer_instance.setWidget(self.inp_barcode)

                if text != corrected_text:
                    self.inp_barcode.insert(corrected_text)
                    return True
                    
        return super().eventFilter(obj, event)

    def setup_product_completer(self):
        try:
            query_options = {"limit": 1000, "offset": 0, "show_zero_stock": False, "status_filter": "SELLABLE"}
            items = self.manager.inventory.get_inventory_paginated(**query_options)[0]
            autocomplete_strings = []
            self.products_autocomplete_map.clear()
            
            for item in items:
                barcode = str(item.get('barcode') or '').strip()
                name = str(item.get('name') or 'Article').strip()
                weight = float(item.get('remaining_weight') or item.get('weight') or 0.0)
                cat = str(item.get('category_name') or '').strip()
                sup = str(item.get('supplier_name') or '').strip()
                display_text = f"{barcode} | {name}"
                if cat: display_text += f" | Cat: {cat}"
                if sup: display_text += f" | Fourn: {sup}"
                display_text += f" | {weight:.2f}g"
                
                if barcode:
                    autocomplete_strings.append(display_text)
                    self.products_autocomplete_map[display_text] = barcode
                    self.products_autocomplete_map[barcode] = barcode
            
            model = QStringListModel(autocomplete_strings)
            completer = QCompleter(model, self)
            self._completer_instance = completer 
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            self.inp_barcode.setCompleter(completer)
            completer.activated[str].connect(self.on_completer_activated)
        except Exception as e:
            logging.error(f"[Versement] Erreur completer: {e}")

    def _extract_barcode_from_text(self, text):
        if " | " in text: return text.split(" | ")[0].strip()
        return self.products_autocomplete_map.get(text, text)

    def force_clear_barcode(self):
        QTimer.singleShot(50, lambda: self.inp_barcode.clear())

    def _on_barcode_text_changed(self, text):
        if self.is_processing: return
        text = text.strip()
        if not text or len(text) < 3: return

        now = time.time()
        delta = now - self._last_key_time
        self._last_key_time = now

        if delta < 0.2 and text in self.products_autocomplete_map:
            self._scan_timer.start()

    def _on_scan_complete(self):
        if self._completer_instance: self._completer_instance.setWidget(self.inp_barcode)
        if self.is_processing: return
        text = self.inp_barcode.text().strip()
        if not text: return
        barcode = self._extract_barcode_from_text(text)
        if barcode in self.products_autocomplete_map:
            self.is_processing = True
            self.process_barcode(barcode)
            QTimer.singleShot(300, lambda: setattr(self, 'is_processing', False))

    def on_completer_activated(self, text):
        if self.is_processing: return
        self.is_processing = True
        self.process_barcode(self._extract_barcode_from_text(text))
        QTimer.singleShot(300, lambda: setattr(self, 'is_processing', False))

    def on_barcode_entered(self):
        if self.is_processing: return
        text = self.inp_barcode.text().strip()
        if not text: return
        self.is_processing = True
        self.process_barcode(self._extract_barcode_from_text(text))
        QTimer.singleShot(300, lambda: setattr(self, 'is_processing', False))

    def process_barcode(self, barcode):
        item = self.manager.inventory.get_item_by_barcode(barcode)
        if not item:
            QMessageBox.warning(self, "Introuvable", f"L'article avec le code '{barcode}' est introuvable.")
            self.force_clear_barcode()
            return
        if any(i['id'] == item['id'] for i in self.cart_items):
            self.force_clear_barcode()
            return
        self.cart_items.append(item)
        self.refresh_cart()
        self.force_clear_barcode()

    def refresh_cart(self):
        self.cart_table.setRowCount(0)
        for i, item in enumerate(self.cart_items):
            self.cart_table.insertRow(i)
            it_code = QTableWidgetItem(str(item.get('barcode', '')))
            
            name = str(item.get('name', 'Article'))
            cat = str(item.get('category_name') or '').strip()
            sup = str(item.get('supplier_name') or '').strip()
            full_desig = name
            if cat: full_desig += f" | Cat: {cat}"
            if sup: full_desig += f" | Fourn: {sup}"
            
            it_name = QTableWidgetItem(full_desig)
            it_weight = QTableWidgetItem(f"{float(item.get('remaining_weight') or item.get('weight') or 0):.2f}")
            it_price = QTableWidgetItem(f"{float(item.get('selling_price') or 0):,.2f} DA")

            for it in [it_code, it_weight, it_price]: it.setTextAlignment(Qt.AlignCenter)
            
            self.cart_table.setItem(i, 0, it_code)
            self.cart_table.setItem(i, 1, it_name)
            self.cart_table.setItem(i, 2, it_weight)
            self.cart_table.setItem(i, 3, it_price)
            
            btn_del = QPushButton("🗑 Suppr.")
            btn_del.setStyleSheet("background-color: #e74c3c; color: white; border-radius: 4px;")
            btn_del.clicked.connect(lambda _, idx=i: self.remove_from_cart(idx))
            self.cart_table.setCellWidget(i, 4, btn_del)
            self.cart_table.setRowHeight(i, 42)
        
        self.auto_calculate_poids_deduit()

    def remove_from_cart(self, index):
        if 0 <= index < len(self.cart_items):
            self.cart_items.pop(index)
            self.refresh_cart()

    def clear_cart(self):
        self.cart_items.clear()
        self.refresh_cart()

    def show_product_details(self):
        try:
            if not self.cart_items:
                QMessageBox.information(self, "Détails Produit", "Le panier est actuellement vide.")
                return

            details_text = ""
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                for item in self.cart_items:
                    inv_id = item.get('id')
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
                dlg.setWindowTitle("📋 Détails Techniques du Panier")
                dlg.setText("Voici les spécifications détaillées des articles du panier :")
                dlg.setInformativeText(details_text.strip())
                dlg.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #2c3e50; }")
                dlg.exec()
            else:
                QMessageBox.information(self, "Détails Produit", "Détails introuvables en base de données.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des détails : {e}")

    def open_client_selection(self):
        dlg = ClientSelectionDialog(self.manager, self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_client_id:
            self.selected_client_id = dlg.selected_client_id
            try:
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT name FROM Clients WHERE id = %s", (self.selected_client_id,))
                    client = cursor.fetchone()
                    if client:
                        self.btn_select_client.setText(f"👤 Client : {client['name']}")
                        self.btn_select_client.setStyleSheet("background-color: #e8f7f4; color: #075f58; border: 1px solid #0f8f83; font-weight: bold; font-size: 15px; padding: 10px; border-radius: 6px;")
            except: pass
        self.inp_barcode.setFocus()

    def save_versement(self):
        try:
            if not self.selected_client_id or self.selected_client_id == 1:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner un client nominatif.")
                return

            method_idx = self.combo_method.currentIndex()
            
            cash = 0.0; tpe = 0.0; euro = 0.0; taux = 0.0; oc = 0.0; prix_g = 0.0
            dollar = 0.0; taux_dollar = 0.0; remise_da = 0.0
            montant_total_da = 0.0
            poids_deduit = 0.0

            if method_idx == 1:
                cash = float(self.inp_cash.text() or 0)
                tpe = float(self.inp_tpe.text() or 0)
                montant_total_da = cash + tpe
                if montant_total_da == 0:
                    QMessageBox.warning(self, "Erreur", "Veuillez entrer le montant en Dinar.")
                    return

            elif method_idx == 2:
                euro = float(self.inp_euro.text() or 0)
                taux = float(self.inp_taux_change.text() or 0)
                montant_total_da = float(self.inp_euro_da.text() or 0)
                if euro == 0 or montant_total_da == 0:
                    QMessageBox.warning(self, "Erreur", "Le montant Euro et son équivalent en Dinar sont obligatoires.")
                    return

            elif method_idx == 3:
                oc = float(self.inp_oc.text() or 0)
                prix_g = float(self.inp_prix_g_casse.text() or 0)
                montant_total_da = float(self.inp_casse_da.text() or 0)
                if oc == 0 or montant_total_da == 0:
                    QMessageBox.warning(self, "Erreur", "Le poids d'Or Cassé et son équivalent en Dinar sont obligatoires.")
                    return

            elif method_idx == 4:
                dollar = float(self.inp_dollar.text() or 0)
                taux_dollar = float(self.inp_taux_change_dollar.text() or 0)
                montant_total_da = float(self.inp_dollar_da.text() or 0)
                if dollar == 0 or montant_total_da == 0:
                    QMessageBox.warning(self, "Erreur", "Le montant Dollar et son équivalent en Dinar sont obligatoires.")
                    return

            if method_idx > 0:
                poids_deduit = float(self.inp_poids_deduit.text() or 0)
                remise_da = float(self.inp_remise_da.text() or 0)

            notes = self.inp_notes.toPlainText().strip()

            if any(value < 0 for value in (cash, tpe, euro, dollar, oc, poids_deduit, montant_total_da)):
                if not notes:
                    QMessageBox.warning(
                        self,
                        "Note Obligatoire",
                        "Vous saisissez une valeur negative (Sortie/Correction du dossier).\n\n"
                        "Veuillez obligatoirement ecrire une note explicative dans le champ 'Notes'.\n\n"
                        "Exemples :\n"
                        "- Remis en especes au client\n"
                        "- Transfere vers VRS-XXXXX\n"
                        "- Erreur de saisie corrigee"
                    )
                    self.inp_notes.setFocus()
                    return

            if not self.cart_items and method_idx == 0:
                reply = QMessageBox.question(
                    self, 
                    "Versement Libre", 
                    "Le dossier est complètement vide (Aucun article, aucun paiement initial). Voulez-vous créer un dossier à vide (Versement Libre) ?", 
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            type_v = "PRODUITS" if self.cart_items else "A_VIDE"
            
            if type_v == "PRODUITS" and method_idx > 0 and poids_deduit == 0:
                reply = QMessageBox.question(self, "Attention", "Le poids à DÉDUIRE est 0g. Êtes-vous sûr ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    self.inp_poids_deduit.setFocus()
                    return

            items_list = [{"inventory_id": item['id'], "designation": item['name']} for item in self.cart_items]

            journee = self.manager.cash_box.get_or_create_today_session(user_id=self.current_user.get('id', 1))
            if not journee:
                QMessageBox.critical(self, "Erreur", "La session de caisse est fermée.")
                return

            try:
                res = self.manager.versements.create_versement(
                    client_id=self.selected_client_id,
                    journee_id=journee['id'],
                    type_versement=type_v,
                    items_list=items_list,
                    montant_da=montant_total_da,
                    montant_euro=euro,
                    taux_change_euro=taux,
                    montant_dollar=dollar,
                    taux_change_dollar=taux_dollar,
                    remise_da=remise_da,
                    or_casse_g=oc,
                    poids_deduit_g=poids_deduit,
                    prix_gramme_jour_da=prix_g,
                    notes=notes
                )
            except TypeError:
                notes_to_save = notes
                if euro > 0 or dollar > 0 or remise_da > 0 or poids_deduit > 0:
                    notes_to_save += f" | [Détails: Euro={euro}€, Dollar={dollar}$, Remise={remise_da}DA, PoidsDéduit={poids_deduit}g]"
                    
                res = self.manager.versements.create_versement(
                    client_id=self.selected_client_id,
                    journee_id=journee['id'],
                    type_versement=type_v,
                    items_list=items_list,
                    montant_da=montant_total_da,
                    or_casse_g=oc,
                    prix_gramme_jour_da=prix_g,
                    notes=notes_to_save
                )

            if res.get("success"):
                QMessageBox.information(self, "Succès", "Le dossier a été validé avec succès.")
                self.accept()
            else:
                QMessageBox.critical(self, "Erreur", str(res.get("message")))
                
        except Exception as e:
            print(f"❌ ERREUR save_versement : {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erreur", f"Une section s'est produite: {e}")
