import unittest
from datetime import date, datetime
from types import SimpleNamespace


from database.profit_calculator import (
    direct_sale_revenues,
    item_cost_da,
    source_versement_id,
    versement_revenues_by_inventory,
)


class ProfitCalculatorTests(unittest.TestCase):
    def test_initial_cost_is_used_as_historical_cost(self):
        item = {
            "item_type": "WEIGHT",
            "inventory_initial_cost": 72000,
            "inventory_weight": 2.4,
            "sold_weight_g": 1.2,
            "metal_cost_per_gram": 99999,
            "labor_cost_per_gram": 99999,
        }
        self.assertAlmostEqual(item_cost_da(item), 36000.0)

    def test_direct_sale_discount_is_allocated_to_each_product(self):
        revenues = direct_sale_revenues(
            [{"total_price_da": 100000}, {"total_price_da": 300000}],
            40000,
        )
        self.assertEqual(revenues, [90000.0, 270000.0])

    def test_versement_uses_targeted_payments_then_weighted_global_payment(self):
        source_items = [
            {"inventory_id": 10, "inventory_weight": 1.0},
            {"inventory_id": 20, "inventory_weight": 3.0},
        ]
        payments = [
            {"payment_inventory_id": 10, "montant_da": 10000},
            {"montant_da": 20000, "montant_euro": 100, "taux_change_euro": 200},
        ]

        revenues = versement_revenues_by_inventory(source_items, payments)
        self.assertAlmostEqual(revenues[10], 15000.0)
        self.assertAlmostEqual(revenues[20], 15000.0)

    def test_reference_is_detected_for_final_and_individual_versement_invoices(self):
        self.assertEqual(source_versement_id("VRS-00007"), 7)
        self.assertEqual(source_versement_id("FAC-20260717-0001", "Facturé depuis Versement N°VRS-00012"), 12)



class _ProfitCursor:
    def __init__(self):
        self._one = None
        self._many = []

    def execute(self, query, params=None):
        compact = " ".join(query.split())
        if "SELECT id, DATE(created_at) AS sale_date" in compact:
            self._one = None
            self._many = [{"id": 77, "sale_date": date(2026, 7, 17)}]
            return
        elif "FROM Sales s" in compact:
            self._one = {
                "id": 77,
                "receipt_number": "VRS-00007",
                "notes": "Cloture Versement",
                "created_at": datetime(2026, 7, 17, 12, 0, 0),
                "discount_da": 0,
                "net_to_pay_da": 0,
            }
            self._many = []
        elif "FROM SaleItems si" in compact:
            self._one = None
            self._many = [{
                "id": 701,
                "sale_id": 77,
                "inventory_id": 10,
                "item_type": "WEIGHT",
                "sold_weight_g": 1.0,
                "sold_quantity": 1,
                "total_price_da": 0,
                "inventory_initial_cost": 12000,
                "inventory_weight": 1.0,
                "inventory_quantity": 1,
                "metal_cost_per_gram": 99999,
                "labor_cost_per_gram": 99999,
            }]
        elif "FROM Versement_Payments p" in compact:
            self._one = None
            self._many = [{
                "id": 1,
                "versement_item_id": 5,
                "payment_inventory_id": 10,
                "montant_da": 30000,
                "tpe_da": 0,
                "montant_euro": 0,
                "taux_change_euro": 0,
                "montant_dollar": 0,
                "taux_change_dollar": 0,
                "or_casse_g": 0,
                "poids_deduit_g": 0,
                "remise_da": 5000,
                "payment_date": datetime(2026, 7, 17, 11, 0, 0),
            }]
        elif "FROM Versement_Items vi" in compact:
            self._one = None
            self._many = [{"inventory_id": 10, "inventory_weight": 1.0, "inventory_quantity": 1}]
        else:
            raise AssertionError(f"Unexpected query: {compact}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)

    def nextset(self):
        return False


class _ProfitConnection:
    def cursor(self, dictionary=False):
        return _ProfitCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class SalesManagerProfitIntegrationTests(unittest.TestCase):
    def test_completed_versement_profit_uses_paid_amount_and_initial_cost(self):
        from database.sales_manager import SalesManager

        manager = SalesManager(SimpleNamespace(get_db_connection=lambda: _ProfitConnection()))
        sale = manager.get_sale_profit_details(77)

        self.assertAlmostEqual(sale["items"][0]["realized_revenue_da"], 30000.0)
        self.assertAlmostEqual(sale["items"][0]["cost_da"], 12000.0)
        self.assertAlmostEqual(sale["total_profit_da"], 18000.0)

    def test_monthly_profit_groups_the_shared_completed_versement_result(self):
        from database.sales_manager import SalesManager

        manager = SalesManager(SimpleNamespace(get_db_connection=lambda: _ProfitConnection()))
        by_day = manager.get_monthly_profit_by_day(2026, 7)

        self.assertAlmostEqual(by_day[date(2026, 7, 17)]["profit_da"], 18000.0)

if __name__ == "__main__":
    unittest.main()
