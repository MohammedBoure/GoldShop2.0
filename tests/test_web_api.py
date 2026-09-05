# tests/test_web_api.py

import unittest
from unittest.mock import patch

import app


class TestWebApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.flask_app.test_client()
        cls.auth_headers = {"X-GoldShop-Password": "test-password"}

    def test_health_and_catalog(self):
        with patch("app.verify_web_password", return_value=True):
            # Test health endpoint
            res_health = self.client.get("/api/v1/health", headers=self.auth_headers)
            self.assertEqual(res_health.status_code, 200)
            data_health = res_health.get_json()
            self.assertTrue(data_health.get("success"))
            self.assertIn("status", data_health.get("data", {}))

            # Test catalog endpoint
            res_catalog = self.client.get("/api/v1", headers=self.auth_headers)
            self.assertEqual(res_catalog.status_code, 200)
            data_catalog = res_catalog.get_json()
            self.assertTrue(data_catalog.get("success"))
            doc = data_catalog.get("data", {}).get("documentation", {})
            self.assertIn("reports", doc)
            self.assertIn("versements", doc)
            self.assertIn("artisan_work", doc)
            self.assertIn("suppliers", doc)

    def test_excel_journal_api(self):
        """Test the Excel Journal View API (ui/widgets/reports/excel_journal_view.py)."""
        with patch("app.verify_web_password", return_value=True):
            # Test sellers list
            res_sellers = self.client.get("/api/v1/reports/journal/sellers", headers=self.auth_headers)
            self.assertEqual(res_sellers.status_code, 200)
            data_sellers = res_sellers.get_json()
            self.assertTrue(data_sellers.get("success"))
            self.assertIsInstance(data_sellers.get("data"), list)

            # Test journal data
            res_journal = self.client.get("/api/v1/reports/journal", headers=self.auth_headers)
            self.assertEqual(res_journal.status_code, 200)
            payload = res_journal.get_json()
            self.assertTrue(payload.get("success"))
            data = payload.get("data", {})
            self.assertIn("sessions", data)
            self.assertIn("grand_totals", data)
            self.assertIn("year", data)
            self.assertIn("month", data)

            gt = data.get("grand_totals", {})
            for key in ("ps_gold", "ps_silver", "recette", "oc_gold", "oc_silver", "tpe", "euro", "dollar"):
                self.assertIn(key, gt)

    def test_monthly_summary_api(self):
        """Test the Monthly Summary View API (ui/widgets/reports/monthly_summary_view.py)."""
        with patch("app.verify_web_password", return_value=True):
            res = self.client.get("/api/v1/reports/monthly-summary", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            payload = res.get_json()
            self.assertTrue(payload.get("success"))
            data = payload.get("data", {})
            self.assertIn("days", data)
            self.assertIn("totals", data)
            self.assertIn("month_name", data)

            totals = data.get("totals", {})
            for key in (
                "total_ps_gold", "total_ps_silver", "total_recette_da",
                "total_oc_gold", "total_oc_silver", "total_tpe_da",
                "total_euro", "total_dollar", "total_benefice"
            ):
                self.assertIn(key, totals)

            # Check day structure
            days = data.get("days", [])
            self.assertGreaterEqual(len(days), 28)
            first_day = days[0]
            self.assertIn("day_name", first_day)
            self.assertIn("date", first_day)
            self.assertIn("benefice", first_day)

    def test_versements_api(self):
        """Test the Versements View API (ui/widgets/versements/versements_view.py)."""
        with patch("app.verify_web_password", return_value=True):
            # Test list dossiers
            res = self.client.get("/api/v1/versements", headers=self.auth_headers)
            self.assertEqual(res.status_code, 200)
            payload = res.get_json()
            self.assertTrue(payload.get("success"))
            dossiers = payload.get("data", [])
            self.assertIsInstance(dossiers, list)

            if dossiers:
                first = dossiers[0]
                self.assertIn("code", first)
                self.assertIn("status", first)
                self.assertIn("total_weight_g", first)
                self.assertIn("total_paid_money_da", first)
                self.assertIn("reste_poids_g", first)
                self.assertIn("summary_text_1", first)
                self.assertIn("summary_text_2", first)
                self.assertIn("items", first)
                self.assertIn("payments", first)

                # Test detail endpoint
                first_id = first["id"]
                res_detail = self.client.get(f"/api/v1/versements/{first_id}", headers=self.auth_headers)
                self.assertEqual(res_detail.status_code, 200)
                detail_payload = res_detail.get_json()
                self.assertTrue(detail_payload.get("success"))

            # Test stats endpoint
            res_stats = self.client.get("/api/v1/versements/stats", headers=self.auth_headers)
            self.assertEqual(res_stats.status_code, 200)
            stats_payload = res_stats.get_json()
            self.assertTrue(stats_payload.get("success"))

    def test_artisan_work_api(self):
        """Test the Artisan Work View API (ui/widgets/artisan_work/artisan_work_view.py)."""
        with patch("app.verify_web_password", return_value=True):
            # Test production orders
            res_orders = self.client.get("/api/v1/artisan-work/orders", headers=self.auth_headers)
            self.assertEqual(res_orders.status_code, 200)
            payload = res_orders.get_json()
            self.assertTrue(payload.get("success"))
            orders = payload.get("data", [])
            self.assertIsInstance(orders, list)

            totals = payload.get("totals") or payload.get("meta", {}).get("totals", {})
            self.assertIn("total_cout_artisan_da", totals)
            self.assertIn("total_prix_client_da", totals)
            self.assertIn("total_diff_da", totals)

            if orders:
                first_order = orders[0]
                self.assertIn("numero", first_order)
                self.assertIn("status_label", first_order)
                self.assertIn("diff", first_order)

            # Test artisans list
            res_artisans = self.client.get("/api/v1/artisan-work/artisans", headers=self.auth_headers)
            self.assertEqual(res_artisans.status_code, 200)
            artisans_payload = res_artisans.get_json()
            self.assertTrue(artisans_payload.get("success"))
            self.assertIsInstance(artisans_payload.get("data"), list)

    def test_suppliers_api(self):
        """Test the French Suppliers Ledger View API (ui/widgets/suppliers/suppliers_view.py)."""
        with patch("app.verify_web_password", return_value=True):
            # Test suppliers list
            res_suppliers = self.client.get("/api/v1/suppliers", headers=self.auth_headers)
            self.assertEqual(res_suppliers.status_code, 200)
            payload = res_suppliers.get_json()
            self.assertTrue(payload.get("success"))
            suppliers = payload.get("data", [])
            self.assertIsInstance(suppliers, list)

            if suppliers:
                first_sup = suppliers[0]
                self.assertIn("poids_net", first_sup)
                self.assertIn("solde_da", first_sup)
                sup_id = first_sup["id"]

                # Test supplier detail
                res_detail = self.client.get(f"/api/v1/suppliers/{sup_id}", headers=self.auth_headers)
                self.assertEqual(res_detail.status_code, 200)
                detail_payload = res_detail.get_json()
                self.assertTrue(detail_payload.get("success"))
                self.assertIn("header_poids_text", detail_payload.get("data", {}))
                self.assertIn("header_solde_text", detail_payload.get("data", {}))

                # Test supplier Excel-style ledger
                res_ledger = self.client.get(f"/api/v1/suppliers/{sup_id}/ledger", headers=self.auth_headers)
                self.assertEqual(res_ledger.status_code, 200)
                ledger_payload = res_ledger.get_json()
                self.assertTrue(ledger_payload.get("success"))
                self.assertIn("total_poids_net", ledger_payload.get("meta", {}).get("totals", {}))
                self.assertIn("total_solde_da", ledger_payload.get("meta", {}).get("totals", {}))

                ops = ledger_payload.get("data", [])
                if ops:
                    first_op = ops[0]
                    self.assertIn("date", first_op)
                    self.assertIn("signed_weight_g", first_op)
                    self.assertIn("signed_amount_da", first_op)
                    self.assertIn("afacon", first_op)
                    self.assertIn("obs", first_op)
                    self.assertIn("is_red", first_op)
                    self.assertIn("is_blue", first_op)

    def test_web_ui_pages(self):
        """Test rendering of mobile web pages, templates, and static assets."""
        # 1. Test Dashboard Home Page
        res_home = self.client.get("/")
        self.assertEqual(res_home.status_code, 200)
        self.assertIn(b"GoldShop 2.0 Mobile", res_home.data)

        # 2. Test Excel Journal Page
        res_journal = self.client.get("/journal")
        self.assertEqual(res_journal.status_code, 200)
        self.assertIn(b"journalYearSelect", res_journal.data)
        self.assertIn(b"kpiJournalFc", res_journal.data)

        # 3. Test Monthly Summary Page
        res_monthly = self.client.get("/monthly-summary")
        self.assertEqual(res_monthly.status_code, 200)
        self.assertIn(b"monthlyMonthSelect", res_monthly.data)
        self.assertIn(b"kpiMonthlySales", res_monthly.data)

        # 4. Test Versements / Layaways Page
        res_versements = self.client.get("/versements")
        self.assertEqual(res_versements.status_code, 200)
        self.assertIn(b"versementsSearchInput", res_versements.data)
        self.assertIn(b"kpiVersementActiveCount", res_versements.data)

        # 5. Test Artisan Work Page
        res_artisan = self.client.get("/artisan-work")
        self.assertEqual(res_artisan.status_code, 200)
        self.assertIn(b"artisanSearchInput", res_artisan.data)
        self.assertIn(b"artisanDateFilter", res_artisan.data)

        # 6. Test Suppliers Page
        res_suppliers = self.client.get("/suppliers")
        self.assertEqual(res_suppliers.status_code, 200)
        self.assertIn(b"suppliersSearchInput", res_suppliers.data)
        self.assertIn(b"supplierLedgerContainer", res_suppliers.data)

        # 7. Test Static Assets
        res_css = self.client.get("/static/css/mobile.css")
        self.assertEqual(res_css.status_code, 200)
        self.assertIn(b"GoldShop 2.0", res_css.data)

        res_js_app = self.client.get("/static/js/app.js")
        self.assertEqual(res_js_app.status_code, 200)
        self.assertIn(b"GoldShopApp", res_js_app.data)

        # 8. Test Auth Status
        res_auth_status = self.client.get("/api/v1/auth/status")
        self.assertEqual(res_auth_status.status_code, 200)
        auth_status_data = res_auth_status.get_json()
        self.assertTrue(auth_status_data.get("success"))
        self.assertIn("password_required", auth_status_data.get("data", {}))


if __name__ == "__main__":
    unittest.main()

