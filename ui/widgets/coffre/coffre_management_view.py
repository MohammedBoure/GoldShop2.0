# ui/widgets/coffre/coffre_management_view.py
"""
Interface Coffre Magasin - Menu contextuel (Clic droit)
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLineEdit, QDialog, QMessageBox, 
    QLabel, QApplication, QAbstractItemView, QComboBox,
    QDateEdit, QFormLayout, QMenu
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QBrush, QAction  # 🟢 QAction من هنا

from ui.deferred_loading import defer_initial_load
from ui.tools.virtual_numpad import VirtualNumpad
from ui.tools.virtual_keyboard import VirtualKeyboardDialog


def extract_year(date_str):
    if not date_str: return None
    d = str(date_str).strip()
    if '/' in d:
        parts = d.split('/')
        if len(parts) == 3 and len(parts[2]) == 4:
            try: return int(parts[2])
            except ValueError: return None
    elif '-' in d:
        try: return int(d[:4])
        except ValueError: return None
    return None

def extract_month(date_str):
    if not date_str: return None
    d = str(date_str).strip()
    if '/' in d:
        parts = d.split('/')
        if len(parts) == 3:
            try: return int(parts[1])
            except ValueError: return None
    elif '-' in d:
        try: return int(d[5:7])
        except (ValueError, IndexError): return None
    return None

def safe_float(val):
    try: return float(str(val).replace(' ', '').replace(',', '.'))
    except (ValueError, TypeError): return 0.0


EXCEL_STYLE = """
    QTableWidget { background-color: white; gridline-color: #000000; font-size: 13px; border: 2px solid #000000; selection-background-color: #0078D7; selection-color: white; }
    QTableWidget::item { padding: 4px 6px; border-bottom: 1px solid #d0d0d0; border-right: 1px solid #d0d0d0; }
    QTableWidget::item:selected { background-color: #0078D7; color: white; }
    QHeaderView::section { background-color: #2c3e50; color: white; font-weight: bold; font-size: 13px; padding: 8px 6px; border: 1px solid #1a252f; }
"""
FILTER_STYLE = "QComboBox { font-size: 14px; font-weight: bold; padding: 6px 10px; border: 2px solid #bdc3c7; border-radius: 5px; background-color: #f8f9fa; min-width: 150px; }"
BTN_ADD_STYLE = "QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; padding: 8px 20px; border-radius: 5px; border: none; } QPushButton:hover { background-color: #219a52; }"
DIALOG_FIELD_STYLE = "font-size: 15px; font-weight: bold; padding: 7px; border: 2px solid #bdc3c7; border-radius: 6px; background-color: #f8f9fa;"
DIALOG_BTN_KB_STYLE = "QPushButton { background-color: #3498db; color: white; border-radius: 6px; font-size: 16px; border: none; padding: 4px; } QPushButton:hover { background-color: #2980b9; }"
DIALOG_BTN_NUM_STYLE = "QPushButton { background-color: #8e44ad; color: white; border-radius: 6px; font-size: 16px; border: none; padding: 4px; } QPushButton:hover { background-color: #7d3c98; }"
DIALOG_BTN_SAVE_STYLE = "QPushButton { background-color: #27ae60; color: white; font-weight: bold; font-size: 17px; padding: 10px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #219a52; }"
DIALOG_BTN_CANCEL_STYLE = "QPushButton { background-color: #95a5a6; color: white; font-weight: bold; font-size: 15px; padding: 8px; border-radius: 6px; border: none; } QPushButton:hover { background-color: #7f8c8d; }"
CONTEXT_MENU_STYLE = "QMenu { background-color: white; border: 2px solid #bdc3c7; border-radius: 8px; padding: 10px 5px; font-size: 15px; font-weight: bold; } QMenu::item { padding: 10px 35px 10px 20px; border-radius: 5px; } QMenu::item:selected { background-color: #0078D7; color: white; }"


class OperationDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        self.move(x, 0)

    def __init__(self, record=None, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("Modifier l'opération" if record else "Nouvelle Opération")
        self.setFixedSize(620, 480)
        self.setStyleSheet("QDialog { background-color: white; }")
        self.init_ui()

    def _open_keyboard(self, target):
        target.setFocus()
        kb = VirtualKeyboardDialog(self.window())
        kb.show(); kb.raise_()

    def _open_numpad(self, target, allow_decimal=True):
        target.setFocus()
        numpad = VirtualNumpad(title="Saisie", mode="direct", target_widget=target, allow_decimal=allow_decimal, allow_leading_zero=True, parent=self)
        numpad.show(); numpad.raise_()

    def _wrap_kb(self, widget):
        lay = QHBoxLayout(); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("⌨️"); btn.setFixedSize(44,44); btn.setStyleSheet(DIALOG_BTN_KB_STYLE)
        btn.clicked.connect(lambda: self._open_keyboard(widget)); lay.addWidget(btn)
        w = QWidget(); w.setLayout(lay); return w

    def _wrap_num(self, widget, allow_decimal=True):
        lay = QHBoxLayout(); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        lay.addWidget(widget, stretch=1)
        btn = QPushButton("🔢"); btn.setFixedSize(44,44); btn.setStyleSheet(DIALOG_BTN_NUM_STYLE)
        btn.clicked.connect(lambda: self._open_numpad(widget, allow_decimal)); lay.addWidget(btn)
        w = QWidget(); w.setLayout(lay); return w

    def init_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(15,10,15,8); layout.setSpacing(8)
        form = QFormLayout(); form.setSpacing(8); form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.inp_date = QDateEdit(); self.inp_date.setCalendarPopup(True); self.inp_date.setDisplayFormat("dd/MM/yyyy"); self.inp_date.setStyleSheet(DIALOG_FIELD_STYLE)
        if self.record and self.record.get('date_operation'):
            d = str(self.record['date_operation'])
            for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd"):
                date_obj = QDate.fromString(d, fmt)
                if date_obj.isValid(): self.inp_date.setDate(date_obj); break
            else: self.inp_date.setDate(QDate.currentDate())
        else: self.inp_date.setDate(QDate.currentDate())
        form.addRow("📅 Date :", self._wrap_kb(self.inp_date))

        fields = [("💰 Montant (DA) :", "montant_da"), ("💳 TPE :", "tpe"), ("📮 CCP :", "ccp"), ("💶 Euro :", "euro"), ("💵 Dollar :", "dollar")]
        self.inp_fields = {}
        for label, key in fields:
            inp = QLineEdit(); inp.setStyleSheet(DIALOG_FIELD_STYLE); inp.setAlignment(Qt.AlignRight | Qt.AlignVCenter); inp.setPlaceholderText("0")
            if self.record: inp.setText(str(self.record.get(key, '0')))
            self.inp_fields[key] = inp
            form.addRow(label, self._wrap_num(inp, allow_decimal=True))

        self.inp_designation = QLineEdit(); self.inp_designation.setStyleSheet(DIALOG_FIELD_STYLE); self.inp_designation.setPlaceholderText("Désignation...")
        if self.record: self.inp_designation.setText(str(self.record.get('designation') or ''))
        form.addRow("📝 Désignation :", self._wrap_kb(self.inp_designation))

        layout.addLayout(form); layout.addStretch()
        btn_lay = QHBoxLayout()
        btn_cancel = QPushButton("Annuler"); btn_cancel.setStyleSheet(DIALOG_BTN_CANCEL_STYLE); btn_cancel.clicked.connect(self.reject); btn_lay.addWidget(btn_cancel)
        btn_save = QPushButton("✅ Enregistrer"); btn_save.setStyleSheet(DIALOG_BTN_SAVE_STYLE); btn_save.clicked.connect(self.accept); btn_lay.addWidget(btn_save)
        layout.addLayout(btn_lay)

    def get_data(self):
        return {
            "id": self.record['id'] if self.record else None,
            "date_operation": self.inp_date.date().toString("dd/MM/yyyy"),
            "montant_da": self.inp_fields['montant_da'].text().strip() or "0",
            "tpe": self.inp_fields['tpe'].text().strip() or "0",
            "ccp": self.inp_fields['ccp'].text().strip() or "0",
            "euro": self.inp_fields['euro'].text().strip() or "0",
            "dollar": self.inp_fields['dollar'].text().strip() or "0",
            "designation": self.inp_designation.text().strip()
        }


class CoffreMagasinView(QWidget):
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
        layout = QVBoxLayout(self); layout.setContentsMargins(5,5,5,5); layout.setSpacing(8)

        self.lbl_title = QLabel("🏦 État Coffre Magasin")
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: white; background-color: #2c3e50; padding: 12px; border-radius: 8px;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_title)

        filter_lay = QHBoxLayout(); filter_lay.setSpacing(10); filter_lay.addWidget(QLabel("<b>Filtrer par :</b>"))
        self.combo_annee = QComboBox(); self.combo_annee.setStyleSheet(FILTER_STYLE); self.combo_annee.addItem("Toutes les années", 0); self.combo_annee.currentIndexChanged.connect(self._update_title_and_filter)
        filter_lay.addWidget(QLabel("Année:")); filter_lay.addWidget(self.combo_annee)
        self.combo_mois = QComboBox(); self.combo_mois.setStyleSheet(FILTER_STYLE); self.combo_mois.addItem("Tous les mois", 0)
        mois_noms = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        for i in range(1, 13): self.combo_mois.addItem(f"{i:02d} - {mois_noms[i-1]}", i)
        self.combo_mois.currentIndexChanged.connect(self._update_title_and_filter)
        filter_lay.addWidget(QLabel("Mois:")); filter_lay.addWidget(self.combo_mois); filter_lay.addStretch()
        layout.addLayout(filter_lay)

        header = QHBoxLayout(); header.addStretch()
        btn_add = QPushButton("➕ Nouvelle Opération"); btn_add.setStyleSheet(BTN_ADD_STYLE); btn_add.clicked.connect(self.open_add_dialog)
        header.addWidget(btn_add); layout.addLayout(header)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Date", "Montant (DA)", "TPE", "CCP", "Euro", "Dollar", "Désignation"])
        self.table.setStyleSheet(EXCEL_STYLE)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.Stretch)
        layout.addWidget(self.table)

    def show_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0: return
        record = self.full_data[row] if row < len(self.full_data) else None
        if not record: return

        menu = QMenu(self); menu.setStyleSheet(CONTEXT_MENU_STYLE)
        action_edit = QAction("✏️  Modifier cette opération", self)
        action_edit.triggered.connect(lambda: self.open_edit_dialog(record))
        menu.addAction(action_edit)
        action_del = QAction("🗑️  Supprimer cette opération", self)
        action_del.triggered.connect(lambda: self.delete_record(record['id']))
        menu.addAction(action_del)
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _update_title_and_filter(self):
        annee = self.combo_annee.currentData(); mois = self.combo_mois.currentData()
        mois_noms = ["", "Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        titre = "🏦 État Coffre Magasin"
        if annee and annee != 0:
            titre += f" - {annee}"
            if mois and mois != 0: titre += f" - {mois_noms[mois]}"
        self.lbl_title.setText(titre)
        self._apply_filter()

    def _build_year_combo(self):
        self.combo_annee.blockSignals(True); current = self.combo_annee.currentData()
        self.combo_annee.clear(); self.combo_annee.addItem("Toutes les années", 0)
        years = set()
        for r in self.full_data:
            year = extract_year(r.get('date_operation', ''))
            if year: years.add(year)
        for y in sorted(years, reverse=True): self.combo_annee.addItem(str(y), y)
        idx = self.combo_annee.findData(current)
        if idx >= 0: self.combo_annee.setCurrentIndex(idx)
        self.combo_annee.blockSignals(False)

    def _apply_filter(self):
        annee = self.combo_annee.currentData(); mois = self.combo_mois.currentData()
        filtered = []
        for r in self.full_data:
            d = str(r.get('date_operation', ''))
            rec_year = extract_year(d); rec_month = extract_month(d)
            ok = True
            if annee and annee != 0 and rec_year != annee: ok = False
            if mois and mois != 0 and rec_month != mois: ok = False
            if ok: filtered.append(r)
        self._render_table(filtered)

    def _color_for_amount(self, val_str):
        val = safe_float(val_str)
        if val < 0: return QColor("#e74c3c")
        elif val > 0: return QColor("#27ae60")
        return QColor("#2c3e50")

    def _render_table(self, records):
        self.table.setRowCount(0)
        total_da = total_tpe = total_ccp = total_euro = total_dollar = 0.0

        for r in records:
            row = self.table.rowCount(); self.table.insertRow(row)
            montant = safe_float(r.get('montant_da', '0')); tpe = safe_float(r.get('tpe', '0'))
            ccp = safe_float(r.get('ccp', '0')); euro = safe_float(r.get('euro', '0')); dollar = safe_float(r.get('dollar', '0'))
            total_da += montant; total_tpe += tpe; total_ccp += ccp; total_euro += euro; total_dollar += dollar
            color = self._color_for_amount(r.get('montant_da', '0'))

            def m_item(text, align=Qt.AlignCenter, color=None, bold=False):
                it = QTableWidgetItem(str(text)); it.setTextAlignment(align)
                if color: it.setForeground(QBrush(color))
                if bold: it.setFont(QFont("", 11, QFont.Bold))
                return it

            self.table.setItem(row, 0, m_item(r.get('date_operation', '')))
            self.table.setItem(row, 1, m_item(r.get('montant_da', '0'), color=color, bold=True))
            self.table.setItem(row, 2, m_item(r.get('tpe', '0')))
            self.table.setItem(row, 3, m_item(r.get('ccp', '0')))
            self.table.setItem(row, 4, m_item(r.get('euro', '0')))
            self.table.setItem(row, 5, m_item(r.get('dollar', '0')))
            self.table.setItem(row, 6, m_item(r.get('designation') or '', align=Qt.AlignLeft | Qt.AlignVCenter))

        if records:
            row = self.table.rowCount(); self.table.insertRow(row)
            it_lbl = QTableWidgetItem("TOTAUX :"); it_lbl.setTextAlignment(Qt.AlignCenter)
            it_lbl.setBackground(QBrush(QColor("#2c3e50"))); it_lbl.setForeground(QBrush(QColor("white"))); it_lbl.setFont(QFont("", 12, QFont.Bold))
            self.table.setItem(row, 0, it_lbl)
            for i, val in enumerate([total_da, total_tpe, total_ccp, total_euro, total_dollar]):
                it = QTableWidgetItem(f"{val:,.2f}"); it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(QBrush(QColor("#2c3e50"))); it.setForeground(QBrush(QColor("white"))); it.setFont(QFont("", 11, QFont.Bold))
                self.table.setItem(row, i + 1, it)
            it_empty = QTableWidgetItem(""); it_empty.setBackground(QBrush(QColor("#2c3e50")))
            self.table.setItem(row, 6, it_empty)

    def load_data(self):
        self.full_data = self.manager.coffre.get_all_operations()
        self._build_year_combo()
        self._update_title_and_filter()

    def open_add_dialog(self):
        dlg = OperationDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.coffre.add_operation(d['date_operation'], d['montant_da'], d['tpe'], d['ccp'], d['euro'], d['dollar'], d['designation'])
            self.load_data()

    def open_edit_dialog(self, record):
        dlg = OperationDialog(record=record, parent=self)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.get_data()
            self.manager.coffre.update_operation(d['id'], d['date_operation'], d['montant_da'], d['tpe'], d['ccp'], d['euro'], d['dollar'], d['designation'])
            self.load_data()

    def delete_record(self, rid):
        if QMessageBox.question(self, "Confirmer", "Supprimer cette opération ?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.manager.coffre.delete_operation(rid)
            self.load_data()









