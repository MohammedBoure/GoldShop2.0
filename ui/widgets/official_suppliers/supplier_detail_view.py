from __future__ import annotations

from typing import Any, Dict, Optional

import qtawesome as qta
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from .helpers import make_action_button
from .operation_dialog import OfficialOperationDialog
from .supplier_identity_panel import SupplierIdentityPanel
from .supplier_operations_tab import SupplierOperationsTab
from .supplier_summary_tab import SupplierSummaryTab


class OfficialSupplierDetailView(QWidget):
    def __init__(self, manager, current_user: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.current_user = current_user or {}
        self.current_supplier: Dict[str, Any] = {}
        self._init_ui()
        self._connect_signals()
        self._expose_child_aliases()
        self.identity_panel.set_supplier({})
        self._update_actions()

    def _service(self):
        return self.manager.official_suppliers

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.identity_panel = SupplierIdentityPanel(self)
        layout.addWidget(self.identity_panel)
        layout.addLayout(self._build_actions())

        self.operations_tab = SupplierOperationsTab(self)
        self.summary_tab = SupplierSummaryTab(self)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.operations_tab, qta.icon("fa5s.list"), "Operations")
        self.tabs.addTab(self.summary_tab, qta.icon("fa5s.chart-pie"), "Synthese")
        layout.addWidget(self.tabs, 1)

    def _build_actions(self):
        actions = QHBoxLayout()
        self.btn_incoming = make_action_button(
            "Entree",
            "fa5s.arrow-down",
            "official_supplier_operation_create",
            primary=True,
        )
        self.btn_edit_operation = make_action_button(
            "Modifier operation",
            "fa5s.pen",
            "official_supplier_operation_update",
        )
        self.btn_delete_operation = make_action_button("Supprimer", "fa5s.trash", "official_supplier_operation_delete")
        self.btn_import = make_action_button("Importer Excel", "fa5s.file-excel", "official_supplier_import")
        for button in (
            self.btn_incoming,
            self.btn_edit_operation,
            self.btn_delete_operation,
            self.btn_import,
        ):
            actions.addWidget(button)
        actions.addStretch()
        return actions

    def _connect_signals(self):
        self.btn_incoming.clicked.connect(lambda: self.new_operation("INCOMING"))
        self.btn_edit_operation.clicked.connect(self.edit_operation)
        self.btn_delete_operation.clicked.connect(self.delete_operation)
        self.btn_import.clicked.connect(self.import_excel)
        self.summary_tab.refreshRequested.connect(self.refresh_summary)
        self.operations_tab.operationSelectionChanged.connect(self._update_actions)
        self.operations_tab.connect_filters(self.load_operations)

    def _expose_child_aliases(self):
        self.lbl_supplier_name = self.identity_panel.lbl_supplier_name
        self.lbl_supplier_code = self.identity_panel.lbl_supplier_code
        self.lbl_supplier_phone = self.identity_panel.lbl_supplier_phone
        self.lbl_supplier_tax = self.identity_panel.lbl_supplier_tax
        self.lbl_supplier_link = self.identity_panel.lbl_supplier_link
        self.operations_table = self.operations_tab.operations_table
        self.operation_type_filter = self.operations_tab.operation_type_filter
        self.operation_search = self.operations_tab.operation_search
        self.operation_start = self.operations_tab.operation_start
        self.operation_end = self.operations_tab.operation_end
        self.summary_table = self.summary_tab.summary_table
        self.summary_year = self.summary_tab.summary_year
        self.summary_month = self.summary_tab.summary_month
        self.btn_summary_refresh = self.summary_tab.btn_summary_refresh

    def set_supplier(self, supplier: Optional[Dict[str, Any]]):
        self.current_supplier = dict(supplier or {})
        self.identity_panel.set_supplier(self.current_supplier)
        self.load_operations()
        self.refresh_summary()
        self._update_actions()

    def load_operations(self):
        self.operations_tab.load_operations(self._service(), self.current_supplier.get("id"))
        self._update_actions()

    def refresh_summary(self):
        self.summary_tab.refresh_summary(self._service(), self.current_supplier.get("id"))

    def selected_operation(self):
        return self.operations_tab.selected_operation()

    def new_operation(self, operation_type):
        supplier = self.current_supplier
        if not supplier:
            QMessageBox.warning(self, "Fournisseurs officiels", "Veuillez selectionner un fournisseur.")
            return
        dialog = OfficialOperationDialog(
            self.manager,
            supplier,
            operation_type=operation_type,
            current_user=self.current_user,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.load_operations()
            self.refresh_summary()

    def edit_operation(self):
        supplier = self.current_supplier
        operation = self.selected_operation()
        if not supplier or not operation:
            return
        dialog = OfficialOperationDialog(
            self.manager,
            supplier,
            operation=operation,
            current_user=self.current_user,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.load_operations()
            self.refresh_summary()

    def delete_operation(self):
        operation = self.selected_operation()
        if not operation:
            return
        reply = QMessageBox.question(
            self,
            "Fournisseurs officiels",
            "Supprimer cette operation officielle ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        if not self._service().delete_operation(int(operation.get("id"))):
            QMessageBox.critical(self, "Fournisseurs officiels", "Impossible de supprimer l'operation.")
            return
        self.load_operations()
        self.refresh_summary()

    def import_excel(self):
        supplier = self.current_supplier
        if not supplier:
            QMessageBox.warning(self, "Fournisseurs officiels", "Veuillez selectionner un fournisseur.")
            return
        file_path, _filter = QFileDialog.getOpenFileName(
            self,
            "Importer registre officiel",
            "",
            "Excel (*.xls *.xlsx);;Tous les fichiers (*.*)",
        )
        if not file_path:
            return
        try:
            result = self._service().import_ps_workbook(
                file_path,
                official_supplier_id=int(supplier.get("id")),
                user_id=self.current_user.get("id"),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import Excel", f"Import impossible:\n{exc}")
            return
        QMessageBox.information(
            self,
            "Import Excel",
            f"Lignes importees: {result.get('imported', 0)}\nLignes ignorees: {result.get('skipped', 0)}",
        )
        self.load_operations()
        self.refresh_summary()

    def _update_actions(self):
        has_supplier = bool(self.current_supplier)
        has_operation = bool(self.selected_operation())
        for button in (self.btn_incoming, self.btn_import):
            button.setEnabled(has_supplier)
        self.btn_edit_operation.setEnabled(has_operation)
        self.btn_delete_operation.setEnabled(has_operation)
