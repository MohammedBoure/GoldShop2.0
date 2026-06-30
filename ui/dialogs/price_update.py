# ui/dialogs/price_update.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QDoubleSpinBox, QLabel, QFrame, QGroupBox, QRadioButton,
    QMessageBox, QFormLayout, QButtonGroup, QTabWidget, QWidget,
    QScrollArea, QCheckBox, QApplication
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont, QIcon
import qtawesome as qta

from ui.tools.virtual_keyboard import VirtualKeyboardDialog

class PriceUpdateDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.vkb = None

        self.settings = QSettings("MyLabApp", "PriceUpdateDialog")
        self.setWindowTitle("Gestionnaire Avancé des Prix")

        screen = QApplication.primaryScreen().availableGeometry()
        w = min(900, int(screen.width() * 0.95))
        h = max(580, int(screen.height() * 0.60))

        self.resize(w, h)
        self.setMinimumSize(600, 400)

        self.setStyleSheet("""
            QDialog, QScrollArea { background-color: #f4f6f9; border: none; }

            #footerFrame {
                background-color: #ffffff;
                border-top: 2px solid #dcdde1;
            }

            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #dcdde1;
                border-radius: 8px;
                margin-top: 15px;
                padding: 20px 10px 15px 10px;
                background-color: #ffffff;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; color: #2c3e50; }
            QTabWidget::pane { border: 1px solid #dcdde1; border-radius: 8px; background: transparent; }
            QTabBar::tab { background: #e1e2e6; padding: 10px 20px; font-size: 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
            QTabBar::tab:selected { background: #ffffff; color: #2980b9; font-weight: bold; border: 1px solid #dcdde1; border-bottom-color: #ffffff; }
            QRadioButton, QCheckBox { font-size: 13px; padding: 4px; color: #2c3e50; font-weight: bold; }
            QRadioButton::indicator { width: 20px; height: 20px; }
            QLabel[class="desc"] {
                color: #7f8c8d;
                font-size: 12px;
                font-weight: normal;
                margin-left: 25px;
                padding-bottom: 5px;
            }
            QComboBox, QDoubleSpinBox {
                font-size: 15px; padding: 5px; border: 1px solid #bdc3c7; border-radius: 6px; background-color: #f8f9fa;
            }
            QComboBox:focus, QDoubleSpinBox:focus {
                border: 2px solid #3498db; background-color: white;
            }
        """)

        self.metals = []
        self.checkboxes = {}

        self.init_ui()
        self.load_saved_settings()

    def showEvent(self, event):
        super().showEvent(event)
        screen_geom = QApplication.primaryScreen().availableGeometry()
        x = screen_geom.x() + (screen_geom.width() - self.width()) // 2
        y = screen_geom.top()
        self.move(x, y)

    def show_virtual_keyboard(self):
        if not self.vkb:
            self.vkb = VirtualKeyboardDialog(self)
        self.vkb.show()
        self.vkb.raise_()

    def close_keyboard(self):
        if self.vkb and self.vkb.isVisible():
            self.vkb.close()

    def accept(self):
        self.save_current_settings()
        self.close_keyboard()
        super().accept()

    def reject(self):
        self.close_keyboard()
        super().reject()

    def init_ui(self):
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.setSpacing(0)

        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setFrameShape(QFrame.NoFrame)

        container_widget = QWidget()
        main_layout = QVBoxLayout(container_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        header_lay = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.balance-scale", color="#f39c12").pixmap(30, 30))
        title_lbl = QLabel("Mise à Jour Sécurisée des Prix")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 900; color: #2c3e50;")
        header_lay.addWidget(icon_lbl)
        header_lay.addWidget(title_lbl)
        header_lay.addStretch()
        main_layout.addLayout(header_lay)

        self.tabs = QTabWidget()
        self.tab_gold = QWidget()
        self.tab_margins_only = QWidget()

        self.tabs.addTab(self.tab_gold, "📈 1. MÀJ Cours de l'Or (Marché)")
        self.tabs.addTab(self.tab_margins_only, "💰 2. Ajuster les Bénéfices Seuls")

        self.setup_gold_tab()
        self.setup_margins_only_tab()
        main_layout.addWidget(self.tabs)

        self.main_scroll_area.setWidget(container_widget)
        dialog_layout.addWidget(self.main_scroll_area)

        footer_frame = QFrame()
        footer_frame.setObjectName("footerFrame")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(15, 15, 15, 15)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(45)
        btn_cancel.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; font-size: 14px; border-radius: 6px;")
        btn_cancel.clicked.connect(self.reject)

        btn_kb = QPushButton("⌨️")
        btn_kb.setFixedSize(55, 45)
        btn_kb.setStyleSheet("background-color: #34495e; color: white; font-size: 20px; border-radius: 6px;")
        btn_kb.clicked.connect(self.show_virtual_keyboard)

        self.btn_apply = QPushButton(" Confirmer et Exécuter")
        self.btn_apply.setIcon(qta.icon("fa5s.shield-alt", color="white"))
        self.btn_apply.setFixedHeight(45)
        self.btn_apply.setStyleSheet("QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 15px; border-radius: 6px; } QPushButton:hover { background-color: #2ecc71; }")
        self.btn_apply.clicked.connect(self.apply_update)

        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_kb)
        footer_layout.addWidget(self.btn_apply, stretch=1)

        dialog_layout.addWidget(footer_frame)

        self.load_combos()

    def setup_gold_tab(self):
        layout = QHBoxLayout(self.tab_gold)
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        ref_group = QGroupBox("1. Définir le nouveau cours")
        ref_layout = QFormLayout(ref_group)
        self.combo_ref_metal = QComboBox(); self.combo_ref_metal.setFixedHeight(35)

        self.spin_ref_price = QDoubleSpinBox()
        self.spin_ref_price.setRange(1, 1000000); self.spin_ref_price.setDecimals(2); self.spin_ref_price.setSuffix(" DA/g"); self.spin_ref_price.setFixedHeight(35)
        self.spin_ref_price.setStyleSheet("QDoubleSpinBox { color: #c0392b; font-weight: bold; }")

        ref_layout.addRow("Métal :", self.combo_ref_metal)
        ref_layout.addRow("Prix (DA) :", self.spin_ref_price)
        left_col.addWidget(ref_group)

        mode_group = QGroupBox("2. Ajustement de la Marge (Optionnel)")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setContentsMargins(15, 25, 15, 15)
        mode_layout.setSpacing(10)

        self.bg_mode = QButtonGroup(self)

        self.rad_all = QRadioButton("Tous les articles (Recommandé)")
        lbl_all = QLabel("Mettre à jour le prix de l'or pour tout le stock (marge fixe et %).")
        lbl_all.setProperty("class", "desc")

        self.rad_percent = QRadioButton("Cibler les articles avec marge en Pourcentage (%)")
        lbl_pct = QLabel("Ne modifiera que les articles configurés en %.")
        lbl_pct.setProperty("class", "desc")

        self.spin_pct_margin = QDoubleSpinBox()
        self.spin_pct_margin.setRange(-100, 500); self.spin_pct_margin.setSuffix(" %"); self.spin_pct_margin.setFixedHeight(30)
        self.spin_pct_margin.setStyleSheet("color: #2980b9; font-weight: bold;")
        self.spin_pct_margin.setEnabled(False) 

        self.rad_fixed = QRadioButton("Cibler les articles avec marge Fixe (DA)")
        lbl_fix = QLabel("Ne modifiera que les articles configurés en DA.")
        lbl_fix.setProperty("class", "desc")

        self.spin_mix_margin = QDoubleSpinBox()
        self.spin_mix_margin.setRange(-1000000, 1000000); self.spin_mix_margin.setSuffix(" DA"); self.spin_mix_margin.setFixedHeight(30)
        self.spin_mix_margin.setStyleSheet("color: #d35400; font-weight: bold;")
        self.spin_mix_margin.setEnabled(False) 

        self.bg_mode.addButton(self.rad_all, 0)
        self.bg_mode.addButton(self.rad_percent, 1)
        self.bg_mode.addButton(self.rad_fixed, 2)
        self.rad_all.setChecked(True) 

        self.bg_mode.buttonClicked.connect(self.toggle_margin_inputs)

        lay_all = QVBoxLayout()
        lay_all.setSpacing(2)
        lay_all.addWidget(self.rad_all)
        lay_all.addWidget(lbl_all)
        mode_layout.addLayout(lay_all)
        mode_layout.addSpacing(5)

        lay_pct = QVBoxLayout()
        lay_pct.setSpacing(2)
        lay_pct.addWidget(self.rad_percent)
        lay_pct.addWidget(lbl_pct)
        spin_pct_lay = QHBoxLayout()
        spin_pct_lay.addSpacing(25)
        spin_pct_lay.addWidget(self.spin_pct_margin)
        lay_pct.addLayout(spin_pct_lay)
        mode_layout.addLayout(lay_pct)
        mode_layout.addSpacing(5)

        lay_fix = QVBoxLayout()
        lay_fix.setSpacing(2)
        lay_fix.addWidget(self.rad_fixed)
        lay_fix.addWidget(lbl_fix)
        spin_fix_lay = QHBoxLayout()
        spin_fix_lay.addSpacing(25)
        spin_fix_lay.addWidget(self.spin_mix_margin)
        lay_fix.addLayout(spin_fix_lay)
        mode_layout.addLayout(lay_fix)

        left_col.addWidget(mode_group)
        left_col.addStretch()

        target_group = QGroupBox("3. Appliquer aux métaux sélectionnés")
        target_layout = QVBoxLayout(target_group)

        self.bg_metal_cat = QButtonGroup(self)
        self.radio_cat_gold = QRadioButton("Or (GOLD)")
        self.radio_cat_silver = QRadioButton("Argent (SILVER)")
        self.radio_cat_gold.setChecked(True)

        self.radio_cat_gold.setStyleSheet("color: #d35400; font-weight: bold;")
        self.radio_cat_silver.setStyleSheet("color: #7f8c8d; font-weight: bold;")

        self.bg_metal_cat.addButton(self.radio_cat_gold, 1)
        self.bg_metal_cat.addButton(self.radio_cat_silver, 2)

        cat_layout = QHBoxLayout()
        cat_layout.addWidget(self.radio_cat_gold)
        cat_layout.addWidget(self.radio_cat_silver)
        target_layout.addLayout(cat_layout)

        self.bg_metal_cat.buttonClicked.connect(self.filter_metals_by_category)

        self.inner_scroll_area = QScrollArea()
        self.inner_scroll_area.setWidgetResizable(True)
        self.inner_scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.inner_scroll_area.setWidget(self.scroll_widget)
        target_layout.addWidget(self.inner_scroll_area)

        right_col.addWidget(target_group)

        layout.addLayout(left_col, stretch=5)
        layout.addLayout(right_col, stretch=4)

    def toggle_margin_inputs(self):
        checked_id = self.bg_mode.checkedId()
        self.spin_pct_margin.setEnabled(checked_id == 1)
        self.spin_mix_margin.setEnabled(checked_id == 2)

    def filter_metals_by_category(self):
        is_gold = self.radio_cat_gold.isChecked()
        target_cat = "GOLD" if is_gold else "SILVER"

        self.combo_ref_metal.clear()
        idx_to_select = 0
        current_idx = 0

        for m in self.metals:
            cat = m.get('metal_category', 'GOLD').upper()
            if cat == target_cat:
                purity = float(m['purity_value'])
                name_full = f"{m['name']} ({purity})"
                self.combo_ref_metal.addItem(name_full, purity)

                if target_cat == "GOLD" and purity == 750:
                    idx_to_select = current_idx
                elif target_cat == "SILVER" and purity == 925:
                    idx_to_select = current_idx
                current_idx += 1

        if self.combo_ref_metal.count() > 0:
            self.combo_ref_metal.setCurrentIndex(idx_to_select)

        for m_id, chk in self.checkboxes.items():
            cat = getattr(chk, 'metal_category', 'GOLD')
            if cat == target_cat:
                chk.setVisible(True)
                chk.setChecked(True)
            else:
                chk.setVisible(False)
                chk.setChecked(False)

    def setup_margins_only_tab(self):
        layout = QHBoxLayout(self.tab_margins_only)
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        target_group = QGroupBox("1. Sélectionner les articles")
        target_layout = QVBoxLayout(target_group)
        self.bg_target = QButtonGroup(self)
        self.radio_all = QRadioButton("Tout le stock"); self.radio_all.setChecked(True)
        self.radio_cat = QRadioButton("Par Catégorie")
        self.radio_metal = QRadioButton("Par Métal")
        self.bg_target.addButton(self.radio_all, 1); self.bg_target.addButton(self.radio_cat, 2); self.bg_target.addButton(self.radio_metal, 3)

        r_lay = QHBoxLayout(); r_lay.addWidget(self.radio_all); r_lay.addWidget(self.radio_cat); r_lay.addWidget(self.radio_metal)
        target_layout.addLayout(r_lay)

        self.combo_cats = QComboBox(); self.combo_cats.setFixedHeight(35); self.combo_cats.setEnabled(False)
        self.combo_metals = QComboBox(); self.combo_metals.setFixedHeight(35); self.combo_metals.setEnabled(False)
        target_layout.addWidget(self.combo_cats); target_layout.addWidget(self.combo_metals)
        left_col.addWidget(target_group)
        left_col.addStretch()
        self.bg_target.buttonClicked.connect(self.on_target_changed)

        op_group = QGroupBox("2. Action directe sur le Bénéfice (Sans toucher l'Or)")
        op_layout = QFormLayout(op_group)
        op_layout.setVerticalSpacing(15)

        self.combo_operation = QComboBox(); self.combo_operation.setFixedHeight(35)
        self.combo_operation.addItems(["Ajustement par Pourcentage (%)", "Montant Fixe (DA)"])
        self.combo_operation.currentIndexChanged.connect(self.on_operation_changed)

        self.spin_value = QDoubleSpinBox(); self.spin_value.setRange(-1000000, 1000000); self.spin_value.setDecimals(2); self.spin_value.setSuffix(" %"); self.spin_value.setFixedHeight(35)
        self.spin_value.setStyleSheet("QDoubleSpinBox { color: #2980b9; font-weight: bold; }")

        op_layout.addRow("Opération :", self.combo_operation)
        op_layout.addRow("Valeur (±) :", self.spin_value)
        right_col.addWidget(op_group)

        lbl_info = QLabel("⚠️ Utile pour faire des soldes ou augmenter les prix de main d'oeuvre sans modifier le prix de base du marché de l'or.")
        lbl_info.setWordWrap(True); lbl_info.setStyleSheet("color: #8e44ad; font-weight: bold; font-size: 13px; margin-top: 10px;")
        right_col.addWidget(lbl_info)
        right_col.addStretch()

        layout.addLayout(left_col, stretch=1)
        layout.addLayout(right_col, stretch=1)

    def load_combos(self):
        try:
            cats = self.manager.categories.get_all_categories()
            for c in cats: self.combo_cats.addItem(c['name'], c['id'])
        except: pass

        try:
            self.metals = self.manager.metal_types.get_all_metal_types()

            for m in self.metals:
                purity = float(m['purity_value'])
                name_full = f"{m['name']} ({purity})"
                m_id = m['id']

                self.combo_metals.addItem(m['name'], m_id)

                chk = QCheckBox(name_full)
                chk.metal_category = m.get('metal_category', 'GOLD').upper()

                self.checkboxes[m_id] = chk
                self.scroll_layout.addWidget(chk)

            self.filter_metals_by_category()

        except Exception as e:
            print(f"Erreur load_combos: {e}")

    def on_target_changed(self):
        checked_id = self.bg_target.checkedId()
        self.combo_cats.setEnabled(checked_id == 2)
        self.combo_metals.setEnabled(checked_id == 3)

    def on_operation_changed(self):
        idx = self.combo_operation.currentIndex()
        if idx == 0: self.spin_value.setSuffix(" %"); self.spin_value.setRange(-99, 500)
        elif idx == 1: self.spin_value.setSuffix(" DA"); self.spin_value.setRange(-1000000, 1000000)

    def save_current_settings(self):
        self.settings.setValue("active_tab", self.tabs.currentIndex())
        self.settings.setValue("ref_price", self.spin_ref_price.value())

        self.settings.setValue("metal_category", self.bg_metal_cat.checkedId())
        self.settings.setValue("ref_metal_index", self.combo_ref_metal.currentIndex())

        self.settings.setValue("margin_target_mode", self.bg_mode.checkedId())

        selected_metals = [m_id for m_id, chk in self.checkboxes.items() if chk.isChecked()]
        self.settings.setValue("selected_metals", selected_metals)

    def load_saved_settings(self):
        self.tabs.setCurrentIndex(self.settings.value("active_tab", 0, type=int))

        saved_price = self.settings.value("ref_price", 0.0, type=float)
        if saved_price > 0: self.spin_ref_price.setValue(saved_price)

        cat_id = self.settings.value("metal_category", 1, type=int)
        if cat_id == 1:
            self.radio_cat_gold.setChecked(True)
        elif cat_id == 2:
            self.radio_cat_silver.setChecked(True)
        self.filter_metals_by_category()

        saved_index = self.settings.value("ref_metal_index", 0, type=int)
        if 0 <= saved_index < self.combo_ref_metal.count():
            self.combo_ref_metal.setCurrentIndex(saved_index)

        saved_mode = self.settings.value("margin_target_mode", 0, type=int) 
        if saved_mode == 0:
            self.rad_all.setChecked(True)
        elif saved_mode == 1:
            self.rad_percent.setChecked(True)
        elif saved_mode == 2:
            self.rad_fixed.setChecked(True)

        if hasattr(self, 'toggle_margin_inputs'):
            self.toggle_margin_inputs()

        self.spin_pct_margin.setValue(0.0)
        self.spin_mix_margin.setValue(0.0)

        saved_metals = self.settings.value("selected_metals", [])
        if saved_metals:
            try:
                saved_metals = [int(m) for m in saved_metals]
                for m_id, chk in self.checkboxes.items():
                    chk.setChecked(m_id in saved_metals)
            except Exception as e:
                pass

    def apply_update(self):
        active_tab = self.tabs.currentIndex()

        if active_tab == 0:
            ref_purity = self.combo_ref_metal.currentData()
            new_price = self.spin_ref_price.value()

            if not ref_purity or new_price <= 0:
                QMessageBox.warning(self, "Erreur", "Veuillez entrer un prix du jour valide.")
                return

            selected_metal_ids = [m_id for m_id, chk in self.checkboxes.items() if chk.isChecked()]
            if not selected_metal_ids:
                QMessageBox.warning(self, "Erreur", "Veuillez sélectionner au moins un métal.")
                return

            mode_id = self.bg_mode.checkedId()

            margin_adj = 0.0
            if mode_id == 1: margin_adj = self.spin_pct_margin.value()
            elif mode_id == 2: margin_adj = self.spin_mix_margin.value()

            msg_desc = "Les marges seront ajustées." if margin_adj != 0 else "Le coût de base de l'or sera actualisé pour le stock sélectionné."

            msg = f"Mettre à jour le cours de base à {new_price} DA/g ({ref_purity}) ?\n\n🛡️ {msg_desc}"

            if QMessageBox.question(self, "Confirmation", msg, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try:
                    affected = 0
                    if mode_id == 0:
                        aff1 = self.manager.inventory.update_prices_by_reference(
                            reference_purity=ref_purity, new_price=new_price,
                            target_metal_ids=selected_metal_ids, target_margin_type='PERCENTAGE',
                            margin_adjustment=0.0
                        )
                        aff2 = self.manager.inventory.update_prices_by_reference(
                            reference_purity=ref_purity, new_price=new_price,
                            target_metal_ids=selected_metal_ids, target_margin_type='FIXED',
                            margin_adjustment=0.0
                        )
                        affected = max(0, aff1 if aff1 else 0) + max(0, aff2 if aff2 else 0)
                    else:
                        target_margin_type = 'PERCENTAGE' if mode_id == 1 else 'FIXED'
                        affected = self.manager.inventory.update_prices_by_reference(
                            reference_purity=ref_purity, new_price=new_price,
                            target_metal_ids=selected_metal_ids, target_margin_type=target_margin_type,
                            margin_adjustment=margin_adj
                        )

                    if affected >= 0:
                        QMessageBox.information(self, "Succès", f"Opération réussie avec succès.\n{affected} article(s) impacté(s).")
                        self.accept()
                    else:
                        QMessageBox.warning(self, "Erreur", "Erreur lors de la mise à jour.")
                except Exception as e:
                    QMessageBox.critical(self, "Erreur Technique", str(e))

        elif active_tab == 1:
            val = self.spin_value.value()
            if val == 0:
                QMessageBox.warning(self, "Erreur", "La valeur ne peut pas être zéro.")
                return

            target_type_id = self.bg_target.checkedId()
            target_type_str = "ALL"
            target_id = None

            if target_type_id == 2:
                target_type_str = "CATEGORY"
                target_id = self.combo_cats.currentData()
            elif target_type_id == 3:
                target_type_str = "METAL"
                target_id = self.combo_metals.currentData()

            operation_type = self.combo_operation.currentIndex()
            is_percentage = (operation_type == 0)
            action_text = "Ajouter" if val > 0 else "Soustraire"
            sym = "%" if is_percentage else "DA"

            msg = f"Voulez-vous vraiment {action_text.lower()} {abs(val)} {sym} aux articles sélectionnés (Sans toucher le coût de l'or) ?"

            if QMessageBox.question(self, "Confirmation", msg, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try:
                    affected = self.manager.inventory.bulk_update_prices(
                        target_type=target_type_str,
                        target_id=target_id,
                        operation_type=operation_type,
                        value=val
                    )

                    if affected >= 0:
                        QMessageBox.information(self, "Succès", f"Bénéfices ajustés.\n{affected} article(s) mis à jour.")
                        self.accept()
                    else:
                        QMessageBox.warning(self, "Erreur", "Erreur lors de la mise à jour.")
                except Exception as e:
                    QMessageBox.critical(self, "Erreur Technique", str(e))