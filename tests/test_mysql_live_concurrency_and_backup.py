import os
import tempfile
import threading
import unittest
from contextlib import contextmanager
from urllib.parse import quote_plus

import mysql.connector
from mysql.connector import pooling
from sqlalchemy import create_engine

from database.base.backup_manager import BackupManager
from database.base.connection import load_db_config
from database.base.schema_initializer import SchemaInitializer
from database.cash_box_manager import CashBoxManager
from database.sales_manager import SalesManager
from database.versement.versement_manager import VersementManager


class _IsolatedMySQLHarness:
    """Isolated MySQL pool + SQLAlchemy engine pointing exclusively at a disposable test schema."""

    def __init__(self, db_config: dict):
        self.db_config = dict(db_config)
        self._pool = pooling.MySQLConnectionPool(
            pool_name=f"test_pool_{os.getpid()}",
            pool_size=12,
            pool_reset_session=True,
            use_pure=True,
            auth_plugin="mysql_native_password",
            **self.db_config,
        )
        user = quote_plus(str(self.db_config.get("user", "")))
        pw = quote_plus(str(self.db_config.get("password", "")))
        url = (
            f"mysql+mysqlconnector://{user}:{pw}"
            f"@{self.db_config['host']}:{self.db_config['port']}"
            f"/{self.db_config['database']}"
        )
        self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)

    @contextmanager
    def get_db_connection(self):
        conn = None
        try:
            conn = self._pool.get_connection()
            yield conn
            conn.commit()
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_raw_connection(self):
        return self._pool.get_connection()

    def dispose(self):
        self.engine.dispose()


