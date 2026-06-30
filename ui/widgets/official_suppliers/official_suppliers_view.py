from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QSplitter, QVBoxLayout, QWidget

from ui.deferred_loading import defer_initial_load

from .supplier_detail_view import OfficialSupplierDetailView
from .supplier_editor_dialog import OfficialSupplierEditorDialog
from .supplier_list_view import OfficialSupplierListView


class OfficialSuppliersView(QWidget):
    """Container that coordinates the supplier list and supplier detail screens."""

    def __init__(self, manager, current_user: Optional[dict] = None):
        super().__init__()
        self.manager = manager
        self.current_user = current_user or {}
        self.current_supplier = {}
        self._init_ui()
        self._connect_signals()
        self._expose_legacy_test_aliases()
        defer_initial_load(self, self.refresh_data)

    def _service(self):
        return self.manager.official_suppliers

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        self.setStyleSheet(
            """
            QFrame#officialPanel {
                background: #ffffff;
                border: 1px solid #d6dee6;
                border-radius: 8px;
            }
            QLabel#metricValue {
                font-size: 20px;
                font-weight: 800;
                color: #24313f;
            }
            QLabel#metricCaption {
                color: #607080;
                font-size: 12px;
                font-weight: 700;
            }
            """
        )

        self.splitter = QSplitter(Qt.Horizontal)
        self.supplier_list = OfficialSupplierListView(self.manager, self.current_user, self)
        self.supplier_detail = OfficialSupplierDetailView(self.manager, self.current_user, self)
        self.splitter.addWidget(self.supplier_list)
        self.splitter.addWidget(self.supplier_detail)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([420, 920])
        layout.addWidget(self.splitter, 1)

    def _connect_signals(self):
        self.supplier_list.refreshRequested.connect(self.refresh_data)
        self.supplier_list.newRequested.connect(self.new_supplier)
        self.supplier_list.editRequested.connect(self.edit_supplier)
        self.supplier_list.supplierSelected.connect(self._on_supplier_selected)

    def _expose_legacy_test_aliases(self):
        self.suppliers_table = self.supplier_list.suppliers_table
        self.supplier_search = self.supplier_list.supplier_search
        self.supplier_tabs = self.supplier_list.tabs
        self.btn_new_supplier = self.supplier_list.btn_new_supplier
        self.btn_edit_supplier = self.supplier_list.btn_edit_supplier
        self.btn_global_outgoing = self.supplier_list.btn_global_outgoing
        self.lbl_global_in_weight = self.supplier_list.lbl_global_in_weight
        self.lbl_global_out_weight = self.supplier_list.lbl_global_out_weight
        self.operations_table = self.supplier_detail.operations_table
        self.summary_table = self.supplier_detail.summary_table
        self.tabs = self.supplier_detail.tabs
        self.btn_incoming = self.supplier_detail.btn_incoming
        self.btn_import = self.supplier_detail.btn_import

    def refresh_data(self):
        current_id = int(self.current_supplier.get("id") or 0)
        self.supplier_list.load_suppliers(self._service(), select_id=current_id)
        self.supplier_list.load_global_statistics()
        self.supplier_detail.refresh_summary()

    def _on_supplier_selected(self, supplier):
        self.current_supplier = dict(supplier or {})
        self.supplier_detail.set_supplier(self.current_supplier)

    def new_supplier(self):
        dialog = OfficialSupplierEditorDialog(self.manager, current_user=self.current_user, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.current_supplier = {}
            self.supplier_list.current_supplier = {}
            self.supplier_list.load_suppliers(self._service(), select_id=dialog.result_id)

    def edit_supplier(self, supplier):
        if not supplier:
            return
        dialog = OfficialSupplierEditorDialog(
            self.manager,
            supplier=supplier,
            current_user=self.current_user,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.supplier_list.load_suppliers(self._service(), select_id=supplier.get("id"))
