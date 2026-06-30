# ui/widgets/settings/users_view.py

import json
import logging

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.deferred_loading import defer_initial_load
from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
    touch_button_stylesheet,
    touch_input_stylesheet,
    touch_table_stylesheet,
)

# =====================================================================
# شجرة الصلاحيات الحقيقية المعرفة برمجياً في البرنامج
# =====================================================================
PERMISSIONS_CATALOG = [
    {
        "label": "Navigation Principale",
        "icon": "fa5s.th-large",
        "children": [
            {"key": "nav_dashboard", "label": "Tableau de Bord", "icon": "fa5s.tachometer-alt"},
            {"key": "nav_inventory", "label": "Stock", "icon": "fa5s.box-open"},
            {"key": "nav_sales", "label": "Point de Vente", "icon": "fa5s.cash-register"},
            {"key": "nav_partners", "label": "Partenaires", "icon": "fa5s.handshake"},
            {"key": "nav_services", "label": "Services", "icon": "fa5s.concierge-bell"},
            {"key": "nav_finance", "label": "Finance", "icon": "fa5s.coins"},
            {"key": "nav_data", "label": "Données de Base", "icon": "fa5s.database"},
            {"key": "nav_settings", "label": "Paramètres", "icon": "fa5s.cogs"},
            {"key": "nav_reports", "label": "Rapports", "icon": "fa5s.file-excel"},
            {"key": "nav_history", "label": "Traçabilité", "icon": "fa5s.history"},
            {"key": "nav_market", "label": "Marché", "icon": "fa5s.globe-africa"},
            {"key": "nav_versement", "label": "Versements & Dettes", "icon": "fa5s.hand-holding-usd"},
            {"key": "nav_client_commands", "label": "Commandes Client", "icon": "fa5s.clipboard-list"},
            {"key": "nav_inventory_count", "label": "Inventaire Physique", "icon": "fa5s.tasks"},
            {"key": "nav_official_suppliers", "label": "Fournisseurs Officiels", "icon": "fa5s.truck"},
            {"key": "nav_rh", "label": "Gestion RH", "icon": "fa5s.users-cog"},
            {"key": "nav_coffre_magasin", "label": "Coffre Magasin", "icon": "fa5s.archive"},
        ]
    },
    {
        "label": "Onglets Stock", "icon": "fa5s.boxes",
        "children": [
            {"key": "tab_inv_list", "label": "Liste du Stock"},
            {"key": "tab_inv_form", "label": "Ajouter Produit / Achat OC"},
        ]
    },
    {
        "label": "Onglets Partenaires", "icon": "fa5s.users",
        "children": [
            {"key": "tab_clients", "label": "Clients"},
        ]
    },
    {
        "label": "Onglets Données de Base", "icon": "fa5s.list",
        "children": [
            {"key": "tab_metals", "label": "Types de Métaux"},
            {"key": "tab_categories", "label": "Catégories (Produits)"},
            {"key": "tab_product_names", "label": "Désignations (Noms)"},
            {"key": "tab_locations", "label": "Emplacements (Stock)"},
            {"key": "tab_invoice_notes", "label": "Notes Facture"},
        ]
    },
    {
        "label": "Onglets Paramètres", "icon": "fa5s.sliders-h",
        "children": [
            {"key": "tab_config", "label": "Configuration"},
            {"key": "tab_users", "label": "Utilisateurs"},
        ]
    },
    {
        "label": "Outils & Pied de page", "icon": "fa5s.tools",
        "children": [
            {"key": "footer_tools", "label": "Bouton Outils"},
            {"key": "footer_account", "label": "Bouton Compte"},
            {"key": "tool_calculator", "label": "Clavier Virtuel / Pavé Numérique"},
            {"key": "tool_audit", "label": "Contrôle Caisse"},
            {"key": "tool_zakat", "label": "Calculateur Zakat"},
            {"key": "tool_market_prices", "label": "Marché (Devises)"},
        ]
    },
    {
        "label": "Actions Spéciales", "icon": "fa5s.shield-alt",
        "children": [
            {"key": "act_account_switch", "label": "Changer de compte"},
            {"key": "act_account_logout", "label": "Déconnexion"},
        ]
    }
]
# =====================================================================

