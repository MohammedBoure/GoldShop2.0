from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem

from .helpers import (
    CHECKED_ITEM_STATUSES,
    ITEM_STATUS_LABELS,
    ITEM_TYPE_LABELS,
    _as_int,
    _fmt_margin,
    _fmt_money,
    _fmt_qty,
    _fmt_weight,
    _metal_label,
)


class InventoryCountItemTablesMixin:
    def refresh_items(self):
        session_id = self.current_session_id()
        if not session_id:
            self.checked_items_table.setRowCount(0)
            self.remaining_items_table.setRowCount(0)
            return
        self._items_loading = True
        try:
            self.checked_items_table.setRowCount(0)
            self.remaining_items_table.setRowCount(0)
            self._checked_offset = 0
            self._remaining_offset = 0
            self._checked_has_more = True
            self._remaining_has_more = True
        finally:
            self._items_loading = False
        self._load_checked_items_page()
        self._load_remaining_items_page()
        self._update_actions()
    def refresh_statistics(self):
        session_id = self.current_session_id()
        service = self._service()
        if not session_id or service is None or not hasattr(service, "get_count_statistics"):
            self._clear_statistics()
            return
        try:
            stats = service.get_count_statistics(session_id) or {}
        except Exception as exc:
            QMessageBox.critical(self, "Inventaire physique", str(exc))
            stats = {}
        totals = stats.get("totals") or {}
        self.stats_total_items.setText(f"Articles scannes: {_as_int(totals.get('item_count'))}")
        self.stats_total_weight.setText(f"Poids scanne: {_fmt_weight(totals.get('total_weight'))}")
        self.stats_total_quantity.setText(f"Pieces scannees: {_fmt_qty(totals.get('total_quantity'))}")
        self.stats_total_value.setText(f"Valeur vente: {_fmt_money(totals.get('total_value'))}")
        self._fill_statistics_table(self.stats_supplier_table, stats.get("by_supplier") or [])
        self._fill_statistics_table(self.stats_metal_table, stats.get("by_metal") or [])
        self._fill_statistics_table(self.stats_category_table, stats.get("by_category") or [])
    def _clear_statistics(self):
        if not hasattr(self, "stats_total_items"):
            return
        self.stats_total_items.setText("Articles scannes: 0")
        self.stats_total_weight.setText("Poids scanne: 0.000 g")
        self.stats_total_quantity.setText("Pieces scannees: 0 pcs")
        self.stats_total_value.setText("Valeur vente: 0.00 DA")
        for table_name in ("stats_supplier_table", "stats_metal_table", "stats_category_table"):
            table = getattr(self, table_name, None)
            if table is not None:
                table.setRowCount(0)
    def _fill_statistics_table(self, table: QTableWidget, rows) -> None:
        table.setRowCount(0)
        for row_data in rows or []:
            row = table.rowCount()
            table.insertRow(row)
            values = [
                row_data.get("label") or "-",
                _as_int(row_data.get("item_count")),
                _fmt_weight(row_data.get("total_weight")),
                _fmt_qty(row_data.get("total_quantity")),
                _fmt_money(row_data.get("total_value")),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column > 0:
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(row, column, cell)
    def _maybe_load_more_items(self, table_kind: str, value: int):
        if self._items_loading:
            return
        table = self.checked_items_table if table_kind == "checked" else self.remaining_items_table
        scrollbar = table.verticalScrollBar()
        if value < scrollbar.maximum() - 3:
            return
        if table_kind == "checked":
            self._load_checked_items_page()
        else:
            self._load_remaining_items_page()
    def _load_checked_items_page(self):
        session_id = self.current_session_id()
        if not session_id or not self._checked_has_more or self._items_loading:
            return
        service = self._service()
        self._items_loading = True
        try:
            rows = service.get_count_items(
                session_id,
                status="__CHECKED__",
                search_text="",
                limit=self._item_page_size,
                offset=self._checked_offset,
            )
            for row_data in rows or []:
                if self._is_checked_item_status(row_data.get("count_status")):
                    self._append_count_item(self.checked_items_table, row_data)
            if self._checked_offset == 0:
                extras = service.get_extra_items(session_id, status=None, limit=self._item_page_size)
                for extra in extras or []:
                    if str(extra.get("status") or "").upper() != "IGNORED":
                        self._append_extra_item(self.checked_items_table, extra)
            self._checked_offset += len(rows or [])
            self._checked_has_more = len(rows or []) >= self._item_page_size
        except Exception as exc:
            self._checked_has_more = False
            QMessageBox.critical(self, "Inventaire physique", str(exc))
        finally:
            self._items_loading = False
    def _load_remaining_items_page(self):
        session_id = self.current_session_id()
        if not session_id or not self._remaining_has_more or self._items_loading:
            return
        service = self._service()
        self._items_loading = True
        try:
            if hasattr(service, "get_remaining_inventory_items"):
                rows = service.get_remaining_inventory_items(
                    session_id,
                    search_text="",
                    limit=self._item_page_size,
                    offset=self._remaining_offset,
                )
            else:
                rows = service.get_count_items(
                    session_id,
                    status="NOT_COUNTED",
                    search_text="",
                    limit=self._item_page_size,
                    offset=self._remaining_offset,
            )
            for row_data in rows or []:
                self._append_count_item(self.remaining_items_table, row_data)
            self._remaining_offset += len(rows or [])
            self._remaining_has_more = len(rows or []) >= self._item_page_size
        except Exception as exc:
            self._remaining_has_more = False
            QMessageBox.critical(self, "Inventaire physique", str(exc))
        finally:
            self._items_loading = False
    @staticmethod
    def _is_checked_item_status(status: str) -> bool:
        return str(status or "").upper() in CHECKED_ITEM_STATUSES
    def _item_matches_filter(self, item_data: Dict[str, Any], filter_value) -> bool:
        if not filter_value:
            return True
        status = str(item_data.get("count_status") or "").upper()
        if filter_value == "__CHECKED__":
            return self._is_checked_item_status(status)
        return status == str(filter_value or "").upper()
    def _append_count_item(self, table: QTableWidget, item_data: Dict[str, Any]) -> int:
        row = table.rowCount()
        table.insertRow(row)
        item_type = str(item_data.get("snapshot_item_type") or "WEIGHT").upper()
        expected = _fmt_qty(item_data.get("expected_remaining_quantity")) if item_type == "PIECE" else _fmt_weight(item_data.get("expected_remaining_weight"))
        counted = ""
        if item_data.get("count_status") != "NOT_COUNTED":
            counted = _fmt_qty(item_data.get("counted_quantity")) if item_type == "PIECE" else _fmt_weight(item_data.get("counted_weight"))
        difference = _fmt_qty(item_data.get("difference_quantity")) if item_type == "PIECE" else _fmt_weight(item_data.get("difference_weight"))
        values = [
            item_data.get("id"),
            item_data.get("snapshot_barcode") or "",
            item_data.get("snapshot_name") or "",
            item_data.get("category_name") or item_data.get("snapshot_category_id") or "",
            _metal_label(item_data),
            item_data.get("supplier_name") or item_data.get("supplier_id") or "",
            ITEM_TYPE_LABELS.get(item_type, item_type),
            expected,
            counted,
            difference,
            _fmt_money(item_data.get("labor_cost_per_gram")),
            _fmt_margin(item_data.get("profit_margin"), item_data.get("margin_type")),
            _fmt_money(item_data.get("selling_price")),
            item_data.get("location_name") or item_data.get("snapshot_location_id") or "",
            item_data.get("inventory_id") or "",
            ITEM_STATUS_LABELS.get(str(item_data.get("count_status") or ""), str(item_data.get("count_status") or "")),
        ]
        row_color = self._row_color_for_item(item_data)
        for column, value in enumerate(values):
            cell = QTableWidgetItem(str(value or ""))
            if row_color is not None:
                cell.setBackground(row_color)
            if column == 0:
                cell.setData(Qt.UserRole, item_data)
            if column in {7, 8, 9, 10, 11, 12}:
                cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, column, cell)
        return row
    def _append_extra_item(self, table: QTableWidget, extra: Dict[str, Any]) -> int:
        row = table.rowCount()
        table.insertRow(row)
        item_type = str(extra.get("observed_item_type") or "WEIGHT").upper()
        counted = _fmt_qty(extra.get("observed_quantity")) if item_type == "PIECE" else _fmt_weight(extra.get("observed_weight"))
        values = [
            f"extra-{extra.get('id')}",
            extra.get("observed_barcode") or "",
            extra.get("observed_name") or "Element en trop",
            extra.get("category_name") or extra.get("category_id") or "",
            _metal_label(extra),
            "",
            ITEM_TYPE_LABELS.get(item_type, item_type),
            "-",
            counted,
            f"+ {counted}",
            "-",
            "-",
            "-",
            extra.get("location_name") or extra.get("location_id") or "",
            extra.get("linked_inventory_id") or "",
            "Element en trop",
        ]
        row_color = QColor("#fde8e4")
        for column, value in enumerate(values):
            cell = QTableWidgetItem(str(value or ""))
            cell.setBackground(row_color)
            if column == 0:
                cell.setData(Qt.UserRole, {"extra": extra})
            if column in {7, 8, 9, 10, 11, 12}:
                cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, column, cell)
        return row
    @staticmethod
    def _row_color_for_item(item_data: Dict[str, Any]):
        status = str(item_data.get("count_status") or "").upper()
        if status == "FOUND":
            return QColor("#dff7e8")
        if status == "DIFFERENT":
            return QColor("#fff4d6")
        if status == "MISSING":
            return QColor("#fde8e4")
        if status == "IGNORED":
            return QColor("#eef3f7")
        return None
    def refresh_extras(self):
        session_id = self.current_session_id()
        if not session_id:
            self.extras_table.setRowCount(0)
            return
        service = self._service()
        try:
            rows = service.get_extra_items(session_id, status=self.extra_status.currentData(), limit=1000)
        except Exception as exc:
            QMessageBox.critical(self, "Inventaire physique", str(exc))
            rows = []
        self.extras_table.setRowCount(0)
        for row_data in rows:
            self._append_extra(row_data)
        self._update_actions()
    def _append_extra(self, extra: Dict[str, Any]) -> int:
        row = self.extras_table.rowCount()
        self.extras_table.insertRow(row)
        values = [
            extra.get("id"),
            extra.get("observed_barcode") or "",
            extra.get("observed_name") or "",
            ITEM_TYPE_LABELS.get(str(extra.get("observed_item_type") or "WEIGHT"), str(extra.get("observed_item_type") or "")),
            _fmt_weight(extra.get("observed_weight")),
            _fmt_qty(extra.get("observed_quantity")),
            str(extra.get("status") or ""),
            extra.get("linked_inventory_id") or "",
            extra.get("notes") or "",
        ]
        row_color = QColor("#fde8e4") if str(extra.get("status") or "").upper() == "NEW" else QColor("#eef3f7")
        for column, value in enumerate(values):
            cell = QTableWidgetItem(str(value or ""))
            cell.setBackground(row_color)
            if column == 0:
                cell.setData(Qt.UserRole, extra)
            if column in {4, 5}:
                cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.extras_table.setItem(row, column, cell)
        return row
    def _fetch_scan_record(self, session_id: int, barcode: str, result: str):
        service = self._service()
        barcode = str(barcode or "").strip()
        if not barcode or service is None:
            return None, None
        try:
            rows = service.get_count_items(session_id, status=None, search_text=barcode, limit=20)
        except Exception:
            rows = []
        for row in rows or []:
            if str(row.get("snapshot_barcode") or "").strip() == barcode:
                return row, None
        if result == "EXTRA":
            try:
                extras = service.get_extra_items(session_id, status=None, search_text=barcode, limit=20)
            except Exception:
                extras = []
            for row in extras or []:
                if str(row.get("observed_barcode") or "").strip() == barcode:
                    return None, row
        return None, None
    def _show_scan_result(self, result: str, barcode: str, item=None, extra=None):
        if item:
            item_type = str(item.get("snapshot_item_type") or "WEIGHT").upper()
            expected = _fmt_qty(item.get("expected_remaining_quantity")) if item_type == "PIECE" else _fmt_weight(item.get("expected_remaining_weight"))
            counted = _fmt_qty(item.get("counted_quantity")) if item_type == "PIECE" else _fmt_weight(item.get("counted_weight"))
            difference = _fmt_qty(item.get("difference_quantity")) if item_type == "PIECE" else _fmt_weight(item.get("difference_weight"))
            product = item.get("snapshot_name") or "-"
            status = ITEM_STATUS_LABELS.get(str(item.get("count_status") or ""), item.get("count_status") or "")
            category = item.get("category_name") or item.get("snapshot_category_id") or "-"
            supplier = item.get("supplier_name") or item.get("supplier_id") or "-"
            metal = _metal_label(item)
            pricing = (
                f"Facon: {_fmt_money(item.get('labor_cost_per_gram'))} | "
                f"Benefice: {_fmt_margin(item.get('profit_margin'), item.get('margin_type'))} | "
                f"Vente: {_fmt_money(item.get('selling_price'))}"
            )
            inventory = item.get("inventory_id") or "-"
            location = item.get("location_name") or item.get("snapshot_location_id") or "-"
            raw_status = str(item.get("count_status") or "").upper()
            self._set_scan_state("ok" if raw_status == "FOUND" else "warning")
            self.lbl_scan_status.setText(f"Derniere lecture: {barcode} | {status}")
            self.lbl_scan_product.setText(f"Produit: {product}")
            self.lbl_scan_supplier.setText(f"Fournisseur: {supplier}")
            self.lbl_scan_category.setText(f"Categorie: {category}")
            self.lbl_scan_metal.setText(f"Titre: {metal}")
            self.lbl_scan_pricing.setText(pricing)
            self.lbl_scan_expected.setText(f"Attendu: {expected}")
            self.lbl_scan_counted.setText(f"Compte: {counted}")
            self.lbl_scan_difference.setText(f"Ecart: {difference}")
            self.lbl_scan_inventory.setText(f"Stock: #{inventory} | Emplacement: {location}")
            return

        if extra:
            self._set_scan_state("error")
            item_type = str(extra.get("observed_item_type") or "WEIGHT").upper()
            measure = _fmt_qty(extra.get("observed_quantity")) if item_type == "PIECE" else _fmt_weight(extra.get("observed_weight"))
            product = extra.get("observed_name") or "-"
            linked = extra.get("linked_inventory_id") or "-"
            status = str(extra.get("status") or "NEW")
            self.lbl_scan_status.setText(f"Derniere lecture: {barcode} | Element en trop")
            self.lbl_scan_product.setText(f"Produit: {product}")
            self.lbl_scan_supplier.setText("Fournisseur: -")
            self.lbl_scan_category.setText(f"Categorie: {extra.get('category_name') or extra.get('category_id') or '-'}")
            self.lbl_scan_metal.setText(f"Titre: {_metal_label(extra)}")
            self.lbl_scan_pricing.setText("Prix: -")
            self.lbl_scan_expected.setText("Attendu: non present dans la session")
            self.lbl_scan_counted.setText(f"Compte: {measure}")
            self.lbl_scan_difference.setText(f"Ecart: + {measure}")
            self.lbl_scan_inventory.setText(f"Stock lie: #{linked} | Etat: {status}")
            return

        self._set_scan_state("error")
        self.lbl_scan_status.setText(f"Derniere lecture: {barcode} | {result or 'Non traite'}")
        self.lbl_scan_product.setText("Produit: introuvable")
        self.lbl_scan_supplier.setText("Fournisseur: -")
        self.lbl_scan_category.setText("Categorie: -")
        self.lbl_scan_metal.setText("Titre: -")
        self.lbl_scan_pricing.setText("Prix: -")
        self.lbl_scan_expected.setText("Attendu: -")
        self.lbl_scan_counted.setText("Compte: -")
        self.lbl_scan_difference.setText("Ecart: -")
        self.lbl_scan_inventory.setText("Stock: -")
    def _select_barcode_row(self, barcode: str, result: str):
        self.count_lists_tabs.setCurrentIndex(0)
        if result == "EXTRA":
            return self._select_table_row_by_barcode(self.checked_items_table, barcode, 1)
        selected = self._select_table_row_by_barcode(self.checked_items_table, barcode, 1)
        if not selected:
            selected = self._select_table_row_by_barcode(self.remaining_items_table, barcode, 1)
        return selected
    @staticmethod
    def _select_table_row_by_barcode(table: QTableWidget, barcode: str, column: int) -> bool:
        barcode = str(barcode or "").strip()
        if not barcode:
            return False
        for row in range(table.rowCount()):
            cell = table.item(row, column)
            if cell and cell.text().strip() == barcode:
                table.selectRow(row)
                table.scrollToItem(cell)
                return True
        return False
    def refresh_adjustments(self):
        session_id = self.current_session_id()
        if not session_id:
            self.adjustments_table.setRowCount(0)
            return
        service = self._service()
        try:
            rows = service.get_adjustments(session_id)
        except Exception:
            rows = []
        self.adjustments_table.setRowCount(0)
        for adjustment in rows:
            row = self.adjustments_table.rowCount()
            self.adjustments_table.insertRow(row)
            values = [
                adjustment.get("id"),
                str(adjustment.get("created_at") or adjustment.get("applied_at") or "")[:16],
                adjustment.get("action_type") or "",
                adjustment.get("inventory_name") or adjustment.get("inventory_id") or "",
                adjustment.get("count_item_id") or "",
                adjustment.get("extra_item_id") or "",
                adjustment.get("applied_by_username") or adjustment.get("applied_by_user_id") or "",
                adjustment.get("notes") or "",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value or ""))
                if column == 0:
                    cell.setData(Qt.UserRole, adjustment)
                self.adjustments_table.setItem(row, column, cell)
