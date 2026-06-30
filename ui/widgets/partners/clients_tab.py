# ui/widgets/partners/clients_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, 
    QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt, QTimer
import qtawesome as qta

from ui.deferred_loading import defer_initial_load
from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)

class ClientsTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_edit_id = None
        
        # --- متغيرات الـ Lazy Loading والبحث ---
        self.current_offset = 0
        self.limit = 50
        self.current_search = ""
        self.is_loading = False
        self.has_more_data = True
        self._touch_keyboard = None
        
        # مؤقت للبحث (Debounce) لتخفيف الضغط على قاعدة البيانات
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # --- الجزء الأيسر: الجدول والتحكم ---
        table_container = QVBoxLayout()
        
        # أزرار التحكم العلوي
        btn_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton(" Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#2c3e50"))
        apply_touch_button_defaults(self.btn_refresh)
        self.btn_refresh.clicked.connect(self.refresh_data)

        self.btn_delete = QPushButton(" Supprimer")
        self.btn_delete.setIcon(qta.icon("fa5s.trash", color="#e74c3c"))
        apply_touch_button_defaults(self.btn_delete, danger=True)
        self.btn_delete.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_client)
        
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        table_container.addLayout(btn_layout)

        # مربع البحث الذكي
        search_row = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Rechercher client: nom, téléphone...")
        apply_touch_input_defaults(self.inp_search)
        self.inp_search.setStyleSheet("font-size: 15px; padding: 8px; border: 1px solid #bdc3c7; border-radius: 5px;")
        self.inp_search.textChanged.connect(self.on_search_text_changed)
        search_row.addWidget(self.inp_search, 1)
        self.btn_search_keyboard = QPushButton("Clavier")
        apply_touch_button_defaults(self.btn_search_keyboard)
        self.btn_search_keyboard.clicked.connect(lambda: self.open_virtual_keyboard(self.inp_search))
        search_row.addWidget(self.btn_search_keyboard)
        table_container.addLayout(search_row)

        # إعداد الجدول مع دعم التحميل التدريجي
        self.table = QTableWidget()
        apply_touch_table_defaults(self.table)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Nom du Client", "Téléphone"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        # ربط أحداث الجدول
        self.table.clicked.connect(self.on_table_click)
        self.table.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        table_container.addWidget(self.table)
        layout.addLayout(table_container, stretch=1)

        # --- الجزء الأيمن: نموذج الإضافة والتعديل ---
        form_wrapper = QGroupBox("Informations du Client")
        form_wrapper.setFixedWidth(350)
        form_layout = QVBoxLayout(form_wrapper)
        
        self.form = QFormLayout()
        self.inp_name = QLineEdit()
        self.inp_phone = QLineEdit()
        self.inp_address = QTextEdit()
        apply_touch_input_defaults(self.inp_name)
        apply_touch_input_defaults(self.inp_phone)
        apply_touch_input_defaults(self.inp_address)
        self.inp_address.setMaximumHeight(60)
        self.inp_notes = QTextEdit()
        apply_touch_input_defaults(self.inp_notes)
        self.inp_notes.setMaximumHeight(60)
        
        self.form.addRow("Nom:", self.inp_name)
        self.form.addRow("Tél:", self.inp_phone)
        self.form.addRow("Adresse:", self.inp_address)
        self.form.addRow("Notes:", self.inp_notes)
        form_layout.addLayout(self.form)
        
        actions_box = QHBoxLayout()
        self.btn_form_keyboard = QPushButton("Clavier")
        apply_touch_button_defaults(self.btn_form_keyboard)
        self.btn_form_keyboard.clicked.connect(lambda: self.open_virtual_keyboard(self.inp_name))
        actions_box.addWidget(self.btn_form_keyboard)

        self.btn_save = QPushButton(" Enregistrer")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        apply_touch_button_defaults(self.btn_save, primary=True)
        self.btn_save.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 8px;")
        self.btn_save.clicked.connect(self.save_client)
        
        self.btn_clear = QPushButton(" Nouveau")
        apply_touch_button_defaults(self.btn_clear)
        self.btn_clear.clicked.connect(self.clear_form)
        
        actions_box.addWidget(self.btn_save)
        actions_box.addWidget(self.btn_clear)
        form_layout.addLayout(actions_box)
        form_layout.addStretch()

        layout.addWidget(form_wrapper)
        
        # تحميل البيانات لأول مرة
        defer_initial_load(self, self.refresh_data)

    def open_virtual_keyboard(self, target=None):
        if target is not None:
            target.setFocus()
        if self._touch_keyboard is None:
            from ui.tools.virtual_keyboard import VirtualKeyboardDialog
            self._touch_keyboard = VirtualKeyboardDialog(self)
        self._touch_keyboard.show()
        self._touch_keyboard.raise_()

    def close_virtual_keyboard(self):
        if self._touch_keyboard and self._touch_keyboard.isVisible():
            self._touch_keyboard.close()

    # ==========================================
    # منطق Lazy Loading والبحث
    # ==========================================
    
    def on_search_text_changed(self, text):
        self.current_search = text.strip()
        self.search_timer.start(400)

    def perform_search(self):
        self.refresh_data()

    def on_scroll(self, value):
        if self.is_loading or not self.has_more_data:
            return
        scrollbar = self.table.verticalScrollBar()
        if value >= scrollbar.maximum() - 10:
            self.current_offset += self.limit
            self.load_data(append=True)

    def load_data(self, append=False):
        if self.is_loading: return
        self.is_loading = True
        
        if not append:
            self.table.setRowCount(0)
            self.current_offset = 0
            self.has_more_data = True
            
        clients = self.manager.clients.get_clients_paginated(
            search_text=self.current_search, 
            limit=self.limit, 
            offset=self.current_offset
        )
        
        if len(clients) < self.limit:
            self.has_more_data = False
            
        for client in clients:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(client['id'])))
            
            name_item = QTableWidgetItem(client['name'])
            name_item.setData(Qt.UserRole, client)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(client.get('phone') or ''))
            
        self.is_loading = False

    def refresh_data(self):
        self.load_data(append=False)

    # ==========================================
    # منطق التحكم في النموذج
    # ==========================================

    def on_table_click(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 1).data(Qt.UserRole)
        if data:
            self.current_edit_id = data['id']
            self.inp_name.setText(data['name'])
            self.inp_phone.setText(data.get('phone') or '')
            self.inp_address.setPlainText(data.get('address') or '')
            self.inp_notes.setPlainText(data.get('notes') or '')
            self.btn_save.setText(" Modifier")

    def save_client(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom est obligatoire.")
            return
            
        try:
            if self.current_edit_id:
                self.manager.clients.update_client(
                    self.current_edit_id, name, self.inp_phone.text(), 
                    self.inp_address.toPlainText(), self.inp_notes.toPlainText()
                )
            else:
                self.manager.clients.add_client(
                    name, self.inp_phone.text(), 
                    self.inp_address.toPlainText(), self.inp_notes.toPlainText()
                )
            self.refresh_data()
            self.clear_form()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def delete_client(self):
        if not self.current_edit_id: return
        if QMessageBox.question(self, "Confirm", "Supprimer ce client ?") == QMessageBox.Yes:
            if self.manager.clients.delete_client(self.current_edit_id):
                self.refresh_data()
                self.clear_form()
            else:
                QMessageBox.warning(self, "Erreur", "Action impossible (Dettes ou historique existant).")

    def clear_form(self):
        self.current_edit_id = None
        self.inp_name.clear()
        self.inp_phone.clear()
        self.inp_address.clear()
        self.inp_notes.clear()
        self.btn_save.setText(" Enregistrer")
        self.table.clearSelection()