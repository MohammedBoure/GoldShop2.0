import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import config as app_config
from database.sales_manager import SalesManager
from database.versement import (
    build_versement_payment_summary,
    calculate_versement_financial_summary,
)
from ui.main_window.appearance import MainWindowAppearanceMixin
from ui.main_window.background import MainWindowBackgroundMixin
from ui.tools.invoice_generator import ReceiptGenerator
from ui.tools.print_functions import _thermal_versement_item_rows, _thermal_versement_summary_lines
from ui.widgets.reports.excel_journal_view import ExcelJournalView
from ui.widgets.settings.pdf_printer_tab import PdfPrinterTab
from ui.widgets.versements.versements_view import VersementsView


class VersementAndSettingsFixesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_payment_summary_bounds_repeated_remise_by_catalog_total(self):
        payments = [
            {"id": 1, "montant_da": 100000.0, "remise_da": 50000.0, "poids_deduit_g": 3.0},
            {"id": 2, "montant_da": 100000.0, "remise_da": 50000.0, "poids_deduit_g": 3.0},
            {"id": 3, "montant_da": 153750.0, "remise_da": 52720.95, "poids_deduit_g": 4.67},
        ]
        summary = build_versement_payment_summary(payments, items_brut_total=405000.0)
        self.assertAlmostEqual(summary["total_paid_da"], 353750.0)
        self.assertAlmostEqual(summary["total_remise_da"], 51250.0)
        self.assertAlmostEqual(summary["total_brut_da"], 405000.0)
        self.assertAlmostEqual(summary["net_to_pay_da"], 353750.0)

    def test_print_invoice_pdf_for_versement_never_inflates_item_prices(self):
        sale_payload = {
            "id": 68,
            "receipt_number": "VRS-00068",
            "client_name": "haddad ahmed nadji",
            "total_amount_da": 506470.95,
            "discount_da": 152720.95,
            "net_to_pay_da": 353750.0,
            "cash_paid_da": 353750.0,
            "tpe_paid_da": 0.0,
            "old_gold_weight_g": 0.0,
            "items": [
                {"name": "Gourmette", "item_type": "WEIGHT", "sold_weight_g": 2.26, "sold_quantity": 1, "unit_price_da": 85880.0, "total_price_da": 85880.0},
                {"name": "Bague", "item_type": "WEIGHT", "sold_weight_g": 0.87, "sold_quantity": 1, "unit_price_da": 33060.0, "total_price_da": 33060.0},
                {"name": "ras de coup", "item_type": "WEIGHT", "sold_weight_g": 6.43, "sold_quantity": 1, "unit_price_da": 244340.0, "total_price_da": 244340.0},
                {"name": "boucle", "item_type": "WEIGHT", "sold_weight_g": 1.11, "sold_quantity": 1, "unit_price_da": 42180.0, "total_price_da": 42180.0},
            ],
            "versement_payment_summary": {
                "total_paid_da": 353750.0,
                "total_remise_da": 51710.0,
                "total_brut_da": 405460.0,
                "net_to_pay_da": 353750.0,
            },
            "payments_history": [],
        }
        view = SimpleNamespace(_get_sale_or_versement_details=Mock(return_value=sale_payload))

        with patch("ui.tools.invoice_generator.generate_invoice_pdf") as mock_pdf:
            ExcelJournalView.print_invoice_pdf(view, "VRS_68", open_pdf=False, direct=False)

        self.assertTrue(mock_pdf.called)
        kwargs = mock_pdf.call_args.kwargs
        self.assertAlmostEqual(kwargs["total_brut"], 405460.0)
        self.assertAlmostEqual(kwargs["discount"], 51710.0)
        self.assertAlmostEqual(kwargs["net"], 353750.0)
        self.assertEqual([it["cart_line_total"] for it in kwargs["items"]], [85880.0, 33060.0, 244340.0, 42180.0])

    def test_enrich_versement_closure_overrides_stale_inflated_discount(self):
        payments = [
            {"id": 1, "montant_da": 353750.0, "tpe_da": 0.0, "montant_euro": 0.0, "taux_change_euro": 0.0,
             "montant_dollar": 0.0, "taux_change_dollar": 0.0, "or_casse_g": 0.0, "prix_gramme_jour_da": 0.0,
             "argent_casse_g": 0.0, "prix_gramme_argent_jour_da": 0.0, "poids_deduit_g": 10.67, "remise_da": 152720.95}
        ]
        source_items = [
            {"inventory_id": 1, "inventory_weight": 10.67, "inventory_quantity": 1, "selling_price": 405460.0, "reserved_quantity": 1, "item_type": "WEIGHT"}
        ]
        cursor = Mock()
        cursor.fetchall.side_effect = [payments, source_items]
        sale = {
            "id": 68,
            "receipt_number": "VRS-00068",
            "discount_da": 152720.95,
            "total_amount_da": 506470.95,
            "net_to_pay_da": 353750.0,
            "items": [{"inventory_id": 1, "total_price_da": 405460.0}],
        }
        sm = SalesManager(SimpleNamespace())
        sm._enrich_versement_closure_sale(cursor, sale)

        self.assertAlmostEqual(sale["total_amount_da"], 405460.0)
        self.assertAlmostEqual(sale["discount_da"], 51710.0)
        self.assertAlmostEqual(sale["net_to_pay_da"], 353750.0)

    def test_overpayment_calculates_surplus_and_renders_correctly_in_receipt_and_view(self):
        items = [{"item_id": 1, "item_status": "EN_COURS", "item_type": "WEIGHT", "weight": 1.11, "selling_price": 35000.0}]
        payments = [{"id": 1, "montant_da": 85000.0, "poids_deduit_g": 1.11, "remise_da": 0.0}]

        fin = calculate_versement_financial_summary(items, payments)
        self.assertAlmostEqual(fin["net_due_da"], 35000.0)
        self.assertAlmostEqual(fin["allocated_paid_da"], 35000.0)
        self.assertAlmostEqual(fin["surplus_da"], 50000.0)
        self.assertAlmostEqual(fin["remaining_due_da"], 0.0)
        self.assertAlmostEqual(fin["per_payment"][0]["allocated_da"], 35000.0)
        self.assertAlmostEqual(fin["per_payment"][0]["surplus_da"], 50000.0)

        data = {
            "customer_name": "chemouni nassima",
            "phone": "0550000000",
            "sale_id": 102,
            "operation_number": "VRS-00102",
            "versement_operation_number": "VRS-00102",
            "total_weight": 1.11,
            "exact_paid_weight": 1.11,
            "remaining_weight": 0.0,
            "total_paid": 85000.0,
            "total_estimated_price_da": 35000.0,
            "surplus_da": 50000.0,
            "items": [{
                "item_name": "chaine cartier (1.11g)",
                "weight": 1.11,
                "selling_price": 35000.0,
                "remaining_weight": 0.0,
                "paid_amount": 35000.0,
                "barcode": "CC-102",
            }],
            "versements": [{
                "id": 1,
                "payment_date": "2026-11-10",
                "amount": 85000.0,
                "allocated_da": 35000.0,
                "surplus_da": 50000.0,
                "weight": 1.11,
                "product_name": "chaine cartier (1.11g)",
                "prix_gramme_apres_remise": 31531.53,
            }],
        }
        with patch("ui.tools.invoice_generator._render_html_document") as mock_render:
            ReceiptGenerator.generate_product_versement_receipt(data, output_path="test_vrs_102.pdf")
        html = mock_render.call_args[0][0]
        self.assertIn("35,000.00 DA", html)
        self.assertIn("85,000.00 DA", html)
        self.assertIn("Surplus / Crédit Client :", html)
        self.assertIn("+ 50,000.00 DA", html)

        versement_row = {
            "id": 102,
            "client_name": "chemouni nassima",
            "phone": "0550000000",
            "status": "EN_COURS",
            "created_at": "2026-11-10",
            "total_weight_g": 1.11,
            "total_estimated_price_da": 35000.0,
            "total_paid_money_da": 85000.0,
            "total_tpe_da": 0.0,
            "total_dollar": 0.0,
            "total_remise_da": 0.0,
            "total_paid_weight_g": 1.11,
            "reste_poids_g": 0.0,
            "allocated_paid_da": 35000.0,
            "surplus_da": 50000.0,
            "items": [{
                "item_id": 1, "inventory_id": 10, "designation": "chaine cartier",
                "item_status": "EN_COURS", "item_type": "WEIGHT", "weight": 1.11,
                "display_weight": 1.11, "selling_price": 35000.0, "display_price": 35000.0,
            }],
            "payments": [{
                "id": 1, "payment_date": "2026-11-10", "montant_da": 85000.0, "tpe_da": 0.0,
                "montant_euro": 0.0, "taux_change_euro": 0.0, "montant_dollar": 0.0,
                "taux_change_dollar": 0.0, "or_casse_g": 0.0, "argent_casse_g": 0.0,
                "poids_deduit_g": 1.11, "remise_da": 0.0, "allocated_da": 35000.0, "surplus_da": 50000.0,
            }],
        }
        mock_manager = SimpleNamespace(
            versements=SimpleNamespace(get_versements=Mock(return_value=[versement_row])),
            db=SimpleNamespace(),
        )
        view = VersementsView(mock_manager)
        all_texts = []
        for r in range(view.table.rowCount()):
            for c in range(view.table.columnCount()):
                it = view.table.item(r, c)
                if it:
                    all_texts.append(it.text())
        joined = "\n".join(all_texts)
        self.assertIn("Affecté: 35,000 DA | Surplus/Crédit: +50,000 DA", joined)
        self.assertIn("SOLDÉ (Crédit +50,000 DA)", joined)

    def test_background_and_zoom_updates_never_wipe_shop_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "config.json"
            bak_path = Path(tmpdir) / "config.json.bak"
            original = {
                "shop_name": "BIJOUTERIE TEST",
                "shop_address": "Rue Kaoula Mokhtar Ayouf - Jijel",
                "shop_phone": "0549153606",
                "shop_rc": "18/00-2271630A21",
                "shop_nif": "19618010536811700000",
                "label_config": {"elements": {"static_text": {"text": "Bijouterie Test"}}},
                "pdf_config": {"printer_name": "MyPrinter"},
                "duckdns": {"enabled": True, "domain": "demo", "token": "tok"},
            }
            cfg_path.write_text(json.dumps(original), encoding="utf-8")

            with patch.object(app_config, "CONFIG_FILE", cfg_path):
                # Corrupt primary file while backup exists: background save must recover backup and NOT wipe settings
                bak_path.write_text(json.dumps(original), encoding="utf-8")
                cfg_path.write_text("{corrupt", encoding="utf-8")

                dummy_win = SimpleNamespace(config_file=str(cfg_path), zoom_scale=1.2)
                MainWindowBackgroundMixin._persist_duckdns_result(
                    dummy_win, {"status": "ok", "ip": "1.2.3.4", "message": "ok", "updated_at": "2026-11-17T10:00:00"}
                )
                MainWindowAppearanceMixin.save_zoom_setting(dummy_win)

                saved = json.loads(cfg_path.read_text(encoding="utf-8"))
                self.assertEqual(saved["shop_name"], "BIJOUTERIE TEST")
                self.assertEqual(saved["shop_rc"], "18/00-2271630A21")
                self.assertEqual(saved["shop_nif"], "19618010536811700000")
                self.assertEqual(saved["label_config"]["elements"]["static_text"]["text"], "Bijouterie Test")
                self.assertEqual(saved["duckdns"]["last_ip"], "1.2.3.4")
                self.assertEqual(saved["zoom_level"], 120)

    def test_pdf_printer_preview_uses_real_shop_header_from_config(self):
        cfg = {
            "shop_name": "BIJOUTERIE REAL SHOP",
            "shop_address": "Rue Kaoula Mokhtar Ayouf - Jijel",
            "shop_phone": "0549153606",
            "shop_rc": "18/00-2271630A21",
            "shop_nif": "19618010536811700000",
        }
        captured_html = []

        class _CaptureDoc:
            def setHtml(self, html):
                captured_html.append(html)
            def setDocumentMargin(self, *args):
                pass
            def setPageSize(self, *args):
                pass
            def drawContents(self, *args):
                pass

        with patch("ui.widgets.settings.pdf_printer_tab.QTextDocument", _CaptureDoc):
            tab = PdfPrinterTab(cfg, save_callback=lambda: None)
            self.assertTrue(captured_html)
            preview_html = captured_html[-1]
            self.assertIn("BIJOUTERIE REAL SHOP", preview_html)
            self.assertIn("Rue Kaoula Mokhtar Ayouf - Jijel", preview_html)
            self.assertIn("18/00-2271630A21", preview_html)
            self.assertIn("19618010536811700000", preview_html)
            self.assertNotIn("1234567", preview_html)
            self.assertNotIn("987654321", preview_html)
            tab.close()

    def test_print_invoice_thermal_builds_items_and_avoids_versement_inflation(self):
        sale_payload = {
            "id": 68,
            "receipt_number": "VRS-00068",
            "client_name": "haddad ahmed nadji",
            "total_amount_da": 506470.95,
            "discount_da": 152720.95,
            "net_to_pay_da": 353750.0,
            "cash_paid_da": 353750.0,
            "tpe_paid_da": 0.0,
            "old_gold_weight_g": 0.0,
            "created_at": "2026-11-10 10:00:00",
            "items": [
                {"name": "Gourmette", "item_type": "WEIGHT", "sold_weight_g": 2.26, "sold_quantity": 1, "unit_price_da": 85880.0, "total_price_da": 85880.0},
                {"name": "Bague", "item_type": "WEIGHT", "sold_weight_g": 0.87, "sold_quantity": 1, "unit_price_da": 33060.0, "total_price_da": 33060.0},
            ],
            "versement_payment_summary": {
                "total_paid_da": 353750.0,
                "total_remise_da": 51710.0,
                "total_brut_da": 405460.0,
                "net_to_pay_da": 353750.0,
            },
            "payments_history": [],
        }
        view = SimpleNamespace(
            _get_sale_or_versement_details=Mock(return_value=sale_payload),
            _get_thermal_printer_name=Mock(return_value="XP-80C"),
        )
        with patch("ui.tools.print_functions.print_thermal_facture") as mock_thermal, patch(
            "ui.widgets.reports.excel_journal_view.QMessageBox.information"
        ):
            ExcelJournalView.print_invoice_thermal(view, "VRS_68")
        self.assertTrue(mock_thermal.called)
        payload = mock_thermal.call_args[0][0]
        self.assertEqual(len(payload["items"]), 2)
        self.assertAlmostEqual(payload["total_weight"], 3.13)
        self.assertAlmostEqual(payload["net"], 353750.0)

    def test_thermal_versement_piece_and_surplus_summary(self):
        rows = _thermal_versement_item_rows({
            "items": [{"barcode": "P-1", "item_name": "Bracelet", "item_type": "PIECE", "remaining_weight": 0.0, "remaining_quantity": 2, "custom_note": ""}]
        })
        self.assertEqual(rows[0][2], "2 Pcs")

        lines = _thermal_versement_summary_lines({
            "total_estimated_price_da": 35000.0,
            "total_paid": 85000.0,
            "exact_paid_weight": 1.11,
            "remaining_weight": 0.0,
            "surplus_da": 50000.0,
        }, "DA")
        labels = dict(lines)
        self.assertEqual(labels["Montant du :"], "35,000.00 DA")
        self.assertEqual(labels["Surplus / Credit :"], "+50,000.00 DA")

    def test_user_manager_pbkdf2_and_legacy_sha256_migration(self):
        import hashlib
        from database.user_manager import UserManager

        legacy_hash = hashlib.sha256(b"secret123").hexdigest()
        cursor = Mock()
        cursor.fetchone.return_value = {
            "id": 5, "username": "cashier", "full_name": "Cashier",
            "role": "User", "is_active": 1, "permissions": "[]", "password_hash": legacy_hash,
        }
        conn = Mock()
        conn.cursor.return_value = cursor
        conn_ctx = Mock()
        conn_ctx.__enter__ = Mock(return_value=conn)
        conn_ctx.__exit__ = Mock(return_value=False)
        db = SimpleNamespace(get_db_connection=Mock(return_value=conn_ctx))

        um = UserManager(db)
        new_hash = um._hash_password("secret123")
        self.assertTrue(new_hash.startswith("pbkdf2:sha256:"))

        user = um.authenticate("cashier", "secret123")
        self.assertIsNotNone(user)
        self.assertNotIn("password_hash", user)
        self.assertTrue(any("UPDATE Users SET password_hash" in str(call.args[0]) for call in cursor.execute.call_args_list))


if __name__ == "__main__":
    unittest.main()
