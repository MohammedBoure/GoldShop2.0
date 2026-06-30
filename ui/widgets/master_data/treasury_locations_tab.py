# ui/widgets/master_data/treasury_locations_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, QMessageBox,
    QComboBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.deferred_loading import defer_initial_load

class TreasuryLocationsTab(QWidget):
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
        
        # تفعيل/تعطيل بدل الحذف الكامل
        self.btn_toggle = QPushButton("Activer/Désactiver")
        self.btn_toggle.setIcon(qta.icon("fa5s.power-off", color="#e67e22"))
        self.btn_toggle.clicked.connect(self.toggle_status)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_toggle)
        
        table_layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nom", "Type", "État"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self.on_table_click)
        
        table_layout.addWidget(self.table)
        
        # --- Formulaire ---
        form_container = QGroupBox("Coffres & Caisses")
        form_container.setFixedWidth(350)
        form_layout = QVBoxLayout(form_container)
        
        form = QFormLayout()
        form.setVerticalSpacing(15)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Ex: Caisse Principale, Coffre Bureau")
        
        self.combo_type = QComboBox()
        self.combo_type.addItem("Caisse (REGISTER)", "REGISTER")
        self.combo_type.addItem("Coffre-fort (SAFE)", "SAFE")
        
        self.inp_desc = QLineEdit()
        self.inp_desc.setPlaceholderText("Description...")

        form.addRow("Nom:", self.inp_name)
        form.addRow("Type:", self.combo_type)
        form.addRow("Description:", self.inp_desc)
        
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
        # جلب الجميع (النشط وغير النشط)
        locations = self.manager.treasury.get_all_locations(only_active=False)
        
        for row_idx, loc in enumerate(locations):
            self.table.insertRow(row_idx)
            
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(loc['id'])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(loc['name'])))
            
            type_text = "Caisse" if loc['type'] == 'REGISTER' else "Coffre"
            self.table.setItem(row_idx, 2, QTableWidgetItem(type_text))
            
            status_text = "Actif" if loc['is_active'] else "Inactif"
            status_item = QTableWidgetItem(status_text)
            if not loc['is_active']:
                status_item.setForeground(Qt.red)
            self.table.setItem(row_idx, 3, status_item)
            
            # Stocker data
            status_item.setData(Qt.UserRole, loc)

    def save_location(self):
        name = self.inp_name.text().strip()
        loc_type = self.combo_type.currentData()
        desc = self.inp_desc.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Attention", "Le nom est obligatoire.")
            return

        try:
            if self.current_edit_id:
                # Update logic (Update name/desc only)
                if self.manager.treasury.update_location(self.current_edit_id, name, desc):
                    pass
            else:
                # Create logic
                if self.manager.treasury.create_location(name, loc_type, desc):
                    pass
            
            self.clear_form()
            self.load_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{e}")

    def toggle_status(self):
        row = self.table.currentRow()
        if row < 0: return
        
        item = self.table.item(row, 3)
        data = item.data(Qt.UserRole)
        
        if data:
            new_status = not bool(data['is_active'])
            action = "Activer" if new_status else "Désactiver"
            
            confirm = QMessageBox.question(self, "Confirmation", f"Voulez-vous {action} '{data['name']}' ?", QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                self.manager.treasury.toggle_active_status(data['id'], new_status)
                self.load_data()

    def on_table_click(self):
        row = self.table.currentRow()
        if row < 0: return
        item = self.table.item(row, 3)
        data = item.data(Qt.UserRole)
        
        if data:
            self.current_edit_id = data['id']
            self.inp_name.setText(data['name'])
            
            index = self.combo_type.findData(data['type'])
            if index >= 0: self.combo_type.setCurrentIndex(index)
            
            self.inp_desc.setText(data.get('description', ''))
            
            self.btn_save.setText("Modifier (Nom/Desc)")
            self.combo_type.setEnabled(False) 
            
    def clear_form(self):
        self.current_edit_id = None
        self.inp_name.clear()
        self.inp_desc.clear()
        self.combo_type.setEnabled(True)
        self.btn_save.setText("Enregistrer")

    def refresh_data(self):
        self.load_data()
