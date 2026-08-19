import unittest

from database.versement import (
    build_versement_payment_summary,
    discount_for_target_price,
    payment_value_da,
    price_after_discount,
    shop_price_per_gram,
)


class VersementPricingTests(unittest.TestCase):
    def test_target_price_generates_the_matching_discount_and_weight(self):
        shop_price = 33908.64
        target_price = 33000.0
        payment = 10000.0

        discount, weight = discount_for_target_price(
            shop_price, target_price, payment, available_weight=1.37
        )

        self.assertAlmostEqual(weight, payment / target_price, places=6)
        self.assertAlmostEqual(discount, 275.345454545455, places=6)
        self.assertAlmostEqual(
            price_after_discount(shop_price, payment, round(discount, 2)),
            target_price,
            places=1,
        )

    def test_target_price_never_exceeds_available_weight(self):
        discount, weight = discount_for_target_price(30000, 10000, 20000, 1.0)

        self.assertEqual(weight, 1.0)
        self.assertEqual(discount, 10000.0)

    def test_payment_value_does_not_double_count_stored_conversions(self):
        self.assertEqual(
            payment_value_da({"montant_da": 10000, "tpe_da": 500}),
            10500.0,
        )
        self.assertEqual(
            payment_value_da(
                {"montant_da": 28000, "montant_euro": 100, "taux_change_euro": 280}
            ),
            28000.0,
        )
        self.assertEqual(
            payment_value_da(
                {"montant_da": 25000, "or_casse_g": 1, "prix_gramme_jour_da": 25000}
            ),
            25000.0,
        )

    def test_shop_price_can_be_scoped_to_one_item(self):
        items = [
            {"item_id": 10, "item_status": "EN_COURS", "weight": 1, "selling_price": 30000},
            {"item_id": 20, "item_status": "EN_COURS", "weight": 2, "selling_price": 70000},
        ]

        self.assertAlmostEqual(shop_price_per_gram(items), 33333.3333333333)
        self.assertEqual(shop_price_per_gram(items, 20), 35000.0)

    def test_build_versement_payment_summary_avoids_double_counting(self):
        payments = [
            {
                "id": 1,
                "montant_da": 10000,
                "tpe_da": 0,
                "montant_euro": 0,
                "taux_change_euro": 0,
                "remise_da": 500,
                "poids_deduit_g": 0.3,
            },
            {
                "id": 2,
                "montant_da": 25000,
                "tpe_da": 2000,
                "montant_euro": 100,
                "taux_change_euro": 250,
                "remise_da": 0,
                "poids_deduit_g": 0.8,
            },
            {
                "id": 3,
                "montant_da": 15000,
                "tpe_da": 0,
                "montant_dollar": 50,
                "taux_change_dollar": 300,
                "remise_da": 0,
                "poids_deduit_g": 0.45,
            },
        ]

        summary = build_versement_payment_summary(payments)
        # Expected:
        # P1: cash 10000
        # P2: euro 100 * 250 = 25000 (pure cash is 0, since raw_da = 25000 is the converted euro), tpe 2000
        # P3: dollar 50 * 300 = 15000 (pure cash is 0, since raw_da = 15000 is converted dollar)
        # Total paid: 10000 + 2000 + 25000 + 15000 = 52000 DA (NOT 10000 + 25000 + 25000 + 15000 + 15000 = 92000)
        self.assertEqual(summary["cash_paid_da"], 10000.0)
        self.assertEqual(summary["tpe_paid_da"], 2000.0)
        self.assertEqual(summary["euro_paid"], 100.0)
        self.assertEqual(summary["euro_equivalent_da"], 25000.0)
        self.assertEqual(summary["dollar_paid"], 50.0)
        self.assertEqual(summary["dollar_equivalent_da"], 15000.0)
        self.assertEqual(summary["total_paid_da"], 52000.0)
        self.assertEqual(summary["total_remise_da"], 500.0)
        self.assertAlmostEqual(summary["deducted_weight_g"], 1.55)

    def test_scrap_gold_overpayment_surplus(self):
        # User scenario: 4g scrap gold paid = 92,000 DA, due amount was 84,178.43 DA
        items = [
            {"item_id": 1, "item_status": "EN_COURS", "item_type": "WEIGHT", "weight": 4.20892, "selling_price": 84178.43}
        ]
        payments = [
            {
                "id": 1,
                "montant_da": 92000,
                "or_casse_g": 4.0,
                "prix_gramme_jour_da": 23000,
                "remise_da": 0,
            }
        ]
        total_paid = sum(payment_value_da(p) for p in payments)
        self.assertEqual(total_paid, 92000.0)

        # Net due calculated from items and remises
        ppg = shop_price_per_gram(items, 1)
        gross_due = items[0]["weight"] * ppg
        net_due = gross_due - sum(float(p.get("remise_da") or 0) for p in payments)
        surplus = max(0.0, round(total_paid - net_due, 2))

        self.assertAlmostEqual(net_due, 84178.43, places=2)
        self.assertAlmostEqual(surplus, 7821.57, places=2)


if __name__ == "__main__":
    unittest.main()