import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tools.invoice_generator import (
    _clean_facture_number,
    generate_invoice_pdf,
)


class InvoicePdfGeneratorTests(unittest.TestCase):
    def test_clean_facture_number_removes_embedded_dates(self):
        self.assertEqual(_clean_facture_number("FAC-20260815-0001"), "FAC-0001")
        self.assertEqual(_clean_facture_number("FAC-20260717-12"), "FAC-0012")
        self.assertEqual(_clean_facture_number("FAC-0005"), "FAC-0005")
        self.assertEqual(_clean_facture_number("123"), "FAC-0123")
        self.assertEqual(_clean_facture_number("", sale_id=7), "FAC-0007")

    def test_generate_invoice_pdf_executes_cleanly_with_discount(self):
        items = [
            {
                "name": "Bague Or 18K",
                "barcode": "1001",
                "item_type": "WEIGHT",
                "cart_sold_weight": 2.5,
                "cart_line_total": 85000.0,
                "custom_note": "A vendre",
            }
        ]

        with patch("ui.tools.invoice_generator._render_html_document") as mock_render:
            path = generate_invoice_pdf(
                sale_id=42,
                client_name="Test Client",
                items=items,
                total_brut=85000.0,
                discount=5000.0,
                net=80000.0,
                cash_paid=80000.0,
                tpe_paid=0.0,
                or_casse_g=0.0,
                show_discount=True,
                facture_number="FAC-20260815-0042",
                open_pdf=False,
            )
            self.assertIn("FAC-0042", path)
            self.assertTrue(mock_render.called)
            html_called = mock_render.call_args[0][0]
            self.assertIn("N° FAC-0042", html_called)
            self.assertIn("- 5,000.00 DA", html_called)
            self.assertIn("NET À PAYER :", html_called)

    def test_generate_invoice_pdf_displays_versement_payments_and_discounts(self):
        items = [
            {
                "name": "Collier Or 18K",
                "barcode": "5002",
                "item_type": "WEIGHT",
                "cart_sold_weight": 10.0,
                "cart_line_total": 350000.0,
                "custom_note": "Commande spéciale",
            }
        ]

        payments_history = [
            {
                "payment_date": "2026-08-01 10:00",
                "cash_paid_da": 150000.0,
                "tpe_paid_da": 0.0,
                "remise_da": 2000.0,
                "product_name": "Collier Or 18K",
                "notes": "Acompte 1",
            },
            {
                "payment_date": "2026-08-10 14:30",
                "cash_paid_da": 195000.0,
                "tpe_paid_da": 0.0,
                "remise_da": 3000.0,
                "product_name": "Collier Or 18K",
                "notes": "Solde final",
            },
        ]

        with patch("ui.tools.invoice_generator._render_html_document") as mock_render:
            path = generate_invoice_pdf(
                sale_id=99,
                client_name="Karim Client",
                items=items,
                total_brut=350000.0,
                discount=5000.0,
                net=345000.0,
                cash_paid=345000.0,
                tpe_paid=0.0,
                or_casse_g=0.0,
                show_discount=True,
                facture_number="VRS-00099",
                open_pdf=False,
                payments_history=payments_history,
            )
            self.assertTrue(mock_render.called)
            html_called = mock_render.call_args[0][0]
            self.assertIn("VRS-00099", html_called)
            self.assertIn("Remise :", html_called)
            self.assertIn("- 5,000.00 DA", html_called)
            self.assertIn("Total Brut :", html_called)
            self.assertIn("NET À PAYER :", html_called)
    def test_generate_product_versement_receipt_with_gold_payment_and_negative_refund(self):
        from ui.tools.invoice_generator import ReceiptGenerator

        data = {
            "customer_name": "Sofiane",
            "phone": "0550000000",
            "sale_id": 25,
            "operation_number": "VRS-00025",
            "versement_operation_number": "VRS-00025",
            "total_weight": 3.0,
            "exact_paid_weight": 3.0,
            "remaining_weight": 0.0,
            "total_paid": 30000.0,
            "total_estimated_price_da": 60000.0,
            "items": [
                {
                    "item_name": "Bague Or (3.00g)",
                    "weight": 3.0,
                    "selling_price": 60000.0,
                    "remaining_weight": 0.0,
                    "paid_amount": 30000.0,
                    "barcode": "BG-01",
                }
            ],
            "versements": [
                {
                    "id": 1,
                    "payment_date": "2026-08-19",
                    "amount": 60000.0,
                    "weight": 3.0,  # acquired weight from product
                    "product_name": "Paiement Or Cassé (3.00g)",
                    "prix_gramme_apres_remise": 20000.0,
                },
                {
                    "id": 2,
                    "payment_date": "2026-08-19",
                    "amount": -30000.0,
                    "weight": 0.0,
                    "product_name": "Rendu surplus au client",
                    "prix_gramme_apres_remise": 0.0,
                }
            ]
        }

        with patch("ui.tools.invoice_generator._render_html_document") as mock_render:
            ReceiptGenerator.generate_product_versement_receipt(data, output_path="test.pdf")
            self.assertTrue(mock_render.called)
            html = mock_render.call_args[0][0]
            # Verify net consolidated payment of 30,000.00 DA appears
            self.assertIn("30,000.00 DA", html)
            # Verify negative row (-30,000.00 DA) was absorbed into preceding payment and does NOT appear
            self.assertNotIn("-30,000.00 DA", html)
            # Verify Montant dû is displayed with montant payé + remise (30,000.00 DA)
            self.assertIn("Montant dû :", html)
            self.assertNotIn("Montant facture :", html)
            # Verify acquired weight is 3.000 g and NOT 6.000 g
            self.assertIn("3.000 g", html)
            self.assertNotIn("6.000 g", html)

    def test_generate_invoice_pdf_renders_custom_invoice_note(self):
        items = [
            {
                "name": "Bague Diamant",
                "barcode": "8888",
                "item_type": "WEIGHT",
                "cart_sold_weight": 3.0,
                "cart_line_total": 120000.0,
            }
        ]

        with patch("ui.tools.invoice_generator._render_html_document") as mock_render:
            generate_invoice_pdf(
                sale_id=99,
                client_name="Madame Leila",
                items=items,
                total_brut=120000.0,
                discount=0.0,
                net=120000.0,
                cash_paid=120000.0,
                invoice_note="Garantie 2 ans avec certificat d'authenticité",
                open_pdf=False,
            )
            self.assertTrue(mock_render.called)
            html = mock_render.call_args[0][0]
            self.assertIn("Note / Observation :", html)
            self.assertIn("Garantie 2 ans avec certificat d&#x27;authenticité", html)


if __name__ == "__main__":
    unittest.main()