class PermissionsDialog(QDialog):
    """نافذة كبيرة ومريحة لإدارة الصلاحيات"""
    def __init__(self, parent=None, permissions_json="[]"):
        super().__init__(parent)
        self.setWindowTitle("Configuration des Permissions")
        self.setMinimumSize(850, 600)
        self.resize(1050, 750)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # شريط الأدوات العلوي
        toolbar = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("🔍 Rechercher une permission...")
        self.inp_search.setClearButtonEnabled(True)
        self.inp_search.textChanged.connect(self.filter_tree)
        apply_touch_input_defaults(self.inp_search)
        
        self.lbl_count = QLabel("0 sélection")
        self.lbl_count.setStyleSheet("background: #eef3f7; color: #34495e; border: 1px solid #d8e0e7; border-radius: 4px; padding: 5px 10px; font-weight: bold;")
        
        self.btn_expand = self._make_btn("Tout ouvrir", "fa5s.expand-alt")
        self.btn_expand.clicked.connect(lambda: self.tree.expandAll())
        self.btn_collapse = self._make_btn("Tout fermer", "fa5s.compress-alt")
        self.btn_collapse.clicked.connect(lambda: self.tree.collapseAll())
        
        toolbar.addWidget(self.inp_search, 1)
        toolbar.addWidget(self.lbl_count)
        toolbar.addWidget(self.btn_expand)
        toolbar.addWidget(self.btn_collapse)
        layout.addLayout(toolbar)

        # أزرار التحكم السريع
        actions = QHBoxLayout()
        self.btn_check_all = self._make_btn("Tout autoriser", "fa5s.check-double")
        self.btn_check_all.setStyleSheet("color: #27ae60; font-weight: bold;")
        self.btn_check_all.clicked.connect(lambda: self.set_all_state(Qt.Checked))
        
        self.btn_uncheck_all = self._make_btn("Tout retirer", "fa5s.times")
        self.btn_uncheck_all.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.btn_uncheck_all.clicked.connect(lambda: self.set_all_state(Qt.Unchecked))
        
        actions.addStretch()
        actions.addWidget(self.btn_check_all)
        actions.addWidget(self.btn_uncheck_all)
        layout.addLayout(actions)

        # شجرة الصلاحيات
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Permission", "Clé technique"])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree.setColumnWidth(1, 350)
        self.tree.itemChanged.connect(self.on_item_changed)
        apply_touch_table_defaults(self.tree)
        self._build_tree()
        layout.addWidget(self.tree, 1)

        # أزرار الحفظ في الأسفل
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Appliquer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        apply_touch_button_defaults(buttons.button(QDialogButtonBox.Ok), primary=True)
        apply_touch_button_defaults(buttons.button(QDialogButtonBox.Cancel))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # تحميل الصلاحيات الحالية
        self.set_permissions_json(permissions_json)

    def _make_btn(self, text, icon_name):
        btn = QPushButton(text)
        btn.setIcon(qta.icon(icon_name, color="#34495e"))
        apply_touch_button_defaults(btn)
        return btn

    def _build_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        font = QFont()
        font.setBold(True)
        for node in PERMISSIONS_CATALOG:
            self._add_node(self.tree, node, font, 0)
        self.tree.expandToDepth(0)
        self.tree.blockSignals(False)

    def _add_node(self, parent, node, font, depth):
        item = QTreeWidgetItem(parent)
        key = node.get("key")
        item.setText(0, node.get("label", key or ""))
        item.setText(1, key or "")
        item.setData(0, Qt.UserRole, key)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Unchecked)

        icon_color = "#007572" if depth == 0 else "#6b7280"
        icon = qta.icon(node.get("icon", "fa5s.circle"), color=icon_color)
        if icon: item.setIcon(0, icon)

        if depth == 0:
            item.setFont(0, font)
            item.setBackground(0, QBrush(QColor("#eef3f7")))

        for child in node.get("children", []):
            self._add_node(item, child, font, depth + 1)

    def on_item_changed(self, item, col):
        if col != 0: return
        self.tree.blockSignals(True)
        state = item.checkState(0)
        if item.childCount() > 0 and state != Qt.PartiallyChecked:
            self._set_children(item, state)
        self._refresh_parent(item.parent())
        self.tree.blockSignals(False)
        self._update_count()

    def _set_children(self, item, state):
        for i in range(item.childCount()):
            c = item.child(i)
            c.setCheckState(0, state)
            self._set_children(c, state)

    def _refresh_parent(self, parent):
        while parent:
            states = [parent.child(i).checkState(0) for i in range(parent.childCount())]
            if all(s == Qt.Checked for s in states): parent.setCheckState(0, Qt.Checked)
            elif all(s == Qt.Unchecked for s in states): parent.setCheckState(0, Qt.Unchecked)
            else: parent.setCheckState(0, Qt.PartiallyChecked)
            parent = parent.parent()

    def set_all_state(self, state):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, state)
            self._set_children(self.tree.topLevelItem(i), state)
        self.tree.blockSignals(False)
        self._update_count()

    def get_permissions_json(self):
        selected = []
        for i in range(self.tree.topLevelItemCount()):
            self._collect(self.tree.topLevelItem(i), selected)
        return json.dumps(selected)

    def _collect(self, item, sel):
        key = item.data(0, Qt.UserRole)
        if key and item.checkState(0) != Qt.Unchecked:
            sel.append(key)
        for i in range(item.childCount()):
            self._collect(item.child(i), sel)

    def set_permissions_json(self, json_str):
        self.tree.blockSignals(True)
        try: perms = set(json.loads(json_str) if json_str else [])
        except: perms = set()
        for i in range(self.tree.topLevelItemCount()):
            self._apply(self.tree.topLevelItem(i), perms)
        self.tree.blockSignals(False)
        self._update_count()

    def _apply(self, item, perms):
        key = item.data(0, Qt.UserRole)
        if item.childCount() == 0:
            item.setCheckState(0, Qt.Checked if key in perms else Qt.Unchecked)
            return item.checkState(0)
        child_states = [self._apply(item.child(i), perms) for i in range(item.childCount())]
        if all(s == Qt.Checked for s in child_states): item.setCheckState(0, Qt.Checked)
        elif key in perms or any(s != Qt.Unchecked for s in child_states): item.setCheckState(0, Qt.PartiallyChecked)
        else: item.setCheckState(0, Qt.Unchecked)
        return item.checkState(0)

    def _update_count(self):
        sel = len(json.loads(self.get_permissions_json()))
        self.lbl_count.setText(f"{sel} sélection(s)")

    def filter_tree(self):
        query = str(self.inp_search.text()).strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            self._filter_item(self.tree.topLevelItem(i), query)

    def _filter_item(self, item, query):
        match_child = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), query): match_child = True
        
        text_match = not query or query in item.text(0).lower() or query in str(item.text(1)).lower()
        visible = text_match or match_child
        item.setHidden(not visible)
        if visible and query: item.setExpanded(True)
        return visible


