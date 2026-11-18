"""
archive_view_manager.py
-----------------------
إدارة "وضع عرض الأرشيف": تحميل نسخة ZIP قديمة في جداول مؤقتة
وتوجيه الاستعلامات نحوها بدلاً من الجداول الحية.
"""

import os
import shutil
import logging
import tempfile

from .backup_manager import (
    _get_table_columns_info,
    _validate_and_filter_columns,
    safe_extract_zip,
    validate_sql_identifier,
)
from .config import ARCHIVE_VIEW_FLAG_FILE


def _load_pandas():
    import pandas as pd
    return pd


class ArchiveViewManager:
    """
    يُحمّل سجلات مؤرشفة من ملف ZIP إلى جداول ARCHIVE_VIEW_*
    في قاعدة البيانات الحالية، مما يُتيح قراءتها عبر نفس الـ managers
    دون تعديل البيانات الحية.
    """

    ARCHIVE_PREFIX = "ARCHIVE_VIEW_"

    def __init__(self, db_connection):
        self._db = db_connection
        self.table_map: dict = {}
        self.is_archive_mode: bool = False

    # ─── Activate ─────────────────────────────────────────────────────────────
    def activate_archive_view(self, input_zip_path: str):
        """
        يستخرج CSV من ZIP ويُنشئ جداول ARCHIVE_VIEW_* مؤقتة.
        يُعيد (True, message) أو (False, error_message).
        """
        temp_dir = tempfile.mkdtemp(prefix="goldshop_archive_view_")
        conn = None
        cursor = None

        try:
            pd = _load_pandas()
            if self.is_archive_mode:
                return False, "Archive mode already active."

            safe_extract_zip(input_zip_path, temp_dir)

            conn = self._db.get_raw_connection()
            cursor = conn.cursor()

            csv_files = [f for f in sorted(os.listdir(temp_dir)) if f.endswith(".csv")]
            if not csv_files:
                return False, "No CSV files found."

            cursor.execute("SHOW TABLES")
            existing_map = {
                row[0].lower(): validate_sql_identifier(row[0], "table")
                for row in cursor.fetchall()
            }

            self.table_map = {}

            for csv_file in csv_files:
                raw_table = os.path.splitext(csv_file)[0]
                validate_sql_identifier(raw_table, "table")
                original_table = existing_map.get(raw_table.lower())
                if original_table is None:
                    raise ValueError(f"Unknown table in archive: {raw_table!r}")
                archive_table = validate_sql_identifier(
                    f"{self.ARCHIVE_PREFIX}{original_table}", "table"
                )

                cursor.execute(f"DROP TABLE IF EXISTS `{archive_table}`")
                cursor.execute(f"CREATE TABLE `{archive_table}` LIKE `{original_table}`")

                csv_path = os.path.join(temp_dir, csv_file)
                df = pd.read_csv(csv_path)
                df.columns = df.columns.astype(str)
                df = df.loc[:, ~df.columns.str.contains("^Unnamed", na=False)]
                df = df.where(pd.notnull(df), None)

                db_cols, generated_cols = _get_table_columns_info(cursor, original_table)
                valid_cols = _validate_and_filter_columns(
                    df.columns, db_cols, generated_cols, original_table
                )

                if not df.empty and valid_cols:
                    df = df[valid_cols]
                    cols = ",".join([f"`{col}`" for col in valid_cols])
                    placeholders = ",".join(["%s"] * len(valid_cols))
                    sql = f"INSERT INTO `{archive_table}` ({cols}) VALUES ({placeholders})"
                    data = [tuple(x) for x in df.to_numpy()]
                    cursor.executemany(sql, data)

                self.table_map[original_table] = archive_table

            conn.commit()

            self.is_archive_mode = True
            with open(ARCHIVE_VIEW_FLAG_FILE, "w", encoding="utf-8") as f:
                f.write("1")
            return True, "Archive View Activated (Read-Only)."

        except Exception as e:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.deactivate_archive_view()
            return False, f"Failed to load archive: {e}"
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ─── Deactivate ───────────────────────────────────────────────────────────
    def deactivate_archive_view(self):
        """يحذف جداول ARCHIVE_VIEW_* ويُعيد النظام إلى الوضع الطبيعي."""
        conn = None
        cursor = None
        try:
            conn = self._db.get_raw_connection()
            cursor = conn.cursor()
            cursor.execute(f"SHOW TABLES LIKE '{self.ARCHIVE_PREFIX}%'")
            tables = cursor.fetchall()
            for (tbl,) in tables:
                safe_tbl = validate_sql_identifier(tbl, "table")
                cursor.execute(f"DROP TABLE IF EXISTS `{safe_tbl}`")
            conn.commit()
        except Exception as exc:
            logging.warning(f"Archive view deactivation error: {exc}")
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        self.table_map = {}
        self.is_archive_mode = False
        if os.path.exists(ARCHIVE_VIEW_FLAG_FILE):
            os.remove(ARCHIVE_VIEW_FLAG_FILE)
        return True, "Archive closed."

    # ─── Table Routing ────────────────────────────────────────────────────────
    def get_table(self, table_name: str) -> str:
        """
        يُعيد اسم الجدول الفعلي للاستعلام:
        - في وضع الأرشيف → ARCHIVE_VIEW_<table_name>
        - في الوضع الطبيعي → table_name بدون تغيير
        """
        if self.is_archive_mode:
            return self.table_map.get(table_name, table_name)
        return table_name

    # ─── Status Helpers ───────────────────────────────────────────────────────
    def is_archive_view_mode(self) -> bool:
        return os.path.exists(ARCHIVE_VIEW_FLAG_FILE)

    def get_archive_view_tables(self) -> dict:
        return self.table_map.copy()

    def get_archive_view_status(self) -> dict:
        return {"active": self.is_archive_view_mode(), "file": None}

    def get_available_archives(self) -> list:
        return []
