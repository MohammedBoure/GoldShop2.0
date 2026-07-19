import unittest

from database.versement_pricing import (
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


if __name__ == "__main__":
    unittest.main()