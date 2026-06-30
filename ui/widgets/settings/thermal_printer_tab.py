# ui/widgets/settings/thermal_printer_tab.py

import os
import io
import copy
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
    QComboBox, QCheckBox, QTextEdit, QPushButton, QLineEdit, QLabel, QFileDialog,
    QScrollArea, QSpinBox, QMessageBox, QInputDialog, QSplitter, QDialog, QSlider
)
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor, QPen, QImage
from PySide6.QtPrintSupport import QPrinterInfo, QPrinter

# ==========================================
# 1. LOGO DIALOG
# ==========================================
class LogoSettingsDialog(QDialog):
    def __init__(self, image_path, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Réglages Avancés du Logo")
        self.setMinimumSize(500, 600)
        self.original_image = QImage(image_path)
        self.settings = current_settings
        self.init_ui()
        self.apply_filters()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #ecf0f1; border: 2px dashed #bdc3c7; padding: 10px;")
        layout.addWidget(self.preview_label)

        layout.addWidget(QLabel("Taille (Scale %) :"))
        self.sld_scale = QSlider(Qt.Horizontal); self.sld_scale.setRange(10, 200)
        self.sld_scale.setValue(self.settings.get('scale', 100))
        layout.addWidget(self.sld_scale)

        layout.addWidget(QLabel("Seuil Noir/Blanc (Threshold) :"))
        self.sld_threshold = QSlider(Qt.Horizontal); self.sld_threshold.setRange(0, 255)
        self.sld_threshold.setValue(self.settings.get('threshold', 127))
        layout.addWidget(self.sld_threshold)

        btns = QHBoxLayout()
        btn_ok = QPushButton("Appliquer"); btn_ok.clicked.connect(self.accept)
        btn_ok.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        btn_cancel = QPushButton("Annuler"); btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel); btns.addWidget(btn_ok)
        layout.addLayout(btns)

        self.sld_scale.valueChanged.connect(self.apply_filters)
        self.sld_threshold.valueChanged.connect(self.apply_filters)

    def apply_filters(self):
        scale = self.sld_scale.value() / 100.0
        new_w = int(self.original_image.width() * scale)
        if new_w <= 0: return
        img = self.original_image.scaledToWidth(new_w, Qt.SmoothTransformation)
        img = img.convertToFormat(QImage.Format_Grayscale8)
        thresh = self.sld_threshold.value()
        for y in range(img.height()):
            for x in range(img.width()):
                val = img.pixelColor(x, y).red()
                img.setPixelColor(x, y, QColor(0,0,0) if val <= thresh else QColor(255,255,255))
        self.processed_image = img
        self.preview_label.setPixmap(QPixmap.fromImage(img))

    def get_final_settings(self):
        return {'scale': self.sld_scale.value(), 'threshold': self.sld_threshold.value()}


