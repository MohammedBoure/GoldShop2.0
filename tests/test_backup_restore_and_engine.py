import builtins
import io
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PySide6.QtWidgets import QApplication

from database.auto_backup_worker import AutoBackupWorker
from database.base.backup_manager import (
    BackupManager,
    _prune_old_auto_backups,
    normalize_max_backups,
    safe_extract_zip,
    validate_sql_identifier,
    write_zip_from_dir,
)
from database.base.connection import ConnectionManager
from ui.widgets.settings.settings_tab import SettingsTab


class _FakeRestoreCursor:
    """Stateful fake MySQL cursor to verify atomic restore transaction & rollback."""

    def __init__(self, state: dict, fail_insert_table: str | None = None):
        self._state = state
        self._fail_insert_table = fail_insert_table
        self._results = []
        self.closed = False

    def execute(self, sql, params=None):
        norm = " ".join(str(sql).split())
        upper = norm.upper()
        if upper == "SHOW TABLES":
            self._results = [(t,) for t in self._state["tables"].keys()]
        elif upper.startswith("SHOW COLUMNS FROM"):
            tbl = norm.split("`")[1]
            self._results = [(c,) for c in self._state["columns"][tbl]]
        elif upper.startswith("SELECT COLUMN_NAME, EXTRA FROM INFORMATION_SCHEMA.COLUMNS"):
            self._results = []
        elif upper.startswith("SET FOREIGN_KEY_CHECKS"):
            val = int(norm.split("=")[1].strip(" ;"))
            self._state["fk_checks_history"].append(val)
        elif upper.startswith("DELETE FROM"):
            tbl = norm.split("`")[1]
            self._state["working"][tbl] = []
        else:
            self._results = []

    def executemany(self, sql, data):
        tbl = sql.split("`")[1]
        if self._fail_insert_table and tbl == self._fail_insert_table:
            raise RuntimeError(f"Simulated insert failure on {tbl}")
        self._state["working"][tbl].extend(list(data))

    def fetchall(self):
        return list(self._results)

    def close(self):
        self.closed = True


class _FakeRestoreConnection:
    def __init__(self, state: dict, fail_insert_table: str | None = None):
        self._state = state
        self._fail_insert_table = fail_insert_table
        self.in_transaction = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def start_transaction(self):
        self.in_transaction = True
        self._state["working"] = {k: list(v) for k, v in self._state["tables"].items()}

    def cursor(self):
        return _FakeRestoreCursor(self._state, self._fail_insert_table)

    def commit(self):
        self.committed = True
        self._state["tables"] = {k: list(v) for k, v in self._state["working"].items()}

    def rollback(self):
        self.rolled_back = True
        self._state["working"] = {k: list(v) for k, v in self._state["tables"].items()}

    def close(self):
        self.closed = True


