from __future__ import annotations

import qtawesome as qta
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)
from ui.widgets.inventory.touch_product_entry import wrap_with_numpad

from .helpers import EXTRA_STATUSES, SESSION_STATUSES, SESSION_TARGET_STATUSES


class InventoryCountUiMixin:
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_overview_page())
        self.stack.addWidget(self._build_counting_page())

        self._connect_signals()
        self._clear_scan_result()
        self._update_actions()
    def _build_overview_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Inventaire physique")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()

        self.btn_new = self._button("Nouvelle session", "fa5s.plus-circle", "inventory_count_create", primary=True)
        self.btn_refresh = self._button("Actualiser", "fa5s.sync-alt", "inventory_count_view")
        self.btn_open_session = self._button("Entrer session", "fa5s.sign-in-alt", "inventory_count_view", primary=True)
        header.addWidget(self.btn_new)
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_open_session)
        layout.addLayout(header)

        layout.addWidget(self._build_sessions_panel(), 1)
        return page
    def _build_counting_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.btn_back_sessions = self._button("Sessions", "fa5s.arrow-left", "inventory_count_view")
        self.detail_title = QLabel("Session de comptage")
        self.detail_title.setObjectName("pageTitle")
        header.addWidget(self.btn_back_sessions)
        header.addWidget(self.detail_title)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(self._build_detail_panel(), 1)
        return page
    def _build_summary_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        summary_layout = QGridLayout(panel)
        summary_layout.setContentsMargins(10, 10, 10, 10)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(8)
        self.lbl_session = self._metric_label("Session: -")
        self.lbl_expected = self._metric_label("Attendus: 0")
        self.lbl_counted = self._metric_label("Comptes: 0")
        self.lbl_missing = self._metric_label("Manquants: 0")
        self.lbl_diff = self._metric_label("Differences: 0")
        self.lbl_extra = self._metric_label("En trop: 0")
        self.lbl_weight = self._metric_label("Poids: 0.000 g")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        for label in (
            self.lbl_session,
            self.lbl_expected,
            self.lbl_counted,
            self.lbl_missing,
            self.lbl_diff,
            self.lbl_extra,
            self.lbl_weight,
        ):
            label.setProperty("ui_element_type", "display_field")
        summary_layout.addWidget(self.lbl_session, 0, 0, 1, 2)
        summary_layout.addWidget(self.lbl_expected, 0, 2)
        summary_layout.addWidget(self.lbl_counted, 0, 3)
        summary_layout.addWidget(self.lbl_missing, 0, 4)
        summary_layout.addWidget(self.lbl_diff, 1, 0)
        summary_layout.addWidget(self.lbl_extra, 1, 1)
        summary_layout.addWidget(self.lbl_weight, 1, 2, 1, 2)
        summary_layout.addWidget(self.progress, 1, 4)
        return panel
    @staticmethod
    def _metric_label(text):
        label = QLabel(text)
        label.setMinimumHeight(34)
        return label
    @staticmethod
    def _scan_label(text):
        label = QLabel(text)
        label.setMinimumHeight(34)
        label.setWordWrap(True)
        return label
    def _build_sessions_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        filters = QFrame()
        filters.setObjectName("panel")
        filter_layout = QVBoxLayout(filters)
        filter_layout.setContentsMargins(10, 10, 10, 10)
        filter_layout.setSpacing(8)
        self.session_status = QComboBox()
        for label, value in SESSION_STATUSES:
            self.session_status.addItem(label, value)
        self.session_search = QLineEdit()
        self.session_search.setPlaceholderText("Numero ou notes...")
        self.session_target_status = QComboBox()
        for label, value in SESSION_TARGET_STATUSES:
            self.session_target_status.addItem(label, value)
        self.btn_apply_session_status = self._button(
            "Appliquer l'etat",
            "fa5s.exchange-alt",
            "inventory_count_status",
            primary=True,
        )
        for widget in (self.session_status, self.session_search, self.session_target_status):
            apply_touch_input_defaults(widget)
        filter_layout.addWidget(QLabel("Sessions"))
        filter_layout.addWidget(QLabel("Filtrer par etat"))
        filter_layout.addWidget(self.session_status)
        filter_layout.addWidget(self.session_search)
        filter_layout.addWidget(QLabel("Nouvel etat"))
        filter_layout.addWidget(self.session_target_status)
        filter_layout.addWidget(self.btn_apply_session_status)
        layout.addWidget(filters)

        self.sessions_table = QTableWidget(0, 10)
        self.sessions_table.setHorizontalHeaderLabels([
            "ID",
            "Numero",
            "Etat",
            "Debut",
            "Attendus",
            "Comptes",
            "Manquants",
            "Differents",
            "En trop",
            "Poids",
        ])
        self.sessions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sessions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.sessions_table.setColumnHidden(0, True)
        apply_touch_table_defaults(self.sessions_table)
        layout.addWidget(self.sessions_table, 1)
        return panel
    def _build_detail_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._build_count_tab(), 1)
        return panel
    def _build_count_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        barcode_panel = QFrame()
        barcode_panel.setObjectName("panel")
        barcode_layout = QHBoxLayout(barcode_panel)
        barcode_layout.setContentsMargins(10, 10, 10, 10)
        barcode_layout.setSpacing(8)
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Scanner ou saisir un code-barres...")
        self.btn_scan = self._button("Compter", "fa5s.barcode", "inventory_count_count", primary=True)
        apply_touch_input_defaults(self.barcode_input)
        barcode_layout.addWidget(QLabel("Code:"))
        barcode_layout.addWidget(self.barcode_input, 1)
        barcode_layout.addWidget(self.btn_scan)
        layout.addWidget(barcode_panel)

        self.scan_panel = QFrame()
        self.scan_panel.setObjectName("scan_result_panel")
        scan_layout = QGridLayout(self.scan_panel)
        scan_layout.setContentsMargins(10, 10, 10, 10)
        scan_layout.setHorizontalSpacing(12)
        scan_layout.setVerticalSpacing(8)
        self.lbl_scan_status = self._scan_label("Derniere lecture: -")
        self.lbl_scan_product = self._scan_label("Produit: -")
        self.lbl_scan_supplier = self._scan_label("Fournisseur: -")
        self.lbl_scan_category = self._scan_label("Categorie: -")
        self.lbl_scan_metal = self._scan_label("Titre: -")
        self.lbl_scan_pricing = self._scan_label("Prix: -")
        self.lbl_scan_expected = self._scan_label("Attendu: -")
        self.lbl_scan_counted = self._scan_label("Compte: -")
        self.lbl_scan_difference = self._scan_label("Ecart: -")
        self.lbl_scan_inventory = self._scan_label("Stock: -")
        for label in (
            self.lbl_scan_status,
            self.lbl_scan_product,
            self.lbl_scan_supplier,
            self.lbl_scan_category,
            self.lbl_scan_metal,
            self.lbl_scan_pricing,
            self.lbl_scan_expected,
            self.lbl_scan_counted,
            self.lbl_scan_difference,
            self.lbl_scan_inventory,
        ):
            label.setProperty("ui_element_type", "display_field")
        scan_layout.addWidget(self.lbl_scan_status, 0, 0, 1, 2)
        scan_layout.addWidget(self.lbl_scan_product, 0, 2, 1, 4)
        scan_layout.addWidget(self.lbl_scan_supplier, 1, 0, 1, 2)
        scan_layout.addWidget(self.lbl_scan_category, 1, 2)
        scan_layout.addWidget(self.lbl_scan_metal, 1, 3)
        scan_layout.addWidget(self.lbl_scan_pricing, 1, 4, 1, 2)
        scan_layout.addWidget(self.lbl_scan_expected, 2, 0)
        scan_layout.addWidget(self.lbl_scan_counted, 2, 1)
        scan_layout.addWidget(self.lbl_scan_difference, 2, 2)
        scan_layout.addWidget(self.lbl_scan_inventory, 2, 3, 1, 3)
        layout.addWidget(self.scan_panel)

        self.count_lists_tabs = QTabWidget()
        self.count_lists_tabs.setDocumentMode(True)
        self.checked_items_table = self._create_count_items_table()
        self.remaining_items_table = self._create_count_items_table()
        self.statistics_page = self._build_statistics_tab()
        self.count_lists_tabs.addTab(self.checked_items_table, qta.icon("fa5s.check-circle"), "Produits scannes")
        self.count_lists_tabs.addTab(self.remaining_items_table, qta.icon("fa5s.hourglass-half"), "Restants")
        self.count_lists_tabs.addTab(self.statistics_page, qta.icon("fa5s.chart-pie"), "Statistiques")
        layout.addWidget(self.count_lists_tabs, 1)
        return page
    def _build_statistics_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        summary = QFrame()
        summary.setObjectName("panel")
        summary_layout = QGridLayout(summary)
        summary_layout.setContentsMargins(10, 10, 10, 10)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(8)
        self.stats_total_items = self._metric_label("Articles scannes: 0")
        self.stats_total_weight = self._metric_label("Poids scanne: 0.000 g")
        self.stats_total_quantity = self._metric_label("Pieces scannees: 0 pcs")
        self.stats_total_value = self._metric_label("Valeur vente: 0.00 DA")
        for label in (
            self.stats_total_items,
            self.stats_total_weight,
            self.stats_total_quantity,
            self.stats_total_value,
        ):
            label.setProperty("ui_element_type", "display_field")
        summary_layout.addWidget(self.stats_total_items, 0, 0)
        summary_layout.addWidget(self.stats_total_weight, 0, 1)
        summary_layout.addWidget(self.stats_total_quantity, 0, 2)
        summary_layout.addWidget(self.stats_total_value, 0, 3)
        layout.addWidget(summary)

        self.statistics_tabs = QTabWidget()
        self.statistics_tabs.setDocumentMode(True)
        self.stats_supplier_table = self._create_statistics_table("Fournisseur")
        self.stats_metal_table = self._create_statistics_table("Titre")
        self.stats_category_table = self._create_statistics_table("Categorie")
        self.statistics_tabs.addTab(self.stats_supplier_table, qta.icon("fa5s.user-tie"), "Par fournisseur")
        self.statistics_tabs.addTab(self.stats_metal_table, qta.icon("fa5s.certificate"), "Par titre")
        self.statistics_tabs.addTab(self.stats_category_table, qta.icon("fa5s.tags"), "Par categorie")
        layout.addWidget(self.statistics_tabs, 1)
        return page
    def _create_count_items_table(self):
        table = QTableWidget(0, 16)
        table.setHorizontalHeaderLabels([
            "ID",
            "Barcode",
            "Article",
            "Categorie",
            "Titre",
            "Fournisseur",
            "Type",
            "Attendu",
            "Compte",
            "Ecart",
            "Facon",
            "Benefice",
            "Prix vente",
            "Emplacement",
            "Stock",
            "Etat",
        ])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setColumnHidden(0, True)
        apply_touch_table_defaults(table)
        return table
    def _create_statistics_table(self, first_column: str):
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels([
            first_column,
            "Articles",
            "Poids",
            "Pieces",
            "Valeur vente",
        ])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        apply_touch_table_defaults(table)
        return table
    def _build_difference_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        self.difference_table = QTableWidget(0, 10)
        self.difference_table.setHorizontalHeaderLabels([
            "ID",
            "Barcode",
            "Article",
            "Type",
            "Attendu",
            "Compte",
            "Ecart",
            "Etat",
            "Emplacement",
            "Stock",
        ])
        self.difference_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.difference_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.difference_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.difference_table.setColumnHidden(0, True)
        apply_touch_table_defaults(self.difference_table)
        layout.addWidget(self.difference_table, 1)

        row = QHBoxLayout()
        self.btn_mark_lost = self._button("Marquer perdu", "fa5s.times-circle", "inventory_count_adjust", danger=True)
        self.btn_adjust_item = self._button("Corriger selection", "fa5s.tools", "inventory_count_adjust", primary=True)
        row.addStretch()
        row.addWidget(self.btn_mark_lost)
        row.addWidget(self.btn_adjust_item)
        layout.addLayout(row)
        return page
    def _build_extra_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        form_panel = QFrame()
        form_panel.setObjectName("panel")
        form = QGridLayout(form_panel)
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(8)
        self.extra_status = QComboBox()
        for label, value in EXTRA_STATUSES:
            self.extra_status.addItem(label, value)
        self.extra_name = QLineEdit()
        self.extra_type = QComboBox()
        self.extra_type.addItem("Poids", "WEIGHT")
        self.extra_type.addItem("Piece", "PIECE")
        self.extra_weight = self._double_spin(" g", maximum=999999)
        self.extra_quantity = QSpinBox()
        self.extra_quantity.setRange(1, 999999)
        self.extra_quantity.setValue(1)
        self.btn_add_extra = self._button("Ajouter element", "fa5s.plus", "inventory_count_extra", primary=True)
        for widget in (
            self.extra_status,
            self.extra_name,
            self.extra_type,
            self.extra_weight,
            self.extra_quantity,
        ):
            apply_touch_input_defaults(widget)
        form.addWidget(QLabel("Filtre:"), 0, 0)
        form.addWidget(self.extra_status, 0, 1)
        form.addWidget(QLabel("Nom:"), 0, 2)
        form.addWidget(self.extra_name, 0, 3, 1, 3)
        form.addWidget(QLabel("Type:"), 1, 0)
        form.addWidget(self.extra_type, 1, 1)
        form.addWidget(QLabel("Poids:"), 1, 2)
        form.addWidget(wrap_with_numpad(self, self.extra_weight, "Poids element", allow_decimal=True), 1, 3)
        form.addWidget(QLabel("Quantite:"), 1, 4)
        form.addWidget(wrap_with_numpad(self, self.extra_quantity, "Quantite element", allow_decimal=False), 1, 5)
        form.addWidget(self.btn_add_extra, 1, 6)
        layout.addWidget(form_panel)

        self.extras_table = QTableWidget(0, 9)
        self.extras_table.setHorizontalHeaderLabels([
            "ID",
            "Barcode",
            "Article",
            "Type",
            "Poids",
            "Qte",
            "Etat",
            "Lien stock",
            "Notes",
        ])
        self.extras_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.extras_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.extras_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.extras_table.setColumnHidden(0, True)
        apply_touch_table_defaults(self.extras_table)
        layout.addWidget(self.extras_table, 1)

        row = QHBoxLayout()
        self.btn_create_from_extra = self._button("Creer stock", "fa5s.box-open", "inventory_count_adjust", primary=True)
        self.btn_adjust_extra = self._button("Corriger element", "fa5s.tools", "inventory_count_adjust")
        self.btn_ignore_extra = self._button("Ignorer element", "fa5s.ban", "inventory_count_adjust", danger=True)
        row.addStretch()
        row.addWidget(self.btn_create_from_extra)
        row.addWidget(self.btn_adjust_extra)
        row.addWidget(self.btn_ignore_extra)
        layout.addLayout(row)
        return page
    def _build_adjustment_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)
        self.adjustments_table = QTableWidget(0, 8)
        self.adjustments_table.setHorizontalHeaderLabels([
            "ID",
            "Date",
            "Action",
            "Article",
            "Item",
            "Extra",
            "Utilisateur",
            "Notes",
        ])
        self.adjustments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.adjustments_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.adjustments_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        self.adjustments_table.setColumnHidden(0, True)
        apply_touch_table_defaults(self.adjustments_table)
        layout.addWidget(self.adjustments_table, 1)
        return page
    @staticmethod
    def _double_spin(suffix="", decimals=3, maximum=999999):
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(0, maximum)
        spin.setSuffix(suffix)
        spin.setSingleStep(0.1)
        return spin
    def _button(self, text, icon, permission_key, primary=False, danger=False):
        button = QPushButton(text)
        button.setIcon(qta.icon(icon, color="#0f8f83"))
        button.setProperty("permission_key", permission_key)
        button.setProperty("permission_label", text)
        button.setProperty("ui_element_type", "action")
        apply_touch_button_defaults(button, primary=primary, danger=danger)
        return button
    def _bind_dialog(self, dialog, permission_key, label):
        binder = getattr(self.window(), "_bind_scoped_dialog", None)
        if callable(binder):
            return binder(dialog, permission_key, label)
        dialog.setProperty("permission_scope_key", permission_key)
        dialog.setProperty("permission_scope_label", label)
        return dialog
    def _connect_signals(self):
        self.btn_new.clicked.connect(self.new_session)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_open_session.clicked.connect(self.open_selected_session)
        self.btn_apply_session_status.clicked.connect(self.apply_session_status)
        self.btn_back_sessions.clicked.connect(self.back_to_sessions)
        self.session_status.currentIndexChanged.connect(self.refresh_data)
        self.session_search.returnPressed.connect(self.refresh_data)
        self.sessions_table.itemSelectionChanged.connect(self._on_session_selected)
        self.btn_scan.clicked.connect(self.count_barcode)
        self.barcode_input.returnPressed.connect(self.count_barcode)
        self.barcode_input.textChanged.connect(self._on_barcode_text_changed)
        self.checked_items_table.itemSelectionChanged.connect(self._on_count_item_selected)
        self.remaining_items_table.itemSelectionChanged.connect(self._on_count_item_selected)
        self.checked_items_table.verticalScrollBar().valueChanged.connect(
            lambda value: self._maybe_load_more_items("checked", value)
        )
        self.remaining_items_table.verticalScrollBar().valueChanged.connect(
            lambda value: self._maybe_load_more_items("remaining", value)
        )
        self.count_lists_tabs.currentChanged.connect(self._update_actions)
