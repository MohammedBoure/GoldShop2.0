# ui/widgets/settings/settings_tab.py

import copy
import os
import json
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QGroupBox, QFormLayout, QLineEdit, QTextEdit, QMessageBox, 
    QFileDialog, QTabWidget, QSpinBox, QDoubleSpinBox, QSlider, QComboBox,
    QInputDialog, QCheckBox, QListWidget, QListWidgetItem, QApplication,
    QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtPrintSupport import QPrinterInfo 
import qtawesome as qta
import sys 

from config import get_config_path
from duckdns_updater import (
    default_duckdns_config,
    normalize_duckdns_config,
    update_duckdns_record,
)
from ui.deferred_loading import defer_initial_load
from ui.touch_design import apply_touch_button_defaults, apply_touch_input_defaults
from ui.ui_customization import (
    DARK_THEME_NAME,
    DEFAULT_THEME_NAME,
    DEFAULT_UI_CUSTOMIZATION,
    ensure_ui_customization,
)

CONFIG_FILE = str(get_config_path())


class DuckDnsUpdateThread(QThread):
    result_ready = Signal(dict)

    def __init__(self, duckdns_config, force=False, parent=None):
        super().__init__(parent)
        self.duckdns_config = copy.deepcopy(duckdns_config or {})
        self.force = force

    def run(self):
        self.result_ready.emit(update_duckdns_record(self.duckdns_config, force=self.force))


class SettingsTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        
        self.config = {
            "shop_name": "Bijouterie GoldShop",
            "shop_address": "Adresse du magasin",
            "shop_phone": "0555 00 00 00",
            "shop_rc": "",
            "shop_nif": "",
            "invoice_path": "./factures",
            "currency": "DA",
            "backup_paths": [],
            "theme": "Standard (Gold)",
            "zoom_level": 100,
            "animations": True,
            "auto_virtual_keyboard_enabled": False,
            "auto_virtual_keyboard_targets": {
                "line_edit": True,
                "text_edit": True,
                "spin_box": False,
                "editable_combo": False,
                "combo_box": False,
            },
            "ui_customization": copy.deepcopy(DEFAULT_UI_CUSTOMIZATION),
            "default_gold_purity": 730.0,   
            "default_silver_purity": 925.0, 
            
            # إعدادات الحفظ التلقائي 
            "auto_backup_enabled": False,
            "auto_backup_interval": 60.0,
            "auto_backup_password": "",
            "duckdns": default_duckdns_config(),
            
            "print_settings": {
                "default": {
                    "page_width_pixels": 576,
                    "center_x": 288,
                    "margin": 20,
                    "line_spacing": 10,
                    "bottom_margin": 50,
                    "extra_bottom_feed_pixels": 100,
                    "fonts": {
                        "title": {"name": "Tahoma", "height": 36, "weight": 700},
                        "normal_bold": {"name": "Tahoma", "height": 28, "weight": 700},
                        "normal": {"name": "Tahoma", "height": 26, "weight": 400},
                        "small": {"name": "Tahoma", "height": 22, "weight": 400}
                    }
                },
                "compact": { 
                    "page_width_pixels": 576,
                    "center_x": 288,
                    "margin": 5,
                    "line_spacing": 5,
                    "bottom_margin": 15,
                    "extra_bottom_feed_pixels": 30,
                    "fonts": {
                        "title": {"name": "Tahoma", "height": 30, "weight": 700},
                        "normal_bold": {"name": "Tahoma", "height": 24, "weight": 700},
                        "normal": {"name": "Tahoma", "height": 22, "weight": 400},
                        "small": {"name": "Tahoma", "height": 18, "weight": 400}
                    }
                },
                "xprinter365b": {
                    "page_width_pixels": 566,
                    "center_x": 283,
                    "margin": 0,
                    "line_spacing": 8,
                    "bottom_margin": 40,
                    "extra_bottom_feed_pixels": 70,
                    "fonts": {
                        "title": {"name": "Tahoma", "height": 34, "weight": 700},
                        "normal_bold": {"name": "Tahoma", "height": 26, "weight": 700},
                        "normal": {"name": "Tahoma", "height": 24, "weight": 400},
                        "small": {"name": "Tahoma", "height": 20, "weight": 400}
                    }
                }
            },
            
            "thermal_config": {
                "active_theme": "Default",
                "printer_name": "",
                "print_profile": "default",
                "paper_width": "80mm",
                "header_text": "Bienvenue chez GoldShop",
                "footer_text": "Merci de votre visite !",
                "cut_paper": True,
                "open_drawer": False
            },
            
            "label_config": {
                "server": {"port": 38476},
                "active_theme": "Default",
                "printer_name": "", 
                "label": {"width_mm": 80, "height_mm": 10, "gap_mm": 3},
                "print_area": {"x_pos_mm": 0, "y_pos_mm": 0},
                "elements": {
                    "product_name": {"show": True, "center_x_mm": 15, "y_pos_mm": 1, "font_size": 16},
                    "price": {"show": True, "center_x_mm": 15, "y_pos_mm": 4.5, "font_size": 20},
                    "barcode": {"show": True, "center_x_mm": 36, "y_pos_mm": 1, "module_width_mm": 0.125, "height_mm": 4},
                    "barcode_text": {"show": False, "center_x_mm": 48, "y_pos_mm": 9, "font_size": 0}
                }
            }
        }
        
        self.load_config()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #bdc3c7; background: white; border-radius: 3px; }
            QTabBar::tab { background: #f0f0f0; color: #333; padding: 8px 15px; margin-right: 2px; }
            QTabBar::tab:selected { background: white; border-top: 2px solid #e67e22; font-weight: bold; }
        """)

        # 1. تبويبة الإعدادات العامة
        self.tab_general = self.create_general_tab()
        self.tabs.addTab(self.tab_general, qta.icon("fa5s.sliders-h"), "Général")

        # 2. تبويبة العرض
        self.tab_graphics = self.create_graphics_tab()
        self.tabs.addTab(self.tab_graphics, qta.icon("fa5s.desktop"), "Affichage")

        self._add_lazy_tab(
            "tab_interface_customization",
            self._create_interface_customization_tab,
            qta.icon("fa5s.palette"),
            "Interface",
        )
        
        # 3. تبويبة الطابعة الحرارية
        self._add_lazy_tab(
            "tab_thermal_printer",
            self._create_thermal_printer_tab,
            qta.icon("fa5s.receipt"),
            "Imprimante Thermique",
        )
        
        # 4. تبويبة طابعة الملصقات
        self._add_lazy_tab(
            "tab_label_printer",
            self._create_label_printer_tab,
            qta.icon("fa5s.tags"),
            "Imprimante Etiquettes",
        )

        self._add_lazy_tab(
            "tab_pdf_printer",
            self._create_pdf_printer_tab,
            qta.icon("fa5s.file-pdf"),
            "Parametres PDF",
        )

        # 5. تبويبة قاعدة البيانات
        self.tab_db = self.create_db_tab()
        self.tabs.addTab(self.tab_db, qta.icon("fa5s.database"), "Base de Données")

        layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self._load_lazy_tab_at)

    def _create_interface_customization_tab(self):
        from .interface_customization_tab import InterfaceCustomizationTab

        return InterfaceCustomizationTab(self.config, self.save_config)

    def _create_thermal_printer_tab(self):
        from .thermal_printer_tab import ThermalPrinterTab

        return ThermalPrinterTab(self.config, self.save_config)

    def _create_label_printer_tab(self):
        from .label_printer_tab import LabelPrinterSettingsTab

        return LabelPrinterSettingsTab(self.config["label_config"], self.save_config)

    def _create_pdf_printer_tab(self):
        from .pdf_printer_tab import PdfPrinterTab

        return PdfPrinterTab(self.config, self.save_config)

    def _add_lazy_tab(self, attr_name, factory, icon, title):
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel("Le contenu sera charge lors de l'ouverture de cet onglet.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label, 1)
        placeholder._lazy_attr_name = attr_name
        placeholder._lazy_factory = factory
        self.tabs.addTab(placeholder, icon, title)
        return placeholder

    def _load_lazy_tab_at(self, index):
        widget = self.tabs.widget(index)
        factory = getattr(widget, "_lazy_factory", None)
        attr_name = getattr(widget, "_lazy_attr_name", None)
        if not callable(factory) or not attr_name:
            return widget

        built = factory()
        setattr(self, attr_name, built)

        icon = self.tabs.tabIcon(index)
        title = self.tabs.tabText(index)
        self.tabs.blockSignals(True)
        self.tabs.removeTab(index)
        self.tabs.insertTab(index, built, icon, title)
        self.tabs.setCurrentIndex(index)
        self.tabs.blockSignals(False)
        return built

    def get_system_printers(self):
        try: return QPrinterInfo.availablePrinterNames()
        except: return []

    def _create_scroll_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        scroll.setWidget(content)
        return scroll, layout

    def create_general_tab(self):
        widget, layout = self._create_scroll_page()
        
        grp_shop = QGroupBox("Informations du Magasin (Entête Facture)")
        form_shop = QFormLayout(grp_shop)
        
        self.inp_shop_name = QLineEdit(self.config.get("shop_name", ""))
        self.inp_shop_address = QLineEdit(self.config.get("shop_address", ""))
        self.inp_shop_phone = QLineEdit(self.config.get("shop_phone", ""))
        self.inp_shop_rc = QLineEdit(self.config.get("shop_rc", ""))
        self.inp_shop_nif = QLineEdit(self.config.get("shop_nif", ""))
        self.inp_currency = QLineEdit(self.config.get("currency", "DA"))
        
        form_shop.addRow("Nom du Magasin:", self.inp_shop_name)
        form_shop.addRow("Adresse:", self.inp_shop_address)
        form_shop.addRow("Téléphone:", self.inp_shop_phone)
        form_shop.addRow("N° Registre Commerce (RC):", self.inp_shop_rc)
        form_shop.addRow("Numéro d'Identification Fiscale (NIF):", self.inp_shop_nif)
        form_shop.addRow("Devise Principale:", self.inp_currency)
        
        layout.addWidget(grp_shop)

        grp_export = QGroupBox("Dossier d'exportation (Factures PDF / A4)")
        form_export = QFormLayout(grp_export)

        self.inp_invoice_path = QLineEdit(self.config.get("invoice_path", "./factures"))
        btn_browse_invoice = QPushButton("...")
        btn_browse_invoice.setFixedWidth(40)
        btn_browse_invoice.clicked.connect(self.browse_invoice_folder)
        
        h_invoice_lay = QHBoxLayout()
        h_invoice_lay.setContentsMargins(0, 0, 0, 0)
        h_invoice_lay.addWidget(self.inp_invoice_path)
        h_invoice_lay.addWidget(btn_browse_invoice)
        form_export.addRow("Chemin de sauvegarde:", h_invoice_lay)
        layout.addWidget(grp_export)

        from .web_access_settings import WebAccessSettingsGroup

        self.web_access_settings = WebAccessSettingsGroup(self.config)
        layout.addWidget(self.web_access_settings)

        grp_duckdns = QGroupBox("DuckDNS (Acces distant au serveur web)")
        form_duckdns = QFormLayout(grp_duckdns)

        duckdns_config = normalize_duckdns_config(self.config.get("duckdns"))
        self.chk_duckdns_enabled = QCheckBox("Activer la correction automatique DuckDNS")
        self.chk_duckdns_enabled.setChecked(duckdns_config.get("enabled", False))

        self.inp_duckdns_domain = QLineEdit(duckdns_config.get("domain", ""))
        self.inp_duckdns_domain.setPlaceholderText("ex: rtxa ou rtxa.duckdns.org")
        apply_touch_input_defaults(self.inp_duckdns_domain)

        self.inp_duckdns_token = QLineEdit(duckdns_config.get("token", ""))
        self.inp_duckdns_token.setEchoMode(QLineEdit.Password)
        self.inp_duckdns_token.setPlaceholderText("Token DuckDNS")
        apply_touch_input_defaults(self.inp_duckdns_token)

        self.btn_duckdns_toggle_token = QPushButton("Afficher")
        self.btn_duckdns_toggle_token.setCheckable(True)
        self.btn_duckdns_toggle_token.clicked.connect(
            lambda checked: self._toggle_secret_field_visibility(
                self.inp_duckdns_token,
                self.btn_duckdns_toggle_token,
                checked,
            )
        )
        apply_touch_button_defaults(self.btn_duckdns_toggle_token)

        self.btn_duckdns_token_keyboard = QPushButton("Clavier")
        self.btn_duckdns_token_keyboard.clicked.connect(
            lambda: self._show_virtual_keyboard(self.inp_duckdns_token)
        )
        apply_touch_button_defaults(self.btn_duckdns_token_keyboard)

        self.spin_duckdns_interval = QDoubleSpinBox()
        self.spin_duckdns_interval.setDecimals(1)
        self.spin_duckdns_interval.setRange(5.0, 1440.0)
        self.spin_duckdns_interval.setSuffix(" minutes")
        self.spin_duckdns_interval.setValue(float(duckdns_config.get("interval_minutes", 30.0)))
        apply_touch_input_defaults(self.spin_duckdns_interval)

        self.lbl_duckdns_status = QLabel()
        self.lbl_duckdns_status.setWordWrap(True)
        self.lbl_duckdns_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        self.update_duckdns_status_label()

        self.btn_duckdns_update = QPushButton("Tester / Mettre a jour maintenant")
        self.btn_duckdns_update.setIcon(qta.icon("fa5s.sync-alt", color="#2980b9"))
        self.btn_duckdns_update.clicked.connect(self.action_update_duckdns_now)

        self.chk_duckdns_enabled.toggled.connect(self._set_duckdns_inputs_enabled)
        self._set_duckdns_inputs_enabled(self.chk_duckdns_enabled.isChecked())

        form_duckdns.addRow(self.chk_duckdns_enabled)
        form_duckdns.addRow("Domaine:", self.inp_duckdns_domain)
        duckdns_token_row = QHBoxLayout()
        duckdns_token_row.addWidget(self.inp_duckdns_token, 1)
        duckdns_token_row.addWidget(self.btn_duckdns_toggle_token)
        duckdns_token_row.addWidget(self.btn_duckdns_token_keyboard)
        form_duckdns.addRow("Token:", duckdns_token_row)
        form_duckdns.addRow("Intervalle de verification:", self.spin_duckdns_interval)
        form_duckdns.addRow("Dernier etat:", self.lbl_duckdns_status)
        form_duckdns.addRow(self.btn_duckdns_update)
        layout.addWidget(grp_duckdns)

        grp_metals = QGroupBox("Métaux par Défaut (Fonte / Coffre)")
        form_metals = QFormLayout(grp_metals)
        
        self.combo_default_gold = QComboBox()
        self.combo_default_silver = QComboBox()
        
        self.load_default_metal_options(include_database=False)
        defer_initial_load(self, self.refresh_data)
        
        form_metals.addRow("Titre d'Or par défaut:", self.combo_default_gold)
        form_metals.addRow("Titre d'Argent par défaut:", self.combo_default_silver)
        
        layout.addWidget(grp_metals)
        
        btn = QPushButton("Enregistrer les paramètres")
        btn.setMinimumHeight(40)
        btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        btn.clicked.connect(self.save_config)
        layout.addWidget(btn)
        
        layout.addStretch()
        return widget

    def _set_duckdns_inputs_enabled(self, enabled):
        for widget in (
            getattr(self, "inp_duckdns_domain", None),
            getattr(self, "inp_duckdns_token", None),
            getattr(self, "btn_duckdns_toggle_token", None),
            getattr(self, "btn_duckdns_token_keyboard", None),
            getattr(self, "spin_duckdns_interval", None),
            getattr(self, "btn_duckdns_update", None),
        ):
            if widget is not None:
                widget.setEnabled(bool(enabled))

    def _toggle_secret_field_visibility(self, field, button, checked):
        field.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        button.setText("Masquer" if checked else "Afficher")

    def _show_virtual_keyboard(self, target=None):
        if target is not None:
            target.setFocus(Qt.OtherFocusReason)
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog

        keyboard = getattr(self, "_touch_keyboard", None)
        if keyboard is None:
            keyboard = VirtualKeyboardDialog(self)
            self._touch_keyboard = keyboard
        keyboard.show()
        keyboard.raise_()

    def _duckdns_config_from_controls(self):
        current = normalize_duckdns_config(self.config.get("duckdns"))
        if hasattr(self, "chk_duckdns_enabled"):
            current.update({
                "enabled": self.chk_duckdns_enabled.isChecked(),
                "domain": self.inp_duckdns_domain.text(),
                "token": self.inp_duckdns_token.text(),
                "interval_minutes": float(self.spin_duckdns_interval.value()),
            })
        return normalize_duckdns_config(current)

    def update_duckdns_status_label(self):
        if not hasattr(self, "lbl_duckdns_status"):
            return

        cfg = normalize_duckdns_config(self.config.get("duckdns"))
        status = cfg.get("last_status") or "never"
        message = cfg.get("last_message") or ""
        last_ip = cfg.get("last_ip") or "-"
        updated_at = cfg.get("last_update_at") or "-"
        if status == "never":
            text = "Aucune mise a jour effectuee."
        else:
            text = f"{status.upper()} | IP: {last_ip} | {updated_at}"
            if message:
                text += f"\n{message}"
        self.lbl_duckdns_status.setText(text)

    def action_update_duckdns_now(self):
        duckdns_config = self._duckdns_config_from_controls()
        self.config["duckdns"] = duckdns_config

        if not duckdns_config.get("domain"):
            QMessageBox.warning(self, "DuckDNS", "Veuillez saisir le domaine DuckDNS.")
            return
        if not duckdns_config.get("token"):
            QMessageBox.warning(self, "DuckDNS", "Veuillez saisir le token DuckDNS.")
            return

        self.btn_duckdns_update.setEnabled(False)
        self.lbl_duckdns_status.setText("Detection de l'IP publique et mise a jour DuckDNS...")

        self.duckdns_update_thread = DuckDnsUpdateThread(duckdns_config, force=True, parent=self)
        self.duckdns_update_thread.result_ready.connect(self._on_duckdns_update_finished)
        self.duckdns_update_thread.finished.connect(self.duckdns_update_thread.deleteLater)
        self.duckdns_update_thread.start()

    def _on_duckdns_update_finished(self, result):
        cfg = self._duckdns_config_from_controls()
        cfg["last_status"] = result.get("status", "error")
        cfg["last_message"] = result.get("message", "")
        cfg["last_ip"] = result.get("ip") or cfg.get("last_ip", "")
        cfg["last_update_at"] = result.get("updated_at", datetime.datetime.now().isoformat(timespec="seconds"))
        self.config["duckdns"] = cfg

        self.update_duckdns_status_label()
        self.btn_duckdns_update.setEnabled(self.chk_duckdns_enabled.isChecked())
        self._write_config(show_success=False)

        if result.get("success"):
            QMessageBox.information(self, "DuckDNS", f"Mise a jour reussie.\nIP: {cfg.get('last_ip', '-')}")
        else:
            QMessageBox.warning(self, "DuckDNS", f"Mise a jour echouee.\n{result.get('message', '')}")

    def refresh_data(self):
        self.load_default_metal_options(include_database=True)

    def load_default_metal_options(self, include_database=True):
        if not hasattr(self, "combo_default_gold") or not hasattr(self, "combo_default_silver"):
            return

        selected_gold = float(self.config.get("default_gold_purity", 730.0))
        selected_silver = float(self.config.get("default_silver_purity", 925.0))

        self.combo_default_gold.blockSignals(True)
        self.combo_default_silver.blockSignals(True)
        self.combo_default_gold.clear()
        self.combo_default_silver.clear()
        self.combo_default_gold.addItem("Standard Or (730.0‰)", 730.0)
        self.combo_default_silver.addItem("Standard Argent (925.0‰)", 925.0)

        if include_database:
            try:
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT name, purity_value FROM MetalTypes ORDER BY purity_value DESC")
                    metals = cursor.fetchall()
                    for m in metals:
                        val = float(m['purity_value'])
                        text = f"{m['name']} ({val}‰)"
                        self.combo_default_gold.addItem(text, val)
                        self.combo_default_silver.addItem(text, val)
            except Exception as e:
                print(f"Erreur chargement métaux: {e}")

        idx_gold = self.combo_default_gold.findData(selected_gold)
        if idx_gold >= 0:
            self.combo_default_gold.setCurrentIndex(idx_gold)

        idx_silver = self.combo_default_silver.findData(selected_silver)
        if idx_silver >= 0:
            self.combo_default_silver.setCurrentIndex(idx_silver)

        self.combo_default_gold.blockSignals(False)
        self.combo_default_silver.blockSignals(False)

    def create_graphics_tab(self):
        widget, layout = self._create_scroll_page()

        ui_config = ensure_ui_customization(self.config)

        grp_theme = QGroupBox("Theme de l'application")
        theme_layout = QFormLayout(grp_theme)
        self.combo_app_theme = QComboBox()
        self.combo_app_theme.addItem("Clair", DEFAULT_THEME_NAME)
        self.combo_app_theme.addItem("Sombre", DARK_THEME_NAME)
        active_theme_name = ui_config.get("active_theme", DEFAULT_THEME_NAME)
        theme_index = self.combo_app_theme.findData(active_theme_name)
        self.combo_app_theme.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.combo_app_theme.currentIndexChanged.connect(self.apply_graphics_live)
        theme_layout.addRow("Mode:", self.combo_app_theme)
        layout.addWidget(grp_theme)
        
        grp = QGroupBox("Zoom")
        h = QHBoxLayout(grp)
        self.slider_zoom = QSlider(Qt.Horizontal)
        self.slider_zoom.setRange(60, 180)
        self.slider_zoom.setValue(int(self.config.get("zoom_level", 100)))
        
        self.spin_zoom = QSpinBox()
        self.spin_zoom.setRange(60, 180)
        self.spin_zoom.setValue(int(self.config.get("zoom_level", 100)))
        
        self.slider_zoom.valueChanged.connect(self.spin_zoom.setValue)
        self.spin_zoom.valueChanged.connect(self.slider_zoom.setValue)
        
        btn_test = QPushButton("Appliquer")
        btn_test.clicked.connect(self.apply_graphics_live)
        
        h.addWidget(QLabel("Zoom:"))
        h.addWidget(self.slider_zoom)
        h.addWidget(self.spin_zoom)
        h.addWidget(btn_test)
        layout.addWidget(grp)

        grp_keyboard = QGroupBox("Clavier virtuel")
        keyboard_layout = QVBoxLayout(grp_keyboard)
        self.chk_auto_virtual_keyboard = QCheckBox(
            "Ouvrir automatiquement le clavier lors du focus sur un champ de saisie"
        )
        self.chk_auto_virtual_keyboard.setChecked(
            bool(self.config.get("auto_virtual_keyboard_enabled", False))
        )
        keyboard_layout.addWidget(self.chk_auto_virtual_keyboard)
        keyboard_layout.addWidget(QLabel("Champs concernes:"))
        keyboard_targets = self.config.get("auto_virtual_keyboard_targets") or {}
        self.chk_vkb_line_edit = QCheckBox("Champs texte simples")
        self.chk_vkb_text_edit = QCheckBox("Zones de texte")
        self.chk_vkb_spin_box = QCheckBox("Champs numeriques")
        self.chk_vkb_editable_combo = QCheckBox("Listes deroulantes editables")
        self.chk_vkb_combo_box = QCheckBox("Listes deroulantes simples")
        self.chk_vkb_line_edit.setChecked(bool(keyboard_targets.get("line_edit", True)))
        self.chk_vkb_text_edit.setChecked(bool(keyboard_targets.get("text_edit", True)))
        self.chk_vkb_spin_box.setChecked(bool(keyboard_targets.get("spin_box", False)))
        self.chk_vkb_editable_combo.setChecked(bool(keyboard_targets.get("editable_combo", False)))
        self.chk_vkb_combo_box.setChecked(bool(keyboard_targets.get("combo_box", False)))
        for checkbox in (
            self.chk_vkb_line_edit,
            self.chk_vkb_text_edit,
            self.chk_vkb_spin_box,
            self.chk_vkb_editable_combo,
            self.chk_vkb_combo_box,
        ):
            keyboard_layout.addWidget(checkbox)
        layout.addWidget(grp_keyboard)

        grp_permissions = QGroupBox("Permissions automatiques")
        permissions_layout = QVBoxLayout(grp_permissions)
        self.btn_refresh_auto_permissions = QPushButton("Actualiser les permissions des tableaux")
        self.btn_refresh_auto_permissions.setIcon(qta.icon("fa5s.columns", color="#2980b9"))
        self.btn_refresh_auto_permissions.clicked.connect(self.refresh_auto_permissions_catalog)
        permissions_layout.addWidget(self.btn_refresh_auto_permissions)
        layout.addWidget(grp_permissions)
        
        btn = QPushButton("Enregistrer Affichage")
        btn.clicked.connect(self.save_config)
        layout.addWidget(btn)
        layout.addStretch()
        return widget

    def refresh_auto_permissions_catalog(self):
        main_window = self.window()
        current_user = getattr(main_window, "current_user", {}) or {}
        if current_user.get("role") != "Admin":
            QMessageBox.warning(self, "Permissions", "Cette operation est reservee a l'administrateur.")
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            discover_now = getattr(main_window, "refresh_auto_permission_discovery_now", None)
            if callable(discover_now):
                counts = discover_now()
            else:
                controller = getattr(main_window, "auto_permissions", None)
                if controller is not None:
                    controller.scan(main_window)
                    controller.registry.flush()
                counts = {"tables": 0, "columns": 0, "items": 0}
        finally:
            QApplication.restoreOverrideCursor()

        tables = int((counts or {}).get("tables") or 0)
        columns = int((counts or {}).get("columns") or 0)
        items = int((counts or {}).get("items") or 0)
        self._refresh_open_permissions_views(main_window)

        if columns:
            QMessageBox.information(
                self,
                "Permissions",
                f"Actualisation terminee.\nTables detectees: {tables}\nColonnes detectees: {columns}\nElements auto: {items}",
            )
            return

        QMessageBox.warning(
            self,
            "Permissions",
            "Aucune colonne de tableau n'a ete detectee. Ouvrez les pages contenant des tableaux puis relancez l'actualisation.",
        )

    def _refresh_open_permissions_views(self, main_window):
        for widget in main_window.findChildren(QWidget):
            if type(widget).__name__ != "UsersManagementView":
                continue
            refresh_view = getattr(widget, "refresh_view_data", None)
            if callable(refresh_view):
                refresh_view()

    def create_db_tab(self):
        widget, layout = self._create_scroll_page()
        
        # 1. إعدادات مسارات الحفظ (متعددة)
        grp_backup = QGroupBox("Dossiers de Sauvegarde (Backup Paths)")
        v_backup = QVBoxLayout(grp_backup)
        
        self.list_backup_paths = QListWidget()
        self.list_backup_paths.setFixedHeight(80) 
        
        saved_paths = self.config.get("backup_paths", [])
        if not saved_paths and "backup_path" in self.config:
            saved_paths = [self.config["backup_path"]]
            
        for path in saved_paths:
            if path: self.list_backup_paths.addItem(path)

        h_btn_paths = QHBoxLayout()
        btn_add_path = QPushButton(" Ajouter un dossier")
        btn_add_path.setIcon(qta.icon("fa5s.plus", color="green"))
        btn_add_path.clicked.connect(self.add_backup_path)
        
        btn_remove_path = QPushButton(" Supprimer le dossier")
        btn_remove_path.setIcon(qta.icon("fa5s.trash", color="red"))
        btn_remove_path.clicked.connect(self.remove_backup_path)
        
        btn_manual_backup = QPushButton(" Créer une sauvegarde maintenant")
        btn_manual_backup.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        btn_manual_backup.clicked.connect(self.action_backup)

        h_btn_paths.addWidget(btn_add_path)
        h_btn_paths.addWidget(btn_remove_path)
        h_btn_paths.addStretch()
        h_btn_paths.addWidget(btn_manual_backup)

        v_backup.addWidget(QLabel("Le système créera une copie dans <b>tous</b> ces dossiers simultanément :"))
        v_backup.addWidget(self.list_backup_paths)
        v_backup.addLayout(h_btn_paths)
        
        layout.addWidget(grp_backup)

        # 2. إعدادات الحفظ التلقائي
        grp_auto_backup = QGroupBox("Sauvegarde Automatique (Auto-Backup)")
        form_auto_backup = QFormLayout(grp_auto_backup)

        self.chk_auto_backup = QCheckBox("Activer la sauvegarde automatique en arrière-plan")
        self.chk_auto_backup.setChecked(self.config.get("auto_backup_enabled", False))

        # تم استبدال QSpinBox بـ QDoubleSpinBox لدعم الكسور (مثل 0.2)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setDecimals(1)
        self.spin_interval.setRange(0.2, 14400.0) 
        self.spin_interval.setSuffix(" minutes")
        self.spin_interval.setValue(float(self.config.get("auto_backup_interval", 60.0)))

        self.inp_backup_password = QLineEdit(self.config.get("auto_backup_password", ""))
        self.inp_backup_password.setEchoMode(QLineEdit.Password) 
        apply_touch_input_defaults(self.inp_backup_password)

        self.btn_backup_toggle_password = QPushButton("Afficher")
        self.btn_backup_toggle_password.setCheckable(True)
        self.btn_backup_toggle_password.clicked.connect(
            lambda checked: self._toggle_secret_field_visibility(
                self.inp_backup_password,
                self.btn_backup_toggle_password,
                checked,
            )
        )
        apply_touch_button_defaults(self.btn_backup_toggle_password)

        self.btn_backup_password_keyboard = QPushButton("Clavier")
        self.btn_backup_password_keyboard.clicked.connect(
            lambda: self._show_virtual_keyboard(self.inp_backup_password)
        )
        apply_touch_button_defaults(self.btn_backup_password_keyboard)
        self.inp_backup_password.setPlaceholderText("Optionnel: Mot de passe pour protéger le fichier ZIP")

        self.spin_interval.setEnabled(self.chk_auto_backup.isChecked())
        self.inp_backup_password.setEnabled(self.chk_auto_backup.isChecked())
        self.btn_backup_toggle_password.setEnabled(self.chk_auto_backup.isChecked())
        self.btn_backup_password_keyboard.setEnabled(self.chk_auto_backup.isChecked())
        self.chk_auto_backup.toggled.connect(self.spin_interval.setEnabled)
        self.chk_auto_backup.toggled.connect(self.inp_backup_password.setEnabled)
        self.chk_auto_backup.toggled.connect(self.btn_backup_toggle_password.setEnabled)
        self.chk_auto_backup.toggled.connect(self.btn_backup_password_keyboard.setEnabled)

        form_auto_backup.addRow(self.chk_auto_backup)
        form_auto_backup.addRow("Intervalle d'exécution:", self.spin_interval)
        backup_password_row = QHBoxLayout()
        backup_password_row.addWidget(self.inp_backup_password, 1)
        backup_password_row.addWidget(self.btn_backup_toggle_password)
        backup_password_row.addWidget(self.btn_backup_password_keyboard)
        form_auto_backup.addRow("Mot de passe ZIP:", backup_password_row)
        
        lbl_info = QLabel("<i>* Le système conservera uniquement la dernière sauvegarde automatique pour économiser l'espace.</i>")
        lbl_info.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        form_auto_backup.addRow(lbl_info)

        layout.addWidget(grp_auto_backup)
        
        # 3. إعدادات الصيانة والخطر
        grp_danger = QGroupBox("Maintenance (Danger)")
        grp_danger.setStyleSheet("border: 1px solid red;")
        v = QVBoxLayout(grp_danger)
        btn_r = QPushButton("Restaurer (Depuis un fichier ZIP)")
        btn_r.clicked.connect(self.action_restore)
        
        btn_z = QPushButton(" ⚠️ Supprimer la Base de Données (Reset Total)")
        btn_z.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 10px;")
        btn_z.clicked.connect(self.action_reset_db)
        
        v.addWidget(btn_r)
        v.addWidget(btn_z)
        layout.addWidget(grp_danger)

        # زر حفظ التغييرات لهذه التبويبة
        btn_save_db = QPushButton("Enregistrer les paramètres de sauvegarde")
        btn_save_db.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        btn_save_db.clicked.connect(self.save_config)
        layout.addWidget(btn_save_db)
        
        layout.addStretch()
        return widget # 🟢 السطر الذي كان مفقوداً وتمت إضافته

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._update_dict_recursive(self.config, data)
            except: pass
        self.config["duckdns"] = normalize_duckdns_config(self.config.get("duckdns"))
        ensure_ui_customization(self.config)

    def _update_dict_recursive(self, d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._update_dict_recursive(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    def _sync_config_from_controls(self):
        # General Settings
        if hasattr(self, "inp_shop_name"):
            self.config["shop_name"] = self.inp_shop_name.text()
            self.config["shop_address"] = self.inp_shop_address.text()
            self.config["shop_phone"] = self.inp_shop_phone.text()
            self.config["shop_rc"] = self.inp_shop_rc.text()
            self.config["shop_nif"] = self.inp_shop_nif.text()
            self.config["currency"] = self.inp_currency.text()
            self.config["invoice_path"] = self.inp_invoice_path.text()
            self.config["default_gold_purity"] = self.combo_default_gold.currentData()
            self.config["default_silver_purity"] = self.combo_default_silver.currentData()
            self.config["duckdns"] = self._duckdns_config_from_controls()
            if not self.web_access_settings.update_config(self.config):
                return False

        if hasattr(self, "spin_zoom"):
            self.config["zoom_level"] = self.spin_zoom.value()
        if hasattr(self, "combo_app_theme"):
            ui_config = ensure_ui_customization(self.config)
            ui_config["active_theme"] = self.combo_app_theme.currentData() or DEFAULT_THEME_NAME
        if hasattr(self, "chk_auto_virtual_keyboard"):
            self.config["auto_virtual_keyboard_enabled"] = self.chk_auto_virtual_keyboard.isChecked()
            self.config["auto_virtual_keyboard_targets"] = {
                "line_edit": self.chk_vkb_line_edit.isChecked(),
                "text_edit": self.chk_vkb_text_edit.isChecked(),
                "spin_box": self.chk_vkb_spin_box.isChecked(),
                "editable_combo": self.chk_vkb_editable_combo.isChecked(),
                "combo_box": self.chk_vkb_combo_box.isChecked(),
            }

        # حفظ قائمة المسارات الجديدة
        if hasattr(self, "list_backup_paths"):
            paths = []
            for i in range(self.list_backup_paths.count()):
                paths.append(self.list_backup_paths.item(i).text())
            self.config["backup_paths"] = paths

        # حفظ إعدادات النسخ التلقائي
        if hasattr(self, "chk_auto_backup"):
            self.config["auto_backup_enabled"] = self.chk_auto_backup.isChecked()
            self.config["auto_backup_interval"] = float(self.spin_interval.value()) # 🟢 تحويل لـ Float
            self.config["auto_backup_password"] = self.inp_backup_password.text()

        # تحديث بيانات الطابعات من الكلاسات المستقلة
        if hasattr(self, "tab_thermal_printer"):
            self.tab_thermal_printer.update_config_dict()
        if hasattr(self, "tab_label_printer"):
            self.tab_label_printer.update_config_dict()
        if hasattr(self, "tab_pdf_printer"):
            self.tab_pdf_printer.update_config_dict()
        if hasattr(self, "tab_interface_customization"):
            self.tab_interface_customization.update_config_dict()
        return True

    def _write_config(self, show_success=True):
        try:
            from config import save_full_config
            save_full_config(self.config)
            if hasattr(self, "spin_zoom"):
                self.apply_graphics_live()

            # إرسال إشارة للنافذة الرئيسية لتحديث المؤقت فوراً دون الحاجة لإعادة التشغيل
            main_window = self.window()
            if hasattr(main_window, 'apply_ui_customization_config'):
                main_window.apply_ui_customization_config(self.config.get("ui_customization"))
            if hasattr(main_window, 'setup_auto_backup_timer'):
                main_window.setup_auto_backup_timer()
            if hasattr(main_window, 'setup_duckdns_timer'):
                main_window.setup_duckdns_timer()
            try:
                from ui.tools.virtual_keyboard import configure_auto_virtual_keyboard

                configure_auto_virtual_keyboard(
                    self.config.get("auto_virtual_keyboard_enabled", False),
                    self.config.get("auto_virtual_keyboard_targets"),
                )
            except Exception:
                pass

            if show_success:
                QMessageBox.information(self, "Succès", "Les paramètres ont été enregistrés avec succès.")
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde : {str(e)}")

    def save_config(self):
        if self._sync_config_from_controls() is False:
            return
        self._write_config(show_success=True)

    def add_backup_path(self):
        d = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier de sauvegarde")
        if d:
            for i in range(self.list_backup_paths.count()):
                if self.list_backup_paths.item(i).text() == d:
                    return
            self.list_backup_paths.addItem(d)

    def remove_backup_path(self):
        current_row = self.list_backup_paths.currentRow()
        if current_row >= 0:
            self.list_backup_paths.takeItem(current_row)

    def action_backup(self):
        """نسخ يدوي إلى جميع المسارات المحددة"""
        paths = [self.list_backup_paths.item(i).text() for i in range(self.list_backup_paths.count())]
        if not paths:
            QMessageBox.warning(self, "Erreur", "Veuillez ajouter au moins un dossier de sauvegarde.")
            return
            
        if hasattr(self.manager.db, '_backup') and hasattr(self.manager.db._backup, 'create_multi_backup'):
            password = self.inp_backup_password.text()
            success, msgs = self.manager.db._backup.create_multi_backup(paths, password, is_auto=False)
            if success:
                QMessageBox.information(self, "Succès", f"Sauvegarde créée dans {len(paths)} emplacement(s).")
            else:
                QMessageBox.warning(self, "Attention", "Certaines sauvegardes ont échoué. Vérifiez les logs.")
        else:
             QMessageBox.critical(self, "Erreur", "La fonction multi-sauvegarde n'est pas disponible.")

    def apply_graphics_live(self):
        main_window = self.window()
        if hasattr(self, "combo_app_theme"):
            ui_config = ensure_ui_customization(self.config)
            ui_config["active_theme"] = self.combo_app_theme.currentData() or DEFAULT_THEME_NAME
            if hasattr(main_window, 'apply_ui_customization_config'):
                main_window.apply_ui_customization_config(ui_config)
        if hasattr(main_window, 'zoom_scale') and hasattr(self, "spin_zoom"):
            main_window.zoom_scale = self.spin_zoom.value() / 100.0
            main_window.refresh_ui_scaling()
            main_window.save_zoom_setting()

    def browse_invoice_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier des factures")
        if d: self.inp_invoice_path.setText(d)

    def action_restore(self):
        # استخدام أول مسار في القائمة كنقطة بداية للبحث
        start_path = ""
        if self.list_backup_paths.count() > 0:
            start_path = self.list_backup_paths.item(0).text()
            
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner le fichier de sauvegarde", start_path, "Archives ZIP (*.zip)")
        if not path:
            return

        reply = QMessageBox.warning(
            self, "Attention (Récupération des données)",
            "La restauration remplacera toutes les données actuelles de la base de données par celles de la sauvegarde.\n\nÊtes-vous sûr de vouloir continuer ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if hasattr(self.manager.db, 'restore_from_archive_zip_destructive'):
                    success, message = self.manager.db.restore_from_archive_zip_destructive(path)
                    if success:
                        QMessageBox.information(
                            self, "Succès", 
                            f"Restauration terminée avec succès !\n\nDétails : {message}\n\nVeuillez redémarrer l'application pour appliquer les changements."
                        )
                    else:
                        QMessageBox.critical(self, "Échec de la Restauration", f"La restauration a échoué.\n\nRaison : {message}")
                else:
                    QMessageBox.critical(self, "Erreur", "La fonction de restauration n'est pas disponible dans le gestionnaire de base de données.")
            except Exception as e:
                QMessageBox.critical(self, "Erreur Critique", f"Une erreur inattendue s'est produite:\n\n{str(e)}")

    def action_reset_db(self):
        reply = QMessageBox.critical(self, "Avertissement Critique",
                                     "Êtes-vous absolument sûr de vouloir supprimer TOUTES les données ?\n\n"
                                     "Cette action est irréversible et effacera l'historique complet du magasin.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            password, ok = QInputDialog.getText(self, "Autorisation Requise",
                                                "Veuillez entrer le mot de passe administrateur pour confirmer le formatage :",
                                                QLineEdit.Password)
            if ok:
                if not password:
                    QMessageBox.warning(self, "Erreur", "Le mot de passe ne peut pas être vide.")
                    return
                
                if hasattr(self.manager.db, 'truncate_all_tables'):
                    success, msg = self.manager.db.truncate_all_tables(password)
                    if success:
                        QMessageBox.information(self, "Formatage Réussi", 
                                                "La base de données a été réinitialisée avec succès.\n"
                                                "L'application va maintenant se fermer pour appliquer les changements.")
                        sys.exit(0)
                    else:
                        QMessageBox.critical(self, "Échec de l'autorisation", msg)
                else:
                    QMessageBox.critical(self, "Erreur", "La fonction n'est pas disponible.")