# ==========================================
# 2. MAIN WIDGET
# ==========================================
class ThermalPrinterTab(QWidget):
    def __init__(self, config, save_callback):
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        self._ensure_theme_config()
        self.logo_settings = self.config.get("thermal_config", {}).get("logo_settings", {'scale': 100, 'threshold': 127})
        self.init_ui()

    def _ensure_theme_config(self):
        tc = self.config.setdefault("thermal_config", {})
        active_theme = str(tc.get("active_theme") or "Default").strip() or "Default"
        themes = tc.get("themes")
        if not isinstance(themes, dict):
            themes = {}
            tc["themes"] = themes

        if not themes:
            themes[active_theme] = self._theme_from_config(tc)
        elif active_theme not in themes:
            themes[active_theme] = self._theme_from_config(tc)

        self.current_theme_name = active_theme
        tc["active_theme"] = active_theme
        self._apply_theme_to_config(themes[active_theme])
        self._loading_theme = False

    def _theme_from_config(self, source):
        return {
            key: copy.deepcopy(value)
            for key, value in (source or {}).items()
            if key not in ("active_theme", "themes")
        }

    def _apply_theme_to_config(self, theme):
        tc = self.config.setdefault("thermal_config", {})
        for key, value in (theme or {}).items():
            tc[key] = copy.deepcopy(value)

    def _set_combo_text(self, combo, text):
        text = str(text or "")
        if text and combo.findText(text) < 0:
            combo.addItem(text)
        combo.setCurrentText(text)

    def _theme_names(self):
        return list(self.config.setdefault("thermal_config", {}).setdefault("themes", {}).keys())

    def _refresh_theme_combo(self):
        if not hasattr(self, "cmb_theme"):
            return

        self.cmb_theme.blockSignals(True)
        self.cmb_theme.clear()
        self.cmb_theme.addItems(self._theme_names())
        self.cmb_theme.setCurrentText(self.current_theme_name)
        self.cmb_theme.blockSignals(False)

    def get_system_printers(self):
        try: return QPrinterInfo.availablePrinterNames()
        except: return []

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # ---------------------------------------------------------
        # LEFT PANEL (SETTINGS)
        # ---------------------------------------------------------
        settings_widget = QWidget(); settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); form_layout = QVBoxLayout(content)
        tc = self.config.get("thermal_config", {})

        grp_theme = QGroupBox("Themes ticket thermique")
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

        # --- Hardware ---
        grp_hw = QGroupBox("1. Imprimante"); f_hw = QFormLayout(grp_hw)
        self.cmb_printer = QComboBox(); self.cmb_printer.addItems([""] + self.get_system_printers())
        self._set_combo_text(self.cmb_printer, tc.get("printer_name", ""))
        f_hw.addRow("Sélection:", self.cmb_printer); form_layout.addWidget(grp_hw)

        # --- Identity & Logo ---
        grp_id = QGroupBox("2. Identité du Magasin"); f_id = QFormLayout(grp_id)
        self.inp_name = QLineEdit(tc.get("store_name", "Bijouterie GoldShop"))
        self.inp_activity = QLineEdit(tc.get("activity", "Vente_Réparation_Transformation"))
        self.inp_address = QLineEdit(tc.get("address", "CAMP CHEVALIER_JIJEL_ALGERIA"))
        self.inp_phone = QLineEdit(tc.get("phone", "0.30.51.49.84"))
        self.inp_mobile = QLineEdit(tc.get("mobile", "06.74.59.60.48"))
        
        self.lbl_logo = QLabel(tc.get("logo_path", "Aucun logo"))
        self.lbl_logo.setStyleSheet("color: gray; font-size: 10px;")
        
        h_logo_btns = QHBoxLayout()
        btn_browse = QPushButton("📁 Parcourir"); btn_browse.clicked.connect(self.browse_logo_file)
        btn_filter = QPushButton("⚙️ Filtres"); btn_filter.clicked.connect(self.open_logo_dialog)
        btn_clear = QPushButton("🗑️"); btn_clear.clicked.connect(self.clear_logo)
        
        h_logo_btns.addWidget(btn_browse); h_logo_btns.addWidget(btn_filter); h_logo_btns.addWidget(btn_clear)
        
        f_id.addRow("Nom:", self.inp_name); f_id.addRow("Activité:", self.inp_activity)
        f_id.addRow("Adresse:", self.inp_address); f_id.addRow("Tél Fixe:", self.inp_phone)
        f_id.addRow("Mobile:", self.inp_mobile); f_id.addRow("Logo:", h_logo_btns)
        f_id.addRow("", self.lbl_logo)
        form_layout.addWidget(grp_id)

        # --- Codes ---
        grp_qr = QGroupBox("3. Codes (QR & Code-Barres)"); f_qr = QFormLayout(grp_qr)
        self.inp_qr_link = QLineEdit(tc.get("qr_link", ""))
        self.inp_qr_text = QLineEdit(tc.get("qr_text", "JEWELRY AMINE LAOUICI"))
        
        self.spin_qr_size = QSpinBox(); self.spin_qr_size.setRange(40, 300)
        self.spin_qr_size.setValue(tc.get("qr_size", 70))
        
        self.cmb_qr_pos = QComboBox(); self.cmb_qr_pos.addItems(["Haut (À Gauche)", "Désactivé"])
        self.cmb_qr_pos.setCurrentText(tc.get("qr_pos", "Haut (À Gauche)"))
        
        self.chk_show_barcode = QCheckBox("Afficher le N° de document en Code-Barres")
        self.chk_show_barcode.setChecked(tc.get("show_barcode", True))
        self.spin_barcode_height = QSpinBox(); self.spin_barcode_height.setRange(20, 150); self.spin_barcode_height.setValue(tc.get("barcode_height", 50))
        
        f_qr.addRow("Lien QR:", self.inp_qr_link); f_qr.addRow("Texte QR:", self.inp_qr_text)
        f_qr.addRow("Taille QR (px):", self.spin_qr_size)
        f_qr.addRow("Position QR:", self.cmb_qr_pos)
        f_qr.addRow("", self.chk_show_barcode); f_qr.addRow("Hauteur Code-Barres N°:", self.spin_barcode_height)
        form_layout.addWidget(grp_qr)

        # --- Options Facture & Versement ---
        grp_opt = QGroupBox("4. Options Facture & Versement"); f_opt = QVBoxLayout(grp_opt)
        self.chk_show_item_barcode = QCheckBox("Convertir le 'Code Produit' en Code-Barres (Tableau Facture)")
        self.chk_show_item_barcode.setChecked(tc.get("show_item_barcode", True)) 
        self.chk_show_weight = QCheckBox("Afficher le Bilan Poids (غرامات الذهب) - Facture"); self.chk_show_weight.setChecked(tc.get("show_weight", True))
        self.chk_show_history = QCheckBox("Afficher l'Historique des paiements - Facture"); self.chk_show_history.setChecked(tc.get("show_history", True))
        
        # 🟢 التحكم الديناميكي الجديد: إخفاء/إظهار سعر الغرام في Versement
        self.chk_show_versement_rate = QCheckBox("Afficher le Prix/g dans le ticket Versement")
        self.chk_show_versement_rate.setChecked(bool(tc.get("show_versement_rate", False)))
        self.chk_show_versement_rate.setStyleSheet("margin-top: 10px; font-weight: bold; color: #c0392b;")
        
        f_opt.addWidget(self.chk_show_item_barcode)
        f_opt.addWidget(self.chk_show_weight)
        f_opt.addWidget(self.chk_show_history)
        f_opt.addWidget(self.chk_show_versement_rate)
        form_layout.addWidget(grp_opt)

        # --- Geometry ---
        grp_geo = QGroupBox("5. Géométrie & Polices"); f_geo = QFormLayout(grp_geo)
        self.spin_w = QSpinBox(); self.spin_w.setRange(200, 800); self.spin_w.setValue(tc.get("page_width", 576))
        self.spin_cx = QSpinBox(); self.spin_cx.setRange(100, 400); self.spin_cx.setValue(tc.get("center_x", 288))
        self.spin_m = QSpinBox(); self.spin_m.setRange(0, 100); self.spin_m.setValue(tc.get("margin", 20))
        self.spin_f_title = QSpinBox(); self.spin_f_title.setRange(10, 80); self.spin_f_title.setValue(tc.get("font_title", 32))
        self.spin_f_norm = QSpinBox(); self.spin_f_norm.setRange(10, 80); self.spin_f_norm.setValue(tc.get("font_normal", 22))
        f_geo.addRow("Largeur:", self.spin_w); f_geo.addRow("Centre X:", self.spin_cx); f_geo.addRow("Marge:", self.spin_m)
        f_geo.addRow("Titre:", self.spin_f_title); f_geo.addRow("Normal:", self.spin_f_norm)
        form_layout.addWidget(grp_geo)

        # Connections
        for widget in [self.inp_name, self.inp_activity, self.inp_address, self.inp_phone, self.inp_mobile, self.inp_qr_link, self.inp_qr_text]:
            widget.textChanged.connect(self.generate_preview)
        for spin in [self.spin_w, self.spin_cx, self.spin_m, self.spin_f_title, self.spin_f_norm, self.spin_barcode_height, self.spin_qr_size]:
            spin.valueChanged.connect(self.generate_preview)
        self.cmb_qr_pos.currentTextChanged.connect(self.generate_preview)
        for chk in [self.chk_show_weight, self.chk_show_history, self.chk_show_barcode, self.chk_show_item_barcode, self.chk_show_versement_rate]:
            chk.stateChanged.connect(self.generate_preview)

        form_layout.addStretch(); scroll.setWidget(content); settings_layout.addWidget(scroll)

        h_btns = QHBoxLayout()
        btn_save = QPushButton("💾 Enregistrer"); btn_save.clicked.connect(self.save_config_local)
        btn_save.setStyleSheet("background-color: #2980b9; color: white; padding: 10px; font-weight: bold;")
        btn_test = QPushButton("🖨️ Imprimer Test"); btn_test.clicked.connect(self.execute_real_print)
        btn_test.setStyleSheet("background-color: #e67e22; color: white; padding: 10px; font-weight: bold;")
        h_btns.addWidget(btn_save); h_btns.addWidget(btn_test); settings_layout.addLayout(h_btns)

        self.splitter.addWidget(settings_widget)

        # ---------------------------------------------------------
        # RIGHT PANEL (PREVIEW)
        # ---------------------------------------------------------
        preview_widget = QGroupBox("Aperçu en Direct"); preview_layout = QVBoxLayout(preview_widget)
        h_test_mode = QHBoxLayout(); h_test_mode.addWidget(QLabel("Type de document:"))
        self.cmb_test_mode = QComboBox()
        self.cmb_test_mode.addItems(["Facture Détaillée (Standard)", "Bon de Versement", "Transaction Rapide"])
        self.cmb_test_mode.currentTextChanged.connect(self.generate_preview)
        h_test_mode.addWidget(self.cmb_test_mode); preview_layout.addLayout(h_test_mode)

        self.lbl_preview = QLabel(); self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: white; border: 1px solid #bdc3c7;")
        p_scroll = QScrollArea(); p_scroll.setWidgetResizable(True); p_scroll.setAlignment(Qt.AlignCenter)
        p_scroll.setWidget(self.lbl_preview); preview_layout.addWidget(p_scroll)
        
        self.splitter.addWidget(preview_widget); self.splitter.setSizes([450, 500])
        self.generate_preview()

    # ==========================================
    # LOGIC & GENERATORS
    # ==========================================
    def _collect_theme_from_widgets(self):
        tc = self._theme_from_config(self.config.setdefault("thermal_config", {}))
        tc.update({
            "printer_name": self.cmb_printer.currentText(),
            "store_name": self.inp_name.text(),
            "activity": self.inp_activity.text(),
            "address": self.inp_address.text(),
            "phone": self.inp_phone.text(),
            "mobile": self.inp_mobile.text(),
            "logo_path": "" if self.lbl_logo.text() == "Aucun logo" else self.lbl_logo.text(),
            "logo_settings": copy.deepcopy(self.logo_settings),
            "qr_link": self.inp_qr_link.text(),
            "qr_text": self.inp_qr_text.text(),
            "qr_size": self.spin_qr_size.value(),
            "qr_pos": self.cmb_qr_pos.currentText(),
            "show_barcode": self.chk_show_barcode.isChecked(),
            "barcode_height": self.spin_barcode_height.value(),
            "show_item_barcode": self.chk_show_item_barcode.isChecked(),
            "show_weight": self.chk_show_weight.isChecked(),
            "show_history": self.chk_show_history.isChecked(),
            "show_versement_rate": self.chk_show_versement_rate.isChecked(),
            "page_width": self.spin_w.value(),
            "center_x": self.spin_cx.value(),
            "margin": self.spin_m.value(),
            "font_title": self.spin_f_title.value(),
            "font_normal": self.spin_f_norm.value(),
        })
        return tc

    def _apply_theme_to_widgets(self, theme):
        self._loading_theme = True
        try:
            self._set_combo_text(self.cmb_printer, theme.get("printer_name", ""))
            self.inp_name.setText(theme.get("store_name", "Bijouterie GoldShop"))
            self.inp_activity.setText(theme.get("activity", "Vente_Reparation_Transformation"))
            self.inp_address.setText(theme.get("address", "CAMP CHEVALIER_JIJEL_ALGERIA"))
            self.inp_phone.setText(theme.get("phone", "0.30.51.49.84"))
            self.inp_mobile.setText(theme.get("mobile", "06.74.59.60.48"))
            self.lbl_logo.setText(theme.get("logo_path") or "Aucun logo")
            self.logo_settings = copy.deepcopy(theme.get("logo_settings", {'scale': 100, 'threshold': 127}))
            self.inp_qr_link.setText(theme.get("qr_link", ""))
            self.inp_qr_text.setText(theme.get("qr_text", "JEWELRY AMINE LAOUICI"))
            self.spin_qr_size.setValue(int(theme.get("qr_size", 70)))
            self._set_combo_text(self.cmb_qr_pos, theme.get("qr_pos", "Haut (À Gauche)"))
            self.chk_show_barcode.setChecked(bool(theme.get("show_barcode", True)))
            self.spin_barcode_height.setValue(int(theme.get("barcode_height", 50)))
            self.chk_show_item_barcode.setChecked(bool(theme.get("show_item_barcode", True)))
            self.chk_show_weight.setChecked(bool(theme.get("show_weight", True)))
            self.chk_show_history.setChecked(bool(theme.get("show_history", True)))
            self.chk_show_versement_rate.setChecked(bool(theme.get("show_versement_rate", False)))
            self.spin_w.setValue(int(theme.get("page_width", 576)))
            self.spin_cx.setValue(int(theme.get("center_x", 288)))
            self.spin_m.setValue(int(theme.get("margin", 20)))
            self.spin_f_title.setValue(int(theme.get("font_title", 32)))
            self.spin_f_norm.setValue(int(theme.get("font_normal", 22)))
        finally:
            self._loading_theme = False
        self.generate_preview()

    def _store_current_theme_from_widgets(self):
        if not hasattr(self, "cmb_printer"):
            return
        tc = self.config.setdefault("thermal_config", {})
        tc.setdefault("themes", {})[self.current_theme_name] = self._collect_theme_from_widgets()

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
        themes = self.config.setdefault("thermal_config", {}).setdefault("themes", {})
        if name not in themes:
            return
        self._store_current_theme_from_widgets()
        self.current_theme_name = name
        self.config["thermal_config"]["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._apply_theme_to_widgets(themes[name])

    def create_theme(self):
        name = self._theme_name_from_user("Nouveau theme", "Nom du nouveau theme:")
        if not name:
            return
        themes = self.config.setdefault("thermal_config", {}).setdefault("themes", {})
        if name in themes:
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return
        self._store_current_theme_from_widgets()
        themes[name] = self._collect_theme_from_widgets()
        self.current_theme_name = name
        self.config["thermal_config"]["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._refresh_theme_combo()

    def duplicate_theme(self):
        name = self._theme_name_from_user("Dupliquer theme", "Nom de la copie:", f"{self.current_theme_name} copie")
        if not name:
            return
        themes = self.config.setdefault("thermal_config", {}).setdefault("themes", {})
        if name in themes:
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return
        self._store_current_theme_from_widgets()
        themes[name] = copy.deepcopy(themes[self.current_theme_name])
        self.current_theme_name = name
        self.config["thermal_config"]["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._refresh_theme_combo()

    def rename_theme(self):
        old_name = self.current_theme_name
        name = self._theme_name_from_user("Renommer theme", "Nouveau nom:", old_name)
        if not name or name == old_name:
            return
        themes = self.config.setdefault("thermal_config", {}).setdefault("themes", {})
        if name in themes:
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return
        self._store_current_theme_from_widgets()
        themes[name] = themes.pop(old_name)
        self.current_theme_name = name
        self.config["thermal_config"]["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._refresh_theme_combo()

    def delete_theme(self):
        themes = self.config.setdefault("thermal_config", {}).setdefault("themes", {})
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
        self.config["thermal_config"]["active_theme"] = self.current_theme_name
        self._apply_theme_to_config(themes[self.current_theme_name])
        self._refresh_theme_combo()
        self._apply_theme_to_widgets(themes[self.current_theme_name])

    def browse_logo_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir le Logo", "", "Images (*.png *.jpg *.bmp *.jpeg)")
        if path:
            self.lbl_logo.setText(path)
            self.logo_settings = {'scale': 100, 'threshold': 127}
            self.generate_preview()

    def clear_logo(self):
        self.lbl_logo.setText("Aucun logo")
        self.generate_preview()

    def open_logo_dialog(self):
        path = self.lbl_logo.text()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Erreur", "Veuillez d'abord choisir un logo en cliquant sur 'Parcourir'.")
            return
        dialog = LogoSettingsDialog(path, self.logo_settings, self)
        if dialog.exec() == QDialog.Accepted:
            self.logo_settings = dialog.get_final_settings()
            self.generate_preview()

    def generate_qr_image(self, link, size):
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=10, border=1)
            qr.add_data(link); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
            qimg = QImage(img.tobytes("raw", "RGBA"), img.size[0], img.size[1], QImage.Format_RGBA8888)
            return qimg.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except: return None

    def generate_barcode_image(self, data, width, height, with_text=False):
        try:
            import barcode; from barcode.writer import ImageWriter
            CODE = barcode.get_barcode_class('code128')
            writer = ImageWriter()
            code = CODE(str(data), writer=writer)
            options = {'module_width': 0.3, 'module_height': 8.0, 'font_size': 0 if not with_text else 6, 'text_distance': 1.0, 'quiet_zone': 1.0}
            fp = io.BytesIO()
            code.write(fp, options); fp.seek(0)
            return QImage.fromData(fp.read()).scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        except: return None

    # ==========================================
    # CORE DRAWING ENGINE
    # ==========================================
    def draw_receipt_content(self, painter, width):
        cx = self.spin_cx.value(); m = self.spin_m.value()
        ls = 6; y = 20 
        f_title = self.spin_f_title.value(); f_norm = self.spin_f_norm.value(); f_small = max(12, f_norm - 6)

        def draw_text_absolute(text, x, y_abs, size, bold=False, align_right=False, limit=None, italic=False):
            font = QFont("Arial"); font.setPixelSize(size); font.setBold(bold); font.setItalic(italic); painter.setFont(font)
            fm = painter.fontMetrics(); tw = fm.horizontalAdvance(str(text))
            if align_right and limit: x = x + limit - tw
            painter.drawText(x, y_abs + fm.ascent(), str(text))
            return fm.height()

        def draw_text_center(text, size, bold=False):
            nonlocal y
            font = QFont("Arial"); font.setPixelSize(size); font.setBold(bold); painter.setFont(font)
            fm = painter.fontMetrics()
            for line in str(text).split('\n'):
                tw = fm.horizontalAdvance(line)
                painter.drawText(cx - (tw // 2), y + fm.ascent(), line)
                y += fm.height() + ls

        def wrap_text_to_lines(text, max_width, font):
            painter.setFont(font)
            fm = painter.fontMetrics()
            words = str(text).split(' ')
            lines = []; current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                if fm.horizontalAdvance(test_line) <= max_width: current_line = test_line
                else:
                    if current_line: lines.append(current_line)
                    current_line = word
            if current_line: lines.append(current_line)
            return lines

        def draw_table(headers, ratios, rows):
            nonlocal y
            table_w = width - (2 * m)
            cols = [int(table_w * r) for r in ratios]
            x_c = [m]
            for c in cols: x_c.append(x_c[-1] + c)
            
            painter.setPen(QPen(Qt.black, 1, Qt.SolidLine))
            painter.drawLine(m, y, width - m, y) 
            
            font_header = QFont("Arial"); font_header.setPixelSize(f_small); font_header.setBold(True)
            header_h = f_small + 10
            for i, h in enumerate(headers): 
                painter.setFont(font_header)
                painter.drawText(QRect(x_c[i] + 4, y + 2, cols[i] - 8, header_h), Qt.AlignLeft | Qt.AlignVCenter, h)
            y += header_h; painter.drawLine(m, y, width - m, y)

            start_y = y 

            font_cell = QFont("Arial"); font_cell.setPixelSize(f_small); font_cell.setBold(False)
            font_note = QFont("Arial"); font_note.setPixelSize(f_small - 2); font_note.setItalic(True)

            for row in rows:
                cell_lines = []
                for i in range(len(headers)):
                    val = row[i] if i < len(row) else ""
                    lines = wrap_text_to_lines(str(val), cols[i] - 8, font_cell)
                    cell_lines.append(lines)
                
                max_lines = max([len(lines) for lines in cell_lines]) if cell_lines else 1
                line_height = f_small + 4
                base_h = (max_lines * line_height) + 10
                
                show_barcode = self.chk_show_item_barcode.isChecked()
                if show_barcode: base_h = max(base_h, 45) 
                
                for i in range(len(headers)):
                    val = row[i] if i < len(row) else ""
                    if i == 0 and show_barcode:
                        b_w = cols[i] - 8; b_h = base_h - 10 
                        b_img = self.generate_barcode_image(str(val), b_w, b_h)
                        if b_img: painter.drawImage(x_c[i] + 4, y + 5, b_img)
                    else:
                        painter.setFont(font_cell); fm = painter.fontMetrics(); text_y = y + 5
                        for line in cell_lines[i]:
                            painter.drawText(x_c[i] + 4, text_y + fm.ascent(), line); text_y += line_height
                
                y += base_h
                
                note_idx = len(headers)
                if len(row) > note_idx and row[note_idx]:
                    note_text = str(row[note_idx]); note_w = cols[1] - 8 
                    note_lines = wrap_text_to_lines(note_text, note_w, font_note)
                    note_h = (len(note_lines) * (f_small + 2)) + 5
                    painter.setFont(font_note); fm = painter.fontMetrics(); text_y = y
                    for line in note_lines:
                        painter.drawText(x_c[1] + 4, text_y + fm.ascent(), line); text_y += f_small + 2
                    y += note_h

                painter.drawLine(m, y, width - m, y) 

            for x_pos in x_c: painter.drawLine(x_pos, start_y, x_pos, y)
            y += 10

        # --- 1. HEADER & LOGO ---
        logo_path = self.lbl_logo.text()
        if os.path.exists(logo_path):
            img = QImage(logo_path)
            scale = self.logo_settings.get('scale', 100) / 100.0; thresh = self.logo_settings.get('threshold', 127)
            img = img.scaledToWidth(int(img.width() * scale), Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
            for iy in range(img.height()):
                for ix in range(img.width()):
                    val = img.pixelColor(ix, iy).red()
                    img.setPixelColor(ix, iy, QColor(0,0,0) if val <= thresh else QColor(255,255,255))
            painter.drawImage(cx - (img.width() // 2), y, img); y += img.height() + 5

        draw_text_center(self.inp_name.text(), f_title, bold=True)

        # --- 2. QR CODE & STORE INFO ---
        link = self.inp_qr_link.text().strip()
        qr_pos = str(self.cmb_qr_pos.currentText() or "")
        if link and qr_pos not in {"Désactivé", "DÃ©sactivÃ©", "DÃ‰SACTIVÃ‰"}:
            qr_size = self.spin_qr_size.value()
            qimg = self.generate_qr_image(link, qr_size)
            if qimg: painter.drawImage(m, y, qimg)
            else: painter.fillRect(m, y, qr_size, qr_size, Qt.lightGray)
            
            draw_text_absolute(self.inp_qr_text.text(), m + qr_size + 10, y + (qr_size//2) - (f_norm//2), f_norm, bold=True)
            y += qr_size + 10
        else:
            y += 10

        draw_text_center(self.inp_activity.text(), f_small)
        draw_text_center(self.inp_address.text(), f_small)
        y += 5
        draw_text_absolute(f"TEL : {self.inp_phone.text()}", m, y, f_small)
        draw_text_absolute(f"Mobile : {self.inp_mobile.text()}", cx, y, f_small)
        y += f_small + 15

        # --- 3. BARCODE ---
        test_mode = self.cmb_test_mode.currentText()
        is_facture = "Facture" in test_mode
        is_versement = "Versement" in test_mode
        inv_num = "F-000006" if is_facture else ("V-000016" if is_versement else "TR-20260416")
        facture_reference = "F-000006" if is_versement else ""
        
        if self.chk_show_barcode.isChecked():
            bw = int(width * 0.85); bh = self.spin_barcode_height.value()
            b_img = self.generate_barcode_image(inv_num, bw, bh)
            if b_img: 
                painter.drawImage(cx - (bw // 2), y, b_img)
                y += bh + 5
                draw_text_center(str(inv_num), f_small, bold=True)
                y += 5
            else: 
                painter.fillRect(cx - (bw // 2), y, bw, bh, Qt.lightGray)
                y += bh + 5
            
        doc_type = "FACTURE" if is_facture else ("BON DE VERSEMENT" if is_versement else "Transaction Rapide")
        draw_text_center(doc_type, f_norm, bold=True); y += 15

        # --- 4. DOC INFO ---
        if is_versement:
            draw_text_absolute(f"Facture N° : {facture_reference}", m, y, f_small, bold=True)
            y += f_small + 5
            if not self.chk_show_barcode.isChecked():
                draw_text_absolute(f"Versement N° : {inv_num}", m, y, f_small, bold=True)
        elif is_facture:
            draw_text_absolute(f"Facture N° : {inv_num}", m, y, f_small, bold=True)
        else:
            draw_text_absolute(f"Ticket N° : {inv_num}", m, y, f_small, bold=True)
            
        import datetime
        date_val = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        date_only = str(date_val).split(' ')[0]
        time_only = str(date_val).split(' ')[1][:5]
        
        draw_text_absolute(date_only, width - m - 100, y, f_small, align_right=True, limit=100); y += f_small + 5
        if time_only: draw_text_absolute(time_only, width - m - 100, y, f_small, align_right=True, limit=100); y += f_small + 15

        draw_text_absolute("Client : Islam", m, y, f_norm, bold=True); y += f_norm + 15

        # --- 5. TABLE & CONTENT ---
        totals_x = cx - 20; totals_w = (width - m) - totals_x

        if test_mode == "Facture Détaillée (Standard)":
            headers = ["Code", "Désignation", "Poids", "Montant"]
            ratios = [0.18, 0.40, 0.17, 0.25] 
            rows = [
                ["0017977", "Chaine IMP 7", "2,75 Gr", "78 375,00 DA", "Importation Chick Or 18 Karats Garantie - Spécial"],
                ["0017980", "Bague Or Super Longue Nom Pour Tester", "4,10 Gr", "45 000,00 DA", "Cette note ne sortira jamais de la zone allouée."]
            ]
            draw_table(headers, ratios, rows)
            draw_text_absolute(f"Nombre des articles :       {len(rows)}", m, y, f_small, bold=True); y += 20
            
            draw_text_absolute("Total TTC :", totals_x, y, f_norm)
            draw_text_absolute("123 375,00 DA", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 10
            draw_text_absolute("Remise :", totals_x, y, f_norm); y += f_norm + 10
            draw_text_absolute("Net à payer :", totals_x, y, f_norm)
            draw_text_absolute("123 375,00 DA", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 25

            if self.chk_show_weight.isChecked():
                painter.drawLine(m, y, width - m, y); y += 10
                draw_text_center("Bilan Poids / ميزان الوزن", f_norm, bold=True)
                
                draw_text_absolute("Poids Payé (الوزن المدفوع):", m, y, f_norm)
                draw_text_absolute("2.00 Gr", m, y, f_norm, align_right=True, limit=width-(2*m)); y += f_norm + 5
                
                draw_text_absolute("Poids Reste (الوزن الباقي):", m, y, f_norm)
                draw_text_absolute("4.85 Gr", m, y, f_norm, align_right=True, limit=width-(2*m)); y += f_norm + 15
                
            if self.chk_show_history.isChecked():
                painter.drawLine(m, y, width - m, y); y += 10
                draw_text_center("Historique des Paiements", f_norm, bold=True)
                draw_text_absolute("10/04/2026", m, y, f_small)
                draw_text_absolute("50 000,00 DA", totals_x, y, f_small, align_right=True, limit=totals_w); y += f_small + 5
                draw_text_absolute("16/04/2026", m, y, f_small)
                draw_text_absolute("73 375,00 DA", totals_x, y, f_small, align_right=True, limit=totals_w); y += f_small + 15

            draw_text_absolute("Arrêter la présente facture à la somme de:", m, y, f_small-2); y += f_small + 5
            draw_text_center("cent vingt-trois mille trois cent soixante-quinze DA", f_small)

        elif test_mode == "Bon de Versement":
            # 🟢 ديناميكية: الأعمدة تتغير فوراً حسب التحكم
            v_headers = ["Date", "Opération", "Poids", "Montant"]
            v_ratios = [0.25, 0.35, 0.20, 0.20]
            
            if self.chk_show_versement_rate.isChecked():
                v_headers.insert(3, "Prix/g")
                v_ratios = [0.20, 0.28, 0.14, 0.16, 0.22]
                
            v_rows = [
                ["16/04/2026", "Versement sur produit", "+5.000 Gr", "50 000,00 DA"],
                ["20/04/2026", "Versement sur produit", "+3.500 Gr", "35 000,00 DA"]
            ]
            
            # إضافة سعر الغرام ديناميكياً للمعاينة فقط عند التفعيل
            if self.chk_show_versement_rate.isChecked():
                v_rows[0].insert(3, "10 000")
                v_rows[1].insert(3, "10 000")
                
            draw_table(v_headers, v_ratios, v_rows)
            
            # 🟢 ملخص الزبون المباشر (بدون تفاصيل المنتجات)
            painter.drawLine(m, y, width - m, y); y += 10
            
            draw_text_absolute("Total Payé :", totals_x, y, f_norm)
            draw_text_absolute("85 000,00 DA", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 10
            
            draw_text_absolute("Poids Acquis :", totals_x, y, f_norm)
            draw_text_absolute("8.500 Gr", totals_x, y, f_norm, align_right=True, limit=totals_w); y += f_norm + 10
            
            draw_text_absolute("Reste Poids :", totals_x, y, f_norm, bold=True)
            draw_text_absolute("11.500 Gr", totals_x, y, f_norm, bold=True, align_right=True, limit=totals_w); y += f_norm + 15

        elif test_mode == "Transaction Rapide":
            draw_text_absolute("Opération:", m, y, f_norm); draw_text_absolute("Achat Or (Casse)", m+100, y, f_norm, bold=True); y += f_norm + 5
            draw_text_absolute("Article:", m, y, f_norm); draw_text_absolute("Gourmette 18K", m+100, y, f_norm, bold=True, limit=200); y += f_norm + 5
            draw_text_absolute("Poids:", m, y, f_norm); draw_text_absolute("12.50 Gr", m+100, y, f_norm, bold=True); y += f_norm + 15
            draw_text_center("*** Paiement Comptant ***", f_norm, bold=True)

        y += 30
        draw_text_absolute("C: 1", width - m - 30, y, f_small, bold=True)
        return y + 20

    def generate_preview(self):
        if getattr(self, "_loading_theme", False):
            return
        w = self.spin_w.value()
        pixmap = QPixmap(w, 2000); pixmap.fill(Qt.white)
        painter = QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
        final_y = self.draw_receipt_content(painter, w)
        painter.end()
        cropped = pixmap.copy(0, 0, w, final_y)
        self.lbl_preview.setPixmap(cropped); self.lbl_preview.setFixedSize(cropped.size())

    def execute_real_print(self):
        printer_name = self.cmb_printer.currentText()
        if not printer_name:
            QMessageBox.warning(self, "Erreur", "Sélectionnez une imprimante.")
            return

        printer = QPrinter(QPrinter.PrinterResolution)
        printer.setPrinterName(printer_name)
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Erreur", f"Impossible d'imprimer sur {printer_name}.")
            return
            
        real_w = printer.pageRect(QPrinter.DevicePixel).width()
        log_w = self.spin_w.value()
        if real_w > 0:
            scale_f = real_w / log_w
            painter.scale(scale_f, scale_f)
            
        self.draw_receipt_content(painter, log_w)
        painter.end()

    def update_config_dict(self):
        tc = self.config.setdefault("thermal_config", {})
        tc["printer_name"] = self.cmb_printer.currentText()
        tc["store_name"] = self.inp_name.text()
        tc["activity"] = self.inp_activity.text()
        tc["address"] = self.inp_address.text()
        tc["phone"] = self.inp_phone.text()
        tc["mobile"] = self.inp_mobile.text()
        
        logo_path = self.lbl_logo.text()
        tc["logo_path"] = logo_path if logo_path != "Aucun logo" else ""
        tc["logo_settings"] = self.logo_settings
        
        tc["qr_link"] = self.inp_qr_link.text()
        tc["qr_text"] = self.inp_qr_text.text()
        tc["qr_size"] = self.spin_qr_size.value()
        tc["qr_pos"] = self.cmb_qr_pos.currentText()
        
        tc["show_barcode"] = self.chk_show_barcode.isChecked()
        tc["barcode_height"] = self.spin_barcode_height.value()
        tc["show_item_barcode"] = self.chk_show_item_barcode.isChecked()
        tc["show_weight"] = self.chk_show_weight.isChecked()
        tc["show_history"] = self.chk_show_history.isChecked()
        tc["show_versement_rate"] = self.chk_show_versement_rate.isChecked()
        
        tc["page_width"] = self.spin_w.value()
        tc["center_x"] = self.spin_cx.value()
        tc["margin"] = self.spin_m.value()
        tc["font_title"] = self.spin_f_title.value()
        tc["font_normal"] = self.spin_f_norm.value()
        tc["active_theme"] = self.current_theme_name
        tc.setdefault("themes", {})[self.current_theme_name] = self._collect_theme_from_widgets()

    def save_config_local(self):
        self.update_config_dict() 
        self.save_callback()