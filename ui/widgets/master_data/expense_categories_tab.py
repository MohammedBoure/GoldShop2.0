# ui/widgets/finance/expense_categories_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QLabel, QMessageBox, QFrame
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.deferred_loading import defer_initial_load

class ExpenseCategoriesTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        
        # الجدول
        table_layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID", "Catégorie Dépense"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self.fill_form)
        table_layout.addWidget(self.table)
        layout.addLayout(table_layout, stretch=2)

        # النموذج
        form_frame = QFrame()
        form_frame.setFixedWidth(300)
        form_frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 8px;")
        form_layout = QVBoxLayout(form_frame)
        
        title = QLabel("Catégories de Dépenses")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        title.setAlignment(Qt.AlignCenter)
        form_layout.addWidget(title)

        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Ex: Taxes, Internet...")
        form_layout.addWidget(self.inp_name)

        self.btn_add = QPushButton("Ajouter")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_add.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        self.btn_add.clicked.connect(self.add_cat)
        form_layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("Modifier")
        self.btn_edit.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 8px;")
        self.btn_edit.clicked.connect(self.edit_cat)
        self.btn_edit.setEnabled(False)
        form_layout.addWidget(self.btn_edit)

        self.btn_del = QPushButton("Supprimer")
        self.btn_del.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 8px;")
        self.btn_del.clicked.connect(self.delete_cat)
        self.btn_del.setEnabled(False)
        form_layout.addWidget(self.btn_del)
        
        self.btn_clear = QPushButton("Annuler")
        self.btn_clear.setFlat(True)
        self.btn_clear.clicked.connect(self.clear_form)
        form_layout.addWidget(self.btn_clear)

        form_layout.addStretch()
        layout.addWidget(form_frame)

        self.current_id = None
        defer_initial_load(self, self.load_data)

    def load_data(self):
        self.table.setRowCount(0)
        cats = self.manager.expense_categories.get_all()
        for i, c in enumerate(cats):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(c['id'])))
            self.table.setItem(i, 1, QTableWidgetItem(c['name']))

    def fill_form(self):
        row = self.table.currentRow()
        if row < 0: return
        self.current_id = int(self.table.item(row, 0).text())
        self.inp_name.setText(self.table.item(row, 1).text())
        self.btn_add.setEnabled(False)
        self.btn_edit.setEnabled(True)
        self.btn_del.setEnabled(True)

    def clear_form(self):
        self.current_id = None
        self.inp_name.clear()
        self.btn_add.setEnabled(True)
        self.btn_edit.setEnabled(False)
        self.btn_del.setEnabled(False)
        self.table.clearSelection()

    def add_cat(self):
        name = self.inp_name.text().strip()
        if not name: return
        ok, msg = self.manager.expense_categories.add_category(name)
        if ok: self.load_data(); self.clear_form()
        else: QMessageBox.critical(self, "Erreur", msg)

    def edit_cat(self):
        if not self.current_id: return
        ok, msg = self.manager.expense_categories.update_category(self.current_id, self.inp_name.text().strip())
        if ok: self.load_data(); self.clear_form()

    def delete_cat(self):
        if not self.current_id: return
        if QMessageBox.question(self, "Confirmer", "Supprimer ?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            ok, msg = self.manager.expense_categories.delete_category(self.current_id)
            if ok: self.load_data(); self.clear_form()
            else: QMessageBox.warning(self, "Erreur", msg)
