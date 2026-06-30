"""
archive_view_manager.py
-----------------------
إدارة "وضع عرض الأرشيف": تحميل نسخة ZIP قديمة في جداول مؤقتة
وتوجيه الاستعلامات نحوها بدلاً من الجداول الحية.
"""

import os
import shutil
import logging
import zipfile

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
        temp_dir = 'temp_view_archive'

        try:
            pd = _load_pandas()
            if self.is_archive_mode:
                return False, "Archive mode already active."

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            conn = self._db.get_raw_connection()
            cursor = conn.cursor()

            csv_files = [f for f in os.listdir(temp_dir) if f.endswith('.csv')]
            if not csv_files:
                return False, "No CSV files found."

            self.table_map = {}

            for csv_file in csv_files:
                original_table = os.path.splitext(csv_file)[0]
                archive_table = f"{self.ARCHIVE_PREFIX}{original_table}"

                cursor.execute(f"DROP TABLE IF EXISTS {archive_table}")
                cursor.execute(f"CREATE TABLE {archive_table} LIKE {original_table}")

                csv_path = os.path.join(temp_dir, csv_file)
                df = pd.read_csv(csv_path)
                df.columns = df.columns.astype(str)
                df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
                df = df.where(pd.notnull(df), None)

                if not df.empty:
                    cols = ",".join([f"`{col}`" for col in df.columns])
                    placeholders = ",".join(["%s"] * len(df.columns))
                    sql = f"INSERT INTO {archive_table} ({cols}) VALUES ({placeholders})"
                    data = [tuple(x) for x in df.to_numpy()]
                    cursor.executemany(sql, data)

                self.table_map[original_table] = archive_table

            conn.commit()
            conn.close()

            self.is_archive_mode = True
            with open(ARCHIVE_VIEW_FLAG_FILE, 'w') as f:
                f.write('1')
            return True, "Archive View Activated (Read-Only)."

        except Exception as e:
            self.deactivate_archive_view()
            return False, f"Failed to load archive: {e}"
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # ─── Deactivate ───────────────────────────────────────────────────────────
    def deactivate_archive_view(self):
        """يحذف جداول ARCHIVE_VIEW_* ويُعيد النظام إلى الوضع الطبيعي."""
        try:
            conn = self._db.get_raw_connection()
            cursor = conn.cursor()
            cursor.execute(f"SHOW TABLES LIKE '{self.ARCHIVE_PREFIX}%'")
            tables = cursor.fetchall()
            for (tbl,) in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {tbl}")
            conn.commit()
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
