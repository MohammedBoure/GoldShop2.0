# ui/widgets/rh/rh_management_view.py
"""
Interface avec Dialogs positionnés en haut de l'écran
- Support complet du clavier virtuel (⌨️) et du pavé numérique (🔢)
- Dialogs tout en haut pour laisser l'espace au clavier en bas
- Filtres Année/Mois
- Tout en français
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QDialog, QMessageBox, 
    QLabel, QTabWidget, QApplication, QAbstractItemView, QComboBox,
    QDateEdit, QFormLayout
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QBrush

from ui.deferred_loading import defer_initial_load
from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog


# =====================================================================
# Fonction utilitaire pour extraire l'année et le mois
# =====================================================================

def extract_year(date_str):
    """Extrait l'année depuis une date au format dd/MM/yyyy ou yyyy-MM-dd"""
    if not date_str:
        return None
    d = str(date_str).strip()
    # Format: dd/MM/yyyy (18/06/2026)
    if '/' in d:
        parts = d.split('/')
        if len(parts) == 3 and len(parts[2]) == 4:
            try:
                return int(parts[2])
            except ValueError:
                return None
    # Format: yyyy-MM-dd (2026-06-18)
    elif '-' in d:
        try:
            return int(d[:4])
        except ValueError:
            return None
    return None

def extract_month(date_str):
    """Extrait le mois depuis une date au format dd/MM/yyyy ou yyyy-MM-dd"""
    if not date_str:
        return None
    d = str(date_str).strip()
    # Format: dd/MM/yyyy (18/06/2026)
    if '/' in d:
        parts = d.split('/')
        if len(parts) == 3:
            try:
                return int(parts[1])
            except ValueError:
                return None
    # Format: yyyy-MM-dd (2026-06-18)
    elif '-' in d:
        try:
            return int(d[5:7])
        except (ValueError, IndexError):
            return None
    return None


# =====================================================================
# Styles
# =====================================================================

EXCEL_STYLE = """
    QTableWidget {
        background-color: white;
        gridline-color: #000000;
        font-size: 14px;
        border: 2px solid #000000;
        selection-background-color: #0078D7;
        selection-color: white;
    }
    QTableWidget::item {
        padding: 5px 8px;
        border-bottom: 1px solid #d0d0d0;
        border-right: 1px solid #d0d0d0;
    }
    QTableWidget::item:selected {
        background-color: #0078D7;
        color: white;
    }
    QHeaderView::section {
        background-color: #4472C4;
        color: white;
        font-weight: bold;
        font-size: 14px;
        padding: 10px 8px;
        border: 1px solid #2F5496;
    }
"""

FILTER_STYLE = """
    QComboBox {
        font-size: 14px;
        font-weight: bold;
        padding: 6px 10px;
        border: 2px solid #bdc3c7;
        border-radius: 5px;
        background-color: #f8f9fa;
        min-width: 150px;
    }
"""

BTN_ADD_STYLE = """
    QPushButton {
        background-color: #27ae60;
        color: white;
        font-weight: bold;
        font-size: 14px;
        padding: 8px 20px;
        border-radius: 5px;
        border: none;
    }
    QPushButton:hover { background-color: #219a52; }
"""

BTN_EDIT_ROW_STYLE = """
    QPushButton {
        background-color: #f39c12;
        color: white;
        border-radius: 4px;
        font-size: 16px;
        border: none;
        padding: 4px 8px;
    }
    QPushButton:hover { background-color: #d68910; }
"""

BTN_DEL_ROW_STYLE = """
    QPushButton {
        background-color: #e74c3c;
        color: white;
        border-radius: 4px;
        font-size: 16px;
        border: none;
        padding: 4px 8px;
    }
    QPushButton:hover { background-color: #c0392b; }
"""

TAB_HEADER_STYLE = """
    QTabBar::tab {
        height: 50px;
        min-width: 300px;
        font-weight: bold;
        font-size: 15px;
        padding: 10px 20px;
    }
    QTabWidget::pane {
        border: 2px solid #000000;
        background: white;
    }
"""

