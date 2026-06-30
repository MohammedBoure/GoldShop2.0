# ui/widgets/master_data/invoice_notes_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.deferred_loading import defer_initial_load

class InvoiceNotesTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # --- Table (Gauche) ---
        table_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#2c3e50"))
        self.btn_refresh.clicked.connect(self.load_data)
        
        self.btn_delete = QPushButton("Supprimer la sélection")
        self.btn_delete.setIcon(qta.icon("fa5s.trash", color="#e74c3c"))
        self.btn_delete.setProperty("class", "btn_danger")
        self.btn_delete.clicked.connect(self.delete_note)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        
        table_layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["ID", "Texte de la Note"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.clicked.connect(self.on_table_click)
        
        table_layout.addWidget(self.table)
        
        # --- Formulaire (Droite) ---
        form_container = QGroupBox("Gestion des Notes de Facture")
        form_container.setFixedWidth(400)
        form_layout = QVBoxLayout(form_container)
        
        form = QFormLayout()
        form.setVerticalSpacing(15)
        
        self.inp_note_text = QLineEdit()
        self.inp_note_text.setPlaceholderText("Ex: Produit vendu sans garantie...")

        form.addRow("Texte de la Note:", self.inp_note_text)
        
        form_layout.addLayout(form)
        
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.btn_save.setProperty("class", "btn_primary")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_note)
        
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
        notes = self.manager.invoice_notes.get_all_notes_with_ids()
        
        for row_idx, note in enumerate(notes):
            self.table.insertRow(row_idx)
            
            id_item = QTableWidgetItem(str(note['id']))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, id_item)
            
            note_text = str(note.get('note_text') or "")
            text_item = QTableWidgetItem(note_text)
            text_item.setData(Qt.UserRole, note)
            self.table.setItem(row_idx, 1, text_item)

    def save_note(self):
        text = self.inp_note_text.text().strip()

        if not text:
            QMessageBox.warning(self, "Attention", "Veuillez entrer le texte de la note.")
            return

        try:
            if self.current_edit_id:
                success = self.manager.invoice_notes.update_note(self.current_edit_id, text)
                if success:
                    pass # Mise à jour silencieuse ou message personnalisé
            else:
                success = self.manager.invoice_notes.add_note(text)
                if success: 
                    QMessageBox.information(self, "Succès", "Nouvelle note ajoutée.")
                else:
                    QMessageBox.warning(self, "Erreur", "La note existe déjà ou n'a pas pu être ajoutée.")
            
            self.clear_form()
            self.load_data()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{e}")

    def delete_note(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner une ligne.")
            return
            
        note_id = int(self.table.item(row, 0).text())
        note_text = self.table.item(row, 1).text()
        
        confirm = QMessageBox.question(self, "Confirmation", f"Supprimer la note :\n'{note_text}' ?", QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            if self.manager.invoice_notes.delete_note(note_id):
                self.load_data()
                self.clear_form()
            else:
                QMessageBox.warning(self, "Erreur", "Impossible de supprimer la note.")

    def on_table_click(self):
        row = self.table.currentRow()
        if row < 0: return
        item = self.table.item(row, 1)
        data = item.data(Qt.UserRole)
        
        if data:
            self.current_edit_id = data['id']
            self.inp_note_text.setText(data.get('note_text') or "")
            self.btn_save.setText("Modifier")

    def clear_form(self):
        self.current_edit_id = None
        self.inp_note_text.clear()
        self.btn_save.setText("Enregistrer")

    def refresh_data(self):
        self.load_data()
