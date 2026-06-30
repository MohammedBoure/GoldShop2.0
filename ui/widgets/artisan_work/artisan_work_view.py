"""
Interface de Gestion des Artisans et Suivi des Travaux
- Système d'onglets (Tabs)
- Interface 100% en Français
- Dialog Opération UX Optimisée (Équilibrage des espaces et couleurs sémantiques)
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QDialog, QMessageBox, QComboBox,
    QLabel, QApplication, QAbstractItemView, QTabWidget,
    QFormLayout, QMenu, QGridLayout, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QBrush, QAction

from ui.deferred_loading import defer_initial_load
from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog
from ui.dialogs.client_selection_dialog import ClientSelectionDialog

# =====================================================================
# Styles CSS
# =====================================================================
EXCEL_STYLE = """
    QTableWidget { background-color: white; gridline-color: #bdc3c7; font-size: 13px; border: 1px solid #bdc3c7; selection-background-color: #0078D7; selection-color: white; }
    QTableWidget::item { padding: 5px 8px; }
    QTableWidget::item:selected { background-color: #0078D7; color: white; }
    QHeaderView::section { background-color: #2c3e50; color: white; font-weight: bold; font-size: 13px; padding: 10px 5px; border: none; }
"""
SEARCH_STYLE = "QLineEdit { font-size: 15px; padding: 10px 15px; border: 2px solid #bdc3c7; border-radius: 8px; background-color: #f8f9fa; } QLineEdit:focus { border: 2px solid #3498db; background-color: white; }"

BTN_ADD_STYLE = "QPushButton { background-color: #2980b9; color: white; font-weight: bold; font-size: 14px; padding: 10px 25px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #2471a3; }"
BTN_GREEN_STYLE = "QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; padding: 10px 25px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #219a52; }"
BTN_RED_STYLE = "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; font-size: 14px; padding: 10px 25px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #c0392b; }"

CONTEXT_MENU_STYLE = "QMenu { background-color: white; border: 2px solid #bdc3c7; border-radius: 8px; padding: 8px; font-size: 14px; font-weight: bold; } QMenu::item { padding: 10px 40px 10px 25px; border-radius: 5px; } QMenu::item:selected { background-color: #0078D7; color: white; }"

TAB_STYLE = """
    QTabWidget::pane { border: 2px solid #bdc3c7; border-radius: 8px; background-color: white; padding: 5px; }
    QTabBar::tab { background-color: #ecf0f1; color: #2c3e50; font-size: 15px; font-weight: bold; padding: 12px 40px; margin-right: 5px; border-top-left-radius: 8px; border-top-right-radius: 8px; border: 2px solid #bdc3c7; border-bottom: none; }
    QTabBar::tab:selected { background-color: white; color: #2980b9; border-color: #2980b9; }
    QTabBar::tab:hover:!selected { background-color: #d5f5e3; }
"""

# =====================================================================
# Styles spécifiques pour la Dialog des Opérations (Sémantique visuelle)
# =====================================================================
LBL_STYLE = "font-size: 14px; font-weight: bold; color: #2c3e50;"
STYLE_TEXT = "font-size: 14px; padding: 8px; border: 2px solid #dcdde1; border-radius: 6px; background-color: #ffffff;"
STYLE_DATE = "font-size: 14px; padding: 8px; border: 2px solid #aed6f1; border-radius: 6px; background-color: #ebf5fb;" # Bleu clair
STYLE_NUM = "font-size: 14px; padding: 8px; border: 2px solid #f9e79f; border-radius: 6px; background-color: #fef9e7;" # Jaune clair
STYLE_RESULT = "font-size: 15px; font-weight: bold; padding: 8px; border: 2px solid #a9dfbf; border-radius: 6px; background-color: #d5f5e3;" # Vert clair

BTN_AUX_STYLE = "QPushButton { border-radius: 5px; font-size: 13px; border: none; padding: 2px; }" # Style de base pour les petits boutons


def safe_float(val):
    try: return float(str(val).replace(' ', '').replace(',', '.'))
    except (ValueError, TypeError): return 0.0


# =====================================================================
# Dialog Artisan
# =====================================================================
class ArtisanDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def __init__(self, record=None, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("Modifier l'Artisan" if record else "Nouvel Artisan")
        self.setFixedSize(500, 280)
        self.setStyleSheet("QDialog { background-color: #ffffff; }")
        self.init_ui()

    def _open_keyboard(self, target):
        target.setFocus(); kb = VirtualKeyboardDialog(self.window()); kb.show(); kb.raise_()

    def _wrap_kb(self, widget):
        lay = QHBoxLayout(); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("⌨"); btn.setFixedSize(32,32); btn.setStyleSheet(BTN_AUX_STYLE + "background-color: #3498db; color: white;")
        btn.clicked.connect(lambda: self._open_keyboard(widget)); lay.addWidget(btn)
        w = QWidget(); w.setLayout(lay); return w

    def init_ui(self):
        # ==========================================
        # التخطيط الرئيسي للتبويب
        # ==========================================
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ==========================================
        # شريط الأدوات العلوي (البحث + الفلاتر + الأزرار)
        # ==========================================
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(10)

        # 1. حقل البحث العام
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher par client, produit ou numéro...")
        self.search_input.setStyleSheet("""
            QLineEdit { 
                font-size: 15px; padding: 10px 15px; border: 2px solid #bdc3c7; 
                border-radius: 8px; background-color: #f8f9fa; 
            } 
            QLineEdit:focus { border: 2px solid #3498db; background-color: white; }
        """)
        self.search_input.textChanged.connect(self.apply_search_filter)
        tools_layout.addWidget(self.search_input, stretch=1)

        # 2. فلتر حالة التسليم (الإضافة المطلوبة)
        self.combo_delivery_filter = QComboBox()
        self.combo_delivery_filter.addItems([
            "📋 Tous les statuts",
            "⏳ Non livrés uniquement",
            "✅ Livrés uniquement"
        ])
        self.combo_delivery_filter.setStyleSheet("""
            QComboBox { 
                font-size: 14px; font-weight: bold; padding: 8px 12px; 
                border: 2px solid #f39c12; border-radius: 8px; 
                background-color: #fef9e7; color: #d68910; min-width: 220px; 
            }
            QComboBox::drop-down { border: none; width: 30px; }
            QComboBox QAbstractItemView { font-size: 14px; padding: 5px; selection-background-color: #0078D7; }
        """)
        # ربط الفلتر بدالة التطبيق
        self.combo_delivery_filter.currentIndexChanged.connect(self.apply_delivery_filter)
        tools_layout.addWidget(self.combo_delivery_filter)

        # 3. زر إضافة حجز جديد
        btn_add = QPushButton("➕ Nouvelle Réservation")
        btn_add.setStyleSheet("""
            QPushButton { 
                background-color: #27ae60; color: white; font-weight: bold; 
                font-size: 14px; padding: 10px 25px; border-radius: 8px; border: none; 
            } 
            QPushButton:hover { background-color: #219a52; }
        """)
        btn_add.clicked.connect(self.open_add_command_dialog)
        tools_layout.addWidget(btn_add)

        main_layout.addLayout(tools_layout)

        # ==========================================
        # جدول المنتجات المحجوزة
        # ==========================================
        self.table_commands = QTableWidget(0, 7)
        # 🟢 تأكد من أن ترتيب هذه الأعمدة يطابق ترتيب الجدول في الكود الخاص بك
        self.table_commands.setHorizontalHeaderLabels([
            "N° Réservation", 
            "Client", 
            "Produit / Objet", 
            "Poids (g)", 
            "Date prévue", 
            "Statut",      # 🟢 العمود رقم 5 (الفهرس 5) هو الذي سنفلتر بناءً عليه
            "Prix (DA)"
        ])
        self.table_commands.setStyleSheet("""
            QTableWidget { 
                background-color: white; gridline-color: #bdc3c7; font-size: 13px; 
                border: 1px solid #bdc3c7; selection-background-color: #0078D7; selection-color: white; 
            }
            QTableWidget::item { padding: 5px 8px; }
            QTableWidget::item:selected { background-color: #0078D7; color: white; }
            QHeaderView::section { 
                background-color: #2c3e50; color: white; font-weight: bold; 
                font-size: 13px; padding: 10px 5px; border: none; 
            }
        """)
        
        self.table_commands.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_commands.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_commands.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_commands.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_commands.customContextMenuRequested.connect(self.show_context_menu)
        self.table_commands.verticalHeader().setVisible(False)
        self.table_commands.verticalHeader().setDefaultSectionSize(40)

        # ضبط عرض الأعمدة
        header = self.table_commands.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # N°
        header.setSectionResizeMode(1, QHeaderView.Stretch)          # Client ( يتمدد)
        header.setSectionResizeMode(2, QHeaderView.Stretch)          # Produit ( يتمدد)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Poids
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Date
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Statut
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Prix

        main_layout.addWidget(self.table_commands)


    # =====================================================================
    # دوال الفلترة (يجب إضافتها في نفس الكلاس)
    # =====================================================================

    def apply_delivery_filter(self):
        """تطبيق فلتر حالة التسليم"""
        selected_text = self.combo_delivery_filter.currentText()
        
        # 🟢 رقم عمود "الstattut" في الجدول (تبدأ من 0، هنا هو العمود السادس أي 5)
        STATUS_COL_INDEX = 5 
        
        for row in range(self.table_commands.rowCount()):
            item = self.table_commands.item(row, STATUS_COL_INDEX)
            if not item:
                continue
                
            status_text = item.text().strip().lower()

            if "Tous" in selected_text:
                self.table_commands.setRowHidden(row, False)
                
            elif "Non livrés" in selected_text:
                # إخفاء فقط إذا كان النص يحتوي على كلمة "livré" أو "delivered"
                is_delivered = "livré" in status_text or "delivered" in status_text
                self.table_commands.setRowHidden(row, is_delivered)
                
            elif "Livrés uniquement" in selected_text:
                # إظهار فقط إذا كان يحتوي على "livré"
                is_delivered = "livré" in status_text or "delivered" in status_text
                self.table_commands.setRowHidden(row, not is_delivered)

    def apply_search_filter(self, text):
        """فلتر البحث النصي (يعمل مع فلتر التسليم معاً)"""
        search_text = text.strip().lower()
        for row in range(self.table_commands.rowCount()):
            # نجمع نص كل الأعمدة في الصف للبحث فيها
            row_text = ""
            for col in range(self.table_commands.columnCount()):
                item = self.table_commands.item(row, col)
                if item:
                    row_text += " " + item.text().lower()
            
            match_search = search_text in row_text
            self.table_commands.setRowHidden(row, not match_search)
            
        # إعادة تطبيق فلتر التسليم فوق فلتر البحث لكي لا يتعارضا
        self.apply_delivery_filter()

    def get_data(self):
        return {"id": self.record['id'] if self.record else None, "name": self.inp_name.text().strip(), "phone": self.inp_phone.text().strip(), "notes": self.inp_notes.text().strip()}


# =====================================================================
# Dialog Opération (Design UX Équilibré)
# =====================================================================
class OrderDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, 30)

    def __init__(self, manager, artisan_id, record=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.artisan_id = artisan_id
        self.record = record
        self.selected_client_id = record.get('client_id') if record else None
        self.selected_client_name = ""
        
        self.setWindowTitle("Modifier l'Opération" if record else "Nouvelle Opération")
        self.setFixedSize(780, 520) # Taille ajustée pour un aspect compact et équilibré
        self.setStyleSheet("QDialog { background-color: #f4f6f7; }")
        self.init_ui()

    def _open_keyboard(self, target):
        target.setFocus(); kb = VirtualKeyboardDialog(self.window()); kb.show(); kb.raise_()

    def _open_numpad(self, target):
        target.setFocus()
        numpad = VirtualNumpad(title="Saisie", mode="direct", target_widget=target, allow_decimal=True, allow_leading_zero=True, parent=self)
        numpad.show(); numpad.raise_()

    def _wrap_kb(self, widget):
        lay = QHBoxLayout(); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("⌨"); btn.setFixedSize(32,32); btn.setStyleSheet(BTN_AUX_STYLE + "background-color: #3498db; color: white;")
        btn.clicked.connect(lambda: self._open_keyboard(widget)); lay.addWidget(btn)
        w = QWidget(); w.setLayout(lay); return w

    def _wrap_num(self, widget):
        lay = QHBoxLayout(); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("🔢"); btn.setFixedSize(32,32); btn.setStyleSheet(BTN_AUX_STYLE + "background-color: #8e44ad; color: white;")
        btn.clicked.connect(lambda: self._open_numpad(widget)); lay.addWidget(btn)
        w = QWidget(); w.setLayout(lay); return w

    def _open_client_selector(self):
        dlg = ClientSelectionDialog(self.manager, self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_client_id:
            self.selected_client_id = dlg.selected_client_id
            try:
                c_data = self.manager.db.cursor.execute("SELECT name FROM Clients WHERE id=%s", (self.selected_client_id,)).fetchone()
                if c_data:
                    self.selected_client_name = c_data[0]
                    self.btn_select_client.setText(f"✅ {self.selected_client_name}")
                    self.btn_select_client.setStyleSheet("background-color: #d5f5e3; color: #1e8449; font-weight: bold; font-size: 14px; padding: 10px; border-radius: 6px; border: 2px solid #27ae60;")
            except Exception as e:
                logging.error(f"Error fetching client name: {e}")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 10)
        main_layout.setSpacing(15)

        # --- 1. Section Client (Pleine largeur) ---
        grp_client = QGroupBox("Client")
        grp_client.setStyleSheet("QGroupBox { font-size: 15px; font-weight: bold; color: #2c3e50; border: 2px solid #dcdde1; border-radius: 8px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px; }")
        client_lay = QHBoxLayout(grp_client)
        client_lay.setContentsMargins(10, 10, 10, 10)

        self.btn_select_client = QPushButton("🔍  Cliquer pour sélectionner un client")
        self.btn_select_client.setCursor(Qt.PointingHandCursor)
        self.btn_select_client.setMinimumHeight(40)
        self.btn_select_client.setStyleSheet("background-color: #eaf2f8; color: #2980b9; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 6px; border: 2px dashed #3498db;")
        self.btn_select_client.clicked.connect(self._open_client_selector)
        client_lay.addWidget(self.btn_select_client)

        if self.selected_client_id:
            try:
                c_data = self.manager.db.cursor.execute("SELECT name FROM Clients WHERE id=%s", (self.selected_client_id,)).fetchone()
                if c_data:
                    self.selected_client_name = c_data[0]
                    self.btn_select_client.setText(f"✅ {self.selected_client_name}")
                    self.btn_select_client.setStyleSheet("background-color: #d5f5e3; color: #1e8449; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 6px; border: 2px solid #27ae60;")
            except: pass
        main_layout.addWidget(grp_client)

        # --- 2. Grille principale (Équilibrée) ---
        grid = QGridLayout()
        grid.setSpacing(12) # Espacement uniforme entre les lignes et colonnes
        grid.setColumnStretch(0, 0) # Labels
        grid.setColumnStretch(1, 1) # Champs courts
        grid.setColumnStretch(2, 0) # Labels
        grid.setColumnStretch(3, 1) # Champs courts/longs

        # Ligne 0 : Identifiant & Objet (L'objet prend plus d'espace)
        lbl_num = QLabel("N° Opération :"); lbl_num.setStyleSheet(LBL_STYLE); lbl_num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_num, 0, 0)
        
        self.inp_numero = QLineEdit(); self.inp_numero.setStyleSheet(STYLE_TEXT); self.inp_numero.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_numero.setText(str(self.record.get('numero', '')))
        else: self.inp_numero.setText("x")
        grid.addWidget(self._wrap_kb(self.inp_numero), 0, 1)

        lbl_obj = QLabel("Objet / Description :"); lbl_obj.setStyleSheet(LBL_STYLE); lbl_obj.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_obj, 0, 2)
        
        self.inp_obj = QLineEdit(); self.inp_obj.setStyleSheet(STYLE_TEXT)
        self.inp_obj.setPlaceholderText("Ex: Bague, Chaîne, Réparation...")
        if self.record: self.inp_obj.setText(str(self.record.get('obj', '')))
        grid.addWidget(self._wrap_kb(self.inp_obj), 0, 3)

        # Ligne 1 : Poids & Date Remis
        lbl_poid = QLabel("Poids (g) :"); lbl_poid.setStyleSheet(LBL_STYLE); lbl_poid.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_poid, 1, 0)
        
        self.inp_poid = QLineEdit(); self.inp_poid.setStyleSheet(STYLE_NUM); self.inp_poid.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_poid.setText(str(self.record.get('poid', '')))
        grid.addWidget(self._wrap_num(self.inp_poid), 1, 1)

        lbl_remis = QLabel("Date remis :"); lbl_remis.setStyleSheet(LBL_STYLE); lbl_remis.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_remis, 1, 2)
        
        self.inp_date_remis = QLineEdit(); self.inp_date_remis.setStyleSheet(STYLE_DATE); self.inp_date_remis.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_date_remis.setText(str(self.record.get('date_remis', '')))
        grid.addWidget(self._wrap_kb(self.inp_date_remis), 1, 3)

        # Ligne 2 : Dates Reçue & Sortie
        lbl_recue = QLabel("Date reçue :"); lbl_recue.setStyleSheet(LBL_STYLE); lbl_recue.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_recue, 2, 0)
        
        self.inp_date_recue = QLineEdit(); self.inp_date_recue.setStyleSheet(STYLE_DATE); self.inp_date_recue.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_date_recue.setText(str(self.record.get('date_recue', '')))
        grid.addWidget(self._wrap_kb(self.inp_date_recue), 2, 1)

        lbl_sortie = QLabel("Date sortie :"); lbl_sortie.setStyleSheet(LBL_STYLE); lbl_sortie.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_sortie, 2, 2)
        
        self.inp_date_sortie = QLineEdit(); self.inp_date_sortie.setStyleSheet(STYLE_DATE); self.inp_date_sortie.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_date_sortie.setText(str(self.record.get('date_sortie', '')))
        grid.addWidget(self._wrap_kb(self.inp_date_sortie), 2, 3)

        # Ligne 3 : Prix & Vente
        lbl_prix = QLabel("Prix (Coût) :"); lbl_prix.setStyleSheet(LBL_STYLE); lbl_prix.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_prix, 3, 0)
        
        self.inp_prix = QLineEdit(); self.inp_prix.setStyleSheet(STYLE_NUM); self.inp_prix.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_prix.setText(str(self.record.get('prix', '')))
        grid.addWidget(self._wrap_num(self.inp_prix), 3, 1)

        lbl_vente = QLabel("Prix Vente :"); lbl_vente.setStyleSheet(LBL_STYLE); lbl_vente.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_vente, 3, 2)
        
        self.inp_vente = QLineEdit(); self.inp_vente.setStyleSheet(STYLE_NUM); self.inp_vente.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_vente.setText(str(self.record.get('vente', '')))
        grid.addWidget(self._wrap_num(self.inp_vente), 3, 3)

        # Ligne 4 : Différence (Étendue sur 2 colonnes pour ressembler à un résultat)
        lbl_diff = QLabel("Différence (Bénéfice) :"); lbl_diff.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e8449;"); lbl_diff.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_diff, 4, 0, 1, 2) # Prend la place de 2 colonnes
        
        self.inp_diff = QLineEdit(); self.inp_diff.setStyleSheet(STYLE_RESULT); self.inp_diff.setAlignment(Qt.AlignCenter)
        self.inp_diff.setReadOnly(True)
        if self.record: self.inp_diff.setText(str(self.record.get('diff', '')))
        grid.addWidget(self._wrap_num(self.inp_diff), 4, 2, 1, 2) # Prend la place de 2 colonnes

        # Connecter pour le calcul auto
        self.inp_prix.textChanged.connect(self.calc_diff)
        self.inp_vente.textChanged.connect(self.calc_diff)

        main_layout.addLayout(grid)

        # --- 3. Boutons ---
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(20)
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(45)
        btn_cancel.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; font-weight: bold; font-size: 15px; padding: 0 30px; border-radius: 8px; border: none; } QPushButton:hover { background-color: #7f8c8d; }")
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)

        btn_lay.addStretch()

        btn_save = QPushButton("Enregistrer l'Opération")
        btn_save.setFixedHeight(45)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 16px; padding: 0 40px; border-radius: 8px; border: none; } QPushButton:hover { background-color: #219a52; }")
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)

        main_layout.addLayout(btn_lay)

    def calc_diff(self):
        try:
            prix = float(self.inp_prix.text().replace(' ', '').replace(',', '.') or 0)
            vente = float(self.inp_vente.text().replace(' ', '').replace(',', '.') or 0)
            diff = vente - prix
            self.inp_diff.setText(f"{diff:,.2f}")
            # Changer la couleur du résultat en fonction du signe
            if diff > 0:
                self.inp_diff.setStyleSheet("font-size: 15px; font-weight: bold; padding: 8px; border: 2px solid #27ae60; border-radius: 6px; background-color: #d5f5e3;")
            elif diff < 0:
                self.inp_diff.setStyleSheet("font-size: 15px; font-weight: bold; padding: 8px; border: 2px solid #e74c3c; border-radius: 6px; background-color: #fadbd8;")
            else:
                self.inp_diff.setStyleSheet(STYLE_RESULT)
        except ValueError:
            self.inp_diff.setText("")

    def get_data(self):
        return {
            "id": self.record['id'] if self.record else None,
            "artisan_id": self.artisan_id,
            "client_id": self.selected_client_id,
            "numero": self.inp_numero.text().strip(),
            "date_remis": self.inp_date_remis.text().strip(),
            "obj": self.inp_obj.text().strip(),
            "poid": self.inp_poid.text().strip(),
            "date_recue": self.inp_date_recue.text().strip(),
            "date_sortie": self.inp_date_sortie.text().strip(),
            "prix": self.inp_prix.text().strip(),
            "vente": self.inp_vente.text().strip(),
            "diff": self.inp_diff.text().strip()
        }


# =====================================================================
# Vue Principale avec Onglets
# =====================================================================
class ArtisanWorkView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_orders_data = []
        self.current_artisan_id = None
        self.init_ui()
        defer_initial_load(self, self._initial_load)

    def _initial_load(self):
        self.load_artisan_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.lbl_title = QLabel("Gestion des Artisans & Suivi des Travaux")
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: white; background-color: #2c3e50; padding: 15px; border-radius: 8px;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)
        
        self.tab_artisans = QWidget()
        self.setup_artisans_tab()
        self.tabs.addTab(self.tab_artisans, "list  Gestion des Artisans")

        self.tab_orders = QWidget()
        self.setup_orders_tab()
        self.tabs.addTab(self.tab_orders, "tasks  Suivi des Travaux")

        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs)

    # ==========================================
    # Onglet Artisans
    # ==========================================
    def setup_artisans_tab(self):
        layout = QVBoxLayout(self.tab_artisans)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tools_lay = QHBoxLayout(); tools_lay.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher un artisan par nom ou téléphone...")
        self.search_input.setStyleSheet(SEARCH_STYLE)
        self.search_input.textChanged.connect(self.filter_artisan_table)
        tools_lay.addWidget(self.search_input, stretch=1)

        for text, style, func in [("Ajouter un Artisan", BTN_GREEN_STYLE, self.open_add_artisan_dialog), ("Modifier", BTN_ADD_STYLE, self.open_edit_artisan_dialog), ("Supprimer", BTN_RED_STYLE, self.delete_selected_artisan)]:
            btn = QPushButton(text); btn.setStyleSheet(style); btn.clicked.connect(func); tools_lay.addWidget(btn)
        layout.addLayout(tools_lay)

        self.table_artisans = QTableWidget(0, 4)
        self.table_artisans.setHorizontalHeaderLabels(["N°", "Nom de l'Artisan", "Téléphone", "Notes"])
        self.table_artisans.setStyleSheet(EXCEL_STYLE)
        self.table_artisans.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_artisans.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_artisans.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_artisans.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_artisans.customContextMenuRequested.connect(self.show_artisan_context_menu)
        self.table_artisans.verticalHeader().setVisible(False)
        self.table_artisans.verticalHeader().setDefaultSectionSize(40)

        hh = self.table_artisans.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents); hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents); hh.setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.table_artisans)

    # ==========================================
    # Onglet Travaux
    # ==========================================
    def setup_orders_tab(self):
        layout = QVBoxLayout(self.tab_orders)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        selector_lay = QHBoxLayout(); selector_lay.setSpacing(15)
        
        lbl = QLabel("<b>Artisan :</b>"); lbl.setStyleSheet("font-size: 16px; color: #2c3e50;")
        selector_lay.addWidget(lbl)
        
        self.combo_artisan = QLineEdit(); self.combo_artisan.setReadOnly(True)
        self.combo_artisan.setPlaceholderText("Sélectionnez un artisan depuis le premier onglet...")
        self.combo_artisan.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px; border: 2px solid #f39c12; border-radius: 8px; background-color: #fef9e7; color: #d68910;")
        selector_lay.addWidget(self.combo_artisan, stretch=1)

        btn_add_order = QPushButton("Ajouter une Opération"); btn_add_order.setStyleSheet(BTN_GREEN_STYLE)
        btn_add_order.clicked.connect(self.open_add_order_dialog); selector_lay.addWidget(btn_add_order)
        layout.addLayout(selector_lay)

        self.table_orders = QTableWidget(0, 10)
        self.table_orders.setHorizontalHeaderLabels(["N°", "Client", "Date remis", "Objet", "Poids", "Date reçue", "Date sortie", "Prix", "Vente", "Diff"])
        self.table_orders.setStyleSheet(EXCEL_STYLE)
        self.table_orders.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_orders.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_orders.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_orders.customContextMenuRequested.connect(self.show_order_context_menu)
        self.table_orders.verticalHeader().setVisible(False)
        self.table_orders.verticalHeader().setDefaultSectionSize(35)

        hh2 = self.table_orders.horizontalHeader()
        hh2.setSectionResizeMode(0, QHeaderView.ResizeToContents); hh2.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, 10): hh2.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        layout.addWidget(self.table_orders)

    def on_tab_changed(self, index):
        if index == 0: self.lbl_title.setText("Gestion des Artisans & Suivi des Travaux")
        elif index == 1: self.lbl_title.setText(f"Travaux de : {self.combo_artisan.text()}" if self.current_artisan_id else "Suivi des Travaux (Aucun artisan sélectionné)")

    # ==========================================
    # Logique Artisans
    # ==========================================
    def load_artisan_data(self):
        artisans = self.manager.artisan_work.get_all_artisans()
        self.table_artisans.setRowCount(0)
        for idx, a in enumerate(artisans, start=1):
            row = self.table_artisans.rowCount(); self.table_artisans.insertRow(row)
            for col, key in enumerate(["id_count", "name", "phone", "notes"]):
                val = str(idx) if key == "id_count" else str(a.get(key) or '')
                self.table_artisans.setItem(row, col, QTableWidgetItem(val))
                self.table_artisans.item(row, col).setData(Qt.UserRole, a['id'])

    def filter_artisan_table(self, text):
        search_text = text.strip().lower()
        for row in range(self.table_artisans.rowCount()):
            name = self.table_artisans.item(row, 1).text().lower()
            phone = self.table_artisans.item(row, 2).text().lower()
            self.table_artisans.setRowHidden(row, not (search_text in name or search_text in phone))

    def get_selected_artisan_id(self):
        row = self.table_artisans.currentRow()
        return self.table_artisans.item(row, 0).data(Qt.UserRole) if row >= 0 else None

    def select_artisan_for_work(self):
        artisan_id = self.get_selected_artisan_id()
        if artisan_id:
            self.current_artisan_id = artisan_id
            row = self.table_artisans.currentRow()
            name = self.table_artisans.item(row, 1).text()
            self.combo_artisan.setText(name)
            self.combo_artisan.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px; border: 2px solid #27ae60; border-radius: 8px; background-color: #d5f5e3; color: #1e8449;")
            self.load_orders()
            self.tabs.setCurrentIndex(1)

    def show_artisan_context_menu(self, pos):
        row = self.table_artisans.rowAt(pos.y())
        if row < 0: return
        self.table_artisans.selectRow(row)
        menu = QMenu(self); menu.setStyleSheet(CONTEXT_MENU_STYLE)
        menu.addAction("Voir les travaux", self.select_artisan_for_work)
        menu.addSeparator()
        menu.addAction("Modifier", self.open_edit_artisan_dialog)
        menu.addAction("Supprimer", self.delete_selected_artisan)
        menu.exec_(self.table_artisans.viewport().mapToGlobal(pos))

    def open_add_artisan_dialog(self):
        dlg = ArtisanDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            if not d['name']: return QMessageBox.warning(self, "Attention", "Le nom est obligatoire.")
            self.manager.artisan_work.add_artisan(d['name'], d.get('notes', ''), d.get('phone', ''))
            self.load_artisan_data(); self.search_input.clear()

    def open_edit_artisan_dialog(self):
        artisan_id = self.get_selected_artisan_id()
        if not artisan_id: return QMessageBox.warning(self, "Attention", "Veuillez sélectionner un artisan.")
        record = None
        for row in range(self.table_artisans.rowCount()):
            if self.table_artisans.item(row, 0).data(Qt.UserRole) == artisan_id:
                record = {'id': artisan_id, 'name': self.table_artisans.item(row, 1).text(), 'phone': self.table_artisans.item(row, 2).text(), 'notes': self.table_artisans.item(row, 3).text()}
                break
        if not record: return
        dlg = ArtisanDialog(record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            if not d['name']: return QMessageBox.warning(self, "Attention", "Le nom est obligatoire.")
            self.manager.artisan_work.update_artisan(d['id'], d['name'], d.get('notes', ''), d.get('phone', ''))
            self.load_artisan_data(); self.search_input.clear()

    def delete_selected_artisan(self):
        artisan_id = self.get_selected_artisan_id()
        if not artisan_id: return QMessageBox.warning(self, "Attention", "Veuillez sélectionner un artisan.")
        if QMessageBox.question(self, "Confirmer", "Supprimer cet artisan et tous ses travaux liés ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.artisan_work.delete_artisan(artisan_id)
            self.load_artisan_data(); self.table_orders.setRowCount(0)
            self.current_artisan_id = None
            self.combo_artisan.setText("")
            self.combo_artisan.setPlaceholderText("Sélectionnez un artisan depuis le premier onglet...")
            self.combo_artisan.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px; border: 2px solid #f39c12; border-radius: 8px; background-color: #fef9e7; color: #d68910;")

    # ==========================================
    # Logique Opérations
    # ==========================================
    def show_order_context_menu(self, pos):
        row = self.table_orders.rowAt(pos.y())
        if row < 0: return
        record = self.current_orders_data[row] if row < len(self.current_orders_data) else None
        if not record: return
        menu = QMenu(self); menu.setStyleSheet(CONTEXT_MENU_STYLE)
        menu.addAction("Modifier cette ligne", lambda: self.open_edit_order_dialog(record))
        menu.addAction("Supprimer cette ligne", lambda: self.delete_order(record['id']))
        menu.exec_(self.table_orders.viewport().mapToGlobal(pos))

    def _render_orders_table(self, records):
        self.table_orders.setRowCount(0)
        total_prix = total_vente = total_diff = 0.0
        for r in records:
            row = self.table_orders.rowCount(); self.table_orders.insertRow(row)
            client_name = "Non défini"
            if r.get('client_id'):
                try:
                    c_data = self.manager.db.cursor.execute("SELECT name FROM Clients WHERE id=%s", (r['client_id'],)).fetchone()
                    if c_data: client_name = c_data[0]
                except: pass
            values = [r.get('numero', ''), client_name, r.get('date_remis', ''), r.get('obj', ''), r.get('poid', ''), r.get('date_recue', ''), r.get('date_sortie', ''), r.get('prix', ''), r.get('vente', ''), r.get('diff', '')]
            for i, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if i in [0, 4, 7, 8, 9]: item.setTextAlignment(Qt.AlignCenter)
                self.table_orders.setItem(row, i, item)
            total_prix += safe_float(r.get('prix', 0)); total_vente += safe_float(r.get('vente', 0)); total_diff += safe_float(r.get('diff', 0))
        if records:
            row = self.table_orders.rowCount(); self.table_orders.insertRow(row)
            it_lbl = QTableWidgetItem("TOTAUX :"); it_lbl.setTextAlignment(Qt.AlignCenter)
            it_lbl.setBackground(QBrush(QColor("#2c3e50"))); it_lbl.setForeground(QBrush(QColor("white"))); it_lbl.setFont(QFont("", 11, QFont.Bold))
            self.table_orders.setItem(row, 6, it_lbl)
            for i, val in enumerate([total_prix, total_vente, total_diff]):
                it = QTableWidgetItem(f"{val:,.2f}"); it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(QBrush(QColor("#2c3e50"))); it.setForeground(QBrush(QColor("#2ecc71" if val >= 0 else "#e74c3c"))); it.setFont(QFont("", 12, QFont.Bold))
                self.table_orders.setItem(row, 7 + i, it)

    def load_orders(self):
        if not self.current_artisan_id: return
        self.current_orders_data = self.manager.artisan_work.get_orders_by_artisan(self.current_artisan_id)
        self._render_orders_table(self.current_orders_data)

    def open_add_order_dialog(self):
        if not self.current_artisan_id: return QMessageBox.warning(self, "Attention", "Sélectionnez d'abord un artisan.")
        dlg = OrderDialog(manager=self.manager, artisan_id=self.current_artisan_id, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.artisan_work.add_order(d['artisan_id'], d['client_id'], d['numero'], d['date_remis'], d['obj'], d['poid'], d['date_recue'], d['date_sortie'], d['prix'], d['vente'], d['diff'])
            self.load_orders()

    def open_edit_order_dialog(self, record):
        dlg = OrderDialog(manager=self.manager, artisan_id=record['artisan_id'], record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.artisan_work.update_order(d['id'], d['artisan_id'], d['client_id'], d['numero'], d['date_remis'], d['obj'], d['poid'], d['date_recue'], d['date_sortie'], d['prix'], d['vente'], d['diff'])
            self.load_orders()

    def delete_order(self, rid):
        if QMessageBox.question(self, "Confirmer", "Supprimer cette ligne ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.artisan_work.delete_order(rid); self.load_orders()