class TestConnectionAndBackupEngine(unittest.TestCase):
    def test_init_engine_creates_real_sqlalchemy_engine(self):
        old_pool = ConnectionManager._pool
        old_engine = ConnectionManager._engine
        try:
            ConnectionManager._pool = MagicMock()
            ConnectionManager._engine = None

            cm = ConnectionManager(
                {
                    "host": "localhost",
                    "port": 3306,
                    "user": "app_user",
                    "password": "p@ss:word/1",
                    "database": "gold_test",
                }
            )
            self.assertIsNotNone(cm.engine)
            self.assertTrue(cm.engine.pool._pre_ping)
            self.assertEqual(cm.engine.url.database, "gold_test")
        finally:
            if ConnectionManager._engine is not None:
                ConnectionManager._engine.dispose()
            ConnectionManager._pool = old_pool
            ConnectionManager._engine = old_engine

    def test_get_db_connection_rolls_back_on_non_mysql_error_and_closes_even_if_disconnected(self):
        old_pool = ConnectionManager._pool
        old_engine = ConnectionManager._engine
        try:
            mock_conn = MagicMock()
            mock_conn.is_connected.return_value = False
            mock_pool = MagicMock()
            mock_pool.get_connection.return_value = mock_conn

            ConnectionManager._pool = mock_pool
            ConnectionManager._engine = MagicMock()

            cm = ConnectionManager(
                {"host": "localhost", "port": 3306, "user": "u", "password": "p", "database": "db"}
            )

            with self.assertRaises(ValueError):
                with cm.get_db_connection():
                    raise ValueError("boom")

            mock_conn.rollback.assert_called_once()
            mock_conn.commit.assert_not_called()
            mock_conn.close.assert_called_once()
        finally:
            ConnectionManager._pool = old_pool
            ConnectionManager._engine = old_engine

    def test_validate_sql_identifier_rejects_injection(self):
        self.assertEqual(validate_sql_identifier("SaleItems_2", "table"), "SaleItems_2")
        for bad in ("", "Users; DROP TABLE Users", "Users`", "a-b", "tab le", "../Users"):
            with self.assertRaises(ValueError):
                validate_sql_identifier(bad, "table")

    def test_safe_extract_zip_blocks_zip_slip(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "evil.zip")
            extract_dir = os.path.join(tmp, "out")
            os.makedirs(extract_dir)

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("../escape.csv", "id\n1\n")
            with open(zip_path, "wb") as f:
                f.write(buf.getvalue())

            with self.assertRaises(ValueError):
                safe_extract_zip(zip_path, extract_dir)

    def _make_state_and_manager(self, fail_insert_table=None):
        state = {
            "tables": {
                "Categories": [(1, "Bague")],
                "Clients": [(10, "Ali")],
            },
            "working": {},
            "columns": {
                "Categories": ["id", "name"],
                "Clients": ["id", "name"],
            },
            "fk_checks_history": [],
        }
        fake_conn = _FakeRestoreConnection(state, fail_insert_table=fail_insert_table)
        fake_db = MagicMock()
        fake_db.get_raw_connection.return_value = fake_conn
        return state, fake_conn, BackupManager(fake_db)

    def test_restore_csv_rolls_back_atomically_on_insert_failure(self):
        state, fake_conn, mgr = self._make_state_and_manager(fail_insert_table="Clients")

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "backup.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("Categories.csv", "id,name\n2,Collier\n")
                zf.writestr("Clients.csv", "id,name\n20,Karim\n")

            ok, msg = mgr.restore_database_csv(zip_path)

        self.assertFalse(ok)
        self.assertIn("Restore failed", msg)
        self.assertTrue(fake_conn.rolled_back)
        self.assertFalse(fake_conn.committed)
        self.assertTrue(fake_conn.closed)
        self.assertEqual(state["tables"]["Categories"], [(1, "Bague")])
        self.assertEqual(state["tables"]["Clients"], [(10, "Ali")])
        self.assertEqual(state["fk_checks_history"], [0, 1])

    def test_restore_excel_rolls_back_atomically_on_insert_failure(self):
        state, fake_conn, mgr = self._make_state_and_manager(fail_insert_table="Clients")

        with tempfile.TemporaryDirectory() as tmp:
            cat_xlsx = os.path.join(tmp, "Categories.xlsx")
            cli_xlsx = os.path.join(tmp, "Clients.xlsx")
            pd.DataFrame([{"id": 2, "name": "Collier"}]).to_excel(cat_xlsx, index=False)
            pd.DataFrame([{"id": 20, "name": "Karim"}]).to_excel(cli_xlsx, index=False)

            zip_path = os.path.join(tmp, "backup_xlsx.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(cat_xlsx, "Categories.xlsx")
                zf.write(cli_xlsx, "Clients.xlsx")

            ok, msg = mgr.restore_from_excel(zip_path)

        self.assertFalse(ok)
        self.assertTrue(fake_conn.rolled_back)
        self.assertFalse(fake_conn.committed)
        self.assertEqual(state["tables"]["Categories"], [(1, "Bague")])
        self.assertEqual(state["tables"]["Clients"], [(10, "Ali")])
        self.assertEqual(state["fk_checks_history"], [0, 1])

    def test_restore_rejects_unknown_table_or_column_before_delete(self):
        state, fake_conn, mgr = self._make_state_and_manager()

        with tempfile.TemporaryDirectory() as tmp:
            bad_table_zip = os.path.join(tmp, "bad_table.zip")
            with zipfile.ZipFile(bad_table_zip, "w") as zf:
                zf.writestr("EvilTable.csv", "id\n1\n")

            ok1, _ = mgr.restore_database_csv(bad_table_zip)
            self.assertFalse(ok1)
            self.assertFalse(fake_conn.in_transaction)

            bad_col_zip = os.path.join(tmp, "bad_col.zip")
            with zipfile.ZipFile(bad_col_zip, "w") as zf:
                zf.writestr("Categories.csv", "id,unknown_col\n2,x\n")

            ok2, _ = mgr.restore_database_csv(bad_col_zip)
            self.assertFalse(ok2)
            self.assertFalse(fake_conn.in_transaction)
            self.assertEqual(state["tables"]["Categories"], [(1, "Bague")])

    def test_encrypted_backup_requires_pyzipper_and_preserves_old_auto_backup_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "src")
            os.makedirs(src_dir)
            Path(src_dir, "Categories.csv").write_text("id,name\n1,Bague\n", encoding="utf-8")

            auto_dir = os.path.join(tmp, "Auto_Backups")
            os.makedirs(auto_dir)
            old_backup = os.path.join(auto_dir, "AutoBackup_20260101_000000.zip")
            Path(old_backup).write_bytes(b"existing-backup")

            mgr = BackupManager(MagicMock())
            real_import = builtins.__import__

            def fake_import(name, *args, **kwargs):
                if name == "pyzipper":
                    raise ImportError("pyzipper missing")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=fake_import):
                with self.assertRaises(RuntimeError):
                    write_zip_from_dir(src_dir, os.path.join(tmp, "enc.zip"), password="secret")

                with patch.object(mgr, "_export_tables_to_dir", return_value=["Categories"]):
                    ok_auto = mgr.create_auto_backup(tmp, password="secret")
                    ok_multi, _ = mgr.create_multi_backup([tmp], password="secret", is_auto=True)

            self.assertFalse(ok_auto)
            self.assertFalse(ok_multi)
            # Previous backup must remain intact when new backup fails
            self.assertTrue(os.path.exists(old_backup))

    def test_encrypted_backup_succeeds_with_pyzipper(self):
        import pyzipper

        with tempfile.TemporaryDirectory() as tmp:
            src_dir = os.path.join(tmp, "src")
            os.makedirs(src_dir)
            Path(src_dir, "Categories.csv").write_text("id,name\n1,Bague\n", encoding="utf-8")

            out_zip = os.path.join(tmp, "encrypted.zip")
            write_zip_from_dir(src_dir, out_zip, password="MyStrongPassword123")

            with pyzipper.AESZipFile(out_zip, "r") as zf:
                zf.setpassword(b"MyStrongPassword123")
                content = zf.read("Categories.csv").decode("utf-8")
            self.assertIn("Bague", content)

    def test_auto_backup_retention_keeps_n_newest_copies_and_deletes_oldest(self):
        with tempfile.TemporaryDirectory() as tmp:
            dir1 = os.path.join(tmp, "dest1")
            dir2 = os.path.join(tmp, "dest2")
            auto1 = os.path.join(dir1, "Auto_Backups")
            os.makedirs(auto1)

            # Seed 3 older backups with distinct mtimes
            old_names = [
                "AutoBackup_20260101_010000.zip",
                "AutoBackup_20260102_010000.zip",
                "AutoBackup_20260103_010000.zip",
            ]
            base_ts = time.time() - 1000
            for idx, name in enumerate(old_names):
                p = os.path.join(auto1, name)
                Path(p).write_bytes(b"zip")
                os.utime(p, (base_ts + idx * 10, base_ts + idx * 10))

            mgr = BackupManager(MagicMock())

            def fake_export(temp_dir, fmt="csv", format_datetimes=True):
                Path(temp_dir, "Categories.csv").write_text("id,name\n1,Bague\n", encoding="utf-8")
                return ["Categories"]

            with patch.object(mgr, "_export_tables_to_dir", side_effect=fake_export):
                ok1, _ = mgr.create_multi_backup([dir1, dir2], is_auto=True, max_backups=3)
                ok2, _ = mgr.create_multi_backup([dir1, dir2], is_auto=True, max_backups=3)

            self.assertTrue(ok1)
            self.assertTrue(ok2)

            files1 = sorted(os.listdir(auto1))
            files2 = sorted(os.listdir(os.path.join(dir2, "Auto_Backups")))
            self.assertEqual(len(files1), 3)
            self.assertEqual(len(files2), 2)
            # Two oldest seeded backups must have been pruned, third oldest + 2 new kept
            self.assertNotIn("AutoBackup_20260101_010000.zip", files1)
            self.assertNotIn("AutoBackup_20260102_010000.zip", files1)
            self.assertIn("AutoBackup_20260103_010000.zip", files1)

    def test_auto_backup_worker_passes_configured_max_copies_and_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "config.json")
            Path(cfg_path).write_text(
                json.dumps(
                    {
                        "auto_backup_enabled": True,
                        "auto_backup_interval": 15.0,
                        "auto_backup_max_copies": 7,
                        "auto_backup_password": "",
                        "backup_paths": [tmp],
                    }
                ),
                encoding="utf-8",
            )
            fake_backup = MagicMock()
            fake_dm = SimpleNamespace(db=SimpleNamespace(_backup=fake_backup))
            worker = AutoBackupWorker(fake_dm, config_file=cfg_path)

            sleep_secs = worker.run_once()

            self.assertEqual(sleep_secs, 900)
            fake_backup.create_multi_backup.assert_called_once_with(
                [tmp], "", is_auto=True, max_backups=7
            )

    def test_settings_tab_exposes_and_syncs_auto_backup_max_copies(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "config.json")
            Path(cfg_path).write_text(
                json.dumps(
                    {
                        "auto_backup_enabled": True,
                        "auto_backup_interval": 30.0,
                        "auto_backup_max_copies": 8,
                    }
                ),
                encoding="utf-8",
            )
            with patch("ui.widgets.settings.settings_tab.CONFIG_FILE", cfg_path):
                tab = SettingsTab(SimpleNamespace(db=MagicMock()))
                self.assertEqual(tab.spin_max_copies.value(), 8)
                self.assertTrue(tab.spin_max_copies.isEnabled())

                tab.spin_max_copies.setValue(12)
                tab.chk_auto_backup.setChecked(False)
                self.assertFalse(tab.spin_max_copies.isEnabled())

                self.assertTrue(tab._sync_config_from_controls())
                self.assertEqual(tab.config["auto_backup_max_copies"], 12)
                self.assertEqual(normalize_max_backups(0), 1)
                tab.close()


if __name__ == "__main__":
    unittest.main()