DIALOG_FIELD_STYLE = """
    font-size: 16px;
    font-weight: bold;
    padding: 8px;
    border: 2px solid #bdc3c7;
    border-radius: 6px;
    background-color: #f8f9fa;
"""

DIALOG_BTN_KB_STYLE = """
    QPushButton {
        background-color: #3498db;
        color: white;
        border-radius: 6px;
        font-size: 18px;
        border: none;
        padding: 5px;
    }
    QPushButton:hover { background-color: #2980b9; }
"""

DIALOG_BTN_NUM_STYLE = """
    QPushButton {
        background-color: #8e44ad;
        color: white;
        border-radius: 6px;
        font-size: 18px;
        border: none;
        padding: 5px;
    }
    QPushButton:hover { background-color: #7d3c98; }
"""

DIALOG_BTN_SAVE_STYLE = """
    QPushButton {
        background-color: #27ae60;
        color: white;
        font-weight: bold;
        font-size: 18px;
        padding: 12px;
        border-radius: 6px;
        border: none;
    }
    QPushButton:hover { background-color: #219a52; }
"""

DIALOG_BTN_CANCEL_STYLE = """
    QPushButton {
        background-color: #95a5a6;
        color: white;
        font-weight: bold;
        font-size: 16px;
        padding: 10px;
        border-radius: 6px;
        border: none;
    }
    QPushButton:hover { background-color: #7f8c8d; }
"""


# =====================================================================
# Dialog de base : Positionné TOUT EN HAUT
# =====================================================================

class BaseTopDialog(QDialog):
    """Dialog positionné tout en haut pour laisser l'espace au clavier virtuel en bas"""
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        self.move(x, 0)

    def _open_keyboard(self, target):
        target.setFocus()
        kb = VirtualKeyboardDialog(self.window())
        kb.show()
        kb.raise_()

    def _open_numpad(self, target, allow_decimal=False):
        target.setFocus()
        numpad = VirtualNumpad(
            title="Saisie Numérique",
            mode="direct",
            target_widget=target,
            allow_decimal=allow_decimal,
            allow_leading_zero=True,
            parent=self
        )
        numpad.show()
        numpad.raise_()

    def _wrap_field_kb(self, widget):
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("⌨️")
        btn.setFixedSize(48, 48)
        btn.setStyleSheet(DIALOG_BTN_KB_STYLE)
        btn.clicked.connect(lambda: self._open_keyboard(widget))
        lay.addWidget(btn)
        w = QWidget()
        w.setLayout(lay)
        return w

    def _wrap_field_num(self, widget, allow_decimal=False):
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("🔢")
        btn.setFixedSize(48, 48)
        btn.setStyleSheet(DIALOG_BTN_NUM_STYLE)
        btn.clicked.connect(lambda: self._open_numpad(widget, allow_decimal))
        lay.addWidget(btn)
        w = QWidget()
        w.setLayout(lay)
        return w


# =====================================================================
# Dialog Entrée
# =====================================================================

