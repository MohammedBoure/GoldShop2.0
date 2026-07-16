import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from database.versement_manager import VersementManager
from ui.widgets.versements.invoice_note_selector import (
    create_invoice_note_combo,
    normalize_custom_note,
    selected_custom_note,
)
from ui.widgets.versements.new_versement_dialog import NewVersementDialog
from ui.widgets.versements.versements_view import VersementsView
from ui.tools.print_functions import _thermal_versement_item_rows


class _InvoiceNotes:
    def get_all_notes(self):
        return ["A vendre", "Commande client", "A vendre"]


class _ClosureCursor:
    def __init__(self):
        self.executions = []
        self._one = None
        self._all = []
        self.lastrowid = 0
        self.closed = False

    def execute(self, query, params=None):
        compact = " ".join(query.split())
        self.executions.append((compact, params))
        self._one = None
        self._all = []
        if compact.startswith("SELECT client_id FROM Versements"):
            self._one = {"client_id": 12}
        elif "SELECT vi.inventory_id, vi.designation, vi.notes AS custom_note" in compact:
            self._all = [
                {
                    "inventory_id": 21,
                    "designation": "Bague A",
                    "custom_note": "A vendre",
                    "weight": 1.2,
                    "barcode": "A-21",
                },
                {
                    "inventory_id": 22,
                    "designation": "Bracelet B",
                    "custom_note": "Commande client",
                    "weight": 2.4,
                    "barcode": "B-22",
                },
            ]
        elif compact.startswith("INSERT INTO Sales"):
            self.lastrowid = 99

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._all)

    def close(self):
        self.closed = True


class _ClosureConnection:
    def __init__(self):
        self.cursor_instance = _ClosureCursor()
        self.autocommit = True
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, dictionary=False):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class VersementCustomNoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_selector_has_blank_catalog_and_preserves_deleted_snapshot(self):
        manager = SimpleNamespace(invoice_notes=_InvoiceNotes())
        combo = create_invoice_note_combo(manager, "Ancienne valeur")

        self.assertEqual(combo.itemData(0), "")
        self.assertEqual(combo.count(), 4)
        self.assertEqual(selected_custom_note(combo), "Ancienne valeur")
        self.assertEqual(combo.itemData(combo.count() - 1), "Ancienne valeur")

    def test_note_binding_survives_reorder_and_delete(self):
        first = {"id": 1, "custom_note": ""}
        second = {"id": 2, "custom_note": ""}
        cart_items = [first, second]

        NewVersementDialog._set_item_note(None, second, "Commande client")
        cart_items.reverse()
        cart_items.pop()

        self.assertIs(cart_items[0], second)
        self.assertEqual(second["custom_note"], "Commande client")
        self.assertEqual(first["custom_note"], "")

    def test_note_is_limited_to_saleitems_capacity(self):
        self.assertEqual(len(normalize_custom_note("x" * 300)), 255)

    def test_thermal_versement_note_stays_attached_to_its_product(self):
        rows = _thermal_versement_item_rows({
            "items": [
                {
                    "barcode": "A-21", "item_name": "Bague A",
                    "remaining_weight": 0.75, "custom_note": "A vendre",
                },
                {
                    "barcode": "B-22", "item_name": "Bracelet B",
                    "remaining_weight": 1.50, "custom_note": "Commande client",
                },
            ]
        })

        self.assertEqual(rows[0], ["A-21", "Bague A", "0.75 Gr", "A vendre"])
        self.assertEqual(
            rows[1], ["B-22", "Bracelet B", "1.50 Gr", "Commande client"]
        )

    def test_full_closure_copies_each_product_note_to_its_sale_item(self):
        connection = _ClosureConnection()
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: connection))

        self.assertTrue(manager.cloture_versement(versement_id=7, journee_id=3))
        sale_item_params = [
            params for query, params in connection.cursor_instance.executions
            if query.startswith("INSERT INTO SaleItems")
        ]

        self.assertTrue(connection.committed)
        self.assertEqual(len(sale_item_params), 2)
        self.assertEqual(sale_item_params[0][-1], "A vendre")
        self.assertEqual(sale_item_params[1][-1], "Commande client")

    def test_failed_individual_invoice_restores_item_to_en_cours(self):
        class FakeDialog:
            def __init__(self, manager, data, parent=None):
                self.inp_price = SimpleNamespace(text=lambda: "36000")
                self.inp_cash = SimpleNamespace(text=lambda: "0")
                self.combo_vendeur = SimpleNamespace(currentData=lambda: 4)
                self.client_id = 8

            def exec(self):
                return QDialog.Accepted

            def get_product_note(self):
                return "A vendre"

        versements = SimpleNamespace(
            update_versement_item_notes=Mock(return_value=True),
            retirer_versement_item=Mock(return_value=True),
            revert_versement_item_status=Mock(return_value=(True, "Succès")),
            add_payment=Mock(return_value=True),
        )
        manager = SimpleNamespace(
            versements=versements,
            sales=SimpleNamespace(create_sale=Mock(return_value={"success": False, "message": "DB error"})),
            cash_box=SimpleNamespace(get_or_create_today_session=Mock(return_value={"id": 5})),
        )
        view = SimpleNamespace(manager=manager, load_data=Mock())
        data = {
            "item_id": 31,
            "v_id": 7,
            "inventory_id": 21,
            "designation": "Bague A",
            "weight": 1.2,
        }

        with patch("ui.widgets.versements.versements_view.FacturationVersementDialog", FakeDialog), patch(
            "ui.widgets.versements.versements_view.QMessageBox.critical"
        ):
            VersementsView._handle_retirer_item(view, data)

        versements.revert_versement_item_status.assert_called_once_with(31)
        versements.add_payment.assert_not_called()
        view.load_data.assert_called_once()

    def test_successful_individual_invoice_receives_selected_product_note(self):
        class FakeDialog:
            def __init__(self, manager, data, parent=None):
                self.inp_price = SimpleNamespace(text=lambda: "36000")
                self.inp_cash = SimpleNamespace(text=lambda: "0")
                self.combo_vendeur = SimpleNamespace(currentData=lambda: 4)
                self.client_id = 8

            def exec(self):
                return QDialog.Accepted

            def get_product_note(self):
                return "Commande client"

        sales = SimpleNamespace(create_sale=Mock(return_value={"success": True, "sale_id": 44}))
        versements = SimpleNamespace(
            update_versement_item_notes=Mock(return_value=True),
            retirer_versement_item=Mock(return_value=True),
            revert_versement_item_status=Mock(return_value=(True, "Succès")),
            add_payment=Mock(return_value=True),
        )
        manager = SimpleNamespace(
            versements=versements,
            sales=sales,
            cash_box=SimpleNamespace(get_or_create_today_session=Mock(return_value={"id": 5})),
        )
        view = SimpleNamespace(manager=manager, load_data=Mock())
        data = {
            "item_id": 31,
            "v_id": 7,
            "inventory_id": 21,
            "designation": "Bague A",
            "weight": 1.2,
        }

        with patch("ui.widgets.versements.versements_view.FacturationVersementDialog", FakeDialog):
            VersementsView._handle_retirer_item(view, data)

        cart_items = sales.create_sale.call_args.kwargs["cart_items"]
        self.assertEqual(cart_items[0]["custom_note"], "Commande client")
        versements.revert_versement_item_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