class UsersManagementView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.current_edit_id = None
        self._current_permissions_json = "[]"
        self.init_ui()

    def init_ui(self):
        self.setObjectName("UsersManagementView")
        self._apply_styles()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Gestion des Utilisateurs")
        title.setObjectName("pageTitle")
        self.lbl_user_count = QLabel("0 utilisateur")
        self.lbl_user_count.setObjectName("mutedLabel")
        title_box.addWidget(title)
        title_box.addWidget(self.lbl_user_count)
        header.addLayout(title_box)
        header.addStretch()

        self.btn_refresh = self._make_button("Actualiser", "fa5s.sync")
        self.btn_refresh.clicked.connect(self.load_users)
        self.btn_new_top = self._make_button("Nouveau", "fa5s.plus", primary=True)
        self.btn_new_top.clicked.connect(self.clear_form)
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_new_top)
        main_layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)
        main_layout.addWidget(splitter, 1)

        splitter.addWidget(self._build_users_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([400, 600])

        defer_initial_load(self, self.load_users)

    def _build_users_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Utilisateur", "Nom complet", "Rôle", "État"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        # تم تصحيح الخطأ: استخدام cellClicked بدلاً من clicked
        self.table.cellClicked.connect(self.on_table_click)
        apply_touch_table_defaults(self.table)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.btn_delete = self._make_button("Supprimer", "fa5s.trash", danger=True)
        self.btn_delete.clicked.connect(self.delete_user)
        footer.addStretch()
        footer.addWidget(self.btn_delete)
        layout.addLayout(footer)
        return panel

    def _build_editor_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- بيانات المستخدم ---
        form_box = QGroupBox("Fiche utilisateur")
        form_layout = QVBoxLayout(form_box)
        form_header = QHBoxLayout()
        self.lbl_form_mode = QLabel("Nouveau compte")
        self.lbl_form_mode.setObjectName("sectionTitle")
        self.chk_active = QCheckBox("Compte actif")
        self.chk_active.setChecked(True)
        form_header.addWidget(self.lbl_form_mode)
        form_header.addStretch()
        form_header.addWidget(self.chk_active)
        form_layout.addLayout(form_header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(14)
        
        self.inp_username = QLineEdit()
        self.inp_fullname = QLineEdit()
        self.inp_password = QLineEdit()
        self.inp_password.setEchoMode(QLineEdit.Password)
        self.inp_password.setPlaceholderText("Vide = garder l'ancien")
        self.combo_role = QComboBox()
        self.combo_role.addItems(["Sales", "Manager", "Admin", "Artisan"])
        
        for w in (self.inp_username, self.inp_fullname, self.inp_password, self.combo_role):
            apply_touch_input_defaults(w)
            
        self.btn_toggle_pwd = self._make_button("Afficher", "fa5s.eye")
        self.btn_toggle_pwd.setCheckable(True)
        self.btn_toggle_pwd.clicked.connect(self.toggle_pwd)

        form.addRow("Nom d'utilisateur", self.inp_username)
        form.addRow("Nom complet", self.inp_fullname)
        pwd_row = QHBoxLayout()
        pwd_row.addWidget(self.inp_password, 1)
        pwd_row.addWidget(self.btn_toggle_pwd)
        form.addRow("Mot de passe", pwd_row)
        form.addRow("Rôle", self.combo_role)
        form_layout.addLayout(form)

        actions = QHBoxLayout()
        self.btn_cancel = self._make_button("Vider", "fa5s.eraser")
        self.btn_cancel.clicked.connect(self.clear_form)
        self.btn_save_user = self._make_button("Enregistrer", "fa5s.save", primary=True)
        self.btn_save_user.clicked.connect(self.save_user)
        actions.addStretch()
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_save_user)
        form_layout.addLayout(actions)
        layout.addWidget(form_box)

        # --- ملخص الصلاحيات (مختصر) ---
        perms_box = QGroupBox("Droits et accès")
        perms_layout = QVBoxLayout(perms_box)
        
        self.lbl_perm_summary = QLabel("Aucune permission sélectionnée.")
        self.lbl_perm_summary.setObjectName("profileDescription")
        self.lbl_perm_summary.setWordWrap(True)
        self.lbl_perm_summary.setMinimumHeight(60)
        perms_layout.addWidget(self.lbl_perm_summary)
        
        self.btn_open_perms = self._make_button("Ouvrir la gestion des permissions", "fa5s.key", primary=True)
        self.btn_open_perms.setMinimumHeight(45)
        self.btn_open_perms.clicked.connect(self.open_permissions_dialog)
        perms_layout.addWidget(self.btn_open_perms)
        
        layout.addWidget(perms_box)
        return panel

    def _apply_styles(self):
        self.setStyleSheet(
            """
            #UsersManagementView { background: #f5f7f9; color: #1f2933; font-size: 13px; }
            #pageTitle { font-size: 22px; font-weight: 700; color: #17202a; }
            #sectionTitle { font-size: 15px; font-weight: 700; color: #17202a; }
            #mutedLabel { color: #6b7280; }
            #profileDescription { background: #f8fafc; color: #566573; border: 1px solid #d9e1e8; border-radius: 4px; padding: 10px; }
            QFrame#panel, QGroupBox { background: #ffffff; border: 1px solid #d9e1e8; border-radius: 6px; }
            QGroupBox { margin-top: 12px; padding: 12px; font-weight: 700; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #2f3b45; }
            QLineEdit, QComboBox { min-height: 30px; border: 1px solid #cfd8df; border-radius: 4px; padding: 4px 8px; background: #ffffff; }
            QPushButton { min-height: 30px; border: 1px solid #c9d3dc; border-radius: 4px; padding: 5px 10px; background: #ffffff; color: #24313d; font-weight: 600; }
            QPushButton:hover { background: #f0f5f8; border-color: #9fb1bf; }
            QPushButton[primary="true"] { background: #007572; color: #ffffff; border-color: #00635f; }
            QPushButton[primary="true"]:hover { background: #006a67; }
            QPushButton[danger="true"] { color: #b42318; border-color: #f0c7c2; }
            QTableWidget { border: 1px solid #d9e1e8; border-radius: 5px; background: #ffffff; alternate-background-color: #f8fafc; gridline-color: #eef2f6; selection-background-color: #dff2f1; selection-color: #17202a; }
            QHeaderView::section { background: #eef3f7; color: #34495e; border: none; border-right: 1px solid #d9e1e8; padding: 7px; font-weight: 700; }
            """
            + touch_button_stylesheet() + touch_input_stylesheet() + touch_table_stylesheet()
        )

    def _make_button(self, text, icon_name=None, primary=False, danger=False):
        button = QPushButton(text)
        if icon_name:
            color = "#ffffff" if primary else "#b42318" if danger else "#34495e"
            icon = qta.icon(icon_name, color=color)
            if icon is not None: button.setIcon(icon)
        apply_touch_button_defaults(button, primary=primary, danger=danger)
        return button

    def toggle_pwd(self, checked):
        self.inp_password.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self.btn_toggle_pwd.setText("Masquer" if checked else "Afficher")

    def open_permissions_dialog(self):
        dialog = PermissionsDialog(self, self._current_permissions_json)
        if dialog.exec() == QDialog.Accepted:
            self._current_permissions_json = dialog.get_permissions_json()
            self.update_perm_summary()

    def update_perm_summary(self):
        perms = json.loads(self._current_permissions_json)
        if not perms:
            self.lbl_perm_summary.setText("Aucune permission sélectionnée.\nL'utilisateur n'aura accès à aucune page.")
        else:
            self.lbl_perm_summary.setText(f"✅ {len(perms)} permission(s) sélectionnée(s).\nCliquez sur le bouton ci-dessous pour les modifier.")
            
    # ==========================================
    # منطق إدارة المستخدمين
    # ==========================================
    def load_users(self):
        self.table.setRowCount(0)
        try:
            users = list(self.manager.users.get_all_users())
            self.lbl_user_count.setText(f"{len(users)} utilisateur(s)")
            for row, user in enumerate(users):
                self.table.insertRow(row)
                item = QTableWidgetItem(str(user.get("username") or ""))
                item.setData(Qt.UserRole, user)
                self.table.setItem(row, 0, item)
                self.table.setItem(row, 1, QTableWidgetItem(str(user.get("full_name") or "")))
                self.table.setItem(row, 2, QTableWidgetItem(str(user.get("role") or "")))
                
                is_active = bool(user.get("is_active"))
                status = QTableWidgetItem("Actif" if is_active else "Inactif")
                status.setTextAlignment(Qt.AlignCenter)
                status.setForeground(QBrush(QColor("#007572" if is_active else "#b42318")))
                self.table.setItem(row, 3, status)
        except Exception as exc:
            logging.error("Error loading users: %s", exc)

    def on_table_click(self, row, col):
        item = self.table.item(row, 0)
        if not item: return
        user = item.data(Qt.UserRole)
        if not user: return

        self.current_edit_id = user.get("id")
        self.lbl_form_mode.setText(f"Modifier: {user.get('username')}")
        
        self.inp_username.setText(str(user.get("username") or ""))
        self.inp_fullname.setText(str(user.get("full_name") or ""))
        self.inp_password.clear()
        
        role_index = self.combo_role.findText(str(user.get("role") or ""))
        if role_index >= 0: self.combo_role.setCurrentIndex(role_index)
            
        self.chk_active.setChecked(bool(user.get("is_active", True)))
        self._current_permissions_json = user.get("permissions", "[]")
        self.update_perm_summary()

    def save_user(self):
        username = self.inp_username.text().strip()
        fullname = self.inp_fullname.text().strip()
        password = self.inp_password.text()
        role = self.combo_role.currentText()
        is_active = self.chk_active.isChecked()
        permissions = self._current_permissions_json

        if not username:
            QMessageBox.warning(self, "Erreur", "Le nom d'utilisateur est obligatoire.")
            return

        try:
            if self.current_edit_id:
                # تحديث مستخدم حالي (تم إصلاح هذه الدالة لتقبل كل البيانات)
                self.manager.users.update_user(
                    self.current_edit_id, 
                    full_name=fullname, 
                    role=role, 
                    is_active=is_active,
                    username=username,
                    password=password if password else None,
                    permissions=permissions
                )
                QMessageBox.information(self, "Succès", "Utilisateur mis à jour avec succès.")
            else:
                if not password:
                    QMessageBox.warning(self, "Erreur", "Le mot de passe est obligatoire pour un nouveau compte.")
                    return
                self.manager.users.add_user(username, password, fullname, role, permissions)
                QMessageBox.information(self, "Succès", "Nouvel utilisateur créé avec succès.")
            
            self.load_users()
            self.clear_form()
        except Exception as exc:
            logging.error("Error saving user: %s", exc)
            QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder:\n{exc}")

    def delete_user(self):
        if not self.current_edit_id:
            QMessageBox.warning(self, "Attention", "Sélectionnez un utilisateur à supprimer.")
            return
        reply = QMessageBox.question(self, "Confirmer", "Supprimer cet utilisateur définitivement ?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.manager.users.delete_user(self.current_edit_id)
                self.load_users()
                self.clear_form()
            except Exception as exc:
                QMessageBox.critical(self, "Erreur", f"Impossible de supprimer:\n{exc}")

    def clear_form(self):
        self.current_edit_id = None
        self.lbl_form_mode.setText("Nouveau compte")
        self.inp_username.clear()
        self.inp_fullname.clear()
        self.inp_password.clear()
        self.combo_role.setCurrentIndex(0)
        self.chk_active.setChecked(True)
        self.table.clearSelection()
        self._current_permissions_json = "[]"
        self.update_perm_summary()