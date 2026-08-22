import unittest
from types import SimpleNamespace
from database.profit_calculator import payment_amount_da
from database.sales_manager import SalesManager
from database.versement.versement_invoice_summary import build_versement_payment_summary


class _FakeCursor:
    def __init__(self):
        self.executions = []
        self.lastrowid = 101

    def execute(self, query, params=None):
        compact = " ".join(query.split())
        self.executions.append((compact, params))
        if compact.startswith("SELECT COUNT(*) as cnt FROM Sales"):
            self._one = {"cnt": 0}
        elif "SELECT id, item_type, weight, remaining_weight" in compact:
            self._one = {
                "id": 1, "item_type": "WEIGHT", "weight": 50.0,
                "remaining_weight": 50.0, "quantity": 1, "remaining_quantity": 1,
                "status": "Available", "reserved_for_client_id": None, "metal_type_id": 2
            }
        elif "SELECT COALESCE(SUM(COALESCE(reserved_quantity" in compact:
            self._one = {"active_reserved_quantity": 0, "active_versement_count": 0}
        elif "SELECT item_type FROM Inventory" in compact:
            self._one = {"item_type": "WEIGHT"}
        else:
            self._one = None

    def fetchone(self):
        return getattr(self, "_one", None)

    def fetchall(self):
        return []

    def close(self):
        pass


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = True

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class MultiMetalSalesTests(unittest.TestCase):
    def test_payment_amount_da_with_old_silver(self):
        payment = {
            "montant_da": 5000.0,
            "tpe_da": 1000.0,
            "montant_euro": 10.0,
            "taux_change_euro": 240.0,
            "montant_dollar": 0.0,
            "taux_change_dollar": 0.0,
            "or_casse_g": 2.0,
            "prix_gramme_jour_da": 10000.0,
            "argent_casse_g": 50.0,
            "prix_gramme_argent_jour_da": 200.0
        }
        total = payment_amount_da(payment)
        self.assertGreater(total, 0)

    def test_versement_summary_with_old_silver(self):
        payments = [{
            "id": 1,
            "payment_date": "2026-08-22",
            "montant_da": 0,
            "tpe_da": 0,
            "montant_euro": 0,
            "taux_change_euro": 0,
            "montant_dollar": 0,
            "taux_change_dollar": 0,
            "or_casse_g": 1.5,
            "prix_gramme_jour_da": 10000.0,
            "argent_casse_g": 25.0,
            "prix_gramme_argent_jour_da": 150.0,
            "poids_deduit_g": 0,
            "remise_da": 0,
        }]
        summary = build_versement_payment_summary(payments)
        self.assertAlmostEqual(summary["old_gold_weight_g"], 1.5)
        self.assertAlmostEqual(summary["old_gold_equivalent_da"], 15000.0)
        self.assertAlmostEqual(summary["old_silver_weight_g"], 25.0)
        self.assertAlmostEqual(summary["old_silver_equivalent_da"], 3750.0)
        self.assertAlmostEqual(summary["total_paid_da"], 18750.0)

    def test_create_sale_with_gold_and_silver_items(self):
        cursor = _FakeCursor()
        conn = _FakeConnection(cursor)
        manager = SalesManager(SimpleNamespace(get_raw_connection=lambda: conn))

        cart = [
            {
                "id": 1,
                "name": "Bague Or 18k",
                "item_type": "WEIGHT",
                "cart_sold_weight": 3.5,
                "cart_sold_qty": 1,
                "cart_unit_price": 12000,
                "cart_line_total": 42000,
                "metal_category": "GOLD"
            },
            {
                "id": 2,
                "name": "Chaine Argent 925",
                "item_type": "WEIGHT",
                "cart_sold_weight": 15.0,
                "cart_sold_qty": 1,
                "cart_unit_price": 400,
                "cart_line_total": 6000,
                "metal_category": "SILVER"
            }
        ]

        result = manager.create_sale(
            journee_id=1,
            client_id=1,
            user_id=1,
            cart_items=cart,
            total_amount=48000,
            discount=0,
            net_to_pay=48000,
            cash_paid=20000,
            tpe_paid=0,
            old_gold_weight=2.0,
            old_silver_weight=10.0,
            old_silver_price=150.0
        )

        self.assertTrue(result["success"])
        sales_insert = next(p for q, p in cursor.executions if q.startswith("INSERT INTO Sales"))
        self.assertEqual(sales_insert[9], 2.0)
        self.assertEqual(sales_insert[10], 10.0)
        self.assertEqual(sales_insert[11], 150.0)

        item_inserts = [p for q, p in cursor.executions if q.startswith("INSERT INTO SaleItems")]
        self.assertEqual(len(item_inserts), 2)
        self.assertEqual(item_inserts[0][3], "GOLD")
        self.assertEqual(item_inserts[1][3], "SILVER")


if __name__ == "__main__":
    unittest.main()
