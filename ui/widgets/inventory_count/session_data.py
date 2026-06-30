from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from .helpers import SESSION_STATUS_LABELS, _as_float, _as_int, _fmt_weight


class InventoryCountSessionDataMixin:
    def _service(self):
        return getattr(self.manager, "inventory_counts", None)
    def _user_id(self):
        return self.current_user.get("id")
    def refresh_data(self):
        service = self._service()
        if service is None:
            QMessageBox.warning(self, "Inventaire physique", "Service inventaire physique indisponible.")
            return
        selected_id = self.current_session_id()
        try:
            rows = service.list_sessions(
                status=self.session_status.currentData(),
                search_text=self.session_search.text().strip(),
                limit=300,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Inventaire physique", str(exc))
            rows = []

        self.sessions_table.setRowCount(0)
        target_row = 0
        for row_data in rows:
            row = self._append_session(row_data)
            if selected_id and int(row_data.get("id") or 0) == int(selected_id):
                target_row = row
        if self.sessions_table.rowCount() > 0:
            self.sessions_table.selectRow(target_row)
        else:
            self.current_session = {}
            self._clear_details()
        self._update_actions()
    def load_data(self):
        self.refresh_data()
    def refresh_all_data(self):
        self.refresh_data()
    def _append_session(self, session: Dict[str, Any]) -> int:
        row = self.sessions_table.rowCount()
        self.sessions_table.insertRow(row)
        expected = _as_int(session.get("expected_item_count"))
        counted = _as_int(session.get("counted_item_count"))
        values = [
            session.get("id"),
            session.get("display_number") or session.get("count_number") or "",
            SESSION_STATUS_LABELS.get(str(session.get("status") or ""), str(session.get("status") or "")),
            str(session.get("started_at") or "")[:16],
            expected,
            counted,
            _as_int(session.get("missing_item_count")),
            _as_int(session.get("different_item_count")),
            _as_int(session.get("extra_item_count")),
            f"{_fmt_weight(session.get('counted_weight'))} / {_fmt_weight(session.get('expected_weight'))}",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value or ""))
            if column == 0:
                item.setData(Qt.UserRole, session)
            if column >= 4:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.sessions_table.setItem(row, column, item)
        return row
    def current_session_id(self):
        if self.current_session:
            return self.current_session.get("id")
        row = self.sessions_table.currentRow()
        if row < 0:
            return None
        item = self.sessions_table.item(row, 0)
        data = item.data(Qt.UserRole) if item else None
        return data.get("id") if isinstance(data, dict) else None
    def _on_session_selected(self):
        session = self._selected_session()
        if not session:
            self.current_session = {}
            if self.stack.currentIndex() == 1:
                self._clear_details()
            self._update_actions()
            return
        self.current_session = dict(session)
        self._sync_session_status_editor()
        if self.stack.currentIndex() == 1:
            self._load_session_details(int(session["id"]))
        else:
            self._update_summary()
            self._update_actions()
    def _sync_session_status_editor(self):
        status = str((self.current_session or {}).get("status") or "").upper()
        index = self.session_target_status.findData(status)
        if index >= 0:
            self.session_target_status.setCurrentIndex(index)
    def open_selected_session(self):
        session = self._selected_session() or self.current_session
        if not session:
            QMessageBox.warning(self, "Inventaire physique", "Veuillez selectionner une session.")
            return
        self.current_session = dict(session)
        self.stack.setCurrentIndex(1)
        self._load_session_details(int(session["id"]))
        self.barcode_input.clear()
        self.barcode_input.setFocus()
    def back_to_sessions(self):
        self._barcode_scan_timer.stop()
        self.stack.setCurrentIndex(0)
        self.refresh_data()
    def _on_barcode_text_changed(self, text):
        if self._barcode_processing or self.stack.currentIndex() != 1:
            self._barcode_scan_timer.stop()
            return
        if str(text or "").strip():
            self._barcode_scan_timer.start()
        else:
            self._barcode_scan_timer.stop()
    def _auto_count_barcode(self):
        if self._barcode_processing or self.stack.currentIndex() != 1:
            return
        if self.barcode_input.text().strip():
            self.count_barcode()
    def _selected_session(self):
        row = self.sessions_table.currentRow()
        if row < 0:
            return None
        item = self.sessions_table.item(row, 0)
        data = item.data(Qt.UserRole) if item else None
        return data if isinstance(data, dict) else None
    def _load_session_details(self, count_id: int):
        service = self._service()
        if service is None:
            return
        try:
            session = service.get_session(count_id) or self.current_session
        except Exception:
            session = self.current_session
        self.current_session = dict(session or {})
        self._sync_session_status_editor()
        self._update_summary()
        self.refresh_items()
        self.refresh_statistics()
        self._update_actions()
    def _update_summary(self):
        session = self.current_session or {}
        number = session.get("display_number") or session.get("count_number") or session.get("id") or "-"
        status = SESSION_STATUS_LABELS.get(str(session.get("status") or ""), str(session.get("status") or "-"))
        if hasattr(self, "detail_title"):
            self.detail_title.setText(f"Session: {number} | {status}")
        if not hasattr(self, "lbl_session"):
            return
        expected = _as_int(session.get("expected_item_count"))
        counted = _as_int(session.get("counted_item_count"))
        missing = _as_int(session.get("missing_item_count"))
        different = _as_int(session.get("different_item_count"))
        extra = _as_int(session.get("extra_item_count"))
        expected_weight = _as_float(session.get("expected_weight"))
        counted_weight = _as_float(session.get("counted_weight"))
        percent = int((counted / expected) * 100) if expected else 0
        self.lbl_session.setText(f"Session: {number} | {status}")
        self.lbl_expected.setText(f"Attendus: {expected}")
        self.lbl_counted.setText(f"Comptes: {counted}")
        self.lbl_missing.setText(f"Manquants: {missing}")
        self.lbl_diff.setText(f"Differences: {different}")
        self.lbl_extra.setText(f"En trop: {extra}")
        self.lbl_weight.setText(f"Poids: {_fmt_weight(counted_weight)} / {_fmt_weight(expected_weight)}")
        self.progress.setValue(percent)
    def _clear_details(self):
        self._update_summary()
        self._clear_scan_result()
        for table_name in ("checked_items_table", "remaining_items_table"):
            table = getattr(self, table_name, None)
            if table is not None:
                table.setRowCount(0)
        self._clear_statistics()
    def _clear_scan_result(self):
        if not hasattr(self, "lbl_scan_status"):
            return
        self._set_scan_state("neutral")
        self.lbl_scan_status.setText("Derniere lecture: -")
        self.lbl_scan_product.setText("Produit: -")
        self.lbl_scan_supplier.setText("Fournisseur: -")
        self.lbl_scan_category.setText("Categorie: -")
        self.lbl_scan_metal.setText("Titre: -")
        self.lbl_scan_pricing.setText("Prix: -")
        self.lbl_scan_expected.setText("Attendu: -")
        self.lbl_scan_counted.setText("Compte: -")
        self.lbl_scan_difference.setText("Ecart: -")
        self.lbl_scan_inventory.setText("Stock: -")
    def _set_scan_state(self, state: str):
        palette = {
            "ok": ("#dff7e8", "#1f8f61", "#14532d"),
            "warning": ("#fff4d6", "#d88a21", "#7a4a00"),
            "error": ("#fde8e4", "#b42318", "#7f1d1d"),
            "neutral": ("#eef3f7", "#d9e1e8", "#1f2933"),
        }
        background, border, text = palette.get(state, palette["neutral"])
        self.scan_panel.setStyleSheet(
            f"""
            QFrame#scan_result_panel {{
                background: {background};
                border: 2px solid {border};
                border-radius: 6px;
            }}
            QFrame#scan_result_panel QLabel {{
                color: {text};
                font-weight: 800;
            }}
            """
        )
