import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSpinBox

from ui.widgets.versements.new_versement_dialog import NewVersementDialog


class VersementQuantityUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_piece_quantity_editor_uses_unreserved_maximum_and_totals(self):
        manager = SimpleNamespace(
            invoice_notes=SimpleNamespace(get_all_notes=lambda: []),
            inventory=SimpleNamespace(get_inventory_paginated=lambda **kwargs: ([], 0, 0.0)),
        )
        dialog = NewVersementDialog(manager, {"id": 1})
        dialog.cart_items = [{
            "id": 10,
            "barcode": "S-10",
            "name": "Bracelet Argent",
            "item_type": "PIECE",
            "weight": 1.25,
            "selling_price": 12000,
            "remaining_quantity": 3,
            "active_reserved_quantity": 1,
            "versement_max_quantity": 2,
            "versement_quantity": 1,
        }]
        dialog.refresh_cart()

        quantity_widget = dialog.cart_table.cellWidget(0, 2)
        self.assertIsInstance(quantity_widget, QSpinBox)
        self.assertEqual(quantity_widget.maximum(), 2)
        self.assertEqual(dialog._item_total_weight(dialog.cart_items[0]), 1.25)
        self.assertEqual(dialog._item_total_price(dialog.cart_items[0]), 12000)

        quantity_widget.setValue(2)
        self.assertEqual(dialog.cart_items[0]["versement_quantity"], 2)
        self.assertEqual(dialog._item_total_weight(dialog.cart_items[0]), 2.5)
        self.assertEqual(dialog._item_total_price(dialog.cart_items[0]), 24000)


if __name__ == "__main__":
    unittest.main()
