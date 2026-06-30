# ui/widgets/master_data/product_names_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.deferred_loading import defer_initial_load

class ProductNamesTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # --- Tableau (Gauche) ---
        table_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#2c3e50"))
        self.btn_refresh.clicked.connect(self.load_data)
        
        self.btn_delete = QPushButton("Supprimer la sélection")
        self.btn_delete.setIcon(qta.icon("fa5s.trash", color="#e74c3c"))
        self.btn_delete.setProperty("class", "btn_danger")
        self.btn_delete.clicked.connect(self.delete_name)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        
        table_layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID", "Désignation (Nom du Produit)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self.on_table_click)
        
        table_layout.addWidget(self.table)
        
        # --- Formulaire (Droite) ---
        form_container = QGroupBox("Dictionnaire des Noms")
        form_container.setFixedWidth(350)
        form_layout = QVBoxLayout(form_container)
        
        form = QFormLayout()
        form.setVerticalSpacing(15)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Ex: Bague, Bracelet, Montre...")

        form.addRow("Désignation:", self.inp_name)
        
        form_layout.addLayout(form)
        
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.btn_save.setProperty("class", "btn_primary")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_name)
        
        self.btn_clear = QPushButton("Nouveau / Annuler")
        self.btn_clear.clicked.connect(self.clear_form)
        
        self.current_edit_id = None 

        form_layout.addSpacing(20)
        form_layout.addWidget(self.btn_save)
        form_layout.addWidget(self.btn_clear)
        form_layout.addStretch()

        layout.addLayout(table_layout, stretch=1)
        layout.addWidget(form_container)
        
        defer_initial_load(self, self.load_data)

    def load_data(self):
        self.table.setRowCount(0)
        names = self.manager.product_names.get_all_product_names()
        
        for row_idx, item in enumerate(names):
            self.table.insertRow(row_idx)
            
            id_item = QTableWidgetItem(str(item['id']))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)
            
            name_item = QTableWidgetItem(str(item['name']))
            name_item.setTextAlignment(Qt.AlignCenter)
            name_item.setData(Qt.UserRole, item)
            self.table.setItem(row_idx, 1, name_item)

    def save_name(self):
        name = self.inp_name.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Attention", "Veuillez entrer une désignation.")
            return

        try:
            if self.current_edit_id:
                success = self.manager.product_names.update_product_name(self.current_edit_id, name)
                if success: pass
            else:
                new_id = self.manager.product_names.add_product_name(name)
                if new_id: 
                    QMessageBox.information(self, "Succès", "Nouveau nom ajouté au dictionnaire.")
                else:
                    QMessageBox.warning(self, "Info", "Ce nom existe déjà dans la liste.")
            
            self.clear_form()
            self.load_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{e}")

    def delete_name(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner une ligne.")
            return
            
        name_id = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        
        confirm = QMessageBox.question(self, "Confirmation", f"Supprimer '{name}' du dictionnaire ?", QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            if self.manager.product_names.delete_product_name(name_id):
                self.load_data()
                self.clear_form()

    def on_table_click(self):
        row = self.table.currentRow()
        if row < 0: return
        item = self.table.item(row, 1)
        data = item.data(Qt.UserRole)
        
        if data:
            self.current_edit_id = data['id']
            self.inp_name.setText(data['name'])
            self.btn_save.setText("Modifier")

    def clear_form(self):
        self.current_edit_id = None
        self.inp_name.clear()
        self.btn_save.setText("Enregistrer")

    def refresh_data(self):
        self.load_data()
