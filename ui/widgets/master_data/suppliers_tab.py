# ui/widgets/master_data/suppliers_tab.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLineEdit, QFormLayout, QGroupBox, 
    QMessageBox, QTextEdit, QComboBox, QCheckBox, QLabel
)
from PySide6.QtCore import Qt, QTimer
import qtawesome as qta

from ui.deferred_loading import defer_initial_load
from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)

class SuppliersTab(QWidget):
    """Onglet Données de base - Répertoire des Fournisseurs (Suppliers)."""

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_edit_id = None
        
        self.current_offset = 0
        self.limit = 50
        self.current_search = ""
        self.is_loading = False
        self.has_more_data = True
        self._touch_keyboard = None
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        
        self.init_ui()
        defer_initial_load(self, self.refresh_data)

    def service(self):
        return self.manager.suppliers

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # --- الجزء الأيسر: الجدول والتحكم ---
        table_container = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton(" Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#2c3e50"))
        apply_touch_button_defaults(self.btn_refresh)
        self.btn_refresh.clicked.connect(self.refresh_data)

        self.btn_delete = QPushButton(" Supprimer / Désactiver")
        self.btn_delete.setIcon(qta.icon("fa5s.trash", color="#e74c3c"))
        apply_touch_button_defaults(self.btn_delete, danger=True)
        self.btn_delete.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_supplier)
        
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_delete)
        table_container.addLayout(btn_layout)

        # البحث
        search_row = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Rechercher fournisseur: nom, téléphone, adresse...")
        apply_touch_input_defaults(self.inp_search)
        self.inp_search.setStyleSheet("font-size: 15px; padding: 8px; border: 1px solid #bdc3c7; border-radius: 5px;")
        self.inp_search.textChanged.connect(self.on_search_text_changed)
        search_row.addWidget(self.inp_search, 1)

        self.btn_search_keyboard = QPushButton("Clavier")
        apply_touch_button_defaults(self.btn_search_keyboard)
        self.btn_search_keyboard.clicked.connect(lambda: self.open_virtual_keyboard(self.inp_search))
        search_row.addWidget(self.btn_search_keyboard)
        table_container.addLayout(search_row)

        # الجدول
        self.table = QTableWidget()
        apply_touch_table_defaults(self.table)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Nom du Fournisseur", "Type Métal", "Titre de Base", "Téléphone"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        self.table.clicked.connect(self.on_table_click)
        self.table.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
        table_container.addWidget(self.table)
        layout.addLayout(table_container, stretch=1)

        # --- الجزء الأيمن: نموذج الإضافة والتعديل ---
        form_wrapper = QGroupBox("Fiche Fournisseur")
        form_wrapper.setFixedWidth(380)
        form_layout = QVBoxLayout(form_wrapper)

        self.form = QFormLayout()
        
        self.inp_name = QLineEdit()
        apply_touch_input_defaults(self.inp_name)
        
        self.combo_type = QComboBox()
        self.combo_type.addItem("Or (Gold)", "Gold")
        self.combo_type.addItem("Argent (Silver)", "Silver")
        apply_touch_input_defaults(self.combo_type)

        self.inp_purity = QLineEdit()
        self.inp_purity.setPlaceholderText("Ex: 750, 875, 925, 999...")
        apply_touch_input_defaults(self.inp_purity)

        self.inp_phone = QLineEdit()
        apply_touch_input_defaults(self.inp_phone)

        self.inp_address = QTextEdit()
        self.inp_address.setMaximumHeight(60)

        self.check_active = QCheckBox("Actif")
        self.check_active.setChecked(True)

        self.form.addRow("Nom du Fournisseur *:", self.inp_name)
        self.form.addRow("Métal de base (Type):", self.combo_type)
        self.form.addRow("Titre de base (Pureté) *:", self.inp_purity)
        self.form.addRow("Téléphone:", self.inp_phone)
        self.form.addRow("Adresse:", self.inp_address)
        self.form.addRow("", self.check_active)

        form_layout.addLayout(self.form)

        # أزرار الإجراءات
        action_layout = QHBoxLayout()
        
        self.btn_save = QPushButton(" Enregistrer")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        apply_touch_button_defaults(self.btn_save, primary=True)
        self.btn_save.clicked.connect(self.save_supplier)

        self.btn_cancel = QPushButton(" Annuler")
        self.btn_cancel.setIcon(qta.icon("fa5s.times", color="#2c3e50"))
        apply_touch_button_defaults(self.btn_cancel)
        self.btn_cancel.clicked.connect(self.reset_form)

        action_layout.addWidget(self.btn_save)
        action_layout.addWidget(self.btn_cancel)
        form_layout.addLayout(action_layout)
        form_layout.addStretch()

        layout.addWidget(form_wrapper)

    def on_search_text_changed(self, text):
        self.search_timer.stop()
        self.search_timer.start(300)

    def perform_search(self):
        self.current_search = self.inp_search.text().strip()
        self.refresh_data()

    def refresh_data(self):
        self.current_offset = 0
        self.has_more_data = True
        self.table.setRowCount(0)
        self.load_more_data()
        self.reset_form()

    def load_more_data(self):
        if self.is_loading or not self.has_more_data:
            return

        self.is_loading = True
        try:
            suppliers = self.service().list_suppliers(
                search_text=self.current_search,
                active_only=False,
                limit=self.limit,
                offset=self.current_offset
            )

            if not suppliers:
                self.has_more_data = False
            else:
                if len(suppliers) < self.limit:
                    self.has_more_data = False
                
                for s in suppliers:
                    row = self.table.rowCount()
                    self.table.insertRow(row)

                    stype_raw = str(s.get("supplier_type") or "Gold").strip().lower()
                    stype = "Argent (Silver)" if stype_raw in ["argent", "silver"] else "Or (Gold)"
                    purity = str(s.get("primary_purity") or "750")
                    if purity == "750": purity += " (18K)"
                    elif purity == "925": purity += " (Argent)"

                    self.table.setItem(row, 0, QTableWidgetItem(str(s['id'])))
                    self.table.setItem(row, 1, QTableWidgetItem(str(s.get('name') or '')))
                    self.table.setItem(row, 2, QTableWidgetItem(stype))
                    self.table.setItem(row, 3, QTableWidgetItem(purity))
                    self.table.setItem(row, 4, QTableWidgetItem(str(s.get('phone') or '-')))

                    self.table.item(row, 0).setData(Qt.UserRole, s)

                self.current_offset += len(suppliers)

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement: {e}")
        finally:
            self.is_loading = False

    def on_scroll(self, value):
        max_scroll = self.table.verticalScrollBar().maximum()
        if value >= max_scroll - 5 and not self.is_loading and self.has_more_data:
            self.load_more_data()

    def on_table_click(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        item = self.table.item(row, 0)
        supplier_data = item.data(Qt.UserRole)
        
        if supplier_data:
            self.current_edit_id = supplier_data['id']
            self.inp_name.setText(str(supplier_data.get('name') or ''))
            
            stype = str(supplier_data.get('supplier_type') or 'Gold').strip()
            idx_t = self.combo_type.findData(stype)
            if idx_t < 0:
                if stype.lower() in ["silver", "argent"]:
                    idx_t = self.combo_type.findData("Silver")
                else:
                    idx_t = self.combo_type.findData("Gold")
            if idx_t >= 0: self.combo_type.setCurrentIndex(idx_t)

            purity = str(supplier_data.get('primary_purity') or '750')
            self.inp_purity.setText(purity)

            self.inp_phone.setText(str(supplier_data.get('phone') or ''))
            self.inp_address.setPlainText(str(supplier_data.get('address') or ''))
            self.check_active.setChecked(bool(supplier_data.get('is_active', True)))

            self.btn_save.setText(" Modifier")
            self.btn_save.setIcon(qta.icon("fa5s.edit", color="white"))

    def reset_form(self):
        self.current_edit_id = None
        self.inp_name.clear()
        self.combo_type.setCurrentIndex(0)
        self.inp_purity.setText("750")
        self.inp_phone.clear()
        self.inp_address.clear()
        self.check_active.setChecked(True)
        self.btn_save.setText(" Enregistrer")
        self.btn_save.setIcon(qta.icon("fa5s.save", color="white"))
        self.table.clearSelection()

    def save_supplier(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Attention", "Le nom du fournisseur est obligatoire.")
            return

        stype = self.combo_type.currentData() or "Gold"
        purity = self.inp_purity.text().strip() or "750"
        phone = self.inp_phone.text().strip() or None
        address = self.inp_address.toPlainText().strip() or None
        is_active = self.check_active.isChecked()

        try:
            if self.current_edit_id:
                success = self.service().update_supplier_details(
                    sid=self.current_edit_id,
                    name=name,
                    phone=phone,
                    address=address,
                    supplier_type=stype,
                    primary_purity=purity,
                    is_active=is_active
                )
                if not success:
                    QMessageBox.critical(self, "Erreur", "Impossible de mettre à jour le fournisseur.")
                    return
            else:
                new_id = self.service().create_supplier(
                    name=name,
                    phone=phone,
                    address=address,
                    supplier_type=stype,
                    primary_purity=purity,
                    is_active=is_active
                )
                if not new_id:
                    QMessageBox.critical(self, "Erreur", "Impossible d'enregistrer le fournisseur.")
                    return

            self.refresh_data()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'enregistrement: {e}")

    def delete_supplier(self):
        if not self.current_edit_id:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un fournisseur à supprimer.")
            return

        reply = QMessageBox.question(
            self, "Confirmation", 
            "Voulez-vous vraiment désactiver / supprimer ce fournisseur ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                deleted = self.service().delete_supplier(self.current_edit_id)
                if not deleted:
                    self.service().update_supplier_details(self.current_edit_id, is_active=False)
                else:
                    pass
                self.refresh_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {e}")

    def open_virtual_keyboard(self, target_widget):
        from ui.tools.virtual_keyboard import VirtualKeyboardDialog
        target_widget.setFocus()
        kb = VirtualKeyboardDialog(self.window())
        kb.show()
        kb.raise_()
