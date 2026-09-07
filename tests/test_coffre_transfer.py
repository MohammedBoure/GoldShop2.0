import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QTableWidgetItem, QMenu
from PySide6.QtCore import Qt, QDate

from database.coffre_manager import CoffreManager
from ui.widgets.coffre.coffre_management_view import (
    OperationDialog,
    CoffreMagasinView,
)
from ui.widgets.reports.excel_journal_view import (
    TransferToCoffreDialog,
    ExcelJournalView,
)


class TestCoffreTransferAndStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_coffre_manager_add_and_update_with_oc(self):
        """اختبار إضافة وتعديل عمليات الخزينة مع دعم كسر الذهب والفضة"""
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 123
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        mock_db = MagicMock()
        mock_db.get_db_connection.return_value = mock_conn

        cm = CoffreManager(mock_db)

        # 1. Add operation
        res = cm.add_operation(
            date_operation="04/09/2026",
            montant_da="150000",
            tpe="25000",
            ccp="0",
            euro="100",
            dollar="50",
            designation="Recette Journal du 04/09/2026",
            oc_or="12.50",
            oc_argent="45.00"
        )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("id"), 123)

        # Verify SQL INSERT parameters
        calls = [c for c in mock_cursor.execute.call_args_list if "INSERT INTO CoffreMagasin" in str(c)]
        self.assertEqual(len(calls), 1)
        insert_args = calls[0][0][1]
        self.assertEqual(insert_args[0], "04/09/2026")
        self.assertEqual(insert_args[1], "150000")
        self.assertEqual(insert_args[2], "12.50")
        self.assertEqual(insert_args[3], "45.00")

        # 2. Update operation
        up_res = cm.update_operation(
            op_id=123,
            date_operation="04/09/2026",
            montant_da="160000",
            tpe="25000",
            ccp="0",
            euro="100",
            dollar="50",
            designation="Recette Journal modifiée",
            oc_or="15.00",
            oc_argent="50.00"
        )
        self.assertTrue(up_res)
        up_calls = [c for c in mock_cursor.execute.call_args_list if "UPDATE CoffreMagasin" in str(c)]
        self.assertEqual(len(up_calls), 1)
        up_args = up_calls[0][0][1]
        self.assertEqual(up_args[1], "160000")
        self.assertEqual(up_args[2], "15.00")
        self.assertEqual(up_args[3], "50.00")

    def test_coffre_operation_dialog_fields(self):
        """اختبار حقول نافذة إضافة عملية في الخزينة وقراءة الذهب والفضة الكسر"""
        rec = {
            "id": 1,
            "date_operation": "04/09/2026",
            "montant_da": "120000",
            "oc_or": "8.75",
            "oc_argent": "22.30",
            "tpe": "15000",
            "ccp": "5000",
            "euro": "200",
            "dollar": "0",
            "designation": "Versement recette"
        }
        dlg = OperationDialog(record=rec)
        data = dlg.get_data()
        self.assertEqual(data["montant_da"], "120000")
        self.assertEqual(data["oc_or"], "8.75")
        self.assertEqual(data["oc_argent"], "22.30")
        self.assertEqual(data["tpe"], "15000")
        self.assertEqual(data["designation"], "Versement recette")

    def test_coffre_magasin_view_structure_and_totals(self):
        """اختبار هيكل جدول الخزينة بـ 9 أعمدة واحتساب الإجماليات بدقة"""
        mock_manager = SimpleNamespace(
            coffre=SimpleNamespace(
                get_all_operations=Mock(return_value=[
                    {
                        "id": 1,
                        "date_operation": "01/09/2026",
                        "montant_da": "100000",
                        "oc_or": "10.00",
                        "oc_argent": "20.00",
                        "tpe": "5000",
                        "ccp": "0",
                        "euro": "50",
                        "dollar": "0",
                        "designation": "Jour 1"
                    },
                    {
                        "id": 2,
                        "date_operation": "02/09/2026",
                        "montant_da": "200000",
                        "oc_or": "5.50",
                        "oc_argent": "15.00",
                        "tpe": "10000",
                        "ccp": "0",
                        "euro": "0",
                        "dollar": "100",
                        "designation": "Jour 2"
                    }
                ])
            )
        )
        view = CoffreMagasinView(mock_manager)
        view.load_data()

        # Check table columns: 9 columns
        self.assertEqual(view.table.columnCount(), 9)
        headers = [view.table.horizontalHeaderItem(i).text() for i in range(9)]
        self.assertEqual(headers, ["Date", "Montant (DA)", "O.C Or (g)", "O.C Ag (g)", "TPE", "CCP", "Euro", "Dollar", "Désignation"])

        # Check row count: 2 data rows + 1 total row = 3 rows
        self.assertEqual(view.table.rowCount(), 3)

        # Check total row (row 2)
        self.assertEqual(view.table.item(2, 0).text(), "TOTAUX :")
        self.assertEqual(view.table.item(2, 1).text(), "300,000.00") # total montant_da
        self.assertEqual(view.table.item(2, 2).text(), "15.50 g")     # total oc_or
        self.assertEqual(view.table.item(2, 3).text(), "35.00 g")     # total oc_argent
        self.assertEqual(view.table.item(2, 4).text(), "15,000.00")  # total tpe

    def test_transfer_to_coffre_dialog_execution(self):
        """اختبار نافذة التحويل وتنفيذ الحفظ في الخزينة"""
        mock_coffre = SimpleNamespace(
            check_existing_transfer=Mock(return_value=[]),
            add_operation=Mock(return_value={"success": True, "id": 55})
        )
        mock_manager = SimpleNamespace(coffre=mock_coffre)

        dlg = TransferToCoffreDialog(
            manager=mock_manager,
            date_str="04/09/2026",
            recette=185000.0,
            oc_gold=14.25,
            oc_silver=30.00,
            tpe=12000.0,
            euro=50.0,
            dollar=0.0
        )

        self.assertEqual(dlg.inp_montant.text(), "185000")
        self.assertEqual(dlg.inp_oc_or.text(), "14.25")
        self.assertEqual(dlg.inp_oc_argent.text(), "30.00")
        self.assertEqual(dlg.inp_tpe.text(), "12000")
        self.assertEqual(dlg.inp_euro.text(), "50")

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            dlg._do_transfer()

        mock_coffre.add_operation.assert_called_once_with(
            date_operation="04/09/2026",
            montant_da="185000",
            tpe="12000",
            ccp="0",
            euro="50",
            dollar="0",
            designation="Recette & O.C Journal du 04/09/2026",
            oc_or="14.25",
            oc_argent="30.00"
        )

    def test_coffre_manager_replace_daily_transfer(self):
        """اختبار دالة استبدال سطر تحويل اليومية في الخزينة وتنظيف التكرار"""
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 77
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        mock_db = MagicMock()
        mock_db.get_db_connection.return_value = mock_conn

        cm = CoffreManager(mock_db)

        # 1. When existing transfers exist, update primary and delete other duplicates
        with patch.object(cm, "check_existing_transfer", return_value=[{"id": 10}, {"id": 11}]), \
             patch.object(cm, "update_operation", return_value=True) as mock_update:
            res = cm.replace_daily_transfer(
                date_operation="07/09/2026",
                montant_da="190000",
                tpe="15000",
                oc_or="10.50",
                oc_argent="20.00"
            )
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("action"), "replaced")
            self.assertEqual(res.get("id"), 10)
            mock_update.assert_called_once()
            # Verify DELETE was called for duplicate id 11
            del_calls = [c for c in mock_cursor.execute.call_args_list if "DELETE FROM CoffreMagasin" in str(c)]
            self.assertEqual(len(del_calls), 1)

        # 2. When no existing transfers exist, add new operation
        with patch.object(cm, "check_existing_transfer", return_value=[]), \
             patch.object(cm, "add_operation", return_value={"success": True, "id": 77}) as mock_add:
            res2 = cm.replace_daily_transfer(
                date_operation="07/09/2026",
                montant_da="190000"
            )
            self.assertTrue(res2.get("success"))
            self.assertEqual(res2.get("action"), "created")
            mock_add.assert_called_once()

    def test_transfer_to_coffre_dialog_replacement_execution(self):
        """اختبار نافذة التحويل في وضع الاستبدال واستدعاء replace_daily_transfer"""
        mock_coffre = SimpleNamespace(
            replace_daily_transfer=Mock(return_value={"success": True, "id": 10}),
            check_existing_transfer=Mock(return_value=[{"id": 10}])
        )
        mock_manager = SimpleNamespace(coffre=mock_coffre)

        dlg = TransferToCoffreDialog(
            manager=mock_manager,
            date_str="07/09/2026",
            recette=250000.0,
            oc_gold=18.00,
            oc_silver=10.00,
            tpe=20000.0,
            euro=0.0,
            dollar=0.0,
            is_replacement=True
        )

        self.assertTrue(dlg.is_replacement)
        self.assertIn("Remplacer", dlg.windowTitle())

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            dlg._do_transfer()

        mock_coffre.replace_daily_transfer.assert_called_once_with(
            date_operation="07/09/2026",
            montant_da="250000",
            tpe="20000",
            ccp="0",
            euro="0",
            dollar="0",
            designation="Recette & O.C Journal du 07/09/2026",
            oc_or="18.00",
            oc_argent="10.00"
        )

    def test_daily_total_context_menu_has_replace_command_when_already_transferred(self):
        """اختبار ظهور أمر استبدال سطر الخزينة كأمر مفعل بدلاً من أمر معطل عند وجود تحويل سابق"""
        mock_manager = SimpleNamespace(
            sales=SimpleNamespace(get_bulk_sales_for_excel=Mock(return_value={})),
            cash_box=SimpleNamespace(get_all_sessions=Mock(return_value=[])),
            coffre=SimpleNamespace(check_existing_transfer=Mock(return_value=[{"id": 10, "montant_da": "100000"}])),
            db=SimpleNamespace(get_db_connection=Mock()),
        )
        view = ExcelJournalView(mock_manager)
        total_item = QTableWidgetItem("Total Journée")
        total_item.setData(Qt.UserRole, "TOTAL_JOURNEE")
        total_item.setData(Qt.UserRole + 1, "07/09/2026")
        total_item.setData(Qt.UserRole + 2, 250000.0)
        total_item.setData(Qt.UserRole + 3, 18.00)
        total_item.setData(Qt.UserRole + 4, 10.00)

        with patch("PySide6.QtWidgets.QMenu.exec_", return_value=None):
            # Capture actions added to QMenu
            actions_added = []
            orig_add_action = QMenu.addAction

            def mock_add_action(self, *args, **kwargs):
                action = orig_add_action(self, *args, **kwargs)
                actions_added.append(action.text())
                return action

            with patch.object(QMenu, "addAction", mock_add_action):
                from PySide6.QtCore import QPoint
                view._show_daily_total_context_menu(QPoint(0, 0), total_item)

            # Vérifier la présence de l'action de remplacement active
            has_replace_act = any("Remplacer la ligne transférée au Coffre" in txt for txt in actions_added)
            self.assertTrue(has_replace_act, f"Actions found: {actions_added}")
            # Vérifier qu'on n'a plus l'ancienne information désactivée 'Déjà transféré au Coffre'
            has_old_disabled = any("Déjà transféré au Coffre" in txt for txt in actions_added)
            self.assertFalse(has_old_disabled, f"Old disabled action still found in: {actions_added}")

    def test_coffre_top_bar_edit_and_delete_buttons_selection_behavior(self):
        """اختبار أزرار التعديل والحذف في الشريط العلوي وتفاعلها مع تحديد الأسطر في جدول الخزينة"""
        record_1 = {
            "id": 101,
            "date_operation": "01/09/2026",
            "montant_da": "100000",
            "oc_or": "10.00",
            "oc_argent": "20.00",
            "tpe": "5000",
            "ccp": "0",
            "euro": "50",
            "dollar": "0",
            "designation": "Op 1"
        }
        record_2 = {
            "id": 102,
            "date_operation": "02/09/2026",
            "montant_da": "200000",
            "oc_or": "5.50",
            "oc_argent": "15.00",
            "tpe": "10000",
            "ccp": "0",
            "euro": "0",
            "dollar": "100",
            "designation": "Op 2"
        }
        mock_manager = SimpleNamespace(
            coffre=SimpleNamespace(
                get_all_operations=Mock(return_value=[record_1, record_2]),
                update_operation=Mock(return_value=True),
                delete_operation=Mock(return_value=True)
            )
        )
        view = CoffreMagasinView(mock_manager)
        view.load_data()

        # 1. Verify buttons exist
        self.assertTrue(hasattr(view, "btn_edit"))
        self.assertTrue(hasattr(view, "btn_delete"))

        # 2. Initially with no selection, both buttons must be disabled
        view.table.clearSelection()
        view._update_action_buttons_state()
        self.assertFalse(view.btn_edit.isEnabled())
        self.assertFalse(view.btn_delete.isEnabled())

        # 3. Select first data row (row 0) -> Both buttons must be enabled
        view.table.selectRow(0)
        self.assertTrue(view.btn_edit.isEnabled())
        self.assertTrue(view.btn_delete.isEnabled())
        self.assertEqual(view._get_selected_record()["id"], 101)

        # 4. Select total row (row 2: "TOTAUX :") -> Both buttons must be disabled
        view.table.selectRow(2)
        self.assertFalse(view.btn_edit.isEnabled())
        self.assertFalse(view.btn_delete.isEnabled())
        self.assertIsNone(view._get_selected_record())

        # 5. Select second data row (row 1) -> Both buttons enabled
        view.table.selectRow(1)
        self.assertTrue(view.btn_edit.isEnabled())
        self.assertTrue(view.btn_delete.isEnabled())
        self.assertEqual(view._get_selected_record()["id"], 102)

        # 6. Test clicking edit button triggers open_edit_dialog with the selected record
        with patch.object(view, "open_edit_dialog") as mock_edit_dlg:
            view.btn_edit.click()
            mock_edit_dlg.assert_called_once_with(record_2)

        # 7. Test clicking delete button triggers delete_record with the record's id
        with patch.object(view, "delete_record") as mock_del_rec:
            view.btn_delete.click()
            mock_del_rec.assert_called_once_with(102)


if __name__ == "__main__":
    unittest.main()
