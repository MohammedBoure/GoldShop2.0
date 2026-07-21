import unittest
from types import SimpleNamespace

from database.sales_manager import SalesManager
from database.versement_manager import VersementManager


class _FakeCursor:
    def __init__(self, inventory=None, closure=False, active_reserved=0):
        self.inventory = inventory or {}
        self.closure = closure
        self.active_reserved = active_reserved
        self.executions = []
        self._one = None
        self._all = []
        self.lastrowid = 1

    def execute(self, query, params=None):
        compact = " ".join(query.split())
        self.executions.append((compact, params))
        self._one = None
        self._all = []

        if compact.startswith("SELECT COUNT(*) as cnt FROM Sales"):
            self._one = {"cnt": 0}
        elif compact.startswith("SELECT client_id FROM Versements"):
            self._one = {"client_id": 7}
        elif "SELECT id, item_type, weight, remaining_weight" in compact:
            self._one = dict(self.inventory)
        elif "SELECT item_type, remaining_weight, remaining_quantity" in compact:
            self._one = dict(self.inventory)
        elif "SELECT COALESCE(SUM(COALESCE(reserved_quantity" in compact:
            self._one = {"reserved_quantity": self.active_reserved, "reservation_count": 1 if self.active_reserved else 0}
        elif "SELECT vi.inventory_id, vi.designation" in compact:
            self._all = [{
                "inventory_id": 10,
                "designation": "Argent",
                "custom_note": "",
                "reserved_quantity": 1,
                "item_type": "PIECE",
                "weight": 1.0,
                "remaining_weight": 0.0,
                "quantity": 3,
                "remaining_quantity": 3,
                "selling_price": 1000,
                "barcode": "AG-10",
            }]
        elif "FROM Versement_Payments p" in compact:
            self._all = []
        elif compact.startswith("INSERT INTO Sales"):
            self.lastrowid = 99

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._all)

    def close(self):
        pass


class _FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.autocommit = True
        self.committed = False
        self.rolled_back = False

    def cursor(self, dictionary=False):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class VersementQuantityManagerTests(unittest.TestCase):
    def test_create_reserves_piece_quantity_without_changing_inventory_status(self):
        inventory = {
            "id": 10, "item_type": "PIECE", "weight": 1.0,
            "remaining_weight": 0.0, "quantity": 3, "remaining_quantity": 3,
            "status": "Available", "reserved_for_client_id": None,
        }
        cursor = _FakeCursor(inventory)
        conn = _FakeConnection(cursor)
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: conn))

        result = manager.create_versement(
            client_id=7, journee_id=1, type_versement="PRODUITS",
            items_list=[{"inventory_id": 10, "designation": "Argent", "item_type": "PIECE", "reserved_quantity": 1}],
            montant_da=0, or_casse_g=0, prix_gramme_jour_da=0,
        )

        self.assertTrue(result["success"])
        item_insert = next(params for query, params in cursor.executions if query.startswith("INSERT INTO Versement_Items"))
        self.assertEqual(item_insert[-1], 1)
        self.assertFalse(any("UPDATE Inventory SET status = 'Reserved'" in query for query, _ in cursor.executions))

    def test_closure_writes_piece_sale_quantity_one(self):
        inventory = {
            "id": 10, "item_type": "PIECE", "weight": 1.0,
            "remaining_weight": 0.0, "quantity": 3, "remaining_quantity": 3,
            "status": "Available", "reserved_for_client_id": None,
        }
        cursor = _FakeCursor(inventory, closure=True)
        conn = _FakeConnection(cursor)
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: conn))

        self.assertTrue(manager.cloture_versement(7, 1))
        sale_item = next(params for query, params in cursor.executions if query.startswith("INSERT INTO SaleItems"))
        self.assertEqual(sale_item[4], "PIECE")
        self.assertEqual(sale_item[6], 1)

    def test_sale_validation_allows_only_unreserved_piece_units(self):
        inventory = {
            "id": 10, "item_type": "PIECE", "remaining_weight": 0.0,
            "remaining_quantity": 3, "status": "Available", "reserved_for_client_id": None,
        }
        cursor = _FakeCursor(inventory, active_reserved=1)
        conn = _FakeConnection(cursor)
        manager = SalesManager(SimpleNamespace(get_raw_connection=lambda: conn))
        cart = [{
            "id": 10, "item_type": "PIECE", "cart_sold_qty": 2,
            "cart_sold_weight": 0, "cart_unit_price": 1000, "cart_line_total": 2000,
        }]
        result = manager.create_sale(1, 2, 3, cart, 2000, 0, 2000, 2000, 0)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
