import unittest

from database.versement_reservation import (
    available_piece_quantity,
    derived_inventory_status,
    is_piece_sellable,
    is_weight_sellable,
    normalize_reserved_quantity,
    sellable_stock_condition_sql,
)
from ui.widgets.sales.POS.pos_inventory_loader import POSInventoryLoader


class VersementReservationTests(unittest.TestCase):
    def test_piece_quantity_is_reserved_partially(self):
        self.assertEqual(available_piece_quantity(3, 1), 2)
        self.assertTrue(is_piece_sellable(3, 1))
        self.assertFalse(is_piece_sellable(1, 1))

    def test_piece_reservation_quantity_is_positive_and_weight_is_one(self):
        self.assertEqual(normalize_reserved_quantity("PIECE", 2), 2)
        self.assertEqual(normalize_reserved_quantity("WEIGHT", 9), 1)
        with self.assertRaises(ValueError):
            normalize_reserved_quantity("PIECE", 0)

    def test_weight_reservation_blocks_full_sale(self):
        self.assertTrue(is_weight_sellable(1.2, 0))
        self.assertFalse(is_weight_sellable(1.2, 1))

    def test_status_is_derived_from_physical_stock(self):
        self.assertEqual(derived_inventory_status("PIECE", 0, 3, 0, 3), "Sold")
        self.assertEqual(derived_inventory_status("PIECE", 0, 3, 2, 3), "Partially_Sold")
        self.assertEqual(derived_inventory_status("PIECE", 0, 3, 3, 3), "Available")
        self.assertEqual(derived_inventory_status("WEIGHT", 0.0, 1.0, 0, 1), "Sold")

    def test_sellable_sql_uses_aggregate_reservations_and_preserves_client_reservation(self):
        sql = sellable_stock_condition_sql("i")
        self.assertIn("SUM(COALESCE(vi.reserved_quantity, 1))", sql)
        self.assertIn("COUNT(*)", sql)
        self.assertIn("reserved_for_client_id IS NULL", sql)
        self.assertIn("remaining_quantity", sql)
        self.assertNotIn("JOIN Versement_Items", sql)

    def test_pos_uses_sellable_piece_quantity(self):
        self.assertTrue(POSInventoryLoader._has_real_stock({
            "item_type": "PIECE",
            "status": "Available",
            "remaining_quantity": 3,
            "active_reserved_quantity": 1,
        }))
        self.assertFalse(POSInventoryLoader._has_real_stock({
            "item_type": "PIECE",
            "status": "Partially_Sold",
            "remaining_quantity": 1,
            "active_reserved_quantity": 1,
        }))
        self.assertFalse(POSInventoryLoader._has_real_stock({
            "item_type": "WEIGHT",
            "status": "Available",
            "remaining_weight": 1.0,
            "active_versement_count": 1,
        }))


if __name__ == "__main__":
    unittest.main()
