import unittest
from types import SimpleNamespace

from database.sales_manager import SalesManager
from database.versement import VersementManager


class _MockCursor:
    def __init__(self, versement=None, items=None, sales=None, inventory=None):
        self.versement = versement or {"client_id": 1, "status": "EN_COURS"}
        self.items = items or []
        self.sales = sales or []
        self.inventory = inventory or {}
        self.executions = []
        self.lastrowid = 1
        self._one = None
        self._all = []

    def execute(self, query, params=None):
        compact = " ".join(query.split())
        self.executions.append((compact, params))
        self._one = None
        self._all = []

        if compact.startswith("SELECT client_id, status FROM Versements") or compact.startswith("SELECT client_id FROM Versements"):
            self._one = dict(self.versement)
        elif compact.startswith("SELECT status FROM Versements"):
            self._one = dict(self.versement)
        elif "SELECT vi.id AS versement_item_id, vi.inventory_id" in compact or "SELECT vi.inventory_id, vi.designation" in compact:
            self._all = [dict(it) for it in self.items if it.get("item_status") == "EN_COURS"]
        elif "FROM Versement_Payments p" in compact:
            self._all = []
        elif "FROM Sales" in compact and "WHERE id = %s" in compact:
            sale_id = params[0] if params else 1
            matching = [s for s in self.sales if s.get("id") == sale_id]
            self._one = dict(matching[0]) if matching else None
        elif "FROM Sales" in compact and ("receipt_number" in compact or "notes LIKE" in compact):
            tag = str(params[0]) if params else ""
            matching = [s for s in self.sales if s.get("receipt_number") == tag or tag.strip("%") in str(s.get("notes", ""))]
            if "SELECT id" in compact and "WHERE receipt_number" in compact:
                self._one = dict(matching[0]) if matching else None
            else:
                self._all = [dict(s) for s in matching]
        elif "FROM SaleItems" in compact:
            self._all = [
                {
                    "id": 1,
                    "sale_id": 100,
                    "inventory_id": 10,
                    "item_type": "WEIGHT",
                    "sold_weight_g": 1.32,
                    "sold_quantity": 1,
                }
            ]
        elif compact.startswith("INSERT INTO Sales"):
            self.lastrowid = 100
        elif compact.startswith("SELECT DISTINCT inventory_id FROM Versement_Items"):
            self._all = [{"inventory_id": it.get("inventory_id")} for it in self.items if it.get("inventory_id")]
        elif compact.startswith("SELECT id, item_type, weight, remaining_weight"):
            self._one = dict(self.inventory)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._all)

    def close(self):
        pass


class _MockConnection:
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


