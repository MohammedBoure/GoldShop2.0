# ui/widgets/settings/pdf_printer_tab.py

import os
import io
import base64
import copy
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox, QFormLayout, 
    QComboBox, QSpinBox, QCheckBox, QPushButton, QLabel, QColorDialog, 
    QScrollArea, QLineEdit, QDialog, QMessageBox, QSlider, QFileDialog, QInputDialog
)
from PySide6.QtCore import Qt, QSize, QByteArray, QBuffer
from PySide6.QtGui import QPixmap, QPainter, QTextDocument, QColor, QImage
from PySide6.QtPrintSupport import QPrinterInfo

from ui.tools.invoice_generator import PdfHelper

# ==========================================
# 1. LOGO SETTINGS DIALOG
# ==========================================
class PdfLogoSettingsDialog(QDialog):
    def __init__(self, image_path, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Réglages du Logo")
        self.setMinimumSize(450, 400)
        self.original_image = QImage(image_path)
        self.settings = current_settings
        self.init_ui()
        self.apply_filters()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.preview_label = QLabel(); self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #ecf0f1; border: 2px dashed #bdc3c7; padding: 10px;")
        layout.addWidget(self.preview_label)

        layout.addWidget(QLabel("Largeur (Pixels) :"))
        self.spin_width = QSpinBox(); self.spin_width.setRange(30, 500); self.spin_width.setValue(self.settings.get('width', 100))
        layout.addWidget(self.spin_width)

        self.chk_bw = QCheckBox("Appliquer le filtre Noir & Blanc")
        self.chk_bw.setChecked(self.settings.get('use_bw_filter', False))
        layout.addWidget(self.chk_bw)

        self.sld_threshold = QSlider(Qt.Horizontal); self.sld_threshold.setRange(0, 255); self.sld_threshold.setValue(self.settings.get('threshold', 127))
        layout.addWidget(QLabel("Seuil Noir/Blanc :")); layout.addWidget(self.sld_threshold)

        layout.addWidget(QLabel("Position du Logo par rapport au nom du magasin :"))
        self.cmb_align = QComboBox(); self.cmb_align.addItems(["À gauche du nom", "À droite du nom", "Au-dessus du nom (Centré)"])
        self.cmb_align.setCurrentText(self.settings.get('align', "À gauche du nom"))
        layout.addWidget(self.cmb_align)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Appliquer"); btn_ok.clicked.connect(self.accept)
        btn_ok.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        btns.addWidget(QPushButton("Annuler", clicked=self.reject)); btns.addWidget(btn_ok)
        layout.addLayout(btns)

        self.spin_width.valueChanged.connect(self.apply_filters)
        self.chk_bw.stateChanged.connect(self.apply_filters)
        self.sld_threshold.valueChanged.connect(self.apply_filters)
        self.chk_bw.stateChanged.connect(lambda: self.sld_threshold.setEnabled(self.chk_bw.isChecked()))
        self.sld_threshold.setEnabled(self.chk_bw.isChecked())

    def apply_filters(self):
        w = self.spin_width.value()
        img = self.original_image.scaledToWidth(w, Qt.SmoothTransformation)
        if self.chk_bw.isChecked():
            img = img.convertToFormat(QImage.Format_Grayscale8)
            thresh = self.sld_threshold.value()
            for y in range(img.height()):
                for x in range(img.width()):
                    val = img.pixelColor(x, y).red()
                    img.setPixelColor(x, y, QColor(0,0,0) if val <= thresh else QColor(255,255,255))
        self.preview_label.setPixmap(QPixmap.fromImage(img))

    def get_final_settings(self):
        return {
            'width': self.spin_width.value(), 'use_bw_filter': self.chk_bw.isChecked(),
            'threshold': self.sld_threshold.value(), 'align': self.cmb_align.currentText()
        }

# ==========================================
# 2. MAIN PDF SETTINGS TAB
# ==========================================
class PdfPrinterTab(QWidget):
    def __init__(self, config, save_callback):
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        
        self.pdf_config = self.config.setdefault("pdf_config", {
            "active_theme": "Default",
            "printer_name": "",
            "page_size": "A5", "margin_mm": 8,
            "fonts": {"shop_name": 22, "doc_title": 18, "normal": 12, "table_header": 12, "qr_text": 10},
            "colors": {
                "text_primary": "#333333",
                "table_header_bg": "#f5f5f5",
                "paid_green": "#27ae60",
                "debt_red": "#c0392b",
                "header_text": "#333333",
                "header_bg": "transparent",
            },
            "logo": {"path": "", "width": 100, "use_bw_filter": False, "threshold": 127, "align": "À gauche du nom"},
            "codes": {"qr_link": "", "qr_text": "Notre Page", "qr_size": 60, "show_qr": True, "invoice_barcode_mode": "Code-Barres + Texte"},
            "display": {"show_rc_nif": True, "show_history": True, "show_weight_balance": True, "show_item_note": True, "show_item_code_column": True, "item_code_format": "Code-Barres", "reste_in_weight": True, "item_barcode_w": 70, "item_barcode_h": 20, "show_versement_items_section": True, "show_versement_payment_rate": True},
            "texts": {"title_facture": "FACTURE", "title_versement": "BON DE VERSEMENT", "title_versement_libre": "BON DE VERSEMENT LIBRE", "title_versement_produit": "BON DE VERSEMENT SUR PRODUIT", "title_credit_client": "DOCUMENT CREDIT CLIENT", "text_arrete": "Arrêté la présente somme de :", "policy_paid": "Le produit vendu n'est ni repris ni échangé.", "policy_debt": "Les versements ne sont ni remboursés ni échangés.", "arabic_paid": "الوزن المدفوع", "arabic_debt": "هذه الوثيقة تثبت الدفعات المسبقة الخاصة بالزبون، ومن الضروري إحضارها.", "versement_items_section_title": "Détail des produits réservés", "versement_payments_section_title": "Versements sur produit", "versement_label_article": "Article", "versement_label_code": "Code Produit", "versement_label_total_weight": "Poids total", "versement_label_total_amount": "Montant total", "versement_label_paid_amount": "Montant payé", "versement_label_paid_weight": "Poids payé", "versement_label_remaining_amount": "Reste montant", "versement_label_remaining_weight": "Reste poids", "versement_label_payment_date": "Date", "versement_label_payment_amount": "Montant Versé", "versement_label_payment_weight": "Poids (غرام)", "versement_label_payment_rate": "Prix/g paiement", "versement_summary_invoice_amount": "Montant facture", "versement_summary_total_weight": "Poids Total d'article", "versement_summary_total_quantity": "Quantite totale", "versement_summary_remaining_quantity": "Reste quantite", "versement_summary_total_paid": "Total Payé", "versement_summary_paid_weight": "Poids Acquis", "versement_summary_remaining_weight": "Reste en Poids (الغرام المتبقي)"}
        })
        self.pdf_config = PdfHelper.normalize_pdf_config(self.pdf_config)
        self.config["pdf_config"] = self.pdf_config
        self._ensure_theme_config()
        self.init_ui()

    def _ensure_theme_config(self):
        active_theme = str(self.pdf_config.get("active_theme") or "Default").strip() or "Default"
        themes = self.pdf_config.get("themes")
        if not isinstance(themes, dict):
            themes = {}
            self.pdf_config["themes"] = themes

        if not themes:
            themes[active_theme] = self._theme_from_config(self.pdf_config)
        else:
            for name in list(themes.keys()):
                if not isinstance(themes[name], dict):
                    del themes[name]

        if active_theme not in themes:
            themes[active_theme] = self._theme_from_config(self.pdf_config)

        self.current_theme_name = active_theme
        self.pdf_config["active_theme"] = active_theme
        self._apply_theme_to_config(themes[active_theme])
        self._loading_theme = False

    def get_system_printers(self):
        try:
            names = QPrinterInfo.availablePrinterNames()
        except Exception:
            return []
        clean_names = []
        for name in names:
            text = str(name or "").strip()
            if text and text not in clean_names:
                clean_names.append(text)
        return clean_names

    def refresh_printer_list(self, preferred_name=None):
        if not hasattr(self, "cmb_printer"):
            return

        printers = self.get_system_printers()
        selected = str(
            preferred_name
            if preferred_name is not None
            else self.cmb_printer.currentText() or self.pdf_config.get("printer_name", "")
        ).strip()

        self.cmb_printer.blockSignals(True)
        self.cmb_printer.clear()
        self.cmb_printer.addItem("")
        self.cmb_printer.addItems(printers)
        if selected:
            self._set_combo_text(self.cmb_printer, selected)
        self.cmb_printer.blockSignals(False)
        self._update_printer_status(printers)

    def _update_printer_status(self, printers=None):
        if not hasattr(self, "lbl_printer_status"):
            return

        printers = printers if printers is not None else self.get_system_printers()
        selected = self.cmb_printer.currentText().strip()
        if not printers:
            message = "Aucune imprimante detectee pour le moment."
        elif not selected:
            message = f"{len(printers)} imprimante(s) detectee(s). Selectionnez celle a tester plus tard."
        elif selected in printers:
            message = "Imprimante selectionnee disponible."
        else:
            message = "Imprimante enregistree, mais non detectee actuellement."
        self.lbl_printer_status.setText(message)

    def _theme_from_config(self, source):
        return {
            key: copy.deepcopy(value)
            for key, value in (source or {}).items()
            if key not in ("active_theme", "themes")
        }

    def _apply_theme_to_config(self, theme):
        for key, value in PdfHelper.normalize_pdf_config(theme or {}).items():
            if key not in ("active_theme", "themes"):
                self.pdf_config[key] = copy.deepcopy(value)

    def _set_combo_text(self, combo, text):
        text = str(text or "")
        if text and combo.findText(text) < 0:
            combo.addItem(text)
        combo.setCurrentText(text)

    def _theme_names(self):
        return list(self.pdf_config.setdefault("themes", {}).keys())

    def _refresh_theme_combo(self):
        if not hasattr(self, "cmb_theme"):
            return

        self.cmb_theme.blockSignals(True)
        self.cmb_theme.clear()
        self.cmb_theme.addItems(self._theme_names())
        self.cmb_theme.setCurrentText(self.current_theme_name)
        self.cmb_theme.blockSignals(False)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # === LEFT PANEL ===
        settings_widget = QWidget(); settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); form_layout = QVBoxLayout(content)

        grp_theme = QGroupBox("Themes PDF")
        f_theme = QFormLayout(grp_theme)
        self.cmb_theme = QComboBox()
        self._refresh_theme_combo()
        self.cmb_theme.currentTextChanged.connect(self.on_theme_changed)

        theme_buttons = QHBoxLayout()
        self.btn_theme_new = QPushButton("Nouveau")
        self.btn_theme_duplicate = QPushButton("Dupliquer")
        self.btn_theme_rename = QPushButton("Renommer")
        self.btn_theme_delete = QPushButton("Supprimer")
        self.btn_theme_new.clicked.connect(self.create_theme)
        self.btn_theme_duplicate.clicked.connect(self.duplicate_theme)
        self.btn_theme_rename.clicked.connect(self.rename_theme)
        self.btn_theme_delete.clicked.connect(self.delete_theme)
        for btn in (
            self.btn_theme_new,
            self.btn_theme_duplicate,
            self.btn_theme_rename,
            self.btn_theme_delete,
        ):
            theme_buttons.addWidget(btn)

        f_theme.addRow("Theme actif:", self.cmb_theme)
        f_theme.addRow(theme_buttons)
        form_layout.addWidget(grp_theme)

        grp_printer = QGroupBox("1. Imprimante PDF")
        f_printer = QFormLayout(grp_printer)
        self.cmb_printer = QComboBox()
        self.btn_refresh_printers = QPushButton("Actualiser")
        self.btn_refresh_printers.clicked.connect(self.refresh_printer_list)
        h_printer = QHBoxLayout()
        h_printer.addWidget(self.cmb_printer, 1)
        h_printer.addWidget(self.btn_refresh_printers)
        self.lbl_printer_status = QLabel()
        self.lbl_printer_status.setStyleSheet("color: #666; font-size: 10px;")
        self.refresh_printer_list(self.pdf_config.get("printer_name", ""))
        self.cmb_printer.currentTextChanged.connect(lambda _text: self._update_printer_status())
        f_printer.addRow("Selection:", h_printer)
        f_printer.addRow("", self.lbl_printer_status)
        form_layout.addWidget(grp_printer)

        # 2. Format & Marges
        grp_format = QGroupBox("2. Format & Marges & Logo")
        f_format = QFormLayout(grp_format)
        self.cmb_page_size = QComboBox(); self.cmb_page_size.addItems(["A4", "A5", "A6"]); self.cmb_page_size.setCurrentText(self.pdf_config.get("page_size", "A5"))
        self.spin_margin = QSpinBox(); self.spin_margin.setRange(0, 50); self.spin_margin.setValue(self.pdf_config.get("margin_mm", 8))
        self.lbl_logo_path = QLabel(self.pdf_config["logo"].get("path", "Aucun logo")); self.lbl_logo_path.setStyleSheet("color: gray; font-size: 10px;")
        h_logo = QHBoxLayout()
        h_logo.addWidget(QPushButton("📁 Parcourir", clicked=self.browse_logo)); h_logo.addWidget(QPushButton("⚙️ Taille/Position", clicked=self.open_logo_dialog)); h_logo.addWidget(QPushButton("🗑️", clicked=self.clear_logo))
        f_format.addRow("Format Papier:", self.cmb_page_size); f_format.addRow("Marges réelles (mm):", self.spin_margin); f_format.addRow("Logo:", h_logo); f_format.addRow("", self.lbl_logo_path)
        form_layout.addWidget(grp_format)

        # 3. Tailles & Polices
        grp_fonts = QGroupBox("3. Tailles & Polices (px)")
        f_fonts = QFormLayout(grp_fonts)
        fonts = self.pdf_config.setdefault("fonts", {})
        self.spin_f_shop = QSpinBox(); self.spin_f_shop.setRange(10, 50); self.spin_f_shop.setValue(fonts.get("shop_name", 22))
        self.spin_f_title = QSpinBox(); self.spin_f_title.setRange(10, 50); self.spin_f_title.setValue(fonts.get("doc_title", 18))
        self.spin_f_norm = QSpinBox(); self.spin_f_norm.setRange(8, 30); self.spin_f_norm.setValue(fonts.get("normal", 12))
        self.spin_f_th = QSpinBox(); self.spin_f_th.setRange(8, 30); self.spin_f_th.setValue(fonts.get("table_header", 12))
        f_fonts.addRow("Nom du Magasin:", self.spin_f_shop); f_fonts.addRow("Titre du Document:", self.spin_f_title)
        f_fonts.addRow("Texte Général:", self.spin_f_norm); f_fonts.addRow("Entête du Tableau:", self.spin_f_th)
        form_layout.addWidget(grp_fonts)

        # 4. QR Code & Codes
        grp_qr = QGroupBox("4. QR Code (Sous le nom du magasin)")
        f_qr = QFormLayout(grp_qr)
        codes = self.pdf_config.setdefault("codes", {})
        self.chk_show_qr = QCheckBox("Activer le QR Code"); self.chk_show_qr.setChecked(codes.get("show_qr", True))
        self.inp_qr_link = QLineEdit(codes.get("qr_link", "")); self.inp_qr_link.setPlaceholderText("Lien (ex: facebook.com/...)")
        self.inp_qr_text = QLineEdit(codes.get("qr_text", "Notre Page"))
        self.spin_qr_size = QSpinBox(); self.spin_qr_size.setRange(30, 200); self.spin_qr_size.setValue(codes.get("qr_size", 60))
        self.spin_f_qr = QSpinBox(); self.spin_f_qr.setRange(6, 20); self.spin_f_qr.setValue(fonts.get("qr_text", 10))
        f_qr.addRow("", self.chk_show_qr); f_qr.addRow("Lien:", self.inp_qr_link); f_qr.addRow("Texte à côté:", self.inp_qr_text)
        f_qr.addRow("Taille QR:", self.spin_qr_size); f_qr.addRow("Taille Texte QR:", self.spin_f_qr)
        form_layout.addWidget(grp_qr)

        # 5. Affichage & Tableau
        grp_disp = QGroupBox("5. Tableau, Poids & Affichage")
        f_disp = QFormLayout(grp_disp)
        disp = self.pdf_config["display"]
        
        self.cmb_inv_bc_mode = QComboBox()
        self.cmb_inv_bc_mode.addItems(["Code-Barres + Texte", "Code-Barres uniquement", "Texte uniquement"])
        self.cmb_inv_bc_mode.setCurrentText(codes.get("invoice_barcode_mode", "Code-Barres + Texte"))
        
        self.chk_col_code = QCheckBox("Colonne 'Code Produit'"); self.chk_col_code.setChecked(disp.get("show_item_code_column", True))
        self.cmb_code_format = QComboBox(); self.cmb_code_format.addItems(["Code-Barres", "Texte Simple"]); self.cmb_code_format.setCurrentText(disp.get("item_code_format", "Code-Barres"))
        self.chk_item_note = QCheckBox("Afficher les notes/descriptions sous les produits"); self.chk_item_note.setChecked(disp.get("show_item_note", True))
        
        self.spin_item_bc_w = QSpinBox(); self.spin_item_bc_w.setRange(20, 300); self.spin_item_bc_w.setValue(disp.get("item_barcode_w", 70))
        self.spin_item_bc_h = QSpinBox(); self.spin_item_bc_h.setRange(10, 150); self.spin_item_bc_h.setValue(disp.get("item_barcode_h", 20))
        h_bc_size = QHBoxLayout()
        h_bc_size.addWidget(QLabel("Largeur (px):")); h_bc_size.addWidget(self.spin_item_bc_w)
        h_bc_size.addWidget(QLabel("Hauteur (px):")); h_bc_size.addWidget(self.spin_item_bc_h)

        self.chk_rc = QCheckBox("Afficher RC et NIF"); self.chk_rc.setChecked(disp.get("show_rc_nif", True))
        self.chk_hist = QCheckBox("Afficher l'historique des paiements"); self.chk_hist.setChecked(disp.get("show_history", True))
        self.chk_weight = QCheckBox("Afficher le Bilan des Poids (غرامات الذهب)"); self.chk_weight.setChecked(disp.get("show_weight_balance", True))
        self.chk_reste_weight = QCheckBox("Afficher la colonne 'Reste' en Poids (Grammes)"); self.chk_reste_weight.setChecked(disp.get("reste_in_weight", True))

        f_disp.addRow("Affichage N° Facture:", self.cmb_inv_bc_mode)
        f_disp.addRow("", self.chk_col_code)
        f_disp.addRow("Format Code Produit:", self.cmb_code_format)
        f_disp.addRow("Taille Code-Barres Produit:", h_bc_size)
        f_disp.addRow("", self.chk_item_note)
        f_disp.addRow("", self.chk_reste_weight); f_disp.addRow("---", QLabel(""))
        f_disp.addRow("", self.chk_rc); f_disp.addRow("", self.chk_hist); f_disp.addRow("", self.chk_weight)
        form_layout.addWidget(grp_disp)

        # 6. Couleurs
        grp_colors = QGroupBox("6. Couleurs")
        v_colors = QVBoxLayout(grp_colors)
        h_colors = QHBoxLayout()
        h_header_colors = QHBoxLayout()
        colors = self.pdf_config["colors"]
        self.btn_c_text = self.create_color_button("text_primary", colors.get("text_primary", "#333333"))
        self.btn_c_th = self.create_color_button("table_header_bg", colors.get("table_header_bg", "#f5f5f5"))
        self.btn_c_green = self.create_color_button("paid_green", colors.get("paid_green", "#27ae60"))
        self.btn_c_red = self.create_color_button("debt_red", colors.get("debt_red", "#c0392b"))
        self.btn_c_header_text = self.create_color_button("header_text", colors.get("header_text", "#333333"))
        self.btn_c_header_bg = self.create_color_button("header_bg", colors.get("header_bg", "transparent"))
        h_colors.addWidget(QLabel("Texte:")); h_colors.addWidget(self.btn_c_text); h_colors.addWidget(QLabel("Entête:")); h_colors.addWidget(self.btn_c_th)
        h_colors.addWidget(QLabel("Payé (+):")); h_colors.addWidget(self.btn_c_green); h_colors.addWidget(QLabel("Reste (-):")); h_colors.addWidget(self.btn_c_red)
        h_header_colors.addWidget(QLabel("Titre haut:")); h_header_colors.addWidget(self.btn_c_header_text); h_header_colors.addWidget(QLabel("Fond haut:")); h_header_colors.addWidget(self.btn_c_header_bg)
        h_header_colors.addStretch(1)
        v_colors.addLayout(h_colors)
        v_colors.addLayout(h_header_colors)
        form_layout.addWidget(grp_colors)

        # 7. Textes & Mentions
        grp_texts = QGroupBox("7. Textes & Mentions")
        f_texts = QFormLayout(grp_texts)
        texts = self.pdf_config.setdefault("texts", {})
        
        self.inp_t_facture = QLineEdit(texts.get("title_facture", "FACTURE"))
        self.inp_t_vers = QLineEdit(texts.get("title_versement", "BON DE VERSEMENT"))
        self.inp_t_vers_libre = QLineEdit(texts.get("title_versement_libre", "BON DE VERSEMENT LIBRE"))
        self.inp_t_vers_product = QLineEdit(texts.get("title_versement_produit", "BON DE VERSEMENT SUR PRODUIT"))
        self.inp_t_credit = QLineEdit(texts.get("title_credit_client", "DOCUMENT CREDIT CLIENT"))
        self.inp_t_arrete = QLineEdit(texts.get("text_arrete", "Arrêté la présente somme de :"))
        self.inp_p_paid = QLineEdit(texts.get("policy_paid", "Le produit vendu n'est ni repris ni échangé."))
        self.inp_p_debt = QLineEdit(texts.get("policy_debt", "Les versements ne sont ni remboursés ni échangés."))
        
        self.inp_a_paid = QLineEdit(texts.get("arabic_paid", "الوزن المدفوع")); self.inp_a_paid.setAlignment(Qt.AlignRight)
        self.inp_a_debt = QLineEdit(texts.get("arabic_debt", "هذه الوثيقة تثبت الدفعات المسبقة الخاصة بالزبون، ومن الضروري إحضارها.")); self.inp_a_debt.setAlignment(Qt.AlignRight)
        
        f_texts.addRow("Titre Facture:", self.inp_t_facture); f_texts.addRow("Titre Versement:", self.inp_t_vers)
        f_texts.addRow("Titre Versement libre:", self.inp_t_vers_libre)
        f_texts.addRow("Titre Versement produit:", self.inp_t_vers_product)
        f_texts.addRow("Titre Crédit client:", self.inp_t_credit)
        f_texts.addRow("Formule Arrêté:", self.inp_t_arrete)
        f_texts.addRow("Mention (Payé):", self.inp_p_paid); f_texts.addRow("Mention (Dette):", self.inp_p_debt)
        f_texts.addRow("Arabe (Bilan Poids):", self.inp_a_paid); f_texts.addRow("Arabe (Note Dette):", self.inp_a_debt)
        form_layout.addWidget(grp_texts)

        grp_versement = QGroupBox("8. Bon de Versement produit")
        f_versement = QFormLayout(grp_versement)
        self.chk_versement_items_section = QCheckBox("Afficher le bloc Articles réservés en haut")
        self.chk_versement_items_section.setChecked(disp.get("show_versement_items_section", True))
        self.chk_versement_payment_rate = QCheckBox("Afficher la colonne Prix/g dans les paiements")
        self.chk_versement_payment_rate.setChecked(disp.get("show_versement_payment_rate", True))
        self.inp_v_items_title = QLineEdit(texts.get("versement_items_section_title", "Détail des produits réservés"))
        self.inp_v_payments_title = QLineEdit(texts.get("versement_payments_section_title", "Versements sur produit"))
        self.inp_v_label_article = QLineEdit(texts.get("versement_label_article", "Article"))
        self.inp_v_label_code = QLineEdit(texts.get("versement_label_code", "Code Produit"))
        self.inp_v_label_total_weight = QLineEdit(texts.get("versement_label_total_weight", "Poids total"))
        self.inp_v_label_total_amount = QLineEdit(texts.get("versement_label_total_amount", "Montant total"))
        self.inp_v_label_paid_amount = QLineEdit(texts.get("versement_label_paid_amount", "Montant payé"))
        self.inp_v_label_paid_weight = QLineEdit(texts.get("versement_label_paid_weight", "Poids payé"))
        self.inp_v_label_remaining_amount = QLineEdit(texts.get("versement_label_remaining_amount", "Reste montant"))
        self.inp_v_label_remaining_weight = QLineEdit(texts.get("versement_label_remaining_weight", "Reste poids"))
        self.inp_v_label_payment_date = QLineEdit(texts.get("versement_label_payment_date", "Date"))
        self.inp_v_label_payment_amount = QLineEdit(texts.get("versement_label_payment_amount", "Montant Versé"))
        self.inp_v_label_payment_weight = QLineEdit(texts.get("versement_label_payment_weight", "Poids (غرام)"))
        self.inp_v_label_payment_rate = QLineEdit(texts.get("versement_label_payment_rate", "Prix/g paiement"))
        self.inp_v_summary_invoice = QLineEdit(texts.get("versement_summary_invoice_amount", "Montant facture"))
        self.inp_v_summary_total_weight = QLineEdit(texts.get("versement_summary_total_weight", "Poids Total d'article"))
        self.inp_v_summary_total_paid = QLineEdit(texts.get("versement_summary_total_paid", "Total Payé"))
        self.inp_v_summary_paid_weight = QLineEdit(texts.get("versement_summary_paid_weight", "Poids Acquis"))
        self.inp_v_summary_remaining_weight = QLineEdit(texts.get("versement_summary_remaining_weight", "Reste en Poids (الغرام المتبقي)"))

        f_versement.addRow("", self.chk_versement_items_section)
        f_versement.addRow("", self.chk_versement_payment_rate)
        f_versement.addRow("Titre bloc Articles:", self.inp_v_items_title)
        f_versement.addRow("Titre bloc Paiements:", self.inp_v_payments_title)
        f_versement.addRow("Libellé Article:", self.inp_v_label_article)
        f_versement.addRow("Libellé Code:", self.inp_v_label_code)
        f_versement.addRow("Libellé Poids total:", self.inp_v_label_total_weight)
        f_versement.addRow("Libellé Montant total:", self.inp_v_label_total_amount)
        f_versement.addRow("Libellé Montant payé:", self.inp_v_label_paid_amount)
        f_versement.addRow("Libellé Poids payé:", self.inp_v_label_paid_weight)
        f_versement.addRow("Libellé Reste montant:", self.inp_v_label_remaining_amount)
        f_versement.addRow("Libellé Reste poids:", self.inp_v_label_remaining_weight)
        f_versement.addRow("Libellé Date paiement:", self.inp_v_label_payment_date)
        f_versement.addRow("Libellé Montant verse:", self.inp_v_label_payment_amount)
        f_versement.addRow("Libellé Poids paiement:", self.inp_v_label_payment_weight)
        f_versement.addRow("Libellé Prix/g:", self.inp_v_label_payment_rate)
        f_versement.addRow("Résumé Montant:", self.inp_v_summary_invoice)
        f_versement.addRow("Résumé Poids total:", self.inp_v_summary_total_weight)
        f_versement.addRow("Résumé Total payé:", self.inp_v_summary_total_paid)
        f_versement.addRow("Résumé Poids acquis:", self.inp_v_summary_paid_weight)
        f_versement.addRow("Résumé Reste poids:", self.inp_v_summary_remaining_weight)
        form_layout.addWidget(grp_versement)

        form_layout.addStretch(); scroll.setWidget(content); settings_layout.addWidget(scroll)
        btn_save = QPushButton("💾 Enregistrer Configuration PDF")
        btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 12px; font-weight: bold; border-radius: 4px;")
        btn_save.clicked.connect(self.save_config_local)
        settings_layout.addWidget(btn_save)
        self.splitter.addWidget(settings_widget)

        # === RIGHT PANEL (Preview) ===
        preview_widget = QGroupBox("Aperçu en Direct")
        preview_layout = QVBoxLayout(preview_widget)
        self.cmb_preview_type = QComboBox(); self.cmb_preview_type.addItems(["Facture (Totalement Payée)", "Bon de Versement (Dette/Échange)"])
        self.cmb_preview_type.currentTextChanged.connect(self.generate_preview)
        preview_layout.addWidget(self.cmb_preview_type)
        
        self.lbl_preview = QLabel(); self.lbl_preview.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.lbl_preview.setStyleSheet("background-color: #e0e0e0; border: 1px solid #bdc3c7;")
        p_scroll = QScrollArea(); p_scroll.setWidgetResizable(True); p_scroll.setAlignment(Qt.AlignCenter); p_scroll.setWidget(self.lbl_preview)
        preview_layout.addWidget(p_scroll)
        self.splitter.addWidget(preview_widget); self.splitter.setSizes([480, 520])

        for w in [self.cmb_page_size, self.spin_margin, self.spin_qr_size, self.inp_qr_link, self.inp_qr_text, self.cmb_code_format,
                  self.spin_f_shop, self.spin_f_title, self.spin_f_norm, self.spin_f_th, self.spin_f_qr,
                  self.inp_t_facture, self.inp_t_vers, self.inp_t_vers_libre, self.inp_t_vers_product, self.inp_t_credit,
                  self.inp_t_arrete, self.inp_p_paid, self.inp_p_debt, self.inp_a_paid, self.inp_a_debt,
                  self.inp_v_items_title, self.inp_v_payments_title, self.inp_v_label_article, self.inp_v_label_code,
                  self.inp_v_label_total_weight, self.inp_v_label_total_amount, self.inp_v_label_paid_amount,
                  self.inp_v_label_paid_weight, self.inp_v_label_remaining_amount, self.inp_v_label_remaining_weight,
                  self.inp_v_label_payment_date, self.inp_v_label_payment_amount,
                  self.inp_v_label_payment_weight, self.inp_v_label_payment_rate, self.inp_v_summary_invoice,
                  self.inp_v_summary_total_weight, self.inp_v_summary_total_paid, self.inp_v_summary_paid_weight,
                  self.inp_v_summary_remaining_weight,
                  self.spin_item_bc_w, self.spin_item_bc_h, self.cmb_inv_bc_mode]: 
            try: w.valueChanged.connect(self.generate_preview)
            except: w.currentTextChanged.connect(self.generate_preview) if isinstance(w, QComboBox) else w.textChanged.connect(self.generate_preview)
            
        for chk in [self.chk_rc, self.chk_hist, self.chk_weight, self.chk_item_note, self.chk_col_code, self.chk_show_qr, self.chk_reste_weight, self.chk_versement_items_section, self.chk_versement_payment_rate]:
            chk.stateChanged.connect(self.generate_preview)
            
        def toggle_bc_sizes():
            is_bc = self.chk_col_code.isChecked() and self.cmb_code_format.currentText() == "Code-Barres"
            self.spin_item_bc_w.setEnabled(is_bc); self.spin_item_bc_h.setEnabled(is_bc)
            
        self.chk_col_code.stateChanged.connect(toggle_bc_sizes); self.cmb_code_format.currentTextChanged.connect(toggle_bc_sizes)
        toggle_bc_sizes()
        self.chk_show_qr.stateChanged.connect(lambda: [w.setEnabled(self.chk_show_qr.isChecked()) for w in [self.inp_qr_link, self.inp_qr_text, self.spin_qr_size, self.spin_f_qr]])
        
        self.generate_preview()

    def _set_color_button(self, btn, color):
        btn.setProperty("selected_color", color)
        btn.setStyleSheet(f"background-color: {color}; border: 1px solid #777; height: 25px;")

    def _write_widgets_to_config(self):
        if hasattr(self, "cmb_printer"):
            self.pdf_config["printer_name"] = self.cmb_printer.currentText().strip()
        self.pdf_config["page_size"] = self.cmb_page_size.currentText()
        self.pdf_config["margin_mm"] = self.spin_margin.value()

        logo_path = self.lbl_logo_path.text()
        self.pdf_config.setdefault("logo", {})
        self.pdf_config["logo"]["path"] = "" if logo_path == "Aucun logo" else logo_path

        self.pdf_config["fonts"] = {
            "shop_name": self.spin_f_shop.value(),
            "doc_title": self.spin_f_title.value(),
            "normal": self.spin_f_norm.value(),
            "table_header": self.spin_f_th.value(),
            "qr_text": self.spin_f_qr.value(),
        }

        self.pdf_config["colors"] = {
            "text_primary": self.btn_c_text.property("selected_color"),
            "table_header_bg": self.btn_c_th.property("selected_color"),
            "paid_green": self.btn_c_green.property("selected_color"),
            "debt_red": self.btn_c_red.property("selected_color"),
            "header_text": self.btn_c_header_text.property("selected_color"),
            "header_bg": self.btn_c_header_bg.property("selected_color"),
        }
        self.pdf_config["codes"] = {
            "qr_link": self.inp_qr_link.text(),
            "qr_text": self.inp_qr_text.text(),
            "qr_size": self.spin_qr_size.value(),
            "show_qr": self.chk_show_qr.isChecked(),
            "invoice_barcode_mode": self.cmb_inv_bc_mode.currentText(),
        }

        self.pdf_config["display"] = {
            "show_rc_nif": self.chk_rc.isChecked(),
            "show_history": self.chk_hist.isChecked(),
            "show_weight_balance": self.chk_weight.isChecked(),
            "show_item_note": self.chk_item_note.isChecked(),
            "show_item_code_column": self.chk_col_code.isChecked(),
            "item_code_format": self.cmb_code_format.currentText(),
            "reste_in_weight": self.chk_reste_weight.isChecked(),
            "item_barcode_w": self.spin_item_bc_w.value(),
            "item_barcode_h": self.spin_item_bc_h.value(),
            "show_versement_items_section": self.chk_versement_items_section.isChecked(),
            "show_versement_payment_rate": self.chk_versement_payment_rate.isChecked(),
        }

        def _text(name, fallback=""):
            widget = getattr(self, name, None)
            return widget.text() if widget is not None else fallback

        title_versement = _text("inp_t_vers", "BON DE VERSEMENT")
        self.pdf_config["texts"] = {
            "title_facture": _text("inp_t_facture", "FACTURE"),
            "title_versement": title_versement,
            "title_versement_libre": _text("inp_t_vers_libre", "BON DE VERSEMENT LIBRE"),
            "title_versement_produit": _text("inp_t_vers_product", title_versement),
            "title_credit_client": _text("inp_t_credit", "DOCUMENT CREDIT CLIENT"),
            "text_arrete": _text("inp_t_arrete", "Arrêté la présente somme de :"),
            "policy_paid": _text("inp_p_paid", ""),
            "policy_debt": _text("inp_p_debt", ""),
            "arabic_paid": _text("inp_a_paid", ""),
            "arabic_debt": _text("inp_a_debt", ""),
            "versement_items_section_title": _text("inp_v_items_title", "Détail des produits réservés"),
            "versement_payments_section_title": _text("inp_v_payments_title", "Versements sur produit"),
            "versement_label_article": _text("inp_v_label_article", "Article"),
            "versement_label_code": _text("inp_v_label_code", "Code Produit"),
            "versement_label_total_weight": _text("inp_v_label_total_weight", "Poids total"),
            "versement_label_total_amount": _text("inp_v_label_total_amount", "Montant total"),
            "versement_label_paid_amount": _text("inp_v_label_paid_amount", "Montant payé"),
            "versement_label_paid_weight": _text("inp_v_label_paid_weight", "Poids payé"),
            "versement_label_remaining_amount": _text("inp_v_label_remaining_amount", "Reste montant"),
            "versement_label_remaining_weight": _text("inp_v_label_remaining_weight", "Reste poids"),
            "versement_label_payment_date": _text("inp_v_label_payment_date", "Date"),
            "versement_label_payment_amount": _text("inp_v_label_payment_amount", "Montant Versé"),
            "versement_label_payment_weight": _text("inp_v_label_payment_weight", "Poids (غرام)"),
            "versement_label_payment_rate": _text("inp_v_label_payment_rate", "Prix/g paiement"),
            "versement_summary_invoice_amount": _text("inp_v_summary_invoice", "Montant facture"),
            "versement_summary_total_weight": _text("inp_v_summary_total_weight", "Poids Total d'article"),
            "versement_summary_total_paid": _text("inp_v_summary_total_paid", "Total Payé"),
            "versement_summary_paid_weight": _text("inp_v_summary_paid_weight", "Poids Acquis"),
            "versement_summary_remaining_weight": _text("inp_v_summary_remaining_weight", "Reste en Poids (الغرام المتبقي)"),
        }

    def _collect_theme_from_widgets(self):
        self._write_widgets_to_config()
        return self._theme_from_config(self.pdf_config)

    def _apply_theme_to_widgets(self, theme):
        theme = PdfHelper.normalize_pdf_config(theme or {})
        self._loading_theme = True
        try:
            self.refresh_printer_list(theme.get("printer_name", ""))
            self._set_combo_text(self.cmb_page_size, theme.get("page_size", "A5"))
            self.spin_margin.setValue(int(theme.get("margin_mm", 8)))

            logo = theme.get("logo", {})
            self.lbl_logo_path.setText(logo.get("path") or "Aucun logo")

            fonts = theme.get("fonts", {})
            self.spin_f_shop.setValue(int(fonts.get("shop_name", 22)))
            self.spin_f_title.setValue(int(fonts.get("doc_title", 18)))
            self.spin_f_norm.setValue(int(fonts.get("normal", 12)))
            self.spin_f_th.setValue(int(fonts.get("table_header", 12)))
            self.spin_f_qr.setValue(int(fonts.get("qr_text", 10)))

            codes = theme.get("codes", {})
            self.chk_show_qr.setChecked(bool(codes.get("show_qr", True)))
            self.inp_qr_link.setText(codes.get("qr_link", ""))
            self.inp_qr_text.setText(codes.get("qr_text", "Notre Page"))
            self.spin_qr_size.setValue(int(codes.get("qr_size", 60)))
            self._set_combo_text(self.cmb_inv_bc_mode, codes.get("invoice_barcode_mode", "Code-Barres + Texte"))

            disp = theme.get("display", {})
            self.chk_col_code.setChecked(bool(disp.get("show_item_code_column", True)))
            self._set_combo_text(self.cmb_code_format, disp.get("item_code_format", "Code-Barres"))
            self.chk_item_note.setChecked(bool(disp.get("show_item_note", True)))
            self.spin_item_bc_w.setValue(int(disp.get("item_barcode_w", 70)))
            self.spin_item_bc_h.setValue(int(disp.get("item_barcode_h", 20)))
            self.chk_rc.setChecked(bool(disp.get("show_rc_nif", True)))
            self.chk_hist.setChecked(bool(disp.get("show_history", True)))
            self.chk_weight.setChecked(bool(disp.get("show_weight_balance", True)))
            self.chk_reste_weight.setChecked(bool(disp.get("reste_in_weight", True)))
            self.chk_versement_items_section.setChecked(bool(disp.get("show_versement_items_section", True)))
            self.chk_versement_payment_rate.setChecked(bool(disp.get("show_versement_payment_rate", True)))

            colors = theme.get("colors", {})
            self._set_color_button(self.btn_c_text, colors.get("text_primary", "#333333"))
            self._set_color_button(self.btn_c_th, colors.get("table_header_bg", "#f5f5f5"))
            self._set_color_button(self.btn_c_green, colors.get("paid_green", "#27ae60"))
            self._set_color_button(self.btn_c_red, colors.get("debt_red", "#c0392b"))
            self._set_color_button(self.btn_c_header_text, colors.get("header_text", "#333333"))
            self._set_color_button(self.btn_c_header_bg, colors.get("header_bg", "transparent"))

            texts = theme.get("texts", {})
            self.inp_t_facture.setText(texts.get("title_facture", "FACTURE"))
            self.inp_t_vers.setText(texts.get("title_versement", "BON DE VERSEMENT"))
            if hasattr(self, "inp_t_vers_libre"):
                self.inp_t_vers_libre.setText(texts.get("title_versement_libre", "BON DE VERSEMENT LIBRE"))
            if hasattr(self, "inp_t_vers_product"):
                self.inp_t_vers_product.setText(texts.get("title_versement_produit", texts.get("title_versement", "BON DE VERSEMENT")))
            if hasattr(self, "inp_t_credit"):
                self.inp_t_credit.setText(texts.get("title_credit_client", "DOCUMENT CREDIT CLIENT"))
            self.inp_t_arrete.setText(texts.get("text_arrete", "Arrete la presente somme de :"))
            self.inp_p_paid.setText(texts.get("policy_paid", "Le produit vendu n'est ni repris ni echange."))
            self.inp_p_debt.setText(texts.get("policy_debt", "Les versements ne sont ni rembourses ni echanges."))
            self.inp_a_paid.setText(texts.get("arabic_paid", ""))
            self.inp_a_debt.setText(texts.get("arabic_debt", ""))
            self.inp_v_items_title.setText(texts.get("versement_items_section_title", "Détail des produits réservés"))
            self.inp_v_payments_title.setText(texts.get("versement_payments_section_title", "Versements sur produit"))
            self.inp_v_label_article.setText(texts.get("versement_label_article", "Article"))
            self.inp_v_label_code.setText(texts.get("versement_label_code", "Code Produit"))
            self.inp_v_label_total_weight.setText(texts.get("versement_label_total_weight", "Poids total"))
            self.inp_v_label_total_amount.setText(texts.get("versement_label_total_amount", "Montant total"))
            self.inp_v_label_paid_amount.setText(texts.get("versement_label_paid_amount", "Montant payé"))
            self.inp_v_label_paid_weight.setText(texts.get("versement_label_paid_weight", "Poids payé"))
            self.inp_v_label_remaining_amount.setText(texts.get("versement_label_remaining_amount", "Reste montant"))
            self.inp_v_label_remaining_weight.setText(texts.get("versement_label_remaining_weight", "Reste poids"))
            self.inp_v_label_payment_date.setText(texts.get("versement_label_payment_date", "Date"))
            self.inp_v_label_payment_amount.setText(texts.get("versement_label_payment_amount", "Montant Versé"))
            self.inp_v_label_payment_weight.setText(texts.get("versement_label_payment_weight", "Poids (غرام)"))
            self.inp_v_label_payment_rate.setText(texts.get("versement_label_payment_rate", "Prix/g paiement"))
            self.inp_v_summary_invoice.setText(texts.get("versement_summary_invoice_amount", "Montant facture"))
            self.inp_v_summary_total_weight.setText(texts.get("versement_summary_total_weight", "Poids Total d'article"))
            self.inp_v_summary_total_paid.setText(texts.get("versement_summary_total_paid", "Total Payé"))
            self.inp_v_summary_paid_weight.setText(texts.get("versement_summary_paid_weight", "Poids Acquis"))
            self.inp_v_summary_remaining_weight.setText(texts.get("versement_summary_remaining_weight", "Reste en Poids (الغرام المتبقي)"))
        finally:
            self._loading_theme = False

        self.generate_preview()

    def _store_current_theme_from_widgets(self):
        if not hasattr(self, "cmb_page_size"):
            return
        self.pdf_config.setdefault("themes", {})[self.current_theme_name] = self._collect_theme_from_widgets()

    def _theme_name_from_user(self, title, label, default=""):
        name, ok = QInputDialog.getText(self, title, label, QLineEdit.Normal, default)
        if not ok:
            return None
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom du theme est obligatoire.")
            return None
        return name

    def on_theme_changed(self, name):
        if self._loading_theme or not name or name == self.current_theme_name:
            return
        themes = self.pdf_config.setdefault("themes", {})
        if name not in themes:
            return
        self._store_current_theme_from_widgets()
        self.current_theme_name = name
        self.pdf_config["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._apply_theme_to_widgets(themes[name])

    def create_theme(self):
        name = self._theme_name_from_user("Nouveau theme", "Nom du nouveau theme:")
        if not name:
            return
        themes = self.pdf_config.setdefault("themes", {})
        if name in themes:
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return
        self._store_current_theme_from_widgets()
        themes[name] = self._collect_theme_from_widgets()
        self.current_theme_name = name
        self.pdf_config["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._refresh_theme_combo()

    def duplicate_theme(self):
        name = self._theme_name_from_user("Dupliquer theme", "Nom de la copie:", f"{self.current_theme_name} copie")
        if not name:
            return
        themes = self.pdf_config.setdefault("themes", {})
        if name in themes:
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return
        self._store_current_theme_from_widgets()
        themes[name] = copy.deepcopy(themes[self.current_theme_name])
        self.current_theme_name = name
        self.pdf_config["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._refresh_theme_combo()

    def rename_theme(self):
        old_name = self.current_theme_name
        name = self._theme_name_from_user("Renommer theme", "Nouveau nom:", old_name)
        if not name or name == old_name:
            return
        themes = self.pdf_config.setdefault("themes", {})
        if name in themes:
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return
        self._store_current_theme_from_widgets()
        themes[name] = themes.pop(old_name)
        self.current_theme_name = name
        self.pdf_config["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._refresh_theme_combo()

    def delete_theme(self):
        themes = self.pdf_config.setdefault("themes", {})
        if len(themes) <= 1:
            QMessageBox.warning(self, "Erreur", "Impossible de supprimer le dernier theme.")
            return
        reply = QMessageBox.question(
            self,
            "Confirmation",
            f"Supprimer le theme '{self.current_theme_name}' ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        del themes[self.current_theme_name]
        self.current_theme_name = next(iter(themes))
        self.pdf_config["active_theme"] = self.current_theme_name
        self._apply_theme_to_config(themes[self.current_theme_name])
        self._refresh_theme_combo()
        self._apply_theme_to_widgets(themes[self.current_theme_name])

    def create_color_button(self, key, default_color):
        btn = QPushButton(); btn.setProperty("selected_color", default_color)
        btn.setStyleSheet(f"background-color: {default_color}; border: 1px solid #777; height: 25px;")
        btn.clicked.connect(lambda: self.pick_color(btn)); return btn

    def pick_color(self, btn):
        color = QColorDialog.getColor(QColor(btn.property("selected_color")), self)
        if color.isValid():
            btn.setProperty("selected_color", color.name()); btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #777; height: 25px;")
            self.generate_preview()

    def browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir le Logo", "", "Images (*.png *.jpg *.jpeg)")
        if path: self.lbl_logo_path.setText(path); self.pdf_config["logo"]["path"] = path; self.generate_preview()

    def clear_logo(self):
        self.lbl_logo_path.setText("Aucun logo"); self.pdf_config["logo"]["path"] = ""; self.generate_preview()

    def open_logo_dialog(self):
        path = self.lbl_logo_path.text()
        if not path or not os.path.exists(path): return QMessageBox.warning(self, "Erreur", "Veuillez d'abord choisir un logo.")
        dialog = PdfLogoSettingsDialog(path, self.pdf_config["logo"], self)
        if dialog.exec() == QDialog.Accepted: self.pdf_config["logo"].update(dialog.get_final_settings()); self.generate_preview()

    def get_base64_qr(self, data):
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=5, border=0); qr.add_data(data); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            fp = io.BytesIO(); img.save(fp, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(fp.getvalue()).decode()}"
        except: return ""

    def get_base64_barcode(self, data, height=10):
        try:
            import barcode; from barcode.writer import ImageWriter
            CODE = barcode.get_barcode_class('code128')
            writer = ImageWriter()
            options = {'module_width': 0.2, 'module_height': height, 'font_size': 0, 'quiet_zone': 1.0}
            fp = io.BytesIO(); CODE(str(data), writer=writer).write(fp, options)
            return f"data:image/png;base64,{base64.b64encode(fp.getvalue()).decode()}"
        except: return ""

    def update_config_dict(self):
        self._write_widgets_to_config()
        self.pdf_config["active_theme"] = self.current_theme_name
        self.pdf_config.setdefault("themes", {})[self.current_theme_name] = self._theme_from_config(self.pdf_config)

    def save_config_local(self):
        self.update_config_dict(); self.save_callback()

    def generate_preview(self):
        if getattr(self, "_loading_theme", False):
            return
        self.update_config_dict(); cfg = self.pdf_config
        c_txt = cfg["colors"]["text_primary"]; c_th = cfg["colors"]["table_header_bg"]
        c_grn = cfg["colors"]["paid_green"]; c_red = cfg["colors"]["debt_red"]
        c_header_txt = cfg["colors"].get("header_text", c_txt)
        c_header_bg = cfg["colors"].get("header_bg", "transparent")
        header_padding = "8px" if c_header_bg != "transparent" else "0"
        f_shop = cfg["fonts"]["shop_name"]; f_title = cfg["fonts"]["doc_title"]
        f_norm = cfg["fonts"]["normal"]; f_th = cfg["fonts"]["table_header"]; f_qr = cfg["fonts"]["qr_text"]
        display = cfg.get("display", {})
        texts = cfg.get("texts", {})
        
        bc_w = display.get("item_barcode_w", 70)
        bc_h = display.get("item_barcode_h", 20)
        
        is_paid = "Facture" in self.cmb_preview_type.currentText()
        title = (
            texts.get("title_facture", "FACTURE")
            if is_paid
            else texts.get(
                "title_versement_produit",
                texts.get("title_versement", "BON DE VERSEMENT"),
            )
        )
        text_arrete = texts.get("text_arrete", "Arrêté la présente somme de :")

        def _txt(key, fallback):
            return texts.get(key) or fallback

        lbl_items_title = _txt("versement_items_section_title", "Détail des produits réservés")
        lbl_payments_title = _txt("versement_payments_section_title", "Versements sur produit")
        lbl_article = _txt("versement_label_article", "Article")
        lbl_code = _txt("versement_label_code", "Code Produit")
        lbl_total_weight = _txt("versement_label_total_weight", "Poids total")
        lbl_total_amount = _txt("versement_label_total_amount", "Montant total")
        lbl_paid_amount = _txt("versement_label_paid_amount", "Montant payé")
        lbl_remaining_amount = _txt("versement_label_remaining_amount", "Reste montant")
        lbl_remaining_weight = _txt("versement_label_remaining_weight", "Reste poids")
        lbl_payment_date = _txt("versement_label_payment_date", "Date")
        lbl_payment_amount = _txt("versement_label_payment_amount", "Montant Versé")
        lbl_payment_weight = _txt("versement_label_payment_weight", "Poids (غرام)")
        lbl_payment_rate = _txt("versement_label_payment_rate", "Prix/g paiement")
        lbl_summary_invoice = _txt("versement_summary_invoice_amount", "Montant facture")
        lbl_summary_total_weight = _txt("versement_summary_total_weight", "Poids Total d'article")
        lbl_summary_total_paid = _txt("versement_summary_total_paid", "Total Payé")
        lbl_summary_paid_weight = _txt("versement_summary_paid_weight", "Poids Acquis")
        lbl_summary_remaining_weight = _txt("versement_summary_remaining_weight", "Reste en Poids (الغرام المتبقي)")
        show_payment_rate = bool(display.get("show_versement_payment_rate", True))
        
        logo_html = ""
        if cfg["logo"].get("path") and os.path.exists(cfg["logo"]["path"]):
            img = QImage(cfg["logo"]["path"]).scaledToWidth(cfg["logo"].get("width", 100), Qt.SmoothTransformation)
            if cfg["logo"].get("use_bw_filter", False):
                img = img.convertToFormat(QImage.Format_Grayscale8)
                thresh = cfg["logo"].get("threshold", 127)
                for y in range(img.height()):
                    for x in range(img.width()):
                        val = img.pixelColor(x, y).red(); img.setPixelColor(x, y, QColor(0,0,0) if val <= thresh else QColor(255,255,255))
            ba = QByteArray(); buffer = QBuffer(ba); buffer.open(QBuffer.WriteOnly); img.save(buffer, "PNG")
            logo_html = f"<img src='data:image/png;base64,{ba.toBase64().data().decode()}' />"

        align_opt = cfg["logo"].get("align", "À gauche du nom")
        cell_logo_l = f"<td width='1%' style='padding-right:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À gauche du nom" and logo_html else ""
        cell_logo_r = f"<td width='1%' style='padding-left:15px; vertical-align:top;'>{logo_html}</td>" if align_opt == "À droite du nom" and logo_html else ""
        block_logo_top = f"<div style='text-align:center; margin-bottom:10px;'>{logo_html}</div>" if align_opt == "Au-dessus du nom (Centré)" and logo_html else ""

        qr_html = ""
        if cfg["codes"]["show_qr"] and cfg["codes"]["qr_link"]:
            qr_b64 = self.get_base64_qr(cfg["codes"]["qr_link"])
            sz = cfg["codes"]["qr_size"]
            if qr_b64:
                qr_html = f"""
                <div style='margin-top:10px;'>
                    <table style='border:none; padding:0;'><tr>
                        <td style='padding:0;'><img src='{qr_b64}' width='{sz}' height='{sz}' /></td>
                        <td style='vertical-align:middle; padding-left:8px; font-weight:bold; font-size:{f_qr}px;'>{cfg['codes']['qr_text']}</td>
                    </tr></table>
                </div>
                """

        inv_mode = cfg["codes"].get("invoice_barcode_mode", "Code-Barres + Texte")
        inv_num_str = "F-000148" if is_paid else "VRS-000151"
        header_extras = ""
        inv_barcode_b64 = self.get_base64_barcode(inv_num_str, height=5)
        
        if inv_mode == "Code-Barres + Texte" and inv_barcode_b64:
            header_extras = f"<div style='margin-top:8px;'><img src='{inv_barcode_b64}' width='120' height='30'/><br><span style='font-size:{int(f_norm*0.8)}px; font-weight:bold;'>{inv_num_str}</span></div>"
        elif inv_mode == "Code-Barres uniquement" and inv_barcode_b64:
            header_extras = f"<div style='margin-top:8px;'><img src='{inv_barcode_b64}' width='120' height='30'/></div>"
        else:
            header_extras = f"<div style='margin-top:5px; font-size:{f_norm}px; font-weight:bold;'>N° {inv_num_str}</div>"

        # 🟢 إعدادات المنتجات المشتركة
        show_code = display["show_item_code_column"]
        code_format = display["item_code_format"]
        th_code = f'<th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_code}</th>' if show_code else ""
        
        td_code_content = "6096164524333"
        if show_code and code_format == "Code-Barres":
            b64_prod = self.get_base64_barcode("6096164524333", height=4)
            if b64_prod: td_code_content = f"<img src='{b64_prod}' width='{bc_w}' height='{bc_h}'/><br><span style='font-size:{int(f_norm*0.8)}px;'>6096164524333</span>"
        code_td = f"<td style='text-align:center; padding:6px 5px; border-bottom:1px solid #eee;'>{td_code_content}</td>" if show_code else ""

        prod_note = f"<br><span style='font-size:{int(f_norm*0.85)}px; color:#7f8c8d; font-style:italic;'>Importation Chick Or 18K Garantie</span>" if display["show_item_note"] else ""
        reste_val = "2.50 g" if display["reste_in_weight"] else "25 000 DA"
        lbl_reste = lbl_remaining_weight if display["reste_in_weight"] else lbl_remaining_amount

        # 🟢 جدول المنتجات (Détails des Produits)
        items_html = f"""
        <tr>
            {code_td}
            <td style="padding:6px 5px; border-bottom:1px solid #eee; vertical-align:middle; color:#2c3e50; font-weight:bold;">Bague Or 18K{prod_note}</td>
            <td style="padding:6px 5px; border-bottom:1px solid #eee; text-align:center; vertical-align:middle;">4.50 g</td>
            <td style="padding:6px 5px; border-bottom:1px solid #eee; text-align:right; font-weight:bold; vertical-align:middle;">45 000 DA</td>
            <td style="padding:6px 5px; border-bottom:1px solid #eee; text-align:right; color:{c_grn}; font-weight:bold; vertical-align:middle;">20 000 DA</td>
            <td style="padding:6px 5px; border-bottom:1px solid #eee; text-align:center; color:{c_red}; font-weight:bold; vertical-align:middle;">{reste_val}</td>
        </tr>
        """
        versement_items_html = ""
        if display.get("show_versement_items_section", True):
            versement_items_html = f"""
                <h4 style="margin: 0 0 6px 0; font-size: {f_th}px; color: #2c3e50; text-transform: uppercase;">{lbl_items_title}</h4>
                <table width="100%" style="border-collapse: collapse; margin-bottom: 15px;">
                    <tr>
                        {th_code}
                        <th style="text-align:left; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_article}</th>
                        <th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_total_weight}</th>
                        <th style="text-align:right; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_total_amount}</th>
                        <th style="text-align:right; color:{c_grn}; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_paid_amount}</th>
                        <th style="text-align:center; color:{c_red}; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_reste}</th>
                    </tr>
                    {items_html}
                </table>
            """

        if is_paid:
            html = f"""
            <html><head><style>
                body {{ font-family: Arial, sans-serif; color: {c_txt}; font-size: {f_norm}px; }}
                th {{ background-color: {c_th}; padding: 8px; border-bottom: 2px solid {c_txt}; font-size: {f_th}px; text-transform: uppercase; }}
                td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            </style></head><body>
                {block_logo_top}
                <table width="100%" style="border: none; margin-bottom: 20px; background-color:{c_header_bg}; color:{c_header_txt}; padding:{header_padding};">
                    <tr>
                        {cell_logo_l}
                        <td style="border:none; padding:0; vertical-align:top;">
                            <div style="margin:0; font-weight:bold; font-size:{f_shop}px; color:{c_header_txt};">BIJOUTERIE GOLDSHOP</div>
                            <div style="margin-top:5px; font-size:{f_norm}px;">Adresse du Magasin<br>{'RC: 1234567 | NIF: 987654321' if cfg['display']['show_rc_nif'] else ''}</div>
                            {qr_html}
                        </td>
                        {cell_logo_r}
                        <td width="40%" style="text-align:right; border:none; padding:0; vertical-align:top;">
                            <div style="margin:0; font-weight:bold; font-size:{f_title}px; color:{c_header_txt};">{title}</div>
                            {header_extras}
                        </td>
                    </tr>
                </table>

                <table width="100%" style="border-collapse: collapse; margin-bottom:15px;">
                    <tr>{th_code}<th style="text-align:left; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">Désignation</th><th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">Qté/Pds</th><th style="text-align:right; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">Total</th></tr>
                    <tr>{code_td}<td style="vertical-align:middle; padding:6px 5px; border-bottom:1px solid #eee; color:#2c3e50; font-weight:bold;">Bague Or 18K{prod_note}</td><td style="text-align:center; vertical-align:middle; padding:6px 5px; border-bottom:1px solid #eee;">4.50 g</td><td style="text-align:right; vertical-align:middle; font-weight:bold; padding:6px 5px; border-bottom:1px solid #eee;">45 000 DA</td></tr>
                </table>
            """
        else: # 🟢 Bon de Versement (فيه جدولين: المنتجات والدفعات)
            rate_td = (
                f'<td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#2c3e50; text-align:center;">41,666.67 DA/g</td>'
                if show_payment_rate else ""
            )
            th_payment_rate = (
                f'<th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_rate}</th>'
                if show_payment_rate else ""
            )
            versements_html = f"""
            <tr>
                <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#333333;"><span style='color:#7f8c8d; font-weight:bold;'>N°86</span> - 2026-04-17 08:53</td>
                <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#2c3e50; font-weight:bold;">Bague Or 18K</td>
                {code_td}
                <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:{c_grn}; text-align:center; font-weight:bold;">10,000.00 DA</td>
                <td style="padding:6px 5px; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px; color:#2980b9; text-align:center;">+ 0.240 g</td>
                {rate_td}
            </tr>
            """

            html = f"""
            <html><head><style>
                body {{ font-family: Arial, sans-serif; color: {c_txt}; font-size: {f_norm}px; }}
                th {{ background-color: {c_th}; padding: 8px; border-bottom: 2px solid {c_txt}; font-size: {f_th}px; text-transform: uppercase; }}
                td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            </style></head><body>
                {block_logo_top}
                <table width="100%" style="border: none; margin-bottom: 15px; background-color:{c_header_bg}; color:{c_header_txt}; padding:{header_padding};">
                    <tr>
                        {cell_logo_l}
                        <td style="border:none; padding:0; vertical-align:top;">
                            <div style="margin:0; font-weight:bold; font-size:{f_shop}px; color:{c_header_txt};">BIJOUTERIE GOLDSHOP</div>
                            <div style="margin-top:5px; font-size:{f_norm}px;">Adresse du Magasin<br>{'RC: 1234567 | NIF: 987654321' if cfg['display']['show_rc_nif'] else ''}</div>
                            {qr_html}
                        </td>
                        {cell_logo_r}
                        <td width="40%" style="text-align:right; border:none; padding:0; vertical-align:top;">
                            <div style="margin:0; font-weight:bold; font-size:{f_title}px; color:{c_header_txt};">{title}</div>
                            {header_extras}
                            <div style="margin-top:5px; font-size:{f_norm}px;">Date: 2026-04-17 12:46</div>
                            <div style="margin-top:5px; font-weight:bold; font-size:{f_norm}px;">Client: test</div>
                        </td>
                    </tr>
                </table>

                {versement_items_html}

                <h4 style="margin: 0 0 6px 0; font-size: {f_th}px; color: #2c3e50; text-transform: uppercase;">{lbl_payments_title}</h4>
                <table width="100%" style="border-collapse: collapse; margin-bottom: 15px;">
                    <tr>
                        <th style="text-align:left; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_date}</th>
                        <th style="text-align:left; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_article}</th>
                        {th_code}
                        <th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_amount}</th>
                        <th style="text-align:center; background-color:{c_th}; padding:8px 5px; border-bottom:2px solid #333;">{lbl_payment_weight}</th>
                        {th_payment_rate}
                    </tr>
                    {versements_html}
                </table>

                <table width="100%" style="border: none;">
                    <tr>
                        <td width="50%" style="vertical-align: top; padding-right: 10px;">
                            <p style="font-size:{int(f_norm*0.9)}px;"><i>{text_arrete}</i><br>.......................................................</p>
                        </td>
                        <td width="50%" style="vertical-align: top; padding: 0;">
                            <table width="100%" style="border-collapse: collapse;">
                                <tr><td style='padding:5px; text-align:right; font-size:{int(f_norm*0.9)}px;'>{lbl_summary_invoice} :</td><td style='padding:5px; text-align:right; font-weight:bold;'>45,000.00 DA</td></tr>
                                <tr><td style='padding:5px; text-align:right; font-size:{int(f_norm*0.9)}px;'>{lbl_summary_total_weight} :</td><td style='padding:5px; text-align:right; font-weight:bold;'>4.50 g</td></tr>
                                <tr><td style='padding:5px; text-align:right; font-size:{int(f_norm*0.9)}px;'>{lbl_summary_total_paid} :</td><td style='padding:5px; text-align:right; color:{c_grn}; font-weight:bold;'>10,000.00 DA</td></tr>
                                <tr><td style='padding:5px; text-align:right; border-bottom:1px solid #eee; font-size:{int(f_norm*0.9)}px;'>{lbl_summary_paid_weight} ({texts.get('arabic_paid', '')}) :</td><td style='padding:5px; text-align:right; color:#2980b9; font-weight:bold; border-bottom:1px solid #eee;'>0.24 g</td></tr>
                                <tr><td style='padding:8px 5px; text-align:right; font-weight:bold; color:{c_red};'>{lbl_summary_remaining_weight} :</td><td style='padding:8px 5px; text-align:right; font-weight:bold; background-color:#f9f9f9; border:1px solid #eee; color:{c_red};'>4.26 g</td></tr>
                            </table>
                        </td>
                    </tr>
                </table>
            """

        if cfg["display"]["show_weight_balance"] and is_paid:
            txt_arabic_paid = cfg['texts'].get('arabic_paid', 'الوزن المدفوع')
            html += f"""
            <div style="padding: 10px; border: 1px solid {c_grn}; border-radius: 4px; width: 60%; background-color:#f9fdfa;">
                <span style="font-weight:bold; font-size:{int(f_norm*0.9)}px; color:#555;">BILAN POIDS ({txt_arabic_paid}):</span><br>
                <span style="font-size:{int(f_norm*1.2)}px; color:{c_grn}; font-weight:bold;">4.50 g <span style="font-size:{int(f_norm*0.8)}px; color:#555;">sur</span> 4.50 g</span>
            </div>
            """

        policy = cfg["texts"].get("policy_paid", "") if is_paid else cfg["texts"].get("policy_debt", "")
        txt_arabic_debt = cfg['texts'].get('arabic_debt', '')
        arab_note = "" if is_paid else f"<br><span dir='rtl' style='font-size:{f_norm}px;'>{txt_arabic_debt}</span>"
        html += f"<div style='margin-top:25px; text-align:center; border-top:1px dashed #aaa; padding-top:15px;'><b style='font-size:{int(f_norm*0.9)}px;'>{policy}</b>{arab_note}</div></body></html>"

        doc = QTextDocument(); doc.setHtml(html)
        margin_px = int(cfg["margin_mm"] * 3.779527)
        doc.setDocumentMargin(margin_px)
        pw = 793 if cfg["page_size"] == "A4" else 559; ph = 1122 if cfg["page_size"] == "A4" else 793 
        doc.setPageSize(QSize(pw, ph))
        pixmap = QPixmap(pw, ph); pixmap.fill(Qt.white); painter = QPainter(pixmap)
        doc.drawContents(painter)
        painter.end()
        scaled = pixmap.scaledToWidth(500, Qt.SmoothTransformation)
        self.lbl_preview.setPixmap(scaled); self.lbl_preview.setFixedSize(scaled.size())
