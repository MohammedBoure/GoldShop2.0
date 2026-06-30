from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QTableWidget

from .dialogs import InventoryAdjustmentDialog
from .helpers import _as_float, _as_int


class InventoryCountActionsMixin:
    def _selected_count_item(self, table: Optional[QTableWidget] = None):
        table = table or self.checked_items_table
        row = table.currentRow()
        if row < 0:
            return None
        cell = table.item(row, 0)
        data = cell.data(Qt.UserRole) if cell else None
        return data if isinstance(data, dict) else None
    def _active_count_table(self):
        if hasattr(self, "count_lists_tabs"):
            table = self.count_lists_tabs.currentWidget()
            if isinstance(table, QTableWidget):
                return table
        return self.checked_items_table
    def _active_count_item(self):
        for table in (
            self._active_count_table(),
            self.checked_items_table,
            self.remaining_items_table,
        ):
            item = self._selected_count_item(table)
            if item:
                return item
        return None
    def _selected_extra(self):
        row = self.extras_table.currentRow()
        if row < 0:
            return None
        cell = self.extras_table.item(row, 0)
        data = cell.data(Qt.UserRole) if cell else None
        return data if isinstance(data, dict) else None
    def _on_count_item_selected(self):
        sender = self.sender()
        table = sender if isinstance(sender, QTableWidget) else self._active_count_table()
        item = self._selected_count_item(table)
        self._update_actions()
    def _on_difference_item_selected(self):
        item = self._selected_count_item(self.difference_table)
        self._fill_count_controls(item)
        self._update_actions()
    def _fill_count_controls(self, item: Optional[Dict[str, Any]]):
        if not item:
            return
        item_type = str(item.get("snapshot_item_type") or "WEIGHT").upper()
        if item_type == "PIECE":
            self.counted_quantity.setValue(_as_int(item.get("counted_quantity") or item.get("expected_remaining_quantity")))
            self.counted_weight.setValue(0)
        else:
            self.counted_weight.setValue(_as_float(item.get("counted_weight") or item.get("expected_remaining_weight")))
            self.counted_quantity.setValue(0)
    def new_session(self):
        service = self._service()
        count_id = service.create_session(
            user_id=self._user_id(),
            notes="",
            auto_snapshot=False,
            allow_parallel=False,
        )
        if not count_id:
            QMessageBox.warning(
                self,
                "Inventaire physique",
                "Impossible de creer la session. Une session ouverte existe peut-etre deja.",
            )
            return
        session = service.get_session(count_id) if hasattr(service, "get_session") else {"id": count_id}
        self.current_session = dict(session or {"id": count_id})
        self.refresh_data()
        self.open_selected_session()
    def apply_session_status(self):
        session_id = self.current_session_id()
        if not session_id:
            QMessageBox.warning(self, "Inventaire physique", "Veuillez selectionner une session.")
            return
        target_status = self.session_target_status.currentData()
        if not target_status:
            return
        current_status = str((self.current_session or {}).get("status") or "").upper()
        if current_status == target_status:
            return
        target_label = self.session_target_status.currentText()
        reply = QMessageBox.question(
            self,
            "Inventaire physique",
            f"Changer l'etat de la session vers {target_label} ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ok = self._service().set_session_status(session_id, target_status, user_id=self._user_id())
        if not ok:
            QMessageBox.critical(self, "Inventaire physique", "Impossible de changer l'etat de la session.")
            return
        self.refresh_data()
        if self.stack.currentIndex() == 1:
            self._load_session_details(session_id)
    def start_session(self):
        self._call_session_action("start_session", "Demarrer cette session ?")
    def send_to_review(self):
        self._call_session_action("send_to_review", "Envoyer en revue et marquer les non comptes comme manquants ?")
    def close_session(self):
        self._call_session_action("close_session", "Cloturer l'inventaire ? Les elements non comptes seront marques manquants.", user_id=True)
    def cancel_session(self):
        self._call_session_action("cancel_session", "Annuler cette session ?", user_id=True)
    def delete_draft_session(self):
        self._call_session_action("delete_draft_session", "Supprimer ce brouillon ?", confirm_only_draft=True)
    def _call_session_action(self, method_name, question, user_id=False, confirm_only_draft=False):
        session_id = self.current_session_id()
        if not session_id:
            return
        if confirm_only_draft and str(self.current_session.get("status") or "") != "DRAFT":
            QMessageBox.warning(self, "Inventaire physique", "Seuls les brouillons peuvent etre supprimes.")
            return
        reply = QMessageBox.question(self, "Inventaire physique", question, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        service = self._service()
        method = getattr(service, method_name)
        ok = method(session_id, self._user_id()) if user_id else method(session_id)
        if not ok:
            QMessageBox.critical(self, "Inventaire physique", "Operation impossible.")
            return
        if method_name in {"close_session", "cancel_session", "delete_draft_session"}:
            self.stack.setCurrentIndex(0)
            if method_name == "delete_draft_session":
                self.current_session = {}
        self.refresh_data()
        if self.stack.currentIndex() == 1:
            self._load_session_details(session_id)
            self.barcode_input.setFocus()
    def count_barcode(self, *_args):
        if self._barcode_processing:
            return
        self._barcode_scan_timer.stop()
        session_id = self.current_session_id()
        barcode = self.barcode_input.text().strip()
        if not session_id or not barcode:
            return
        self._barcode_processing = True
        try:
            result = self._service().count_barcode(session_id, barcode, user_id=self._user_id())
            if not result:
                self._show_scan_result("Erreur lecture", barcode)
                self.barcode_input.clear()
                self.barcode_input.setFocus()
                return
            item, extra = self._fetch_scan_record(session_id, barcode, result)
            self.barcode_input.clear()
            self._load_session_details(session_id)
            self._show_scan_result(result, barcode, item=item, extra=extra)
            self._select_barcode_row(barcode, result)
            self.barcode_input.setFocus()
        finally:
            self._barcode_processing = False
    def count_selected_item(self):
        item = self._active_count_item()
        if not item:
            return
        item_type = str(item.get("snapshot_item_type") or "WEIGHT").upper()
        ok = self._service().count_item(
            int(item["id"]),
            counted_weight=self.counted_weight.value() if item_type == "WEIGHT" else None,
            counted_quantity=self.counted_quantity.value() if item_type == "PIECE" else None,
            user_id=self._user_id(),
        )
        if not ok:
            QMessageBox.critical(self, "Inventaire physique", "Impossible de compter l'article.")
            return
        self._load_session_details(self.current_session_id())
    def mark_selected_missing(self):
        item = self._active_count_item()
        if item and self._service().mark_item_missing(int(item["id"]), user_id=self._user_id()):
            self._load_session_details(self.current_session_id())
    def ignore_selected_item(self):
        item = self._active_count_item()
        if item and self._service().ignore_count_item(int(item["id"]), user_id=self._user_id()):
            self._load_session_details(self.current_session_id())
    def reset_selected_item(self):
        item = self._active_count_item()
        if item and self._service().reset_count_item(int(item["id"])):
            self._load_session_details(self.current_session_id())
    def add_extra_item(self):
        session_id = self.current_session_id()
        if not session_id:
            return
        extra_id = self._service().add_extra_item(
            session_id,
            observed_barcode=None,
            observed_name=self.extra_name.text().strip() or None,
            observed_item_type=self.extra_type.currentData(),
            observed_weight=self.extra_weight.value(),
            observed_quantity=self.extra_quantity.value(),
            user_id=self._user_id(),
        )
        if not extra_id:
            QMessageBox.critical(self, "Inventaire physique", "Impossible d'ajouter l'element en trop.")
            return
        self.extra_name.clear()
        self.extra_weight.setValue(0)
        self.extra_quantity.setValue(1)
        self._load_session_details(session_id)
    def create_stock_from_extra(self):
        extra = self._selected_extra()
        session_id = self.current_session_id()
        if not extra or not session_id:
            return
        reply = QMessageBox.question(
            self,
            "Inventaire physique",
            "Creer un article stock a partir de cet element physique ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        adjustment_id = self._service().apply_adjustment(
            session_id,
            "CREATE_INVENTORY",
            extra_item_id=int(extra["id"]),
            payload={
                "name": extra.get("observed_name"),
                "barcode": extra.get("observed_barcode"),
                "item_type": extra.get("observed_item_type"),
                "weight": extra.get("observed_weight"),
                "quantity": extra.get("observed_quantity"),
                "category_id": extra.get("category_id"),
                "metal_type_id": extra.get("metal_type_id"),
                "location_id": extra.get("location_id"),
            },
            user_id=self._user_id(),
        )
        if not adjustment_id:
            QMessageBox.critical(self, "Inventaire physique", "Impossible de creer le stock.")
            return
        self._load_session_details(session_id)
    def ignore_selected_extra(self):
        extra = self._selected_extra()
        if extra and self._service().ignore_extra_item(int(extra["id"])):
            self._load_session_details(self.current_session_id())
    def mark_selected_lost(self):
        item = self._active_count_item()
        session_id = self.current_session_id()
        if not item or not session_id:
            return
        reply = QMessageBox.question(
            self,
            "Inventaire physique",
            "Marquer cet article comme perdu dans le stock ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        adjustment_id = self._service().apply_adjustment(
            session_id,
            "MARK_LOST",
            count_item_id=int(item["id"]),
            user_id=self._user_id(),
        )
        if not adjustment_id:
            QMessageBox.critical(self, "Inventaire physique", "Correction impossible.")
            return
        self._load_session_details(session_id)
    def adjust_selected_item(self):
        item = self._active_count_item()
        if item:
            self._open_adjustment_dialog(item=item)
    def adjust_selected_extra(self):
        extra = self._selected_extra()
        if extra:
            self._open_adjustment_dialog(extra=extra)
    def _open_adjustment_dialog(self, item=None, extra=None):
        session_id = self.current_session_id()
        if not session_id:
            return
        dialog = self._bind_dialog(
            InventoryAdjustmentDialog(self.manager, self, item=item, extra=extra),
            "inventory_count_adjust",
            "Correction inventaire",
        )
        if dialog.exec() != QDialog.Accepted:
            return
        adjustment_id = self._service().apply_adjustment(
            session_id,
            dialog.action_type(),
            count_item_id=int(item["id"]) if item else None,
            extra_item_id=int(extra["id"]) if extra else None,
            payload=dialog.payload(),
            user_id=self._user_id(),
            notes=dialog.notes_text(),
        )
        if not adjustment_id:
            QMessageBox.critical(self, "Inventaire physique", "Correction impossible.")
            return
        self._load_session_details(session_id)
    def _update_actions(self):
        has_session = bool(self.current_session_id())
        status = str((self.current_session or {}).get("status") or "").upper()
        open_for_count = has_session and status in {"DRAFT", "COUNTING", "REVIEW"}

        self.btn_open_session.setEnabled(has_session)
        self.btn_apply_session_status.setEnabled(has_session)
        self.btn_scan.setEnabled(open_for_count)