class EntreeDialog(BaseTopDialog):
    def __init__(self, manager, record=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.record = record
        title = "Modifier l'entrée" if record else "Nouvelle Entrée"
        self.setWindowTitle(title)
        self.setFixedSize(550, 260)
        self.setStyleSheet("QDialog { background-color: white; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 10)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.inp_nom = QLineEdit()
        self.inp_nom.setStyleSheet(DIALOG_FIELD_STYLE)
        self.inp_nom.setPlaceholderText("Nom de l'ouvrier...")
        if self.record:
            self.inp_nom.setText(str(self.record.get('nom', '')))
        form.addRow("👤 Nom :", self._wrap_field_kb(self.inp_nom))

        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setDisplayFormat("dd/MM/yyyy")
        self.inp_date.setStyleSheet(DIALOG_FIELD_STYLE)
        if self.record and self.record.get('date_debut'):
            d = str(self.record['date_debut'])
            for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd"):
                date_obj = QDate.fromString(d, fmt)
                if date_obj.isValid():
                    self.inp_date.setDate(date_obj)
                    break
            else:
                self.inp_date.setDate(QDate.currentDate())
        else:
            self.inp_date.setDate(QDate.currentDate())
        form.addRow("📅 Date :", self._wrap_field_kb(self.inp_date))

        self.inp_obs = QLineEdit()
        self.inp_obs.setStyleSheet(DIALOG_FIELD_STYLE)
        self.inp_obs.setPlaceholderText("Observations...")
        if self.record:
            self.inp_obs.setText(str(self.record.get('observations') or ''))
        form.addRow("📝 Obs :", self._wrap_field_kb(self.inp_obs))

        layout.addLayout(form)
        layout.addStretch()

        btn_lay = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet(DIALOG_BTN_CANCEL_STYLE)
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)

        btn_save = QPushButton("✅ Enregistrer")
        btn_save.setStyleSheet(DIALOG_BTN_SAVE_STYLE)
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)
        layout.addLayout(btn_lay)

    def get_data(self):
        date_str = self.inp_date.date().toString("dd/MM/yyyy")
        return {
            "id": self.record['id'] if self.record else None,
            "nom": self.inp_nom.text().strip(),
            "date_debut": date_str,
            "obs": self.inp_obs.text().strip()
        }


# =====================================================================
# Dialog Sortie
# =====================================================================

class SortieDialog(BaseTopDialog):
    def __init__(self, manager, record=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.record = record
        title = "Modifier la sortie" if record else "Nouvelle Sortie"
        self.setWindowTitle(title)
        self.setFixedSize(550, 260)
        self.setStyleSheet("QDialog { background-color: white; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 10)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.inp_nom = QLineEdit()
        self.inp_nom.setStyleSheet(DIALOG_FIELD_STYLE)
        self.inp_nom.setPlaceholderText("Nom de l'ouvrier...")
        if self.record:
            self.inp_nom.setText(str(self.record.get('nom', '')))
        form.addRow("👤 Nom :", self._wrap_field_kb(self.inp_nom))

        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setDisplayFormat("dd/MM/yyyy")
        self.inp_date.setStyleSheet(DIALOG_FIELD_STYLE)
        if self.record and self.record.get('date_sortie'):
            d = str(self.record['date_sortie'])
            for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd"):
                date_obj = QDate.fromString(d, fmt)
                if date_obj.isValid():
                    self.inp_date.setDate(date_obj)
                    break
            else:
                self.inp_date.setDate(QDate.currentDate())
        else:
            self.inp_date.setDate(QDate.currentDate())
        form.addRow("🚪 Date :", self._wrap_field_kb(self.inp_date))

        self.inp_duree = QLineEdit()
        self.inp_duree.setStyleSheet(DIALOG_FIELD_STYLE)
        self.inp_duree.setPlaceholderText("Ex: 4 mois, 5 Ans...")
        if self.record:
            self.inp_duree.setText(str(self.record.get('duree_travail') or ''))
        form.addRow("⏳ Durée :", self._wrap_field_kb(self.inp_duree))

        layout.addLayout(form)
        layout.addStretch()

        btn_lay = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet(DIALOG_BTN_CANCEL_STYLE)
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)

        btn_save = QPushButton("✅ Enregistrer")
        btn_save.setStyleSheet(DIALOG_BTN_SAVE_STYLE)
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)
        layout.addLayout(btn_lay)

    def get_data(self):
        date_str = self.inp_date.date().toString("dd/MM/yyyy")
        return {
            "id": self.record['id'] if self.record else None,
            "nom": self.inp_nom.text().strip(),
            "date_sortie": date_str,
            "duree": self.inp_duree.text().strip()
        }


# =====================================================================
# Dialog Avance
# =====================================================================

