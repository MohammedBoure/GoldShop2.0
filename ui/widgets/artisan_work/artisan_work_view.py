"""
Interface de Gestion de l'Atelier (Réception & Suivi des Travaux Artisans)
- Conformité TOTALE (100%) avec le modèle Excel de Production :
  Colonnes : [numero | Nom | Tel : | date remis | Obj | Poid | Date Reçue | Date Sortie | Prix (Façon) | Prix (Client) | Diff | Statut | Artisan]
- Ligne des Totaux permanente et parfaitement alignée en bas de tableau
- Conservation stricte des Numéros Uniques et des Statuts
- Simplification du Répertoire Artisans (Ajout, Modification, Suppression et Feuille de Production uniquement)
- Optimisation maximale de l'expérience utilisateur (UX) : Boutons raccourcis "📅 Aujourd'hui" & Calendrier "📆" pour les dates
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QDialog, QMessageBox, QComboBox,
    QLabel, QApplication, QAbstractItemView, QTabWidget,
    QFormLayout, QMenu, QGridLayout, QGroupBox, QCalendarWidget
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QBrush

from ui.deferred_loading import defer_initial_load
from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog
from ui.dialogs.client_selection_dialog import ClientSelectionDialog

# =====================================================================
# Styles CSS & Statuts (Thème Production Excel #00796B)
# =====================================================================
EXCEL_STYLE = """
    QTableWidget { background-color: white; gridline-color: #cbd5df; font-size: 13px; border: 1px solid #cbd5df; selection-background-color: #d1d8e0; selection-color: #1f2937; }
    QTableWidget::item { padding: 6px 8px; }
    QTableWidget::item:selected { background-color: #d1d8e0; color: #1f2937; }
    QHeaderView::section { background-color: #0f8f83; color: white; font-weight: bold; font-size: 13px; padding: 8px 5px; border: 1px solid #0b776d; }
"""
SEARCH_STYLE = "QLineEdit { font-size: 14px; padding: 8px 12px; border: 1px solid #cbd5df; border-radius: 6px; background-color: #ffffff; } QLineEdit:focus { border: 2px solid #0f8f83; background-color: white; }"

BTN_ADD_STYLE = "QPushButton { background-color: #2980b9; color: white; font-weight: bold; font-size: 14px; padding: 8px 16px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #2471a3; }"
BTN_GREEN_STYLE = "QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; padding: 8px 16px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #219a52; }"
BTN_RED_STYLE = "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; font-size: 14px; padding: 8px 16px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #c0392b; }"

CONTEXT_MENU_STYLE = "QMenu { background-color: white; border: 1px solid #cbd5df; border-radius: 6px; padding: 6px; font-size: 14px; font-weight: bold; } QMenu::item { padding: 8px 30px 8px 20px; border-radius: 4px; } QMenu::item:selected { background-color: #0f8f83; color: white; }"

TAB_STYLE = """
    QTabWidget::pane { border: 1px solid #cbd5df; border-radius: 6px; background-color: white; padding: 4px; }
    QTabBar::tab { background-color: #edf2f6; color: #526170; font-size: 14px; font-weight: bold; padding: 10px 25px; margin-right: 4px; border-top-left-radius: 6px; border-top-right-radius: 6px; border: 1px solid #cbd5df; border-bottom: none; }
    QTabBar::tab:selected { background-color: #ffffff; color: #075f58; border-top: 3px solid #0f8f83; }
    QTabBar::tab:hover:!selected { background-color: #f7f9fb; color: #24313f; }
"""

LBL_STYLE = "font-size: 14px; font-weight: bold; color: #2c3e50;"
STYLE_TEXT = "font-size: 14px; padding: 8px; border: 2px solid #dcdde1; border-radius: 6px; background-color: #ffffff;"
STYLE_DATE = "font-size: 14px; padding: 8px; border: 2px solid #aed6f1; border-radius: 6px; background-color: #ebf5fb;"
STYLE_NUM = "font-size: 14px; padding: 8px; border: 2px solid #f9e79f; border-radius: 6px; background-color: #fef9e7;"
STYLE_RESULT = "font-size: 15px; font-weight: bold; padding: 8px; border: 2px solid #a9dfbf; border-radius: 6px; background-color: #d5f5e3;"

BTN_AUX_STYLE = "QPushButton { border-radius: 5px; font-size: 13px; border: none; padding: 2px; }"

STATUS_MAP = {
    "RECEPTION": ("🟢 Au Réceptionniste", "#27ae60", "#d5f5e3"),
    "CHEZ_ARTISAN": ("🟡 Chez l'Artisan", "#d68910", "#fef9e7"),
    "RETOUR_ARTISAN": ("🔵 Retourné au Magasin", "#2980b9", "#ebf5fb"),
    "LIVRE": ("✅ Livré au Client", "#7f8c8d", "#eaecee")
}


def safe_float(val):
    try: return float(str(val).replace(' ', '').replace(',', '.'))
    except (ValueError, TypeError): return 0.0


# =====================================================================
# Dialog Calendar Picker (Sélection de Date Popup UX)
# =====================================================================
class DatePickerDialog(QDialog):
    def __init__(self, current_date_str="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner une date 📅")
        self.setFixedSize(340, 300)
        self.setStyleSheet("QDialog { background-color: white; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        
        if current_date_str:
            qdate = QDate.fromString(current_date_str, "yyyy-MM-dd")
            if qdate.isValid():
                self.calendar.setSelectedDate(qdate)
                
        layout.addWidget(self.calendar)
        
        btn_lay = QHBoxLayout()
        btn_today = QPushButton("📅 Aujourd'hui")
        btn_today.setStyleSheet(BTN_ADD_STYLE)
        btn_today.clicked.connect(self._select_today)
        btn_lay.addWidget(btn_today)
        
        btn_ok = QPushButton("OK")
        btn_ok.setStyleSheet(BTN_GREEN_STYLE)
        btn_ok.clicked.connect(self.accept)
        btn_lay.addWidget(btn_ok)
        
        layout.addLayout(btn_lay)

    def _select_today(self):
        self.calendar.setSelectedDate(QDate.currentDate())
        self.accept()

    def get_selected_date(self):
        return self.calendar.selectedDate().toString("yyyy-MM-dd")


# =====================================================================
# Dialog Artisan (Création / Modification)
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(15)

        form = QFormLayout()
        form.setSpacing(12)

        self.inp_name = QLineEdit()
        self.inp_name.setStyleSheet(STYLE_TEXT)
        if self.record: self.inp_name.setText(str(self.record.get('name', '')))
        form.addRow("👤 Nom de l'Artisan :", self._wrap_kb(self.inp_name))

        self.inp_phone = QLineEdit()
        self.inp_phone.setStyleSheet(STYLE_TEXT)
        if self.record: self.inp_phone.setText(str(self.record.get('phone', '')))
        form.addRow("📞 Téléphone :", self._wrap_kb(self.inp_phone))

        self.inp_notes = QLineEdit()
        self.inp_notes.setStyleSheet(STYLE_TEXT)
        if self.record: self.inp_notes.setText(str(self.record.get('notes', '')))
        form.addRow("📝 Notes :", self._wrap_kb(self.inp_notes))

        layout.addLayout(form)
        layout.addStretch()

        btn_lay = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet(BTN_RED_STYLE)
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)

        btn_save = QPushButton("Enregistrer")
        btn_save.setFixedHeight(40)
        btn_save.setStyleSheet(BTN_GREEN_STYLE)
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)

        layout.addLayout(btn_lay)

    def get_data(self):
        return {
            "id": self.record['id'] if self.record else None,
            "name": self.inp_name.text().strip(),
            "phone": self.inp_phone.text().strip(),
            "notes": self.inp_notes.text().strip()
        }


# =====================================================================
# Dialog Feuille de Production Individuelle de l'Artisan
# (Tableau de Production Excel Réel 100% Conforme)
# =====================================================================
class ArtisanStatementDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, 20)

    def __init__(self, manager, artisan, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.artisan = artisan
        self.setWindowTitle(f"📜 Feuille de Production - Artisan : {artisan.get('name', '')}")
        self.setFixedSize(1150, 680)
        self.setStyleSheet("QDialog { background-color: #f4f6f7; }")
        self.init_ui()
        self.load_statement()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # En-tête
        lbl_header = QLabel(f"📋 Feuille de Production & Travaux d'Atelier : {self.artisan.get('name', '')}")
        lbl_header.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background-color: #00796B; padding: 12px; border-radius: 6px;")
        lbl_header.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_header)

        # Tableau de Production Excel Réel pour cet Artisan (12 Colonnes Réelles)
        self.table_prod = QTableWidget(0, 12)
        self.table_prod.setHorizontalHeaderLabels([
            "numero", "Nom", "Tel :", "date remis", "Obj", "Poid", 
            "Date Reçue", "Date Sortie", "Prix (Façon)", "Prix (Client)", "Diff", "Statut"
        ])
        self.table_prod.setStyleSheet(EXCEL_STYLE)
        self.table_prod.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_prod.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_prod.verticalHeader().setVisible(False)
        self.table_prod.verticalHeader().setDefaultSectionSize(38)

        hh_p = self.table_prod.horizontalHeader()
        hh_p.setSectionResizeMode(0, QHeaderView.ResizeToContents) # numero
        hh_p.setSectionResizeMode(1, QHeaderView.Stretch)          # Nom
        hh_p.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Tel :
        hh_p.setSectionResizeMode(3, QHeaderView.ResizeToContents) # date remis
        hh_p.setSectionResizeMode(4, QHeaderView.Stretch)          # Obj
        hh_p.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Poid
        hh_p.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Date Reçue
        hh_p.setSectionResizeMode(7, QHeaderView.ResizeToContents) # Date Sortie
        hh_p.setSectionResizeMode(8, QHeaderView.ResizeToContents) # Prix Artisan
        hh_p.setSectionResizeMode(9, QHeaderView.ResizeToContents) # Prix Client
        hh_p.setSectionResizeMode(10, QHeaderView.ResizeToContents)# Diff
        hh_p.setSectionResizeMode(11, QHeaderView.ResizeToContents)# Statut

        layout.addWidget(self.table_prod)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(BTN_ADD_STYLE)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def load_statement(self):
        art_id = self.artisan['id']
        orders = self.manager.artisan_work.get_orders_by_artisan(art_id)
        self.table_prod.setRowCount(0)
        
        tot_prix_artisan = tot_prix_client = tot_diff = 0.0

        for o in orders:
            row = self.table_prod.rowCount()
            self.table_prod.insertRow(row)

            numero = str(o.get('numero') or o.get('id', ''))
            nom = o.get('client_name') or ""
            tel = o.get('client_phone') or ""
            date_remis = o.get('date_remis') or ""
            obj = o.get('obj') or ""
            poid = str(o.get('poid') or o.get('poids_entre_g') or '')
            date_recue = o.get('date_recue') or ""
            date_sortie = o.get('date_sortie') or ""

            prix_artisan = safe_float(o.get('cout_artisan_da') or o.get('prix') or 0)
            prix_client = safe_float(o.get('prix_vente_da') or o.get('vente') or 0)
            diff = safe_float(o.get('diff') or (prix_client - prix_artisan))

            st_key = o.get('status', 'RECEPTION')
            st_label, st_fg, st_bg = STATUS_MAP.get(st_key, ("🟢 Au Réceptionniste", "#27ae60", "#d5f5e3"))

            vals = [
                numero, nom, tel, date_remis, obj, poid,
                date_recue, date_sortie,
                f"{prix_artisan:,.2f}" if prix_artisan else "",
                f"{prix_client:,.2f}" if prix_client else "",
                f"{diff:,.2f}" if diff else "",
                st_label
            ]

            for col, val in enumerate(vals):
                it = QTableWidgetItem(str(val))
                if col in [0, 2, 3, 5, 6, 7, 8, 9, 10, 11]:
                    it.setTextAlignment(Qt.AlignCenter)
                if col == 10 and diff != 0:
                    it.setForeground(QBrush(QColor("#27ae60" if diff >= 0 else "#e74c3c")))
                    it.setFont(QFont("", 10, QFont.Bold))
                elif col == 11:
                    it.setBackground(QBrush(QColor(st_bg)))
                    it.setForeground(QBrush(QColor(st_fg)))
                    it.setFont(QFont("", 10, QFont.Bold))
                self.table_prod.setItem(row, col, it)

            tot_prix_artisan += prix_artisan
            tot_prix_client += prix_client
            tot_diff += diff

        # Ligne de total du tableau de production (Totaux en bas du tableau)
        if orders:
            row = self.table_prod.rowCount()
            self.table_prod.insertRow(row)

            # Remplir le fond clair #e2e8f0 sur toute la ligne de total
            for col in range(12):
                it = QTableWidgetItem("")
                it.setBackground(QBrush(QColor("#e2e8f0")))
                self.table_prod.setItem(row, col, it)

            lbl_tot = self.table_prod.item(row, 7)
            lbl_tot.setText("TOTAUX :")
            lbl_tot.setTextAlignment(Qt.AlignCenter)
            lbl_tot.setForeground(QBrush(QColor("#000000")))
            lbl_tot.setFont(QFont("", 11, QFont.Bold))

            # Prix Artisan Total
            it_pa = self.table_prod.item(row, 8)
            it_pa.setText(f"{tot_prix_artisan:,.2f} DA")
            it_pa.setTextAlignment(Qt.AlignCenter)
            it_pa.setForeground(QBrush(QColor("#000000")))
            it_pa.setFont(QFont("", 11, QFont.Bold))

            # Prix Client Total
            it_pc = self.table_prod.item(row, 9)
            it_pc.setText(f"{tot_prix_client:,.2f} DA")
            it_pc.setTextAlignment(Qt.AlignCenter)
            it_pc.setForeground(QBrush(QColor("#000000")))
            it_pc.setFont(QFont("", 11, QFont.Bold))

            # Diff Total
            it_diff = self.table_prod.item(row, 10)
            it_diff.setText(f"{tot_diff:,.2f} DA")
            it_diff.setTextAlignment(Qt.AlignCenter)
            it_diff.setForeground(QBrush(QColor("#1e8449" if tot_diff >= 0 else "#c0392b")))
            it_diff.setFont(QFont("", 11, QFont.Bold))


# =====================================================================
# Dialog Opération / Dépôt Atelier Conforme 100% Au Tableau de Production
# =====================================================================
class OrderDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, 20)

    def __init__(self, manager, artisan_id=None, record=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.artisan_id = artisan_id
        self.record = record
        self.selected_client_id = record.get('client_id') if record else None
        self.selected_client_name = ""
        self.selected_client_phone = ""
        
        self.setWindowTitle("Modifier la fiche d'Atelier (Production)" if record else "Nouveau Dépôt Atelier (Production)")
        self.setFixedSize(920, 650)
        self.setStyleSheet("QDialog { background-color: #f4f6f7; }")
        self.init_ui()

    def _open_keyboard(self, target):
        target.setFocus(); kb = VirtualKeyboardDialog(self.window()); kb.show(); kb.raise_()

    def _open_numpad(self, target):
        target.setFocus()
        numpad = VirtualNumpad(title="Saisie", mode="direct", target_widget=target, allow_decimal=True, allow_leading_zero=True, parent=self)
        numpad.show(); numpad.raise_()

    def _open_calendar_picker(self, target):
        dlg = DatePickerDialog(current_date_str=target.text().strip(), parent=self)
        if dlg.exec() == QDialog.Accepted:
            target.setText(dlg.get_selected_date())

    def _set_today_date(self, target):
        target.setText(QDate.currentDate().toString("yyyy-MM-dd"))

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

    def _wrap_date_input(self, widget):
        """Enrobage UX complet pour la saisie rapide de date (Bouton Aujourd'hui + Calendrier + Clavier)"""
        lay = QHBoxLayout(); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        
        btn_today = QPushButton("📅 Aujourd'hui")
        btn_today.setStyleSheet("QPushButton { font-size: 11px; font-weight: bold; background-color: #00796B; color: white; border-radius: 4px; padding: 4px 6px; } QPushButton:hover { background-color: #004D40; }")
        btn_today.clicked.connect(lambda: self._set_today_date(widget))
        lay.addWidget(btn_today)

        btn_cal = QPushButton("📆")
        btn_cal.setFixedSize(32,32)
        btn_cal.setStyleSheet(BTN_AUX_STYLE + "background-color: #e67e22; color: white;")
        btn_cal.clicked.connect(lambda: self._open_calendar_picker(widget))
        lay.addWidget(btn_cal)

        btn_kb = QPushButton("⌨")
        btn_kb.setFixedSize(32,32)
        btn_kb.setStyleSheet(BTN_AUX_STYLE + "background-color: #3498db; color: white;")
        btn_kb.clicked.connect(lambda: self._open_keyboard(widget))
        lay.addWidget(btn_kb)

        w = QWidget(); w.setLayout(lay); return w

    def _open_client_selector(self):
        dlg = ClientSelectionDialog(self.manager, self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_client_id:
            self.selected_client_id = dlg.selected_client_id
            try:
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT name, phone FROM Clients WHERE id=%s", (self.selected_client_id,))
                    c_data = cursor.fetchone()
                    if c_data:
                        self.selected_client_name = c_data['name']
                        self.selected_client_phone = c_data.get('phone') or ""
                        self.btn_select_client.setText(f"✅ Client : {self.selected_client_name}  |  📞 Tel : {self.selected_client_phone}")
                        self.btn_select_client.setStyleSheet("background-color: #d5f5e3; color: #1e8449; font-weight: bold; font-size: 14px; padding: 10px; border-radius: 6px; border: 2px solid #27ae60;")
            except Exception as e:
                logging.error(f"Error fetching client name: {e}")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 10)
        main_layout.setSpacing(12)

        # --- 1. Client ---
        grp_client = QGroupBox("Propriétaire / Client (Nom & Tel)")
        grp_client.setStyleSheet("QGroupBox { font-size: 15px; font-weight: bold; color: #004D40; border: 2px solid #00796B; border-radius: 8px; margin-top: 8px; padding-top: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px; }")
        client_lay = QHBoxLayout(grp_client)
        client_lay.setContentsMargins(10, 8, 10, 8)

        self.btn_select_client = QPushButton("🔍  Cliquer pour sélectionner le client / propriétaire")
        self.btn_select_client.setCursor(Qt.PointingHandCursor)
        self.btn_select_client.setMinimumHeight(40)
        self.btn_select_client.setStyleSheet("background-color: #e0f2f1; color: #004D40; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 6px; border: 2px dashed #00796B;")
        self.btn_select_client.clicked.connect(self._open_client_selector)
        client_lay.addWidget(self.btn_select_client)

        if self.selected_client_id:
            try:
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT name, phone FROM Clients WHERE id=%s", (self.selected_client_id,))
                    c_data = cursor.fetchone()
                    if c_data:
                        self.selected_client_name = c_data['name']
                        self.selected_client_phone = c_data.get('phone') or ""
                        self.btn_select_client.setText(f"✅ Client : {self.selected_client_name}  |  📞 Tel : {self.selected_client_phone}")
                        self.btn_select_client.setStyleSheet("background-color: #d5f5e3; color: #1e8449; font-weight: bold; font-size: 14px; padding: 8px; border-radius: 6px; border: 2px solid #27ae60;")
            except Exception as e:
                logging.error(f"Error fetching client name in init_ui: {e}")
        main_layout.addWidget(grp_client)

        # --- 2. Formulaire Grille ---
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)

        # Ligne 0 : numero & Statut
        lbl_num = QLabel("numero (N°) :"); lbl_num.setStyleSheet(LBL_STYLE); lbl_num.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_num, 0, 0)
        
        self.inp_numero = QLineEdit(); self.inp_numero.setStyleSheet(STYLE_TEXT); self.inp_numero.setAlignment(Qt.AlignCenter)
        if self.record:
            num_val = str(self.record.get('numero') or self.record.get('id', ''))
            self.inp_numero.setText(num_val)
        else:
            try:
                with self.manager.db.get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM ArtisanWorkOrders")
                    row = cursor.fetchone()
                    self.inp_numero.setText(str(row[0]) if row else "1")
            except Exception:
                self.inp_numero.setText("1")
        grid.addWidget(self._wrap_kb(self.inp_numero), 0, 1)

        lbl_statut = QLabel("Statut :"); lbl_statut.setStyleSheet(LBL_STYLE); lbl_statut.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_statut, 0, 2)
        
        self.combo_status = QComboBox()
        self.combo_status.setStyleSheet("QComboBox { font-size: 14px; font-weight: bold; padding: 8px; border: 2px solid #27ae60; border-radius: 6px; background-color: #d5f5e3; color: #1e8449; }")
        self.combo_status.addItem("🟢 Au Réceptionniste (لدى المستقبل)", "RECEPTION")
        self.combo_status.addItem("🟡 Chez l'Artisan (عند الصانع)", "CHEZ_ARTISAN")
        self.combo_status.addItem("🔵 Retourné au Magasin (عاد للمستقبل)", "RETOUR_ARTISAN")
        self.combo_status.addItem("✅ Livré au Client (تم تسليمه)", "LIVRE")

        cur_status = self.record.get('status', 'RECEPTION') if self.record else 'RECEPTION'
        idx = self.combo_status.findData(cur_status)
        if idx >= 0: self.combo_status.setCurrentIndex(idx)
        grid.addWidget(self.combo_status, 0, 3)

        # Ligne 1 : Obj & Artisan
        lbl_obj = QLabel("Obj (Travail) :"); lbl_obj.setStyleSheet(LBL_STYLE); lbl_obj.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_obj, 1, 0)
        
        self.inp_obj = QLineEdit(); self.inp_obj.setStyleSheet(STYLE_TEXT)
        self.inp_obj.setPlaceholderText("Ex: Transformation 01 Bague loc T=62, 01 Gtte a souder...")
        if self.record: self.inp_obj.setText(str(self.record.get('obj', '')))
        grid.addWidget(self._wrap_kb(self.inp_obj), 1, 1)

        lbl_artisan = QLabel("Artisan / الصانع :"); lbl_artisan.setStyleSheet(LBL_STYLE); lbl_artisan.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_artisan, 1, 2)

        self.combo_artisan_dlg = QComboBox()
        self.combo_artisan_dlg.setStyleSheet("QComboBox { font-size: 14px; font-weight: bold; padding: 8px; border: 2px solid #bdc3c7; border-radius: 6px; background-color: white; }")
        self.combo_artisan_dlg.addItem("Non assigné / Aucun", None)
        try:
            artisan_list = self.manager.artisan_work.get_all_artisans()
            for art in artisan_list:
                self.combo_artisan_dlg.addItem(art['name'], art['id'])
        except Exception as e:
            logging.error(f"Error loading artisans in dialog: {e}")

        cur_art_id = self.record.get('artisan_id') if self.record else self.artisan_id
        if cur_art_id:
            idx_art = self.combo_artisan_dlg.findData(cur_art_id)
            if idx_art >= 0: self.combo_artisan_dlg.setCurrentIndex(idx_art)
        grid.addWidget(self.combo_artisan_dlg, 1, 3)

        # Ligne 2 : Poid Aller & Poids Retour
        lbl_poid = QLabel("Poid Aller (g) :"); lbl_poid.setStyleSheet(LBL_STYLE); lbl_poid.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_poid, 2, 0)
        
        self.inp_poids = QLineEdit(); self.inp_poids.setStyleSheet(STYLE_NUM); self.inp_poids.setAlignment(Qt.AlignCenter)
        self.inp_poids.setPlaceholderText("Ex: 1.21")
        if self.record: self.inp_poids.setText(str(self.record.get('poid') or self.record.get('poids_entre_g') or ''))
        grid.addWidget(self._wrap_num(self.inp_poids), 2, 1)

        lbl_poids_retour = QLabel("Poids Retour (g) :"); lbl_poids_retour.setStyleSheet(LBL_STYLE); lbl_poids_retour.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_poids_retour, 2, 2)
        
        self.inp_poids_retour = QLineEdit(); self.inp_poids_retour.setStyleSheet(STYLE_NUM); self.inp_poids_retour.setAlignment(Qt.AlignCenter)
        self.inp_poids_retour.setPlaceholderText("Ex: 1.15")
        if self.record: self.inp_poids_retour.setText(str(self.record.get('poids_retour_g') or ''))
        grid.addWidget(self._wrap_num(self.inp_poids_retour), 2, 3)

        # Ligne 3 : Date Remis & Date Reçue
        lbl_date_remis = QLabel("Date Remis :"); lbl_date_remis.setStyleSheet(LBL_STYLE); lbl_date_remis.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_date_remis, 3, 0)
        
        self.inp_date_remis = QLineEdit(); self.inp_date_remis.setStyleSheet(STYLE_DATE); self.inp_date_remis.setAlignment(Qt.AlignCenter)
        if self.record and self.record.get('date_remis'):
            self.inp_date_remis.setText(str(self.record.get('date_remis')))
        else:
            self.inp_date_remis.setText(QDate.currentDate().toString("yyyy-MM-dd"))
        grid.addWidget(self._wrap_date_input(self.inp_date_remis), 3, 1)

        lbl_date_recue = QLabel("Date Reçue :"); lbl_date_recue.setStyleSheet(LBL_STYLE); lbl_date_recue.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_date_recue, 3, 2)
        
        self.inp_date_recue = QLineEdit(); self.inp_date_recue.setStyleSheet(STYLE_DATE); self.inp_date_recue.setAlignment(Qt.AlignCenter)
        if self.record and self.record.get('date_recue'): self.inp_date_recue.setText(str(self.record.get('date_recue')))
        grid.addWidget(self._wrap_date_input(self.inp_date_recue), 3, 3)

        # Ligne 4 : Date Sortie & Prix (Façon)
        lbl_date_sortie = QLabel("Date Sortie :"); lbl_date_sortie.setStyleSheet(LBL_STYLE); lbl_date_sortie.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_date_sortie, 4, 0)
        
        self.inp_date_sortie = QLineEdit(); self.inp_date_sortie.setStyleSheet(STYLE_DATE); self.inp_date_sortie.setAlignment(Qt.AlignCenter)
        if self.record and self.record.get('date_sortie'): self.inp_date_sortie.setText(str(self.record.get('date_sortie')))
        grid.addWidget(self._wrap_date_input(self.inp_date_sortie), 4, 1)

        lbl_prix = QLabel("Prix (Façon) :"); lbl_prix.setStyleSheet(LBL_STYLE); lbl_prix.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_prix, 4, 2)
        
        self.inp_prix = QLineEdit(); self.inp_prix.setStyleSheet(STYLE_NUM); self.inp_prix.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_prix.setText(str(self.record.get('cout_artisan_da') or self.record.get('prix', '')))
        grid.addWidget(self._wrap_num(self.inp_prix), 4, 3)

        # Ligne 5 : Prix (Client) & Diff (Bénéfice)
        lbl_vente = QLabel("Prix (Client) :"); lbl_vente.setStyleSheet(LBL_STYLE); lbl_vente.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_vente, 5, 0)
        
        self.inp_vente = QLineEdit(); self.inp_vente.setStyleSheet(STYLE_NUM); self.inp_vente.setAlignment(Qt.AlignCenter)
        if self.record: self.inp_vente.setText(str(self.record.get('prix_vente_da') or self.record.get('vente', '')))
        grid.addWidget(self._wrap_num(self.inp_vente), 5, 1)

        lbl_diff = QLabel("Diff (Bénéfice) :"); lbl_diff.setStyleSheet("font-size: 15px; font-weight: bold; color: #1e8449;"); lbl_diff.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_diff, 5, 2)
        
        self.inp_diff = QLineEdit(); self.inp_diff.setStyleSheet(STYLE_RESULT); self.inp_diff.setAlignment(Qt.AlignCenter)
        self.inp_diff.setReadOnly(True)
        if self.record: self.inp_diff.setText(str(self.record.get('diff', '')))
        grid.addWidget(self._wrap_num(self.inp_diff), 5, 3)

        # Ligne 6 : Observations
        lbl_obs = QLabel("Observation :"); lbl_obs.setStyleSheet(LBL_STYLE); lbl_obs.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(lbl_obs, 6, 0)
        
        self.inp_obs = QLineEdit(); self.inp_obs.setStyleSheet(STYLE_TEXT)
        self.inp_obs.setPlaceholderText("Observations / Remarques pour l'opération...")
        if self.record: self.inp_obs.setText(str(self.record.get('observations') or ''))
        grid.addWidget(self._wrap_kb(self.inp_obs), 6, 1, 1, 3)

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
            prix = safe_float(self.inp_prix.text())
            vente = safe_float(self.inp_vente.text())
            diff = vente - prix
            self.inp_diff.setText(f"{diff:,.2f}")
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
            "artisan_id": self.combo_artisan_dlg.currentData(),
            "client_id": self.selected_client_id,
            "numero": self.inp_numero.text().strip(),
            "status": self.combo_status.currentData(),
            "obj": self.inp_obj.text().strip(),
            "poid": self.inp_poids.text().strip(),
            "poids_entre_g": self.inp_poids.text().strip(),
            "poids_retour_g": self.inp_poids_retour.text().strip(),
            "date_remis": self.inp_date_remis.text().strip(),
            "date_recue": self.inp_date_recue.text().strip(),
            "date_sortie": self.inp_date_sortie.text().strip(),
            "prix": self.inp_prix.text().strip(),
            "vente": self.inp_vente.text().strip(),
            "cout_artisan_da": self.inp_prix.text().strip(),
            "prix_vente_da": self.inp_vente.text().strip(),
            "diff": self.inp_diff.text().strip(),
            "observations": self.inp_obs.text().strip()
        }


