import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem
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


if __name__ == "__main__":
    unittest.main()