class TestLiveMySQLConcurrencyAndBackup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_cfg = load_db_config()
        cls.test_db_name = f"goldshop_isolated_test_{os.getpid()}"
        cls.admin_cfg = {k: v for k, v in base_cfg.items() if k != "database"}
        cls.admin_cfg["use_pure"] = True
        cls.admin_cfg["auth_plugin"] = "mysql_native_password"

        try:
            with mysql.connector.connect(**cls.admin_cfg) as conn:
                cur = conn.cursor()
                cur.execute(f"DROP DATABASE IF EXISTS `{cls.test_db_name}`")
                cur.execute(
                    f"CREATE DATABASE `{cls.test_db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        except mysql.connector.Error as exc:
            raise unittest.SkipTest(f"MySQL server unavailable for live integration test: {exc}")

        test_cfg = dict(base_cfg)
        test_cfg["database"] = cls.test_db_name
        cls.db = _IsolatedMySQLHarness(test_cfg)
        SchemaInitializer(cls.db).initialize(force=True)

        # Ensure baseline reference rows exist for foreign keys
        with cls.db.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT IGNORE INTO Users (id, username, password_hash, full_name, role) "
                "VALUES (2, 'cashier2', 'hash2', 'Cashier Two', 'Sales')"
            )
            cur.execute(
                "INSERT IGNORE INTO Clients (id, name, phone) VALUES (1, 'Client Passage', '0000')"
            )
            cur.execute("INSERT IGNORE INTO Categories (id, name) VALUES (1, 'Bague')")
            cur.execute(
                "INSERT IGNORE INTO MetalTypes (id, name, purity_value, metal_category) "
                "VALUES (1, 'Or 18K', 750.0, 'GOLD')"
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "db"):
            cls.db.dispose()
        if hasattr(cls, "admin_cfg"):
            try:
                with mysql.connector.connect(**cls.admin_cfg) as conn:
                    cur = conn.cursor()
                    cur.execute(f"DROP DATABASE IF EXISTS `{cls.test_db_name}`")
            except Exception:
                pass

    def test_concurrent_cashiers_create_sales_sessions_and_versement_closure(self):
        cash_box = CashBoxManager(self.db)
        sales_mgr = SalesManager(self.db)
        versement_mgr = VersementManager(self.db)

        # 1. Concurrent session creation must produce exactly 1 DailySession for today
        session_results = []
        barrier = threading.Barrier(6)

        def _open_session():
            barrier.wait()
            session_results.append(cash_box.get_or_create_today_session(user_id=2))

        threads = [threading.Thread(target=_open_session) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        session_ids = {s["id"] for s in session_results if s}
        self.assertEqual(len(session_results), 6)
        self.assertEqual(len(session_ids), 1)
        journee_id = next(iter(session_ids))

        # 2. Create 6 available inventory items and sell them concurrently across 6 threads
        inv_ids = []
        with self.db.get_db_connection() as conn:
            cur = conn.cursor()
            for idx in range(6):
                cur.execute(
                    "INSERT INTO Inventory (barcode, name, category_id, metal_type_id, item_type, weight, remaining_weight, quantity, remaining_quantity, selling_price, status) "
                    "VALUES (%s, %s, 1, 1, 'WEIGHT', 5.000, 5.000, 1, 1, 50000.00, 'Available')",
                    (f"CONC-{idx}", f"Bague Conc {idx}"),
                )
                inv_ids.append(cur.lastrowid)

        sale_results = []
        sale_barrier = threading.Barrier(6)

        def _make_sale(inv_id):
            sale_barrier.wait()
            res = sales_mgr.create_sale(
                journee_id=journee_id,
                client_id=1,
                user_id=2,
                cart_items=[
                    {
                        "id": inv_id,
                        "name": "Bague Conc",
                        "item_type": "WEIGHT",
                        "cart_sold_weight": 5.0,
                        "cart_sold_qty": 1,
                        "cart_unit_price": 50000.0,
                        "cart_line_total": 50000.0,
                    }
                ],
                total_amount=50000.0,
                discount=0.0,
                net_to_pay=50000.0,
                cash_paid=50000.0,
                tpe_paid=0.0,
            )
            sale_results.append(res)

        sale_threads = [threading.Thread(target=_make_sale, args=(iid,)) for iid in inv_ids]
        for t in sale_threads:
            t.start()
        for t in sale_threads:
            t.join(timeout=15)

        self.assertTrue(all(r.get("success") for r in sale_results), sale_results)
        receipts = {r["receipt_number"] for r in sale_results}
        self.assertEqual(len(receipts), 6)

        # 3. Verify update_sale_notes syncs both Sales.notes and SaleItems.custom_note (non-shadowed)
        first_sale_id = sale_results[0]["sale_id"]
        self.assertTrue(sales_mgr.update_sale_notes(first_sale_id, "  Note multi-caisse  "))
        with self.db.get_db_connection() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT notes FROM Sales WHERE id = %s", (first_sale_id,))
            self.assertEqual(cur.fetchone()["notes"], "Note multi-caisse")
            cur.execute("SELECT custom_note FROM SaleItems WHERE sale_id = %s", (first_sale_id,))
            self.assertEqual(cur.fetchone()["custom_note"], "Note multi-caisse")

        # 4. Concurrent sale of the SAME item -> only 1 succeeds, 3 fail cleanly
        with self.db.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO Inventory (barcode, name, category_id, metal_type_id, item_type, weight, remaining_weight, quantity, remaining_quantity, selling_price, status) "
                "VALUES ('SINGLE-1', 'Unique Ring', 1, 1, 'WEIGHT', 3.000, 3.000, 1, 1, 30000.00, 'Available')"
            )
            single_inv_id = cur.lastrowid

        race_results = []
        race_barrier = threading.Barrier(4)

        def _race_single():
            race_barrier.wait()
            race_results.append(
                sales_mgr.create_sale(
                    journee_id=journee_id,
                    client_id=1,
                    user_id=2,
                    cart_items=[
                        {
                            "id": single_inv_id,
                            "name": "Unique Ring",
                            "item_type": "WEIGHT",
                            "cart_sold_weight": 3.0,
                            "cart_sold_qty": 1,
                            "cart_unit_price": 30000.0,
                            "cart_line_total": 30000.0,
                        }
                    ],
                    total_amount=30000.0,
                    discount=0.0,
                    net_to_pay=30000.0,
                    cash_paid=30000.0,
                    tpe_paid=0.0,
                )
            )

        race_threads = [threading.Thread(target=_race_single) for _ in range(4)]
        for t in race_threads:
            t.start()
        for t in race_threads:
            t.join(timeout=15)

        self.assertEqual(sum(1 for r in race_results if r.get("success")), 1)
        self.assertEqual(sum(1 for r in race_results if not r.get("success")), 3)

        # 5. Concurrent cloture_versement with explicit user_id=2
        with self.db.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO Inventory (barcode, name, category_id, metal_type_id, item_type, weight, remaining_weight, quantity, remaining_quantity, selling_price, status) "
                "VALUES ('VRS-RING', 'VRS Ring', 1, 1, 'WEIGHT', 4.000, 4.000, 1, 1, 40000.00, 'Available')"
            )
            vrs_inv_id = cur.lastrowid

        created = versement_mgr.create_versement(
            client_id=1,
            journee_id=journee_id,
            type_versement="PRODUITS",
            items_list=[{"inventory_id": vrs_inv_id, "designation": "VRS Ring", "reserved_quantity": 1}],
            montant_da=40000.0,
            or_casse_g=0.0,
            prix_gramme_jour_da=0.0,
            poids_deduit_g=4.0,
        )
        self.assertTrue(created.get("success"))
        v_id = created["versement_id"]

        cloture_results = []
        v_barrier = threading.Barrier(4)

        def _close_v():
            v_barrier.wait()
            cloture_results.append(versement_mgr.cloture_versement(v_id, journee_id=journee_id, user_id=2))

        v_threads = [threading.Thread(target=_close_v) for _ in range(4)]
        for t in v_threads:
            t.start()
        for t in v_threads:
            t.join(timeout=15)

        self.assertTrue(all(cloture_results))
        with self.db.get_db_connection() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT user_id, status FROM Sales WHERE receipt_number = %s", (f"VRS-{v_id:05d}",))
            v_sales = cur.fetchall()
            self.assertEqual(len(v_sales), 1)
            self.assertEqual(v_sales[0]["user_id"], 2)
            cur.execute("SELECT remaining_weight, status FROM Inventory WHERE id = %s", (vrs_inv_id,))
            inv_after = cur.fetchone()
            self.assertEqual(float(inv_after["remaining_weight"]), 0.0)
            self.assertEqual(inv_after["status"], "Sold")

    def test_live_mysql_csv_and_excel_backup_restore_and_rollback(self):
        backup_mgr = BackupManager(self.db)

        with self.db.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("INSERT IGNORE INTO Categories (id, name) VALUES (99, 'Collier Original')")

        with tempfile.TemporaryDirectory() as tmp:
            csv_zip = os.path.join(tmp, "mysql_backup_csv.zip")
            xlsx_zip = os.path.join(tmp, "mysql_backup_xlsx.zip")

            ok_csv, msg_csv = backup_mgr.backup_database_csv(csv_zip)
            self.assertTrue(ok_csv, msg_csv)
            ok_xlsx, msg_xlsx = backup_mgr.export_to_excel(xlsx_zip)
            self.assertTrue(ok_xlsx, msg_xlsx)

            # Mutate category name in live test DB
            with self.db.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE Categories SET name = 'Collier Mutated' WHERE id = 99")

            # Restore from CSV ZIP and verify original value returns
            ok_res_csv, msg_res_csv = backup_mgr.restore_database_csv(csv_zip)
            self.assertTrue(ok_res_csv, msg_res_csv)
            with self.db.get_db_connection() as conn:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT name FROM Categories WHERE id = 99")
                self.assertEqual(cur.fetchone()["name"], "Collier Original")

            # Mutate again and restore from Excel ZIP
            with self.db.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE Categories SET name = 'Collier Mutated 2' WHERE id = 99")

            ok_res_xlsx, msg_res_xlsx = backup_mgr.restore_from_excel(xlsx_zip)
            self.assertTrue(ok_res_xlsx, msg_res_xlsx)
            with self.db.get_db_connection() as conn:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT name FROM Categories WHERE id = 99")
                self.assertEqual(cur.fetchone()["name"], "Collier Original")

            # Corrupt restore must roll back cleanly on real MySQL and preserve Categories=99
            bad_zip = os.path.join(tmp, "corrupt_restore.zip")
            import zipfile
            with zipfile.ZipFile(bad_zip, "w") as zf:
                zf.writestr("Categories.csv", "id,name\n99,ShouldRollback\n")
                # Force SQL error on Users (NULL in NOT NULL username)
                zf.writestr("Users.csv", "id,username,password_hash\n1,<NULL>,abc\n")

            ok_bad, _ = backup_mgr.restore_database_csv(bad_zip)
            self.assertFalse(ok_bad)
            with self.db.get_db_connection() as conn:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT name FROM Categories WHERE id = 99")
                self.assertEqual(cur.fetchone()["name"], "Collier Original")


if __name__ == "__main__":
    unittest.main()
