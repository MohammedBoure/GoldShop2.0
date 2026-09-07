import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem, QLineEdit
from PySide6.QtCore import Qt

from ui.widgets.reports.excel_journal_view import (
    EditWeightDialog,
    SaleProductsDialog,
    ExcelJournalView,
)


class TestExcelJournalFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_edit_weight_dialog(self):
        dlg = EditWeightDialog(current_weight=4.50, designation="Bague Or 18k")
        self.assertEqual(dlg.get_weight(), 4.50)
        dlg.inp_weight.setText("5.25")
        self.assertEqual(dlg.get_weight(), 5.25)

    def test_update_sale_item_weight_called(self):
        mock_sales = SimpleNamespace(
            update_sale_item_weight=Mock(return_value=True),
            get_bulk_sales_for_excel=Mock(return_value={}),
        )
        mock_manager = SimpleNamespace(
            sales=mock_sales,
            versements=SimpleNamespace(),
            cash_box=SimpleNamespace(get_all_sessions=Mock(return_value=[])),
            users=SimpleNamespace(),
            db=SimpleNamespace(get_db_connection=Mock()),
        )
        view = ExcelJournalView(mock_manager)
        view.table.setRowCount(1)
        item0 = QTableWidgetItem("Bague Or 18k")
        item0.setData(Qt.UserRole, 101)  # sale_id
        item0.setData(Qt.UserRole + 1, 202)  # item_id
        item0.setData(Qt.UserRole + 11, 4.50)  # P_S
        view.table.setItem(0, 0, item0)

        with patch.object(EditWeightDialog, "exec", return_value=QDialog.Accepted), \
             patch.object(EditWeightDialog, "get_weight", return_value=5.80), \
             patch.object(view, "load_data"):
            view.edit_p_s(0)

        mock_sales.update_sale_item_weight.assert_called_once_with(202, 5.80)

    def test_copy_barcode_to_clipboard(self):
        mock_manager = SimpleNamespace(
            sales=SimpleNamespace(get_bulk_sales_for_excel=Mock(return_value={})),
            cash_box=SimpleNamespace(get_all_sessions=Mock(return_value=[])),
            db=SimpleNamespace(get_db_connection=Mock()),
        )
        view = ExcelJournalView(mock_manager)
        with patch("PySide6.QtWidgets.QMessageBox.information"):
            view.copy_barcode_to_clipboard("BARCODE-999")
            self.assertEqual(QApplication.clipboard().text(), "BARCODE-999")

    def test_get_bulk_sales_for_excel_mixed_timestamps(self):
        from datetime import datetime, date
        from unittest.mock import MagicMock
        from database.sales_manager import SalesManager

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.side_effect = [
            # 1. Sales
            [
                {
                    "journee_id": 1,
                    "sale_id": 10,
                    "receipt_number": "100",
                    "item_id": 1,
                    "client_name": "Client A",
                    "raw_notes": "",
                    "timestamp": datetime(2026, 9, 7, 14, 0, 0),
                }
            ],
            # 2. Versements
            [
                {
                    "journee_id": 1,
                    "sale_id": "VRS_20",
                    "receipt_number": "VRS-00020",
                    "item_id": 2,
                    "client_name": "Client B",
                    "raw_notes": "",
                    "timestamp": datetime(2026, 9, 7, 10, 0, 0),
                }
            ],
            # 3. ArtisanWorkOrders (has string timestamp '2026-09-07')
            [
                {
                    "journee_id": 1,
                    "sale_id": "REP_30",
                    "receipt_number": "REP-3",
                    "item_id": 3,
                    "client_name": "Client C",
                    "repair_numero": "3",
                    "raw_notes": "Reparation bague",
                    "timestamp": "2026-09-07",
                }
            ],
        ]
        mock_cursor.nextset.return_value = False

        mock_db = MagicMock()
        mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn
        mock_db.get_db_connection.return_value.__exit__.return_value = False

        sm = SalesManager(mock_db)
        res = sm.get_bulk_sales_for_excel([1])

        self.assertIn(1, res)
        items = res[1]
        self.assertEqual(len(items), 3)
        # Order should be: REP_30 (2026-09-07 00:00:00), VRS_20 (10:00:00), Sale 10 (14:00:00)
        self.assertEqual(items[0]["sale_id"], "REP_30")
        self.assertEqual(items[1]["sale_id"], "VRS_20")
        self.assertEqual(items[2]["sale_id"], 10)


    def test_edit_sale_dialog_negative_values(self):
        from ui.widgets.reports.excel_journal_view import EditSaleDialog
        dlg = EditSaleDialog(cash=-500, tpe=250, oc=-2.5, euro=-50, dollar=0, impos=0, oc_silver=0)
        c, t, o, e, d, i, os_val = dlg.get_values()
        self.assertEqual(c, -500.0)
        self.assertEqual(t, 250.0)
        self.assertEqual(o, -2.5)
        self.assertEqual(e, -50.0)

        # Test typing directly with keyboard in line edits
        dlg.inp_cash.setText("-750.50")
        dlg.inp_tpe.setText("-100")
        c, t, o, e, d, i, os_val = dlg.get_values()
        self.assertEqual(c, -750.50)
        self.assertEqual(t, -100.0)

    def test_virtual_numpad_negative_display_and_keyboard(self):
        from ui.tools.virtual_numpad import VirtualNumpad
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent

        # 1. Negative initial value shows minus on display immediately
        w = QLineEdit("-1200")
        pad = VirtualNumpad(mode="direct", target_widget=w, allow_negative=True, allow_decimal=True)
        self.assertTrue(pad.is_negative)
        self.assertEqual(pad.display.text(), "-1200")
        self.assertEqual(w.text(), "-1200")

        # 2. Keyboard minus key toggles sign
        ev_minus = QKeyEvent(QEvent.KeyPress, Qt.Key_Minus, Qt.NoModifier, "-")
        pad.keyPressEvent(ev_minus)
        self.assertFalse(pad.is_negative)
        self.assertEqual(pad.display.text(), "1200")
        self.assertEqual(w.text(), "1200")

        # Toggle back
        pad.keyPressEvent(ev_minus)
        self.assertTrue(pad.is_negative)
        self.assertEqual(pad.display.text(), "-1200")

        # 3. Fresh typing resets is_negative unless explicitly set
        pad.append_char("3")
        self.assertFalse(pad.is_negative)
        self.assertEqual(pad.display.text(), "3")
        self.assertEqual(pad.get_value(), "3")

        # 4. Toggle sign button
        pad.toggle_sign()
        self.assertTrue(pad.is_negative)
        self.assertEqual(pad.display.text(), "-3")
        self.assertEqual(pad.get_value(), "-3")

    def test_on_cell_double_clicked_routes_properly(self):
        mock_sales = SimpleNamespace(get_bulk_sales_for_excel=Mock(return_value={}))
        mock_manager = SimpleNamespace(
            sales=mock_sales,
            cash_box=SimpleNamespace(get_all_sessions=Mock(return_value=[])),
            db=SimpleNamespace(get_db_connection=Mock()),
        )
        view = ExcelJournalView(mock_manager)
        view.table.setRowCount(1)
        item0 = QTableWidgetItem("Collier Or")
        item0.setData(Qt.UserRole, 555)  # sale_id
        item0.setData(Qt.UserRole + 1, 666)  # item_id
        item0.setData(Qt.UserRole + 2, 1000.0)  # cash
        item0.setData(Qt.UserRole + 3, 500.0)  # tpe
        item0.setData(Qt.UserRole + 4, 10.0)  # oc
        item0.setData(Qt.UserRole + 5, 0.0)  # euro
        item0.setData(Qt.UserRole + 6, 0.0)  # dollar
        item0.setData(Qt.UserRole + 7, 0.0)  # impos
        item0.setData(Qt.UserRole + 8, 1)  # seller_id
        item0.setData(Qt.UserRole + 9, "Note test")  # raw_obs
        item0.setData(Qt.UserRole + 14, 0.0)  # oc_silver
        view.table.setItem(0, 0, item0)

        with patch.object(view, "edit_sale") as mock_edit_sale, \
             patch.object(view, "edit_p_s") as mock_edit_ps, \
             patch.object(view, "edit_seller") as mock_edit_seller, \
             patch.object(view, "edit_observation") as mock_edit_obs:

            # Double click col 0 or col 2 (amounts) calls edit_sale directly
            view.on_cell_double_clicked(0, 2)
            mock_edit_sale.assert_called_once_with(555, 1000.0, 500.0, 10.0, 0.0, 0.0, 0.0, 0.0)

            # Double click col 1 (weight) calls edit_p_s
            view.on_cell_double_clicked(0, 1)
            mock_edit_ps.assert_called_once_with(0)

            # Double click col 7 (seller) calls edit_seller
            view.on_cell_double_clicked(0, 7)
            mock_edit_seller.assert_called_once_with(555, 1)

            # Double click col 8 (obs) calls edit_observation
            view.on_cell_double_clicked(0, 8)
            mock_edit_obs.assert_called_once_with(555, 666, "Note test")


if __name__ == "__main__":
    unittest.main()