# =====================================================================
# Vue Principale avec Onglets (Atelier + Artisans)
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
        self.load_atelier_orders()
        self.load_artisan_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.lbl_title = QLabel("SUIVI DE L'ATELIER & GESTION DES ARTISANS")
        self.lbl_title.setStyleSheet("""
            font-size: 20px; font-weight: 900; color: white;
            background-color: #0f8f83; padding: 10px; border-radius: 4px; letter-spacing: 1px;
        """)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.lbl_title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)

        # Onglet 1 : Suivi Réception & Atelier
        self.tab_atelier = QWidget()
        self.setup_atelier_tab()
        self.tabs.addTab(self.tab_atelier, "📋 Réparations")

        # Onglet 2 : Répertoire des Artisans
        self.tab_artisans = QWidget()
        self.setup_artisans_tab()
        self.tabs.addTab(self.tab_artisans, "👨‍🔧 Artisans")

        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs)

    # ==========================================
    # Onglet 1 : Atelier & Réception (Tableau Production Excel Réel)
    # ==========================================
    def setup_atelier_tab(self):
        layout = QVBoxLayout(self.tab_atelier)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tools_lay = QHBoxLayout()
        tools_lay.setSpacing(10)

        self.search_atelier = QLineEdit()
        self.search_atelier.setPlaceholderText("🔍 Rechercher par N°, client, téléphone, travail...")
        self.search_atelier.setStyleSheet(SEARCH_STYLE)
        self.search_atelier.textChanged.connect(self.filter_atelier_table)
        tools_lay.addWidget(self.search_atelier, stretch=1)

        self.combo_date_filter = QComboBox()
        self.combo_date_filter.setStyleSheet("QComboBox { font-size: 14px; font-weight: bold; padding: 8px 12px; border: 2px solid #00796B; border-radius: 8px; background-color: #e0f2f1; color: #004D40; min-width: 210px; }")
        self.combo_date_filter.addItem("📅 30 derniers jours (Dernier Mois)", "30")
        self.combo_date_filter.addItem("📅 7 derniers jours (Cette Semaine)", "7")
        self.combo_date_filter.addItem("📅 3 derniers mois", "90")
        self.combo_date_filter.addItem("📅 6 derniers mois", "180")
        self.combo_date_filter.addItem("📅 Cette année", "365")
        self.combo_date_filter.addItem("🌐 Historique complet (Tout)", "ALL")
        self.combo_date_filter.currentIndexChanged.connect(lambda: self.load_atelier_orders())
        tools_lay.addWidget(self.combo_date_filter)

        self.combo_status_filter = QComboBox()
        self.combo_status_filter.setStyleSheet("QComboBox { font-size: 14px; font-weight: bold; padding: 8px 12px; border: 2px solid #2980b9; border-radius: 8px; background-color: #ebf5fb; color: #2980b9; min-width: 220px; }")
        self.combo_status_filter.addItem("📋 Tous les statuts", "ALL")
        self.combo_status_filter.addItem("🟢 Au Réceptionniste (لدى المستقبل)", "RECEPTION")
        self.combo_status_filter.addItem("🟡 Chez l'Artisan (عند الصانع)", "CHEZ_ARTISAN")
        self.combo_status_filter.addItem("🔵 Retourné au Magasin (عاد للمستقبل)", "RETOUR_ARTISAN")
        self.combo_status_filter.addItem("✅ Livré au Client (تم تسليمه)", "LIVRE")
        self.combo_status_filter.currentIndexChanged.connect(lambda: self.load_atelier_orders())
        tools_lay.addWidget(self.combo_status_filter)

        btn_add = QPushButton("➕ Nouveau Dépôt Atelier")
        btn_add.setStyleSheet(BTN_GREEN_STYLE)
        btn_add.clicked.connect(self.open_add_atelier_dialog)
        tools_lay.addWidget(btn_add)

        layout.addLayout(tools_lay)

        # Tableau Général de Production (14 Colonnes Conformes au Modèle Réel)
        self.table_atelier = QTableWidget(0, 14)
        self.table_atelier.setHorizontalHeaderLabels([
            "numero", "Nom", "Tel :", "date remis", "Obj", "Poids", "Poids R.",
            "Date Reçue", "Date Sortie", "Prix (Façon)", "Prix (Client)", "Diff", "Statut", "Artisan"
        ])
        self.table_atelier.setStyleSheet(EXCEL_STYLE)
        self.table_atelier.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_atelier.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_atelier.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_atelier.customContextMenuRequested.connect(self.show_atelier_context_menu)
        self.table_atelier.doubleClicked.connect(self.on_table_double_clicked)
        self.table_atelier.verticalHeader().setVisible(False)
        self.table_atelier.verticalHeader().setDefaultSectionSize(38)

        hh = self.table_atelier.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents) # numero
        hh.setSectionResizeMode(1, QHeaderView.Stretch)          # Nom
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Tel :
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents) # date remis
        hh.setSectionResizeMode(4, QHeaderView.Stretch)          # Obj
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Poids
        hh.setSectionResizeMode(6, QHeaderView.ResizeToContents) # Poids R.
        hh.setSectionResizeMode(7, QHeaderView.ResizeToContents) # Date Reçue
        hh.setSectionResizeMode(8, QHeaderView.ResizeToContents) # Date Sortie
        hh.setSectionResizeMode(9, QHeaderView.ResizeToContents) # Prix Artisan
        hh.setSectionResizeMode(10, QHeaderView.ResizeToContents) # Prix Client
        hh.setSectionResizeMode(11, QHeaderView.ResizeToContents)# Diff
        hh.setSectionResizeMode(12, QHeaderView.ResizeToContents)# Statut
        hh.setSectionResizeMode(13, QHeaderView.ResizeToContents)# Artisan

        layout.addWidget(self.table_atelier)

    # ==========================================
    # Onglet 2 : Artisans (Gestion Simple)
    # ==========================================
    def setup_artisans_tab(self):
        layout = QVBoxLayout(self.tab_artisans)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        tools_lay = QHBoxLayout(); tools_lay.setSpacing(10)
        
        self.search_artisan = QLineEdit()
        self.search_artisan.setPlaceholderText("Rechercher un artisan par nom ou téléphone...")
        self.search_artisan.setStyleSheet(SEARCH_STYLE)
        self.search_artisan.textChanged.connect(self.filter_artisan_table)
        tools_lay.addWidget(self.search_artisan, stretch=1)

        btn_statement = QPushButton("📜 Feuille de Production de l'Artisan")
        btn_statement.setStyleSheet(BTN_ADD_STYLE)
        btn_statement.clicked.connect(self.open_artisan_statement_dialog)
        tools_lay.addWidget(btn_statement)

        btn_add = QPushButton("➕ Ajouter un Artisan")
        btn_add.setStyleSheet(BTN_GREEN_STYLE)
        btn_add.clicked.connect(self.open_add_artisan_dialog)
        tools_lay.addWidget(btn_add)

        btn_edit = QPushButton("✏️ Modifier")
        btn_edit.setStyleSheet(BTN_ADD_STYLE)
        btn_edit.clicked.connect(self.open_edit_artisan_dialog)
        tools_lay.addWidget(btn_edit)

        btn_del = QPushButton("🗑️ Supprimer")
        btn_del.setStyleSheet(BTN_RED_STYLE)
        btn_del.clicked.connect(self.delete_selected_artisan)
        tools_lay.addWidget(btn_del)

        layout.addLayout(tools_lay)

        # Tableau des Artisans Simplifié (4 Colonnes)
        self.table_artisans = QTableWidget(0, 4)
        self.table_artisans.setHorizontalHeaderLabels([
            "N°", "Nom de l'Artisan", "Téléphone", "Notes / Remarques"
        ])
        self.table_artisans.setStyleSheet(EXCEL_STYLE)
        self.table_artisans.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_artisans.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_artisans.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_artisans.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_artisans.customContextMenuRequested.connect(self.show_artisan_context_menu)
        self.table_artisans.doubleClicked.connect(self.open_artisan_statement_dialog)
        self.table_artisans.verticalHeader().setVisible(False)
        self.table_artisans.verticalHeader().setDefaultSectionSize(40)

        hh = self.table_artisans.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.table_artisans)

    def on_tab_changed(self, index):
        if index == 0:
            self.lbl_title.setText("🛠️ Suivi de l'Atelier & Gestion des Artisans (Format Production)")
            self.load_atelier_orders()
        elif index == 1:
            self.lbl_title.setText("👨‍د Répertoire Artisans & Feuilles de Production Excel")
            self.load_artisan_data()

    # ==========================================
    # Logique Atelier
    # ==========================================
    def load_atelier_orders(self):
        status_filter = self.combo_status_filter.currentData() if hasattr(self, 'combo_status_filter') else "ALL"
        date_option = self.combo_date_filter.currentData() if hasattr(self, 'combo_date_filter') else "30"

        date_from = None
        if date_option and date_option != 'ALL':
            try:
                days = int(date_option)
                date_from = QDate.currentDate().addDays(-days).toString("yyyy-MM-dd")
            except ValueError:
                pass

        self.current_orders_data = self.manager.artisan_work.get_all_atelier_orders(
            status_filter=status_filter,
            date_from=date_from
        )
        self._render_atelier_table(self.current_orders_data)

    def filter_atelier_table(self, text):
        search = text.strip().lower()
        filtered = []
        for r in self.current_orders_data:
            num = str(r.get('numero') or r.get('id', '')).lower()
            client = str(r.get('client_name') or '').lower()
            phone = str(r.get('client_phone') or '').lower()
            obj = str(r.get('obj') or '').lower()
            obs = str(r.get('observations') or '').lower()
            if search in num or search in client or search in phone or search in obj or search in obs:
                filtered.append(r)
        self._render_atelier_table(filtered)

    def _render_atelier_table(self, records):
        self.table_atelier.setRowCount(0)
        tot_prix_artisan = tot_prix_client = tot_diff = 0.0

        for r in records:
            row = self.table_atelier.rowCount()
            self.table_atelier.insertRow(row)

            numero = str(r.get('numero') or r.get('id', ''))
            client_name = r.get('client_name') or ""
            client_phone = r.get('client_phone') or ""
            date_remis = r.get('date_remis') or ""
            obj = r.get('obj') or ""
            poid = str(r.get('poid') or r.get('poids_entre_g') or '')
            poids_r = str(r.get('poids_retour_g') or '')
            date_recue = r.get('date_recue') or ""
            date_sortie = r.get('date_sortie') or ""

            prix_artisan = safe_float(r.get('cout_artisan_da') or r.get('prix') or 0)
            prix_client = safe_float(r.get('prix_vente_da') or r.get('vente') or 0)
            diff = safe_float(r.get('diff') or (prix_client - prix_artisan))

            st_key = r.get('status', 'RECEPTION')
            st_label, st_fg, st_bg = STATUS_MAP.get(st_key, ("🟢 Au Réceptionniste", "#27ae60", "#d5f5e3"))
            artisan_name = r.get('artisan_name') or "Non assigné"

            values = [
                numero, client_name, client_phone, date_remis, obj, poid, poids_r,
                date_recue, date_sortie,
                f"{prix_artisan:,.2f}" if prix_artisan else "",
                f"{prix_client:,.2f}" if prix_client else "",
                f"{diff:,.2f}" if diff else "",
                st_label, artisan_name
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col in [0, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]:
                    item.setTextAlignment(Qt.AlignCenter)
                
                # Badges Couleur
                if col == 11 and diff != 0:
                    item.setForeground(QBrush(QColor("#27ae60" if diff >= 0 else "#e74c3c")))
                    item.setFont(QFont("", 10, QFont.Bold))
                elif col == 12:
                    item.setBackground(QBrush(QColor(st_bg)))
                    item.setForeground(QBrush(QColor(st_fg)))
                    item.setFont(QFont("", 10, QFont.Bold))

                self.table_atelier.setItem(row, col, item)

            tot_prix_artisan += prix_artisan
            tot_prix_client += prix_client
            tot_diff += diff

        # Ligne des Totaux en bas de tableau (Alignée 100% avec les colonnes)
        if records:
            row = self.table_atelier.rowCount()
            self.table_atelier.insertRow(row)

            # Remplir le fond clair #e2e8f0 sur toute la ligne de total
            for col in range(13):
                it = QTableWidgetItem("")
                it.setBackground(QBrush(QColor("#e2e8f0")))
                self.table_atelier.setItem(row, col, it)

            lbl = self.table_atelier.item(row, 7)
            lbl.setText("TOTAUX :")
            lbl.setTextAlignment(Qt.AlignCenter)
            lbl.setForeground(QBrush(QColor("#000000")))
            lbl.setFont(QFont("", 11, QFont.Bold))

            # Prix Artisan Total
            it_pa = self.table_atelier.item(row, 8)
            it_pa.setText(f"{tot_prix_artisan:,.2f} DA")
            it_pa.setTextAlignment(Qt.AlignCenter)
            it_pa.setForeground(QBrush(QColor("#000000")))
            it_pa.setFont(QFont("", 11, QFont.Bold))

            # Prix Client Total
            it_pc = self.table_atelier.item(row, 9)
            it_pc.setText(f"{tot_prix_client:,.2f} DA")
            it_pc.setTextAlignment(Qt.AlignCenter)
            it_pc.setForeground(QBrush(QColor("#000000")))
            it_pc.setFont(QFont("", 11, QFont.Bold))

            # Diff Total
            it_diff = self.table_atelier.item(row, 10)
            it_diff.setText(f"{tot_diff:,.2f} DA")
            it_diff.setTextAlignment(Qt.AlignCenter)
            it_diff.setForeground(QBrush(QColor("#1e8449" if tot_diff >= 0 else "#c0392b")))
            it_diff.setFont(QFont("", 11, QFont.Bold))

    def show_atelier_context_menu(self, pos):
        row = self.table_atelier.rowAt(pos.y())
        if row < 0 or row >= len(self.current_orders_data): return
        record = self.current_orders_data[row]
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)

        menu.addAction("✏️ Modifier cette fiche", lambda: self.open_edit_atelier_dialog(record))
        menu.addSeparator()

        st_menu = menu.addMenu("🔄 Changer le statut rapidement")
        st_menu.addAction("🟢 Au Réceptionniste (لدى المستقبل)", lambda: self.change_status(record['id'], "RECEPTION"))
        st_menu.addAction("🟡 Chez l'Artisan (عند الصانع)", lambda: self.change_status(record['id'], "CHEZ_ARTISAN"))
        st_menu.addAction("🔵 Retourné au Magasin (عاد للمستقبل)", lambda: self.change_status(record['id'], "RETOUR_ARTISAN"))
        st_menu.addAction("✅ Livré au Client (تم تسليمه)", lambda: self.change_status(record['id'], "LIVRE"))

        menu.addSeparator()
        menu.addAction("🗑️ Supprimer", lambda: self.delete_atelier_order(record['id']))
        menu.exec_(self.table_atelier.viewport().mapToGlobal(pos))

    def on_table_double_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self.current_orders_data):
            record = self.current_orders_data[row]
            self.open_edit_atelier_dialog(record)

    def change_status(self, order_id, new_status):
        if self.manager.artisan_work.update_order_status(order_id, new_status):
            self.load_atelier_orders()

    def open_add_atelier_dialog(self):
        dlg = OrderDialog(manager=self.manager, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.artisan_work.add_order(
                d['artisan_id'], d['client_id'], d['numero'], d['date_remis'], d['obj'], d['poid'],
                d['date_recue'], d['date_sortie'], d['prix'], d['vente'], d['diff'],
                status=d['status'], poids_entre_g=d['poids_entre_g'], poids_retour_g=d['poids_retour_g'],
                observations=d['observations'], cout_artisan_da=d['cout_artisan_da'], prix_vente_da=d['prix_vente_da']
            )
            self.load_atelier_orders()

    def open_edit_atelier_dialog(self, record):
        dlg = OrderDialog(manager=self.manager, record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.artisan_work.update_order(
                d['id'], d['artisan_id'], d['client_id'], d['numero'], d['date_remis'], d['obj'], d['poid'],
                d['date_recue'], d['date_sortie'], d['prix'], d['vente'], d['diff'],
                status=d['status'], poids_entre_g=d['poids_entre_g'], poids_retour_g=d['poids_retour_g'],
                observations=d['observations'], cout_artisan_da=d['cout_artisan_da'], prix_vente_da=d['prix_vente_da']
            )
            self.load_atelier_orders()

    def delete_atelier_order(self, order_id):
        if QMessageBox.question(self, "Confirmer", "Voulez-vous vraiment supprimer cette fiche d'atelier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.artisan_work.delete_order(order_id)
            self.load_atelier_orders()

    # ==========================================
    # Logique Artisans (Simplifiée)
    # ==========================================
    def load_artisan_data(self):
        artisans = self.manager.artisan_work.get_all_artisans()
        self.table_artisans.setRowCount(0)
        for idx, a in enumerate(artisans, start=1):
            row = self.table_artisans.rowCount()
            self.table_artisans.insertRow(row)

            art_id = a['id']

            values = [
                str(idx),
                str(a.get('name') or ''),
                str(a.get('phone') or ''),
                str(a.get('notes') or '')
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col in [0, 2]:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table_artisans.setItem(row, col, item)
                self.table_artisans.item(row, col).setData(Qt.UserRole, art_id)

    def filter_artisan_table(self, text):
        search_text = text.strip().lower()
        for row in range(self.table_artisans.rowCount()):
            name = self.table_artisans.item(row, 1).text().lower()
            phone = self.table_artisans.item(row, 2).text().lower()
            self.table_artisans.setRowHidden(row, not (search_text in name or search_text in phone))

    def get_selected_artisan(self):
        row = self.table_artisans.currentRow()
        if row >= 0:
            art_id = self.table_artisans.item(row, 0).data(Qt.UserRole)
            name = self.table_artisans.item(row, 1).text()
            phone = self.table_artisans.item(row, 2).text()
            notes = self.table_artisans.item(row, 3).text()
            return {'id': art_id, 'name': name, 'phone': phone, 'notes': notes}
        return None

    def show_artisan_context_menu(self, pos):
        row = self.table_artisans.rowAt(pos.y())
        if row < 0: return
        self.table_artisans.selectRow(row)
        menu = QMenu(self)
        menu.setStyleSheet(CONTEXT_MENU_STYLE)
        
        menu.addAction("📜 Voir la Feuille de Production de l'Artisan", self.open_artisan_statement_dialog)
        menu.addSeparator()
        menu.addAction("🔍 Voir les travaux filtrés par cet artisan", self.filter_atelier_by_artisan)
        menu.addSeparator()
        menu.addAction("✏️ Modifier les coordonnées", self.open_edit_artisan_dialog)
        menu.addAction("🗑️ Supprimer l'artisan", self.delete_selected_artisan)
        menu.exec_(self.table_artisans.viewport().mapToGlobal(pos))

    def filter_atelier_by_artisan(self):
        artisan = self.get_selected_artisan()
        if artisan:
            self.current_orders_data = self.manager.artisan_work.get_all_atelier_orders(artisan_id=artisan['id'])
            self._render_atelier_table(self.current_orders_data)
            self.tabs.setCurrentIndex(0)

    def open_artisan_statement_dialog(self):
        artisan = self.get_selected_artisan()
        if not artisan:
            return QMessageBox.warning(self, "Attention", "Veuillez sélectionner un artisan dans le tableau.")
        dlg = ArtisanStatementDialog(manager=self.manager, artisan=artisan, parent=self)
        dlg.exec()

    def open_add_artisan_dialog(self):
        dlg = ArtisanDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            if not d['name']: return QMessageBox.warning(self, "Attention", "Le nom est obligatoire.")
            self.manager.artisan_work.add_artisan(d['name'], d.get('notes', ''), d.get('phone', ''))
            self.load_artisan_data()
            self.search_artisan.clear()

    def open_edit_artisan_dialog(self):
        record = self.get_selected_artisan()
        if not record: return QMessageBox.warning(self, "Attention", "Veuillez sélectionner un artisan.")
        dlg = ArtisanDialog(record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            if not d['name']: return QMessageBox.warning(self, "Attention", "Le nom est obligatoire.")
            self.manager.artisan_work.update_artisan(d['id'], d['name'], d.get('notes', ''), d.get('phone', ''))
            self.load_artisan_data()
            self.search_artisan.clear()

    def delete_selected_artisan(self):
        artisan = self.get_selected_artisan()
        if not artisan: return QMessageBox.warning(self, "Attention", "Veuillez sélectionner un artisan.")
        if QMessageBox.question(self, "Confirmer", "Supprimer cet artisan et ses travaux d'atelier ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.artisan_work.delete_artisan(artisan['id'])
            self.load_artisan_data()
