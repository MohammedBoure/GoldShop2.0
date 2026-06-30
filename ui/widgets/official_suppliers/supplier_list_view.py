from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget

from .global_statistics_tab import GlobalStatisticsTab
from .helpers import make_action_button
from .supplier_registry_tab import SupplierRegistryTab


class OfficialSupplierListView(QWidget):
    supplierSelected = Signal(dict)
    newRequested = Signal()
    editRequested = Signal(dict)
    refreshRequested = Signal()

    def __init__(self, manager, current_user=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.current_user = current_user or {}
        self.current_supplier = {}
        self._init_ui()
        self._connect_signals()
        self._expose_tab_aliases()
        self._update_actions()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Fournisseurs officiels")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        self.btn_refresh = make_action_button("Actualiser", "fa5s.sync-alt", "official_supplier_view")
        self.btn_new_supplier = make_action_button(
            "Nouveau",
            "fa5s.plus-circle",
            "official_supplier_create",
            primary=True,
        )
        self.btn_edit_supplier = make_action_button("Modifier", "fa5s.edit", "official_supplier_update")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_new_supplier)
        header.addWidget(self.btn_edit_supplier)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.registry_tab = SupplierRegistryTab(self)
        self.global_statistics_tab = GlobalStatisticsTab(self.manager, self.current_user, self)
        self.tabs.addTab(self.registry_tab, "Fournisseurs")
        self.tabs.addTab(self.global_statistics_tab, "Statistiques")
        layout.addWidget(self.tabs, 1)

    def _connect_signals(self):
        self.btn_refresh.clicked.connect(self.refreshRequested.emit)
        self.btn_new_supplier.clicked.connect(self.newRequested.emit)
        self.btn_edit_supplier.clicked.connect(self._emit_edit_requested)
        self.registry_tab.refreshRequested.connect(self.refreshRequested.emit)
        self.registry_tab.supplierSelected.connect(self._on_supplier_selected)

    def _expose_tab_aliases(self):
        self.supplier_search = self.registry_tab.supplier_search
        self.supplier_status = self.registry_tab.supplier_status
        self.suppliers_table = self.registry_tab.suppliers_table
        self.global_start_date = self.global_statistics_tab.global_start_date
        self.global_end_date = self.global_statistics_tab.global_end_date
        self.btn_global_stats_refresh = self.global_statistics_tab.btn_global_stats_refresh
        self.btn_global_outgoing = self.global_statistics_tab.btn_global_outgoing
        self.lbl_global_in_weight = self.global_statistics_tab.lbl_global_in_weight
        self.lbl_global_out_weight = self.global_statistics_tab.lbl_global_out_weight
        self.lbl_global_net_weight = self.global_statistics_tab.lbl_global_net_weight
        self.lbl_global_in_amount = self.global_statistics_tab.lbl_global_in_amount
        self.lbl_global_out_amount = self.global_statistics_tab.lbl_global_out_amount
        self.lbl_global_net_amount = self.global_statistics_tab.lbl_global_net_amount
        self.lbl_global_operation_count = self.global_statistics_tab.lbl_global_operation_count

    def load_suppliers(self, service, select_id: Optional[int] = None):
        self.registry_tab.load_suppliers(service, select_id=select_id)
        self.current_supplier = dict(self.registry_tab.current_supplier or {})
        self._update_actions()

    def load_global_statistics(self):
        self.global_statistics_tab.load_global_statistics()

    def selected_supplier(self):
        return self.registry_tab.selected_supplier()

    def _on_supplier_selected(self, supplier):
        self.current_supplier = dict(supplier or {})
        self.supplierSelected.emit(self.current_supplier)
        self._update_actions()

    def _emit_edit_requested(self):
        supplier = self.selected_supplier()
        if supplier:
            self.editRequested.emit(dict(supplier))

    def _update_actions(self):
        self.btn_edit_supplier.setEnabled(bool(self.selected_supplier()))
