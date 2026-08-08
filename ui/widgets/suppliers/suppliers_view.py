from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import qtawesome as qta
from PySide6.QtCore import QDate, QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.deferred_loading import defer_initial_load
from ui.touch_design import (
    apply_touch_button_defaults,
    apply_touch_input_defaults,
    apply_touch_table_defaults,
)

from .supplier_editor_dialog import SupplierEditorDialog
from .supplier_operation_dialog import SupplierOperationDialog


class SuppliersView(QWidget):
    """
    100% French Suppliers Ledger View matching the Excel spreadsheet structure:
    Date | Poids | Afaçon | Montant | Obs / Libellé
    Features row color highlighting (Red for settlements/updates) and embedded totals row in blue (#0284c7).
    """

    def __init__(self, manager, current_user: Optional[dict] = None):
        super().__init__()
        self.manager = manager
        self.current_user = current_user or {}
        self.current_supplier: Dict[str, Any] = {}
        self.suppliers_list: List[Dict[str, Any]] = []
        self.operations_list: List[Dict[str, Any]] = []
        self._init_ui()
        self._connect_signals()
        defer_initial_load(self, self.refresh_data)

    def _service(self):
        if self.manager and hasattr(self.manager, "suppliers"):
            return self.manager.suppliers
        return None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 1. Top Bar: Supplier Selection & Controls
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        lbl_select = QLabel("Fournisseur :")
        lbl_select.setStyleSheet("font-weight: bold; font-size: 14px; color: #1e293b;")
        top_bar.addWidget(lbl_select)

        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(280)
        apply_touch_input_defaults(self.supplier_combo)
        top_bar.addWidget(self.supplier_combo)

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="#334155"))
        apply_touch_button_defaults(self.btn_refresh)
        top_bar.addWidget(self.btn_refresh)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # 2. Prominent Header Card
        self.header_card = QFrame()
        self.header_card.setObjectName("supplierHeaderCard")
        self.header_card.setStyleSheet(
            """
            QFrame#supplierHeaderCard {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 14px;
            }
            """
        )
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(14, 8, 14, 8)

        self.lbl_supplier_title = QLabel("Sélectionnez un fournisseur")
        self.lbl_supplier_title.setStyleSheet("font-size: 20px; font-weight: 900; color: #000000;")
        header_layout.addWidget(self.lbl_supplier_title)

        header_layout.addStretch()

        self.lbl_stat_poids = QLabel("Poids Net: 0.00 g")
        self.lbl_stat_poids.setStyleSheet("font-size: 15px; font-weight: 800; color: #000000; background: #e2e8f0; border: 1px solid #cbd5e1; padding: 5px 12px; border-radius: 6px;")
        
        self.lbl_stat_montant = QLabel("Solde: 0 DA")
        self.lbl_stat_montant.setStyleSheet("font-size: 15px; font-weight: 800; color: #000000; background: #e2e8f0; border: 1px solid #cbd5e1; padding: 5px 12px; border-radius: 6px;")
        
        header_layout.addWidget(self.lbl_stat_poids)
        header_layout.addWidget(self.lbl_stat_montant)

        layout.addWidget(self.header_card)

        # 3. Action Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.btn_add_op = QPushButton("Nouvelle Opération")
        self.btn_add_op.setIcon(qta.icon("fa5s.plus", color="white"))
        apply_touch_button_defaults(self.btn_add_op, primary=True)

        self.btn_edit_op = QPushButton("Modifier")
        self.btn_edit_op.setIcon(qta.icon("fa5s.edit", color="#334155"))
        apply_touch_button_defaults(self.btn_edit_op)

        self.btn_delete_op = QPushButton("Supprimer")
        self.btn_delete_op.setIcon(qta.icon("fa5s.trash", color="#dc2626"))
        apply_touch_button_defaults(self.btn_delete_op, danger=True)

        self.btn_toggle_color = QPushButton("Changer Couleur (Rouge/Normal)")
        self.btn_toggle_color.setIcon(qta.icon("fa5s.palette", color="#b91c1c"))
        apply_touch_button_defaults(self.btn_toggle_color)

        toolbar.addWidget(self.btn_add_op)
        toolbar.addWidget(self.btn_edit_op)
        toolbar.addWidget(self.btn_delete_op)
        toolbar.addWidget(self.btn_toggle_color)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 4. Main Table (Exact Excel layout: Date | Poids | Afaçon | Montant | Obs)
        self.table = QTableWidget()
        apply_touch_table_defaults(self.table)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Date", "Poids", "Afaçon", "Montant", "Obs / Libellé"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.table, 1)

    def _connect_signals(self):
        self.supplier_combo.currentIndexChanged.connect(self._on_supplier_changed)
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_add_op.clicked.connect(self._on_add_operation)
        self.btn_edit_op.clicked.connect(self._on_edit_operation)
        self.btn_delete_op.clicked.connect(self._on_delete_operation)
        self.btn_toggle_color.clicked.connect(self._on_toggle_color)
        self.table.doubleClicked.connect(self._on_edit_operation)

    def refresh_data(self):
        service = self._service()
        if not service:
            return

        selected_id = self.supplier_combo.currentData()
        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()

        try:
            self.suppliers_list = service.list_suppliers(active_only=True, limit=500)
            if not self.suppliers_list:
                self.supplier_combo.addItem("Aucun fournisseur disponible", None)
            else:
                for s in self.suppliers_list:
                    label = s.get("name") or f"Fournisseur #{s['id']}"
                    self.supplier_combo.addItem(label, s["id"])

                # Restore previous selection or select first supplier
                if selected_id:
                    idx = self.supplier_combo.findData(selected_id)
                    if idx >= 0:
                        self.supplier_combo.setCurrentIndex(idx)
                    else:
                        self.supplier_combo.setCurrentIndex(0)
                else:
                    self.supplier_combo.setCurrentIndex(0)
        except Exception as exc:
            logging.error(f"Error loading suppliers: {exc}")
        finally:
            self.supplier_combo.blockSignals(False)

        self._on_supplier_changed()

    def _on_supplier_changed(self):
        supplier_id = self.supplier_combo.currentData()
        if not supplier_id:
            self.current_supplier = {}
            self.lbl_supplier_title.setText("Sélectionnez un fournisseur")
            self.lbl_stat_poids.setText("Poids Net: 0.00 g")
            self.lbl_stat_montant.setText("Solde: 0 DA")
            self.table.setRowCount(0)
            return

        self.current_supplier = next((s for s in self.suppliers_list if s["id"] == supplier_id), {"id": supplier_id})
        supplier_name = self.current_supplier.get("name") or f"Fournisseur #{supplier_id}"
        self.lbl_supplier_title.setText(supplier_name)
        self._load_operations()

    def _load_operations(self):
        supplier_id = self.current_supplier.get("id")
        if not supplier_id:
            return

        service = self._service()
        if not service:
            return

        try:
            self.operations_list = service.list_operations(supplier_id=supplier_id, limit=2000) if hasattr(service, "list_operations") else []
            self._render_table()
        except Exception as exc:
            logging.error(f"Error loading supplier operations: {exc}")

    def _render_table(self):
        self.table.setRowCount(0)
        if not self.operations_list:
            self.lbl_stat_poids.setText("Poids Net: 0.00 g")
            self.lbl_stat_montant.setText("Solde: 0 DA")
            return

        total_poids = 0.0
        total_montant = 0.0

        for op in self.operations_list:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            # Extract date ONLY (dd/MM/yyyy) without time
            raw_date = op.get("transaction_date") or op.get("operation_date") or ""
            if hasattr(raw_date, "strftime"):
                op_date = raw_date.strftime("%d/%m/%Y")
            else:
                s_date = str(raw_date).strip()
                if " " in s_date: s_date = s_date.split(" ")[0]
                if "T" in s_date: s_date = s_date.split("T")[0]
                if "-" in s_date:
                    parts = s_date.split("-")
                    if len(parts) == 3:
                        op_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    else:
                        op_date = s_date
                else:
                    op_date = s_date

            op_type = str(op.get("operation_type") or op.get("type") or "INCOMING").upper()
            
            raw_w = op.get("weight_g") if op.get("weight_g") is not None else (op.get("weight_delta") if op.get("weight_delta") is not None else op.get("weight"))
            weight_val = float(raw_w or 0.0)

            raw_m = op.get("amount_da") if op.get("amount_da") is not None else (op.get("money_delta") if op.get("money_delta") is not None else op.get("amount"))
            amount_val = float(raw_m or 0.0)

            # Signed values
            if op_type == "OUTGOING":
                signed_weight = -abs(weight_val)
                signed_amount = -abs(amount_val)
            else:
                signed_weight = weight_val
                signed_amount = amount_val

            total_poids += signed_weight
            total_montant += signed_amount

            # Formatting
            poids_str = f"{signed_weight:,.2f}".replace(",", " ").replace(".", ",") if abs(signed_weight) > 0.0001 else "0,00"
            
            afacon_val = op.get("afacon") or op.get("labor_price_per_gram") or ""
            afacon_str = str(afacon_val) if afacon_val and str(afacon_val) not in ("0", "0.00", "0.0") else "0"

            montant_str = f"{int(round(signed_amount)):,}".replace(",", " ") if abs(signed_amount) > 0.01 else "0"
            if signed_amount < 0 and not montant_str.startswith("-"):
                montant_str = "-" + montant_str

            description = str(op.get("description") or op.get("notes") or "")

            # Check for color highlight
            is_red = False
            is_blue = False
            
            if "[COLOR:RED]" in description:
                is_red = True
                description = description.replace("[COLOR:RED]", "").strip()
            elif "régler" in description.lower() or "regler" in description.lower():
                is_red = True
                
            if "alliage" in description.lower():
                is_blue = True

            # Items
            item_date = QTableWidgetItem(str(op_date))
            item_poids = QTableWidgetItem(poids_str)
            item_afacon = QTableWidgetItem(afacon_str)
            item_montant = QTableWidgetItem(montant_str)
            item_obs = QTableWidgetItem(description)

            # Alignment
            item_date.setTextAlignment(Qt.AlignCenter)
            item_poids.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_afacon.setTextAlignment(Qt.AlignCenter)
            item_montant.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_obs.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            # Standard colors
            normal_dark = QColor("#1e293b")
            red_color = QColor("#dc2626")
            green_color = QColor("#16a34a")
            blue_color = QColor("#0284c7")

            # Row text coloring for Date, Afaçon, Obs
            row_color = normal_dark
            if is_red:
                row_color = red_color
            elif is_blue:
                row_color = blue_color
                
            for item in (item_date, item_afacon, item_obs):
                item.setForeground(row_color)

            # Poids number coloring: Green (+), Red (-)
            if signed_weight < 0:
                item_poids.setForeground(red_color)
            elif signed_weight > 0:
                item_poids.setForeground(green_color)
            else:
                item_poids.setForeground(normal_dark)

            # Montant number coloring: Green (+), Red (-)
            if signed_amount < 0:
                item_montant.setForeground(red_color)
            elif signed_amount > 0:
                item_montant.setForeground(green_color)
            else:
                item_montant.setForeground(normal_dark)

            # Bold text for numbers
            font_num = QFont()
            font_num.setBold(True)
            item_poids.setFont(font_num)
            item_montant.setFont(font_num)

            item_date.setData(Qt.UserRole, op)

            self.table.setItem(row_idx, 0, item_date)
            self.table.setItem(row_idx, 1, item_poids)
            self.table.setItem(row_idx, 2, item_afacon)
            self.table.setItem(row_idx, 3, item_montant)
            self.table.setItem(row_idx, 4, item_obs)

        # Totals Card update (Money as integer, Gold with 2 decimals)
        tot_p_str = f"{total_poids:,.2f}".replace(",", " ").replace(".", ",")
        tot_m_str = f"{int(round(total_montant)):,}".replace(",", " ")
        self.lbl_stat_poids.setText(f"Poids Net: {tot_p_str} g")
        self.lbl_stat_montant.setText(f"Solde: {tot_m_str} DA")

        # Insert Embedded Totals Row at the bottom of the table
        totals_row = self.table.rowCount()
        self.table.insertRow(totals_row)

        tot_date_item = QTableWidgetItem("SOLDE / TOTAL")
        tot_poids_item = QTableWidgetItem(tot_p_str)
        tot_afacon_item = QTableWidgetItem("")
        tot_montant_item = QTableWidgetItem(tot_m_str)
        tot_obs_item = QTableWidgetItem("--- Solde Général ---")

        tot_date_item.setTextAlignment(Qt.AlignCenter)
        tot_poids_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tot_afacon_item.setTextAlignment(Qt.AlignCenter)
        tot_montant_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tot_obs_item.setTextAlignment(Qt.AlignCenter)

        # Style Totals Row: Light Blue background (#e0f2fe) with Dark Navy bold text (#0369a1)
        tot_bg = QColor("#e0f2fe")
        tot_fg = QColor("#0369a1")
        bold_font = QFont()
        bold_font.setBold(True)
        bold_font.setPointSize(11)

        for item in (tot_date_item, tot_poids_item, tot_afacon_item, tot_montant_item, tot_obs_item):
            item.setBackground(tot_bg)
            item.setForeground(tot_fg)
            item.setFont(bold_font)

        self.table.setItem(totals_row, 0, tot_date_item)
        self.table.setItem(totals_row, 1, tot_poids_item)
        self.table.setItem(totals_row, 2, tot_afacon_item)
        self.table.setItem(totals_row, 3, tot_montant_item)
        self.table.setItem(totals_row, 4, tot_obs_item)

        # Automatically scroll to bottom upon loading data
        QTimer.singleShot(50, self.table.scrollToBottom)

    def _selected_operation(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0 or row >= self.table.rowCount():
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _on_add_operation(self):
        if not self.current_supplier:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un fournisseur.")
            return

        dialog = SupplierOperationDialog(
            self.manager,
            supplier=self.current_supplier,
            current_user=self.current_user,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self._load_operations()

    def _on_edit_operation(self):
        op = self._selected_operation()
        if not op:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne d'opération à modifier.")
            return

        dialog = SupplierOperationDialog(
            self.manager,
            supplier=self.current_supplier,
            operation=op,
            current_user=self.current_user,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self._load_operations()

    def _on_delete_operation(self):
        op = self._selected_operation()
        if not op:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne d'opération à supprimer.")
            return

        op_id = op.get("id")
        reply = QMessageBox.question(
            self,
            "Confirmation",
            "Voulez-vous vraiment supprimer cette ligne d'opération ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            service = self._service()
            if service and hasattr(service, "delete_operation"):
                service.delete_operation(op_id)
            self._load_operations()

    def _on_toggle_color(self):
        op = self._selected_operation()
        if not op:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne d'opération.")
            return

        desc = str(op.get("description") or op.get("notes") or "")
        if "[COLOR:RED]" in desc:
            new_desc = desc.replace("[COLOR:RED]", "").strip()
        else:
            new_desc = (desc + " [COLOR:RED]").strip()

        service = self._service()
        if service and hasattr(service, "update_operation"):
            service.update_operation(op["id"], description=new_desc, notes=new_desc)
        self._load_operations()

OfficialSuppliersView = SuppliersView
