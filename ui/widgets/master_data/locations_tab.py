# ui/widgets/master_data/locations_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.deferred_loading import defer_initial_load

class LocationsTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # --- Tableau ---
        table_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#2c3e50"))
        self.btn_refresh.clicked.connect(self.load_data)
        
        self.btn_delete = QPushButton("Supprimer la sélection")
        self.btn_delete.setIcon(qta.icon("fa5s.trash", color="#e74c3c"))
        self.btn_delete.setProperty("class", "btn_danger")
        self.btn_delete.clicked.connect(self.delete_location)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        
        table_layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID", "Nom de l'Emplacement"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self.on_table_click)
        
        table_layout.addWidget(self.table)
        
        # --- Formulaire ---
        form_container = QGroupBox("Emplacements de Stockage")
        form_container.setFixedWidth(350)
        form_layout = QVBoxLayout(form_container)
        
        form = QFormLayout()
        form.setVerticalSpacing(15)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Ex: Vitrine A, Coffre-fort, Tiroir 1...")

        form.addRow("Emplacement:", self.inp_name)
        
        form_layout.addLayout(form)
        
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.btn_save.setProperty("class", "btn_primary")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_location)
        
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
        locations = self.manager.storage_locations.get_all_locations()
        
        for row_idx, loc in enumerate(locations):
            self.table.insertRow(row_idx)
            
            id_item = QTableWidgetItem(str(loc['id']))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)
            
            name_item = QTableWidgetItem(str(loc['name']))
            name_item.setTextAlignment(Qt.AlignCenter)
            name_item.setData(Qt.UserRole, loc)
            self.table.setItem(row_idx, 1, name_item)

    def save_location(self):
        name = self.inp_name.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Attention", "Veuillez entrer un nom d'emplacement.")
            return

        try:
            if self.current_edit_id:
                success = self.manager.storage_locations.update_location(self.current_edit_id, name)
                if success: pass
            else:
                new_id = self.manager.storage_locations.add_location(name)
                if new_id: QMessageBox.information(self, "Succès", "Nouvel emplacement ajouté.")
            
            self.clear_form()
            self.load_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{e}")

    def delete_location(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner une ligne.")
            return
            
        loc_id = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        
        confirm = QMessageBox.question(self, "Confirmation", f"Supprimer '{name}' ?", QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            if self.manager.storage_locations.delete_location(loc_id):
                self.load_data()
                self.clear_form()
            else:
                QMessageBox.warning(self, "Erreur", "Impossible de supprimer (Contient des articles).")

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