class AvanceDialog(BaseTopDialog):
    def __init__(self, manager, record=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.record = record
        title = "Modifier l'avance" if record else "Nouvelle Avance"
        self.setWindowTitle(title)
        self.setFixedSize(550, 320)
        self.setStyleSheet("QDialog { background-color: white; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 10)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.inp_nom = QLineEdit()
        self.inp_nom.setStyleSheet(DIALOG_FIELD_STYLE)
        self.inp_nom.setPlaceholderText("Nom de l'ouvrier...")
        if self.record:
            self.inp_nom.setText(str(self.record.get('nom_ouvrier', '')))
        form.addRow("👤 Nom :", self._wrap_field_kb(self.inp_nom))

        self.inp_date = QDateEdit()
        self.inp_date.setCalendarPopup(True)
        self.inp_date.setDisplayFormat("dd/MM/yyyy")
        self.inp_date.setStyleSheet(DIALOG_FIELD_STYLE)
        if self.record and self.record.get('date_avance'):
            d = str(self.record['date_avance'])
            for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd"):
                date_obj = QDate.fromString(d, fmt)
                if date_obj.isValid():
                    self.inp_date.setDate(date_obj)
                    break
            else:
                self.inp_date.setDate(QDate.currentDate())
        else:
            self.inp_date.setDate(QDate.currentDate())
        form.addRow("📅 Date :", self._wrap_field_kb(self.inp_date))

        self.inp_montant = QLineEdit()
        self.inp_montant.setStyleSheet(DIALOG_FIELD_STYLE)
        self.inp_montant.setPlaceholderText("Montant en DA...")
        self.inp_montant.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if self.record:
            self.inp_montant.setText(str(self.record.get('montant_da', '')))
        form.addRow("💰 Montant :", self._wrap_field_num(self.inp_montant, allow_decimal=False))

        self.inp_obs = QLineEdit()
        self.inp_obs.setStyleSheet(DIALOG_FIELD_STYLE)
        self.inp_obs.setPlaceholderText("Observations...")
        if self.record:
            self.inp_obs.setText(str(self.record.get('observations') or ''))
        form.addRow("📝 Obs :", self._wrap_field_kb(self.inp_obs))

        layout.addLayout(form)
        layout.addStretch()

        btn_lay = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet(DIALOG_BTN_CANCEL_STYLE)
        btn_cancel.clicked.connect(self.reject)
        btn_lay.addWidget(btn_cancel)

        btn_save = QPushButton("✅ Enregistrer")
        btn_save.setStyleSheet(DIALOG_BTN_SAVE_STYLE)
        btn_save.clicked.connect(self.accept)
        btn_lay.addWidget(btn_save)
        layout.addLayout(btn_lay)

    def get_data(self):
        date_str = self.inp_date.date().toString("dd/MM/yyyy")
        return {
            "id": self.record['id'] if self.record else None,
            "nom": self.inp_nom.text().strip(),
            "date": date_str,
            "montant": self.inp_montant.text().strip(),
            "obs": self.inp_obs.text().strip()
        }


# =====================================================================
# Onglet Entrées
# =====================================================================

class EntreesTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.full_data = []
        self.init_ui()
        defer_initial_load(self, self._initial_load)

    def _initial_load(self):
        self._build_year_combo()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        filter_lay = QHBoxLayout()
        filter_lay.setSpacing(10)
        filter_lay.addWidget(QLabel("<b>Filtrer par :</b>"))

        self.combo_annee = QComboBox()
        self.combo_annee.setStyleSheet(FILTER_STYLE)
        self.combo_annee.addItem("Toutes les années", 0)
        self.combo_annee.currentIndexChanged.connect(self.on_filter_changed)
        filter_lay.addWidget(QLabel("Année:"))
        filter_lay.addWidget(self.combo_annee)

        self.combo_mois = QComboBox()
        self.combo_mois.setStyleSheet(FILTER_STYLE)
        self.combo_mois.addItem("Tous les mois", 0)
        mois_noms = ["Janvier","Février","Mars","Avril","Mai","Juin",
                      "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        for i in range(1, 13):
            self.combo_mois.addItem(f"{i:02d} - {mois_noms[i-1]}", i)
        self.combo_mois.currentIndexChanged.connect(self.on_filter_changed)
        filter_lay.addWidget(QLabel("Mois:"))
        filter_lay.addWidget(self.combo_mois)
        filter_lay.addStretch()
        layout.addLayout(filter_lay)

        header = QHBoxLayout()
        title = QLabel("📋 Date d'entrée des ouvriers")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("➕ Ajouter")
        btn_add.setStyleSheet(BTN_ADD_STYLE)
        btn_add.clicked.connect(self.open_add_dialog)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nom de l'ouvrier", "Date d'entrée", "Observations", "Actions"])
        self.table.setStyleSheet(EXCEL_STYLE)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(45)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 110)
        layout.addWidget(self.table)

    def _build_year_combo(self):
        self.combo_annee.blockSignals(True)
        current = self.combo_annee.currentData()
        self.combo_annee.clear()
        self.combo_annee.addItem("Toutes les années", 0)
        records = self.manager.rh.get_all_entrees()
        years = set()
        for r in records:
            year = extract_year(r.get('date_debut', ''))
            if year:
                years.add(year)
        for y in sorted(years, reverse=True):
            self.combo_annee.addItem(str(y), y)
        idx = self.combo_annee.findData(current)
        if idx >= 0:
            self.combo_annee.setCurrentIndex(idx)
        self.combo_annee.blockSignals(False)

    def on_filter_changed(self):
        self._apply_filter()

    def _apply_filter(self):
        annee = self.combo_annee.currentData()
        mois = self.combo_mois.currentData()
        filtered = []
        for r in self.full_data:
            d = str(r.get('date_debut', ''))
            rec_year = extract_year(d)
            rec_month = extract_month(d)
            
            ok = True
            if annee and annee != 0:
                if rec_year != annee:
                    ok = False
            if mois and mois != 0:
                if rec_month != mois:
                    ok = False
            if ok:
                filtered.append(r)
        self._render_table(filtered)

    def _render_table(self, records):
        self.table.setRowCount(0)
        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r.get('nom', ''))))
            self.table.setItem(row, 1, QTableWidgetItem(str(r.get('date_debut', ''))))
            self.table.setItem(row, 2, QTableWidgetItem(str(r.get('observations') or '')))

            container = QWidget()
            lay = QHBoxLayout(container)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(5)

            btn_edit = QPushButton("✏️")
            btn_edit.setFixedSize(45, 35)
            btn_edit.setStyleSheet(BTN_EDIT_ROW_STYLE)
            btn_edit.setToolTip("Modifier")
            btn_edit.clicked.connect(lambda _, rec=r: self.open_edit_dialog(rec))
            lay.addWidget(btn_edit)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(45, 35)
            btn_del.setStyleSheet(BTN_DEL_ROW_STYLE)
            btn_del.setToolTip("Supprimer")
            btn_del.clicked.connect(lambda _, rid=r['id']: self.delete_record(rid))
            lay.addWidget(btn_del)

            self.table.setCellWidget(row, 3, container)

    def load_data(self):
        self.full_data = self.manager.rh.get_all_entrees()
        self._build_year_combo()
        self._apply_filter()

    def open_add_dialog(self):
        dlg = EntreeDialog(self.manager, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data['nom']:
                self.manager.rh.add_entree(data['nom'], data['date_debut'], data['obs'])
                self.load_data()

    def open_edit_dialog(self, record):
        dlg = EntreeDialog(self.manager, record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.manager.rh.update_entree(data['id'], data['nom'], data['date_debut'], data['obs'])
            self.load_data()

    def delete_record(self, rid):
        if QMessageBox.question(self, "Confirmer", "Supprimer cette ligne ?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.rh.delete_entree(rid)
            self.load_data()


# =====================================================================
# Onglet Sorties
# =====================================================================

class SortiesTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.full_data = []
        self.init_ui()
        defer_initial_load(self, self._initial_load)

    def _initial_load(self):
        self._build_year_combo()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        filter_lay = QHBoxLayout()
        filter_lay.setSpacing(10)
        filter_lay.addWidget(QLabel("<b>Filtrer par :</b>"))

        self.combo_annee = QComboBox()
        self.combo_annee.setStyleSheet(FILTER_STYLE)
        self.combo_annee.addItem("Toutes les années", 0)
        self.combo_annee.currentIndexChanged.connect(self.on_filter_changed)
        filter_lay.addWidget(QLabel("Année:"))
        filter_lay.addWidget(self.combo_annee)

        self.combo_mois = QComboBox()
        self.combo_mois.setStyleSheet(FILTER_STYLE)
        self.combo_mois.addItem("Tous les mois", 0)
        mois_noms = ["Janvier","Février","Mars","Avril","Mai","Juin",
                      "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        for i in range(1, 13):
            self.combo_mois.addItem(f"{i:02d} - {mois_noms[i-1]}", i)
        self.combo_mois.currentIndexChanged.connect(self.on_filter_changed)
        filter_lay.addWidget(QLabel("Mois:"))
        filter_lay.addWidget(self.combo_mois)
        filter_lay.addStretch()
        layout.addLayout(filter_lay)

        header = QHBoxLayout()
        title = QLabel("🚪 Date de Sortie des ouvriers")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("➕ Ajouter")
        btn_add.setStyleSheet(BTN_ADD_STYLE)
        btn_add.clicked.connect(self.open_add_dialog)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nom de l'ouvrier", "Date de Sortie", "Durée", "Actions"])
        self.table.setStyleSheet(EXCEL_STYLE)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(45)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 110)
        layout.addWidget(self.table)

    def _build_year_combo(self):
        self.combo_annee.blockSignals(True)
        current = self.combo_annee.currentData()
        self.combo_annee.clear()
        self.combo_annee.addItem("Toutes les années", 0)
        records = self.manager.rh.get_all_sorties()
        years = set()
        for r in records:
            year = extract_year(r.get('date_sortie', ''))
            if year:
                years.add(year)
        for y in sorted(years, reverse=True):
            self.combo_annee.addItem(str(y), y)
        idx = self.combo_annee.findData(current)
        if idx >= 0:
            self.combo_annee.setCurrentIndex(idx)
        self.combo_annee.blockSignals(False)

    def on_filter_changed(self):
        self._apply_filter()

    def _apply_filter(self):
        annee = self.combo_annee.currentData()
        mois = self.combo_mois.currentData()
        filtered = []
        for r in self.full_data:
            d = str(r.get('date_sortie', ''))
            rec_year = extract_year(d)
            rec_month = extract_month(d)
            
            ok = True
            if annee and annee != 0:
                if rec_year != annee:
                    ok = False
            if mois and mois != 0:
                if rec_month != mois:
                    ok = False
            if ok:
                filtered.append(r)
        self._render_table(filtered)

    def _render_table(self, records):
        self.table.setRowCount(0)
        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r.get('nom', ''))))
            self.table.setItem(row, 1, QTableWidgetItem(str(r.get('date_sortie', ''))))
            self.table.setItem(row, 2, QTableWidgetItem(str(r.get('duree_travail') or '')))

            container = QWidget()
            lay = QHBoxLayout(container)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(5)

            btn_edit = QPushButton("✏️")
            btn_edit.setFixedSize(45, 35)
            btn_edit.setStyleSheet(BTN_EDIT_ROW_STYLE)
            btn_edit.setToolTip("Modifier")
            btn_edit.clicked.connect(lambda _, rec=r: self.open_edit_dialog(rec))
            lay.addWidget(btn_edit)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(45, 35)
            btn_del.setStyleSheet(BTN_DEL_ROW_STYLE)
            btn_del.setToolTip("Supprimer")
            btn_del.clicked.connect(lambda _, rid=r['id']: self.delete_record(rid))
            lay.addWidget(btn_del)

            self.table.setCellWidget(row, 3, container)

    def load_data(self):
        self.full_data = self.manager.rh.get_all_sorties()
        self._build_year_combo()
        self._apply_filter()

    def open_add_dialog(self):
        dlg = SortieDialog(self.manager, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data['nom']:
                self.manager.rh.add_sortie(data['nom'], data['date_sortie'], data['duree'])
                self.load_data()

    def open_edit_dialog(self, record):
        dlg = SortieDialog(self.manager, record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.manager.rh.update_sortie(data['id'], data['nom'], data['date_sortie'], data['duree'])
            self.load_data()

    def delete_record(self, rid):
        if QMessageBox.question(self, "Confirmer", "Supprimer cette ligne ?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.rh.delete_sortie(rid)
            self.load_data()


# =====================================================================
# Onglet Avances
# =====================================================================

class AvancesTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.full_data = []
        self.init_ui()
        defer_initial_load(self, self._initial_load)

    def _initial_load(self):
        self._build_year_combo()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        filter_lay = QHBoxLayout()
        filter_lay.setSpacing(10)
        filter_lay.addWidget(QLabel("<b>Filtrer par :</b>"))

        self.combo_annee = QComboBox()
        self.combo_annee.setStyleSheet(FILTER_STYLE)
        self.combo_annee.addItem("Toutes les années", 0)
        self.combo_annee.currentIndexChanged.connect(self.on_filter_changed)
        filter_lay.addWidget(QLabel("Année:"))
        filter_lay.addWidget(self.combo_annee)

        self.combo_mois = QComboBox()
        self.combo_mois.setStyleSheet(FILTER_STYLE)
        self.combo_mois.addItem("Tous les mois", 0)
        mois_noms = ["Janvier","Février","Mars","Avril","Mai","Juin",
                      "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        for i in range(1, 13):
            self.combo_mois.addItem(f"{i:02d} - {mois_noms[i-1]}", i)
        self.combo_mois.currentIndexChanged.connect(self.on_filter_changed)
        filter_lay.addWidget(QLabel("Mois:"))
        filter_lay.addWidget(self.combo_mois)
        filter_lay.addStretch()
        layout.addLayout(filter_lay)

        header = QHBoxLayout()
        title = QLabel("💸 Avances (Sallafia)")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        header.addWidget(title)
        header.addStretch()

        btn_add = QPushButton("➕ Ajouter")
        btn_add.setStyleSheet(BTN_ADD_STYLE)
        btn_add.clicked.connect(self.open_add_dialog)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nom de l'ouvrier", "Date", "Montant (DA)", "Actions"])
        self.table.setStyleSheet(EXCEL_STYLE)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(45)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 110)
        layout.addWidget(self.table)

    def _build_year_combo(self):
        self.combo_annee.blockSignals(True)
        current = self.combo_annee.currentData()
        self.combo_annee.clear()
        self.combo_annee.addItem("Toutes les années", 0)
        records = self.manager.rh.get_all_avances()
        years = set()
        for r in records:
            year = extract_year(r.get('date_avance', ''))
            if year:
                years.add(year)
        for y in sorted(years, reverse=True):
            self.combo_annee.addItem(str(y), y)
        idx = self.combo_annee.findData(current)
        if idx >= 0:
            self.combo_annee.setCurrentIndex(idx)
        self.combo_annee.blockSignals(False)

    def on_filter_changed(self):
        self._apply_filter()

    def _apply_filter(self):
        annee = self.combo_annee.currentData()
        mois = self.combo_mois.currentData()
        filtered = []
        total = 0.0
        for r in self.full_data:
            d = str(r.get('date_avance', ''))
            rec_year = extract_year(d)
            rec_month = extract_month(d)
            
            ok = True
            if annee and annee != 0:
                if rec_year != annee:
                    ok = False
            if mois and mois != 0:
                if rec_month != mois:
                    ok = False
            if ok:
                filtered.append(r)
                try:
                    total += float(str(r.get('montant_da', '0')).replace(' ', '').replace(',', '.'))
                except ValueError:
                    pass
        self._render_table(filtered, total)

    def _render_table(self, records, total=0.0):
        self.table.setRowCount(0)
        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r.get('nom_ouvrier', ''))))
            self.table.setItem(row, 1, QTableWidgetItem(str(r.get('date_avance', ''))))
            self.table.setItem(row, 2, QTableWidgetItem(str(r.get('montant_da', ''))))

            container = QWidget()
            lay = QHBoxLayout(container)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(5)

            btn_edit = QPushButton("✏️")
            btn_edit.setFixedSize(45, 35)
            btn_edit.setStyleSheet(BTN_EDIT_ROW_STYLE)
            btn_edit.setToolTip("Modifier")
            btn_edit.clicked.connect(lambda _, rec=r: self.open_edit_dialog(rec))
            lay.addWidget(btn_edit)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(45, 35)
            btn_del.setStyleSheet(BTN_DEL_ROW_STYLE)
            btn_del.setToolTip("Supprimer")
            btn_del.clicked.connect(lambda _, rid=r['id']: self.delete_record(rid))
            lay.addWidget(btn_del)

            self.table.setCellWidget(row, 3, container)

        if records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            it_lbl = QTableWidgetItem(f"TOTAL ({len(records)} lignes) :")
            it_lbl.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_lbl.setBackground(QBrush(QColor("#4472C4")))
            it_lbl.setForeground(QBrush(QColor("white")))
            it_lbl.setFont(QFont("", 13, QFont.Bold))
            self.table.setItem(row, 1, it_lbl)

            it_val = QTableWidgetItem(f"{total:,.0f} DA")
            it_val.setTextAlignment(Qt.AlignCenter)
            it_val.setBackground(QBrush(QColor("#4472C4")))
            it_val.setForeground(QBrush(QColor("white")))
            it_val.setFont(QFont("", 14, QFont.Bold))
            self.table.setItem(row, 2, it_val)

    def load_data(self):
        self.full_data = self.manager.rh.get_all_avances()
        self._build_year_combo()
        self._apply_filter()

    def open_add_dialog(self):
        dlg = AvanceDialog(self.manager, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if data['nom'] and data['montant']:
                self.manager.rh.add_avance(data['nom'], data['date'], data['montant'], data['obs'])
                self.load_data()

    def open_edit_dialog(self, record):
        dlg = AvanceDialog(self.manager, record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.manager.rh.update_avance(data['id'], data['nom'], data['date'], data['montant'], data['obs'])
            self.load_data()

    def delete_record(self, rid):
        if QMessageBox.question(self, "Confirmer", "Supprimer cette avance ?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.rh.delete_avance(rid)
            self.load_data()


# =====================================================================
# Vue Principale
# =====================================================================

class RHManagementView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        info = QLabel("📝 Mode libre : Aucune contrainte ni relation — Chaque ligne est indépendante")
        info.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                color: #1565c0;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 5px;
                border: 1px solid #90caf9;
            }
        """)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_HEADER_STYLE)

        self.tab_entrees = EntreesTab(self.manager)
        self.tabs.addTab(self.tab_entrees, "📋 Date d'entrée des ouvriers")

        self.tab_sorties = SortiesTab(self.manager)
        self.tabs.addTab(self.tab_sorties, "🚪 Date de Sortie des ouvriers")

        self.tab_avances = AvancesTab(self.manager)
        self.tabs.addTab(self.tab_avances, "💸 Avances (Sallafia)")

        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tabs)

    def on_tab_changed(self, index):
        if index == 0:
            self.tab_entrees.load_data()
        elif index == 1:
            self.tab_sorties.load_data()
        elif index == 2:
            self.tab_avances.load_data()