class VersementIdempotencyAndWeightTests(unittest.TestCase):
    def test_cloture_versement_bounds_sold_weight_to_original_weight(self):
        """Even if remaining_weight in DB was inflated to 2.64g, sold_weight is bounded by unit weight 1.32g."""
        items = [
            {
                "inventory_id": 10,
                "designation": "Bague Or",
                "custom_note": "",
                "reserved_quantity": 1,
                "item_type": "WEIGHT",
                "weight": 1.32,
                "remaining_weight": 2.64,  # Inflated corrupted weight
                "quantity": 1,
                "remaining_quantity": 1,
                "selling_price": 10000,
                "barcode": "BG-01",
                "item_status": "EN_COURS",
            }
        ]
        cursor = _MockCursor(
            versement={"client_id": 5, "status": "EN_COURS"},
            items=items,
        )
        conn = _MockConnection(cursor)
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: conn))

        self.assertTrue(manager.cloture_versement(versement_id=12, journee_id=1))
        sale_item_insert = next(params for query, params in cursor.executions if query.startswith("INSERT INTO SaleItems"))
        # Check sold_weight_g is 1.32, NOT 2.64
        self.assertEqual(sale_item_insert[5], 1.32)

    def test_cloture_versement_idempotent_when_already_closed(self):
        """Calling cloture on an already closed versement does nothing and returns True."""
        cursor = _MockCursor(
            versement={"client_id": 5, "status": "CLOTURE"},
            items=[],
        )
        conn = _MockConnection(cursor)
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: conn))

        self.assertTrue(manager.cloture_versement(versement_id=12, journee_id=1))
        # No INSERT into Sales should happen
        self.assertFalse(any(query.startswith("INSERT INTO Sales") for query, _ in cursor.executions))

    def test_cancel_versement_caps_inventory_restoration(self):
        """Cancelling a versement with completed closure sales restores stock using LEAST(weight, ...)"""
        sales = [
            {"id": 100, "receipt_number": "VRS-00012", "notes": "Clôture Versement N° VRS-00012", "status": "COMPLETED"}
        ]
        cursor = _MockCursor(
            versement={"client_id": 5, "status": "CLOTURE"},
            sales=sales,
        )
        conn = _MockConnection(cursor)
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: conn))

        self.assertTrue(manager.cancel_versement(versement_id=12))
        # Verify Inventory update uses LEAST(weight, ...)
        inv_updates = [query for query, _ in cursor.executions if query.startswith("UPDATE Inventory")]
        self.assertTrue(any("LEAST(weight" in q for q in inv_updates))

    def test_cancel_versement_idempotent_when_already_cancelled(self):
        """Calling cancel on already cancelled versement returns True without re-running restorations."""
        cursor = _MockCursor(
            versement={"client_id": 5, "status": "ANNULE"},
        )
        conn = _MockConnection(cursor)
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: conn))

        self.assertTrue(manager.cancel_versement(versement_id=12))
        self.assertFalse(any(query.startswith("UPDATE Sales SET status = 'CANCELLED'") for query, _ in cursor.executions))

    def test_cancel_sale_caps_inventory_restoration_and_syncs_versement(self):
        """Cancelling a sale caps stock restoration at weight and resets closed versement to EN_COURS."""
        sales = [
            {"id": 100, "receipt_number": "VRS-00012", "notes": "Clôture Versement N° VRS-00012", "status": "COMPLETED"}
        ]
        cursor = _MockCursor(
            versement={"client_id": 5, "status": "CLOTURE"},
            sales=sales,
        )
        conn = _MockConnection(cursor)
        manager = SalesManager(SimpleNamespace(get_raw_connection=lambda: conn))

        self.assertTrue(manager.cancel_sale(sale_id=100))
        # Check stock update uses LEAST(weight, ...)
        inv_updates = [query for query, _ in cursor.executions if query.startswith("UPDATE Inventory")]
        self.assertTrue(any("LEAST(weight" in q for q in inv_updates))
        # Check versement is synced to EN_COURS
        self.assertTrue(any("UPDATE Versements SET status = 'EN_COURS'" in query for query, _ in cursor.executions))

    def test_cloture_versement_cleans_up_stale_cancelled_sale(self):
        """If an old cancelled sale with receipt_number VRS-00012 exists, it is deleted and re-inserted cleanly."""
        items = [
            {
                "inventory_id": 10,
                "designation": "Bague Or",
                "custom_note": "",
                "reserved_quantity": 1,
                "item_type": "WEIGHT",
                "weight": 1.32,
                "remaining_weight": 1.32,
                "quantity": 1,
                "remaining_quantity": 1,
                "selling_price": 10000,
                "barcode": "BG-01",
                "item_status": "EN_COURS",
            }
        ]
        sales = [
            {"id": 99, "receipt_number": "VRS-00012", "notes": "Ancienne clôture", "status": "CANCELLED"}
        ]
        cursor = _MockCursor(
            versement={"client_id": 5, "status": "EN_COURS"},
            items=items,
            sales=sales,
        )
        conn = _MockConnection(cursor)
        manager = VersementManager(SimpleNamespace(get_raw_connection=lambda: conn))

        self.assertTrue(manager.cloture_versement(versement_id=12, journee_id=1))
        # Ensure stale cancelled sale was deleted
        self.assertTrue(any("DELETE FROM Sales WHERE id = %s" in q for q, _ in cursor.executions))
        # Ensure new sale was inserted
        self.assertTrue(any(q.startswith("INSERT INTO Sales") for q, _ in cursor.executions))

    def test_negative_payment_cash_refund_summary(self):
        """A versement with 5g gold payment (50k DA) and a -10k DA cash refund yields net 40k DA paid."""
        from database.versement.versement_invoice_summary import build_versement_payment_summary
        from database.versement.versement_pricing import payment_value_da

        payments = [
            {
                "id": 1,
                "montant_da": 50000.0,
                "tpe_da": 0.0,
                "montant_euro": 0.0,
                "taux_change_euro": 0.0,
                "montant_dollar": 0.0,
                "taux_change_dollar": 0.0,
                "or_casse_g": 5.0,
                "prix_gramme_jour_da": 10000.0,
                "poids_deduit_g": 5.0,
                "remise_da": 0.0,
                "notes": "Paiement en or cassé",
            },
            {
                "id": 2,
                "montant_da": -10000.0,
                "tpe_da": 0.0,
                "montant_euro": 0.0,
                "taux_change_euro": 0.0,
                "montant_dollar": 0.0,
                "taux_change_dollar": 0.0,
                "or_casse_g": 0.0,
                "prix_gramme_jour_da": 0.0,
                "poids_deduit_g": 0.0,
                "remise_da": 0.0,
                "notes": "Rendu surplus au client (différence or cassé)",
            }
        ]

        val1 = payment_value_da(payments[0])
        val2 = payment_value_da(payments[1])
        self.assertEqual(val1, 50000.0)
        self.assertEqual(val2, -10000.0)

        summary = build_versement_payment_summary(payments)
        self.assertEqual(summary["cash_paid_da"], -10000.0)
        self.assertEqual(summary["old_gold_weight_g"], 5.0)
        self.assertEqual(summary["old_gold_equivalent_da"], 50000.0)
        self.assertEqual(summary["total_paid_da"], 40000.0)
        self.assertEqual(summary["net_to_pay_da"], 40000.0)


if __name__ == "__main__":
    unittest.main()
