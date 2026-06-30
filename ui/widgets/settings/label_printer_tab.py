# ui/widgets/settings/label_printer_tab.py

import copy
import io
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QCheckBox, 
    QLabel, QDoubleSpinBox, QSpinBox, QScrollArea, QComboBox, QPushButton,
    QMessageBox, QLineEdit, QInputDialog
)
from PySide6.QtPrintSupport import QPrinterInfo 
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, QTimer

# Drawing, Barcode, and Printing libraries
from PIL import Image, ImageDraw, ImageFont, ImageOps
import barcode
from barcode.writer import ImageWriter
import win32print

class LabelPrinterSettingsTab(QWidget):
    def __init__(self, label_config, save_callback):
        super().__init__()
        self.cfg = label_config 
        self.save_callback = save_callback
        self.DPI_MULTIPLIER = 8 # 203 DPI (8 dots per mm)
        
        self._ensure_config_defaults()
        
        # Timer for updating the preview without lagging the UI
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200) 
        self.preview_timer.timeout.connect(self.generate_preview)

        self.init_ui()
        self.connect_signals_for_preview()
        self.generate_preview() 

    def _ensure_config_defaults(self):
        """Ensures all new keys exist in the configuration to prevent KeyErrors."""
        self.cfg.setdefault("server", {"port": 38476})
        self.cfg.setdefault("printer_name", "")
        self.cfg.setdefault("label", {"width_mm": 80, "height_mm": 10, "gap_mm": 3})
        self.cfg.setdefault("print_area", {"x_pos_mm": 0, "y_pos_mm": 0})
        self.cfg.setdefault("elements", {})
        self._ensure_theme_defaults(self.cfg)

        active_theme = str(self.cfg.get("active_theme") or "Default").strip() or "Default"
        themes = self.cfg.get("themes")
        if not isinstance(themes, dict):
            themes = {}
            self.cfg["themes"] = themes

        if not themes:
            themes[active_theme] = self._theme_from_config(self.cfg)
        else:
            for name in list(themes.keys()):
                if not isinstance(themes[name], dict):
                    del themes[name]
                    continue
                self._ensure_theme_defaults(themes[name])

        if active_theme not in themes:
            themes[active_theme] = self._theme_from_config(self.cfg)

        self.current_theme_name = active_theme
        self.cfg["active_theme"] = active_theme
        self._apply_theme_to_config(themes[active_theme])
        self._loading_theme = False

    def _element_defaults(self):
        return {
            "product_name": {"show": True, "center_x_mm": 20, "y_pos_mm": 3, "font_size": 12, "font_family": "arial.ttf"},
            "category": {"show": True, "center_x_mm": 10, "y_pos_mm": 9, "font_size": 10, "font_family": "arial.ttf"},
            "price": {"show": True, "center_x_mm": 20, "y_pos_mm": 8, "font_size": 14, "font_family": "arial.ttf"},
            "static_text": {"show": True, "text": "Moussi", "center_x_mm": 20, "y_pos_mm": 1, "font_size": 10, "font_family": "arial.ttf"},
            "model_name": {"show": True, "center_x_mm": 10, "y_pos_mm": 12, "font_size": 10, "font_family": "arial.ttf"},
            "metal_type": {"show": True, "center_x_mm": 30, "y_pos_mm": 12, "font_size": 10, "font_family": "arial.ttf"},
            "barcode": {"show": True, "center_x_mm": 20, "y_pos_mm": 16, "module_width_mm": 0.2, "height_mm": 6},
            "barcode_text": {"show": True, "center_x_mm": 20, "y_pos_mm": 22, "font_size": 10, "font_family": "arial.ttf"},
            "weight": {"show": True, "center_x_mm": 20, "y_pos_mm": 15, "font_size": 10, "font_family": "arial.ttf", "prefix": "Poids: ", "suffix": " g", "decimals": 2}
        }

    def _ensure_theme_defaults(self, theme):
        theme.setdefault("printer_name", "")
        theme.setdefault("label", {})
        theme["label"].setdefault("width_mm", 80)
        theme["label"].setdefault("height_mm", 10)
        theme["label"].setdefault("gap_mm", 3)
        theme.setdefault("print_area", {})
        theme["print_area"].setdefault("x_pos_mm", 0)
        theme["print_area"].setdefault("y_pos_mm", 0)
        theme.setdefault("elements", {})

        for key, defaults in self._element_defaults().items():
            element = theme["elements"].setdefault(key, {})
            for sub_key, sub_val in defaults.items():
                element.setdefault(sub_key, sub_val)

    def _theme_from_config(self, source):
        theme = {
            "printer_name": source.get("printer_name", ""),
            "label": copy.deepcopy(source.get("label", {})),
            "print_area": copy.deepcopy(source.get("print_area", {})),
            "elements": copy.deepcopy(source.get("elements", {})),
        }
        self._ensure_theme_defaults(theme)
        return theme

    def _apply_theme_to_config(self, theme):
        self._ensure_theme_defaults(theme)
        for key in ("printer_name", "label", "print_area", "elements"):
            self.cfg[key] = copy.deepcopy(theme[key])

    def _create_double_spinbox(self, value, min_v=-100, max_v=200, step=0.5, dec=2):
        sb = QDoubleSpinBox()
        sb.setRange(min_v, max_v)
        sb.setSingleStep(step)
        sb.setDecimals(dec)
        sb.setValue(float(value))
        return sb

    def _create_spinbox(self, value, min_v=0, max_v=100):
        sb = QSpinBox()
        sb.setRange(min_v, max_v)
        sb.setValue(int(value))
        return sb
        
    def _create_font_combobox(self, current_font):
        cmb = QComboBox()
        # Common fonts that are usually available on Windows systems
        fonts = ["arial.ttf", "tahoma.ttf", "times.ttf", "cour.ttf", "calibri.ttf", "segoeui.ttf", "comic.ttf"]
        cmb.addItems(fonts)
        if current_font in fonts:
            cmb.setCurrentText(current_font)
        else:
            cmb.setCurrentText("arial.ttf")
        return cmb

    def get_system_printers(self):
        return QPrinterInfo.availablePrinterNames()

    def _set_combo_text(self, combo, text):
        text = str(text or "")
        if text and combo.findText(text) < 0:
            combo.addItem(text)
        combo.setCurrentText(text)

    def _theme_names(self):
        return list(self.cfg.get("themes", {}).keys())

    def _refresh_theme_combo(self):
        if not hasattr(self, "cmb_theme"):
            return

        self.cmb_theme.blockSignals(True)
        self.cmb_theme.clear()
        self.cmb_theme.addItems(self._theme_names())
        self.cmb_theme.setCurrentText(self.current_theme_name)
        self.cmb_theme.blockSignals(False)

    def init_ui(self):
        # التخطيط الرئيسي: عمودي
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 1. قسم المعاينة (Aperçu) - الجزء العلوي
        preview_panel = QGroupBox("👁️ Aperçu en direct")
        preview_layout = QVBoxLayout(preview_panel)
        self.lbl_preview = QLabel("Chargement...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background-color: #ffffff; border: 2px dashed #bdc3c7; border-radius: 8px;")
        preview_layout.addWidget(self.lbl_preview)
        main_layout.addWidget(preview_panel, 1)

        # 2. منطقة الإعدادات - الجزء السفلي (مقسمة يمين ويسار)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_content = QWidget()
        settings_split_layout = QHBoxLayout(scroll_content)

        # --- العمود الأيسر: الإعدادات العامة ---
        left_column = QVBoxLayout()

        grp_theme = QGroupBox("Themes d'etiquette")
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
        left_column.addWidget(grp_theme)
        
        # الطابعة والقياسات والإزاحة
        grp_gen = QGroupBox("🖨️ Configuration Générale")
        f_gen = QFormLayout(grp_gen)
        self.cmb_label_printer = QComboBox()
        self.cmb_label_printer.addItem("")
        self.cmb_label_printer.addItems(self.get_system_printers())
        self._set_combo_text(self.cmb_label_printer, self.cfg.get("printer_name", ""))
        
        self.lbl_w = self._create_double_spinbox(self.cfg["label"]["width_mm"])
        self.lbl_h = self._create_double_spinbox(self.cfg["label"]["height_mm"])
        self.lbl_gap = self._create_double_spinbox(self.cfg["label"]["gap_mm"])
        self.off_x = self._create_double_spinbox(self.cfg["print_area"]["x_pos_mm"])
        self.off_y = self._create_double_spinbox(self.cfg["print_area"]["y_pos_mm"])
        
        f_gen.addRow("Imprimante:", self.cmb_label_printer)
        f_gen.addRow("Largeur (mm):", self.lbl_w)
        f_gen.addRow("Hauteur (mm):", self.lbl_h)
        f_gen.addRow("Gap (mm):", self.lbl_gap)
        f_gen.addRow("Offset X:", self.off_x)
        f_gen.addRow("Offset Y:", self.off_y)
        left_column.addWidget(grp_gen)
        left_column.addStretch()
        settings_split_layout.addLayout(left_column, 1)

        # --- العمود الأيمن: إعدادات العناصر والخطوط (تعريف صريح 100%) ---
        right_column = QVBoxLayout()
        grp_el = QGroupBox("✏️ Personnalisation des Éléments")
        v_el = QVBoxLayout(grp_el)

        def make_row(key, label):
            e = self.cfg["elements"].get(key, {})
            row_v = QVBoxLayout()
            row_h1 = QHBoxLayout()
            chk = QCheckBox(label)
            chk.setChecked(e.get("show", True))
            cx = self._create_double_spinbox(e.get("center_x_mm", 20))
            yp = self._create_double_spinbox(e.get("y_pos_mm", 5))
            row_h1.addWidget(chk, 2); row_h1.addWidget(QLabel("X:")); row_h1.addWidget(cx, 1)
            row_h1.addWidget(QLabel("Y:")); row_h1.addWidget(yp, 1)
            
            row_h2 = QHBoxLayout()
            fs = self._create_spinbox(e.get("font_size", 10), 1, 50)
            ff = self._create_font_combobox(e.get("font_family", "arial.ttf"))
            row_h2.addWidget(QLabel("Taille:")); row_h2.addWidget(fs, 1)
            row_h2.addWidget(QLabel("Font:")); row_h2.addWidget(ff, 2)
            
            row_v.addLayout(row_h1); row_v.addLayout(row_h2)
            v_el.addLayout(row_v)
            v_el.addWidget(QLabel("<hr>"))
            return chk, cx, yp, fs, ff

        # تعريف كل عنصر لضمان وجود الـ Attributes المطلوبة في دالة الرسم
        self.chk_static_show, self.static_cx, self.static_y, self.static_font, self.static_font_family = make_row("static_text", "En-tête (Magasin)")
        self.static_text_input = QLineEdit(self.cfg["elements"]["static_text"].get("text", "Moussi"))
        v_el.insertWidget(v_el.count()-1, self.static_text_input)

        self.chk_name_show, self.name_cx, self.name_y, self.name_font, self.name_font_family = make_row("product_name", "Produit")
        self.chk_category_show, self.category_cx, self.category_y, self.category_font, self.category_font_family = make_row("category", "Catégorie")
        self.chk_model_show, self.model_cx, self.model_y, self.model_font, self.model_font_family = make_row("model_name", "Modèle")
        self.chk_metal_show, self.metal_cx, self.metal_y, self.metal_font, self.metal_font_family = make_row("metal_type", "Métal")
        self.chk_price_show, self.price_cx, self.price_y, self.price_font, self.price_font_family = make_row("price", "Prix")

        # عنصر الوزن (مع إصلاح الـ weight_decimals)
        self.chk_weight_show, self.weight_cx, self.weight_y, self.weight_font, self.weight_font_family = make_row("weight", "Poids")
        ew = self.cfg["elements"]["weight"]
        self.weight_prefix = QLineEdit(ew.get("prefix", "Poids: "))
        self.weight_suffix = QLineEdit(ew.get("suffix", " g"))
        self.weight_decimals = self._create_spinbox(ew.get("decimals", 2), 0, 5) # 🎯 هذا هو المفقود
        w_lay = QHBoxLayout()
        w_lay.addWidget(QLabel("Préf:")); w_lay.addWidget(self.weight_prefix)
        w_lay.addWidget(QLabel("Suff:")); w_lay.addWidget(self.weight_suffix)
        w_lay.addWidget(QLabel("Dec:")); w_lay.addWidget(self.weight_decimals)
        v_el.insertLayout(v_el.count()-1, w_lay)

        # الباركود (الخطوط)
        eb = self.cfg["elements"]["barcode"]
        grp_bc = QGroupBox("📊 Code-barres (Barres)")
        f_bc = QFormLayout(grp_bc)
        self.chk_bc_show = QCheckBox("Afficher les lignes")
        self.chk_bc_show.setChecked(eb["show"])
        self.bc_cx = self._create_double_spinbox(eb["center_x_mm"])
        self.bc_y = self._create_double_spinbox(eb["y_pos_mm"])
        self.bc_w = self._create_double_spinbox(eb["module_width_mm"], 0.01, 2.0, 0.01, 3)
        self.bc_h = self._create_double_spinbox(eb["height_mm"])
        f_bc.addRow(self.chk_bc_show)
        f_bc.addRow("X:", self.bc_cx); f_bc.addRow("Y:", self.bc_y)
        f_bc.addRow("Largeur Mod:", self.bc_w); f_bc.addRow("Hauteur:", self.bc_h)
        v_el.addWidget(grp_bc)

        # الباركود (النص)
        ebt = self.cfg["elements"]["barcode_text"]
        grp_bct = QGroupBox("🔢 Code-barres (Texte)")
        f_bct = QFormLayout(grp_bct)
        self.chk_bc_text_show = QCheckBox("Afficher numéros")
        self.chk_bc_text_show.setChecked(ebt["show"])
        self.bc_text_cx = self._create_double_spinbox(ebt["center_x_mm"])
        self.bc_text_y = self._create_double_spinbox(ebt["y_pos_mm"])
        self.bc_text_font = self._create_spinbox(ebt["font_size"], 1, 50)
        self.bc_text_font_family = self._create_font_combobox(ebt["font_family"])
        f_bct.addRow(self.chk_bc_text_show)
        f_bct.addRow("X:", self.bc_text_cx); f_bct.addRow("Y:", self.bc_text_y)
        f_bct.addRow("Taille:", self.bc_text_font); f_bct.addRow("Font:", self.bc_text_font_family)
        v_el.addWidget(grp_bct)

        right_column.addWidget(grp_el)
        settings_split_layout.addLayout(right_column, 2)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 2)

        # أزرار الحفظ والطباعة
        btns = QHBoxLayout()
        self.btn_save = QPushButton("💾 Enregistrer")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_save.clicked.connect(self.save_callback)
        self.btn_test = QPushButton("🖨️ Imprimer Test")
        self.btn_test.setMinimumHeight(40)
        self.btn_test.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_test.clicked.connect(self.print_test_label)
        btns.addWidget(self.btn_save); btns.addWidget(self.btn_test)
        main_layout.addLayout(btns)

    def connect_signals_for_preview(self):
        for widget in self.findChildren(QDoubleSpinBox) + self.findChildren(QSpinBox):
            widget.valueChanged.connect(self.trigger_preview)
        for widget in self.findChildren(QCheckBox):
            widget.stateChanged.connect(self.trigger_preview)
        for widget in self.findChildren(QComboBox):
            widget.currentTextChanged.connect(self.trigger_preview)
        self.static_text_input.textChanged.connect(self.trigger_preview)
        self.weight_prefix.textChanged.connect(self.trigger_preview)
        self.weight_suffix.textChanged.connect(self.trigger_preview)

    def _text_element_from_widgets(self, chk, cx, yp, fs, ff):
        return {
            "show": chk.isChecked(),
            "center_x_mm": cx.value(),
            "y_pos_mm": yp.value(),
            "font_size": fs.value(),
            "font_family": ff.currentText(),
        }

    def _collect_theme_from_widgets(self):
        theme = {
            "printer_name": self.cmb_label_printer.currentText(),
            "label": {
                "width_mm": self.lbl_w.value(),
                "height_mm": self.lbl_h.value(),
                "gap_mm": self.lbl_gap.value(),
            },
            "print_area": {
                "x_pos_mm": self.off_x.value(),
                "y_pos_mm": self.off_y.value(),
            },
            "elements": {
                "static_text": self._text_element_from_widgets(
                    self.chk_static_show,
                    self.static_cx,
                    self.static_y,
                    self.static_font,
                    self.static_font_family,
                ),
                "product_name": self._text_element_from_widgets(
                    self.chk_name_show,
                    self.name_cx,
                    self.name_y,
                    self.name_font,
                    self.name_font_family,
                ),
                "category": self._text_element_from_widgets(
                    self.chk_category_show,
                    self.category_cx,
                    self.category_y,
                    self.category_font,
                    self.category_font_family,
                ),
                "model_name": self._text_element_from_widgets(
                    self.chk_model_show,
                    self.model_cx,
                    self.model_y,
                    self.model_font,
                    self.model_font_family,
                ),
                "metal_type": self._text_element_from_widgets(
                    self.chk_metal_show,
                    self.metal_cx,
                    self.metal_y,
                    self.metal_font,
                    self.metal_font_family,
                ),
                "price": self._text_element_from_widgets(
                    self.chk_price_show,
                    self.price_cx,
                    self.price_y,
                    self.price_font,
                    self.price_font_family,
                ),
                "barcode": {
                    "show": self.chk_bc_show.isChecked(),
                    "center_x_mm": self.bc_cx.value(),
                    "y_pos_mm": self.bc_y.value(),
                    "module_width_mm": self.bc_w.value(),
                    "height_mm": self.bc_h.value(),
                },
                "barcode_text": {
                    "show": self.chk_bc_text_show.isChecked(),
                    "center_x_mm": self.bc_text_cx.value(),
                    "y_pos_mm": self.bc_text_y.value(),
                    "font_size": self.bc_text_font.value(),
                    "font_family": self.bc_text_font_family.currentText(),
                },
                "weight": self._text_element_from_widgets(
                    self.chk_weight_show,
                    self.weight_cx,
                    self.weight_y,
                    self.weight_font,
                    self.weight_font_family,
                ),
            },
        }
        theme["elements"]["static_text"]["text"] = self.static_text_input.text()
        theme["elements"]["weight"]["prefix"] = self.weight_prefix.text()
        theme["elements"]["weight"]["suffix"] = self.weight_suffix.text()
        theme["elements"]["weight"]["decimals"] = self.weight_decimals.value()
        self._ensure_theme_defaults(theme)
        return theme

    def _set_text_element_widgets(self, element, chk, cx, yp, fs, ff):
        chk.setChecked(bool(element.get("show", True)))
        cx.setValue(float(element.get("center_x_mm", 20)))
        yp.setValue(float(element.get("y_pos_mm", 5)))
        fs.setValue(int(element.get("font_size", 10)))
        self._set_combo_text(ff, element.get("font_family", "arial.ttf"))

    def _apply_theme_to_widgets(self, theme):
        self._ensure_theme_defaults(theme)
        self._loading_theme = True
        try:
            self._set_combo_text(self.cmb_label_printer, theme.get("printer_name", ""))
            self.lbl_w.setValue(float(theme["label"].get("width_mm", 80)))
            self.lbl_h.setValue(float(theme["label"].get("height_mm", 10)))
            self.lbl_gap.setValue(float(theme["label"].get("gap_mm", 3)))
            self.off_x.setValue(float(theme["print_area"].get("x_pos_mm", 0)))
            self.off_y.setValue(float(theme["print_area"].get("y_pos_mm", 0)))

            elements = theme["elements"]
            self._set_text_element_widgets(elements["static_text"], self.chk_static_show, self.static_cx, self.static_y, self.static_font, self.static_font_family)
            self.static_text_input.setText(elements["static_text"].get("text", "Moussi"))
            self._set_text_element_widgets(elements["product_name"], self.chk_name_show, self.name_cx, self.name_y, self.name_font, self.name_font_family)
            self._set_text_element_widgets(elements["category"], self.chk_category_show, self.category_cx, self.category_y, self.category_font, self.category_font_family)
            self._set_text_element_widgets(elements["model_name"], self.chk_model_show, self.model_cx, self.model_y, self.model_font, self.model_font_family)
            self._set_text_element_widgets(elements["metal_type"], self.chk_metal_show, self.metal_cx, self.metal_y, self.metal_font, self.metal_font_family)
            self._set_text_element_widgets(elements["price"], self.chk_price_show, self.price_cx, self.price_y, self.price_font, self.price_font_family)
            self._set_text_element_widgets(elements["weight"], self.chk_weight_show, self.weight_cx, self.weight_y, self.weight_font, self.weight_font_family)
            self.weight_prefix.setText(elements["weight"].get("prefix", "Poids: "))
            self.weight_suffix.setText(elements["weight"].get("suffix", " g"))
            self.weight_decimals.setValue(int(elements["weight"].get("decimals", 2)))

            barcode_cfg = elements["barcode"]
            self.chk_bc_show.setChecked(bool(barcode_cfg.get("show", True)))
            self.bc_cx.setValue(float(barcode_cfg.get("center_x_mm", 20)))
            self.bc_y.setValue(float(barcode_cfg.get("y_pos_mm", 16)))
            self.bc_w.setValue(float(barcode_cfg.get("module_width_mm", 0.2)))
            self.bc_h.setValue(float(barcode_cfg.get("height_mm", 6)))

            barcode_text_cfg = elements["barcode_text"]
            self.chk_bc_text_show.setChecked(bool(barcode_text_cfg.get("show", True)))
            self.bc_text_cx.setValue(float(barcode_text_cfg.get("center_x_mm", 20)))
            self.bc_text_y.setValue(float(barcode_text_cfg.get("y_pos_mm", 22)))
            self.bc_text_font.setValue(int(barcode_text_cfg.get("font_size", 10)))
            self._set_combo_text(self.bc_text_font_family, barcode_text_cfg.get("font_family", "arial.ttf"))
        finally:
            self._loading_theme = False

        self.trigger_preview()

    def _store_current_theme_from_widgets(self):
        if not hasattr(self, "lbl_w"):
            return

        themes = self.cfg.setdefault("themes", {})
        themes[self.current_theme_name] = self._collect_theme_from_widgets()

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

        themes = self.cfg.setdefault("themes", {})
        if name not in themes:
            return

        self._store_current_theme_from_widgets()
        self.current_theme_name = name
        self.cfg["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._apply_theme_to_widgets(themes[name])

    def create_theme(self):
        name = self._theme_name_from_user("Nouveau theme", "Nom du nouveau theme:")
        if not name:
            return
        if name in self.cfg.get("themes", {}):
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return

        self._store_current_theme_from_widgets()
        self.cfg["themes"][name] = self._collect_theme_from_widgets()
        self.current_theme_name = name
        self.cfg["active_theme"] = name
        self._apply_theme_to_config(self.cfg["themes"][name])
        self._refresh_theme_combo()

    def duplicate_theme(self):
        name = self._theme_name_from_user(
            "Dupliquer theme",
            "Nom de la copie:",
            f"{self.current_theme_name} copie",
        )
        if not name:
            return
        if name in self.cfg.get("themes", {}):
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return

        self._store_current_theme_from_widgets()
        self.cfg["themes"][name] = copy.deepcopy(self.cfg["themes"][self.current_theme_name])
        self.current_theme_name = name
        self.cfg["active_theme"] = name
        self._apply_theme_to_config(self.cfg["themes"][name])
        self._refresh_theme_combo()

    def rename_theme(self):
        old_name = self.current_theme_name
        name = self._theme_name_from_user("Renommer theme", "Nouveau nom:", old_name)
        if not name or name == old_name:
            return
        if name in self.cfg.get("themes", {}):
            QMessageBox.warning(self, "Erreur", "Ce theme existe deja.")
            return

        self._store_current_theme_from_widgets()
        themes = self.cfg.setdefault("themes", {})
        themes[name] = themes.pop(old_name)
        self.current_theme_name = name
        self.cfg["active_theme"] = name
        self._apply_theme_to_config(themes[name])
        self._refresh_theme_combo()

    def delete_theme(self):
        themes = self.cfg.setdefault("themes", {})
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
        self.cfg["active_theme"] = self.current_theme_name
        self._apply_theme_to_config(themes[self.current_theme_name])
        self._refresh_theme_combo()
        self._apply_theme_to_widgets(themes[self.current_theme_name])

    def trigger_preview(self, *args):
        if getattr(self, "_loading_theme", False):
            return
        self.preview_timer.start()

    # ==========================================
    # 🎨 Label Image Generation
    # ==========================================
    def get_current_label_image(self):
        w_mm = self.lbl_w.value()
        h_mm = self.lbl_h.value()
        if w_mm <= 0 or h_mm <= 0: return None

        W_raw = int(w_mm * self.DPI_MULTIPLIER)
        W = (W_raw + 7) // 8 * 8  
        H = int(h_mm * self.DPI_MULTIPLIER)
        
        img = Image.new('L', (W, H), 255)
        draw = ImageDraw.Draw(img)
        
        def get_font(font_name, size):
            if size <= 0: return None
            try: return ImageFont.truetype(font_name, size)
            except: return ImageFont.load_default()

        # 1. Static Text
        if self.chk_static_show.isChecked() and self.static_font.value() > 0:
            font = get_font(self.static_font_family.currentText(), self.static_font.value())
            nx = int(self.static_cx.value() * self.DPI_MULTIPLIER)
            ny = int(self.static_y.value() * self.DPI_MULTIPLIER)
            text = self.static_text_input.text()
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((nx - (bbox[2]-bbox[0])//2, ny), text, fill=0, font=font)

        # 2. Product Name
        if self.chk_name_show.isChecked() and self.name_font.value() > 0:
            font = get_font(self.name_font_family.currentText(), self.name_font.value())
            nx = int(self.name_cx.value() * self.DPI_MULTIPLIER)
            ny = int(self.name_y.value() * self.DPI_MULTIPLIER)
            text = "Bijou Test"
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((nx - (bbox[2]-bbox[0])//2, ny), text, fill=0, font=font)

        # 2.5 Category (Catégorie)
        if hasattr(self, 'chk_category_show') and self.chk_category_show.isChecked() and self.category_font.value() > 0:
            font = get_font(self.category_font_family.currentText(), self.category_font.value())
            nx = int(self.category_cx.value() * self.DPI_MULTIPLIER)
            ny = int(self.category_y.value() * self.DPI_MULTIPLIER)
            text = "Collier" # 🟢 اسم صنف تجريبي للمعاينة
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((nx - (bbox[2]-bbox[0])//2, ny), text, fill=0, font=font)

        # 3. Model Name
        if self.chk_model_show.isChecked() and self.model_font.value() > 0:
            font = get_font(self.model_font_family.currentText(), self.model_font.value())
            nx = int(self.model_cx.value() * self.DPI_MULTIPLIER)
            ny = int(self.model_y.value() * self.DPI_MULTIPLIER)
            text = "Bague"
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((nx - (bbox[2]-bbox[0])//2, ny), text, fill=0, font=font)

        # 4. Metal Type
        if self.chk_metal_show.isChecked() and self.metal_font.value() > 0:
            font = get_font(self.metal_font_family.currentText(), self.metal_font.value())
            nx = int(self.metal_cx.value() * self.DPI_MULTIPLIER)
            ny = int(self.metal_y.value() * self.DPI_MULTIPLIER)
            text = "Or 18K"
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((nx - (bbox[2]-bbox[0])//2, ny), text, fill=0, font=font)

        # 5. Price
        if self.chk_price_show.isChecked() and self.price_font.value() > 0:
            font = get_font(self.price_font_family.currentText(), self.price_font.value())
            px = int(self.price_cx.value() * self.DPI_MULTIPLIER)
            py = int(self.price_y.value() * self.DPI_MULTIPLIER)
            text = "15000 DA"
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((px - (bbox[2]-bbox[0])//2, py), text, fill=0, font=font)

        # 6. Barcode Lines
        barcode_value = "123123123123"
        if self.chk_bc_show.isChecked():
            try:
                writer = ImageWriter(format="PNG")
                bc_class = barcode.get_barcode_class('code128')
                opts = {
                    "module_width": max(0.05, self.bc_w.value()), 
                    "module_height": max(1, self.bc_h.value()),
                    "background": "white", "foreground": "black", 
                    "write_text": False, # ⬅️ Disabled text here
                    "quiet_zone": 0.0
                }
                fp = io.BytesIO()
                bc_class(barcode_value, writer=writer).write(fp, options=opts)
                fp.seek(0)
                
                bc_img = Image.open(fp).convert("L")
                inv = ImageOps.invert(bc_img) 
                bbox = inv.getbbox()
                if bbox: bc_img = bc_img.crop(bbox)
                
                bc_cx = int(self.bc_cx.value() * self.DPI_MULTIPLIER)
                bc_y = int(self.bc_y.value() * self.DPI_MULTIPLIER)
                
                img.paste(bc_img, (bc_cx - bc_img.width//2, bc_y))
            except Exception as e:
                print("Barcode Error:", e)

        # 7. Barcode Text (Independent Element) - Using exact same logic as Price/Name
        if self.chk_bc_text_show.isChecked() and self.bc_text_font.value() > 0:
            font = get_font(self.bc_text_font_family.currentText(), self.bc_text_font.value())
            nx = int(self.bc_text_cx.value() * self.DPI_MULTIPLIER)
            ny = int(self.bc_text_y.value() * self.DPI_MULTIPLIER)
            text = "123123123123" # Text to display
            
            # Bounding box and centering logic identical to other text elements
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((nx - (bbox[2] - bbox[0]) // 2, ny), text, fill=0, font=font)

        # 8. Weight (Poids)
        if self.chk_weight_show.isChecked() and self.weight_font.value() > 0:
            font = get_font(self.weight_font_family.currentText(), self.weight_font.value())
            nx = int(self.weight_cx.value() * self.DPI_MULTIPLIER)
            ny = int(self.weight_y.value() * self.DPI_MULTIPLIER)
            decimals = self.weight_decimals.value()
            sample_weight = round(3.75, decimals)
            text = f"{self.weight_prefix.text()}{sample_weight:.{decimals}f}{self.weight_suffix.text()}"
            bbox = draw.textbbox((0, 0), text, font=font)
            draw.text((nx - (bbox[2] - bbox[0]) // 2, ny), text, fill=0, font=font)

        return img.point(lambda x: 0 if x < 128 else 255).convert('1', dither=Image.NONE)

    # ==========================================
    # 👁️ Draw Preview Grid
    # ==========================================
    def generate_preview(self):
        label_bw = self.get_current_label_image()
        if not label_bw: return

        w_mm = self.lbl_w.value()
        h_mm = self.lbl_h.value()
        W, H = label_bw.size

        grid_img = Image.new('RGB', (W, H), 'white')
        draw = ImageDraw.Draw(grid_img)
        
        for i in range(0, int(w_mm) + 1):
            x = int(i * self.DPI_MULTIPLIER)
            if i % 10 == 0:
                draw.line([(x, 0), (x, H)], fill="#ffcccc", width=2) 
                if i > 0: draw.text((x + 2, 2), str(i), fill="#ff5555")
            elif i % 5 == 0: draw.line([(x, 0), (x, H)], fill="#cceeff", width=1)
            else: draw.line([(x, 0), (x, H)], fill="#f0f0f0", width=1)

        for i in range(0, int(h_mm) + 1):
            y = int(i * self.DPI_MULTIPLIER)
            if i % 10 == 0:
                draw.line([(0, y), (W, y)], fill="#ffcccc", width=2)
                if i > 0: draw.text((2, y + 2), str(i), fill="#ff5555")
            elif i % 5 == 0: draw.line([(0, y), (W, y)], fill="#cceeff", width=1)
            else: draw.line([(0, y), (W, y)], fill="#f0f0f0", width=1)

        mask = ImageOps.invert(label_bw.convert("L"))
        black_layer = Image.new("RGB", label_bw.size, "black")
        grid_img.paste(black_layer, (0, 0), mask)
        
        data = grid_img.tobytes("raw", "RGB")
        qim = QImage(data, grid_img.width, grid_img.height, grid_img.width * 3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qim)
        scaled_pix = pix.scaled(grid_img.width * 2, grid_img.height * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_preview.setPixmap(scaled_pix)

    def print_test_label(self):
        printer_name = self.cmb_label_printer.currentText()
        if not printer_name:
            QMessageBox.warning(self, "Erreur", "Veuillez d'abord sélectionner une imprimante.")
            return

        img = self.get_current_label_image()
        if not img: return

        # === 💡 التعديل الحاسم: تنسيق الأرقام لإزالة الفواصل الصفرية (مثال: 40.0 تصبح 40) ===
        # هذا يمنع خطأ TSPL Syntax Error الذي يسبب خروج الورقة بيضاء
        w_mm = f"{self.lbl_w.value():g}"
        h_mm = f"{self.lbl_h.value():g}"
        gap = f"{self.lbl_gap.value():g}"
        
        shift_x_dots = int(self.off_x.value() * self.DPI_MULTIPLIER)
        shift_y_dots = int(self.off_y.value() * self.DPI_MULTIPLIER)
        
        W, H = img.size
        print_canvas = Image.new('1', (W, H), 255) 
        print_canvas.paste(img, (shift_x_dots, shift_y_dots))
        
        Wb = W // 8  
        cmds = [
            f"SIZE {w_mm} mm, {h_mm} mm",
            f"GAP {gap} mm, 0 mm",
            "DIRECTION 1", "CLS",
            "SET PEEL OFF", "SET TEAR ON",   
            f"BITMAP 0,0,{Wb},{H},0," 
        ]
        
        # دمج الأوامر وتحويلها للطباعة بنفس الطريقة الدقيقة المستخدمة في inventory_view.py
        data = print_canvas.tobytes()
        tspl = "\r\n".join(cmds).encode("ascii") + data + b"\r\nPRINT 1\r\n"
        
        try:
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                win32print.StartDocPrinter(hprinter, 1, ("Test Label", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, tspl)
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
                
            QMessageBox.information(self, "Succès", "Impression de test envoyée à l'imprimante !")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'impression :\n{str(e)}")

    def update_config_dict(self):
        self.cfg["printer_name"] = self.cmb_label_printer.currentText()
        self.cfg["label"]["width_mm"] = self.lbl_w.value()
        self.cfg["label"]["height_mm"] = self.lbl_h.value()
        self.cfg["label"]["gap_mm"] = self.lbl_gap.value()
        
        self.cfg["print_area"]["x_pos_mm"] = self.off_x.value()
        self.cfg["print_area"]["y_pos_mm"] = self.off_y.value()
        
        # Static Text
        self.cfg["elements"]["static_text"]["show"] = self.chk_static_show.isChecked()
        self.cfg["elements"]["static_text"]["text"] = self.static_text_input.text()
        self.cfg["elements"]["static_text"]["center_x_mm"] = self.static_cx.value()
        self.cfg["elements"]["static_text"]["y_pos_mm"] = self.static_y.value()
        self.cfg["elements"]["static_text"]["font_size"] = self.static_font.value()
        self.cfg["elements"]["static_text"]["font_family"] = self.static_font_family.currentText()

        # Product Name
        self.cfg["elements"]["product_name"]["show"] = self.chk_name_show.isChecked()
        self.cfg["elements"]["product_name"]["center_x_mm"] = self.name_cx.value()
        self.cfg["elements"]["product_name"]["y_pos_mm"] = self.name_y.value()
        self.cfg["elements"]["product_name"]["font_size"] = self.name_font.value()
        self.cfg["elements"]["product_name"]["font_family"] = self.name_font_family.currentText()

        # Category
        if "category" not in self.cfg["elements"]:
            self.cfg["elements"]["category"] = {}
        self.cfg["elements"]["category"]["show"] = self.chk_category_show.isChecked()
        self.cfg["elements"]["category"]["center_x_mm"] = self.category_cx.value()
        self.cfg["elements"]["category"]["y_pos_mm"] = self.category_y.value()
        self.cfg["elements"]["category"]["font_size"] = self.category_font.value()
        self.cfg["elements"]["category"]["font_family"] = self.category_font_family.currentText()
        
        # Model Name
        self.cfg["elements"]["model_name"]["show"] = self.chk_model_show.isChecked()
        self.cfg["elements"]["model_name"]["center_x_mm"] = self.model_cx.value()
        self.cfg["elements"]["model_name"]["y_pos_mm"] = self.model_y.value()
        self.cfg["elements"]["model_name"]["font_size"] = self.model_font.value()
        self.cfg["elements"]["model_name"]["font_family"] = self.model_font_family.currentText()

        # Metal Type
        self.cfg["elements"]["metal_type"]["show"] = self.chk_metal_show.isChecked()
        self.cfg["elements"]["metal_type"]["center_x_mm"] = self.metal_cx.value()
        self.cfg["elements"]["metal_type"]["y_pos_mm"] = self.metal_y.value()
        self.cfg["elements"]["metal_type"]["font_size"] = self.metal_font.value()
        self.cfg["elements"]["metal_type"]["font_family"] = self.metal_font_family.currentText()

        # Price
        self.cfg["elements"]["price"]["show"] = self.chk_price_show.isChecked()
        self.cfg["elements"]["price"]["center_x_mm"] = self.price_cx.value()
        self.cfg["elements"]["price"]["y_pos_mm"] = self.price_y.value()
        self.cfg["elements"]["price"]["font_size"] = self.price_font.value()
        self.cfg["elements"]["price"]["font_family"] = self.price_font_family.currentText()

        # Barcode Lines
        self.cfg["elements"]["barcode"]["show"] = self.chk_bc_show.isChecked()
        self.cfg["elements"]["barcode"]["center_x_mm"] = self.bc_cx.value()
        self.cfg["elements"]["barcode"]["y_pos_mm"] = self.bc_y.value()
        self.cfg["elements"]["barcode"]["module_width_mm"] = self.bc_w.value()
        self.cfg["elements"]["barcode"]["height_mm"] = self.bc_h.value()

        # Barcode Text (Independent)
        self.cfg["elements"]["barcode_text"]["show"] = self.chk_bc_text_show.isChecked()
        self.cfg["elements"]["barcode_text"]["center_x_mm"] = self.bc_text_cx.value()
        self.cfg["elements"]["barcode_text"]["y_pos_mm"] = self.bc_text_y.value()
        self.cfg["elements"]["barcode_text"]["font_size"] = self.bc_text_font.value()
        self.cfg["elements"]["barcode_text"]["font_family"] = self.bc_text_font_family.currentText()

        # Weight (Poids)
        self.cfg["elements"]["weight"]["show"] = self.chk_weight_show.isChecked()
        self.cfg["elements"]["weight"]["center_x_mm"] = self.weight_cx.value()
        self.cfg["elements"]["weight"]["y_pos_mm"] = self.weight_y.value()
        self.cfg["elements"]["weight"]["font_size"] = self.weight_font.value()
        self.cfg["elements"]["weight"]["font_family"] = self.weight_font_family.currentText()
        self.cfg["elements"]["weight"]["prefix"] = self.weight_prefix.text()
        self.cfg["elements"]["weight"]["suffix"] = self.weight_suffix.text()
        self.cfg["elements"]["weight"]["decimals"] = self.weight_decimals.value()

        self.cfg["active_theme"] = self.current_theme_name
        self.cfg.setdefault("themes", {})[self.current_theme_name] = self._theme_from_config(self.cfg)
