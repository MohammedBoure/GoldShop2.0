"""
database.py
-----------
الكلاس الرئيسي Database — Singleton يجمع كل المكوّنات:
  ┌─ ConnectionManager   → Pool + SQLAlchemy Engine
  ├─ SchemaInitializer   → تهيئة الجداول والـ Views
  ├─ BackupManager       → نسخ احتياطي / استعادة
  └─ ArchiveViewManager  → وضع عرض الأرشيف

جميع الملفات الأخرى (sales_manager, inventory_manager…) تستورد
هذا الكلاس بنفس الطريقة القديمة:
    from database.database import Database
أو عبر الاختصار الموجود في __init__.py:
    from database import Database
"""

import logging

import mysql.connector

from .config import (
    get_external_path,
    TABLE_IMPORT_ORDER,
    ARCHIVE_VIEW_FLAG_FILE,
    HARD_RESET_PASSWORD,
    CustomJSONEncoder,
)
from .connection import ConnectionManager, load_db_config, ensure_database_exists
from .schema_initializer import SchemaInitializer
from .backup_manager import BackupManager
from .archive_view_manager import ArchiveViewManager

logger = logging.getLogger("JEWELLERY_SYS")


class Database:
    """
    Singleton رئيسي للتطبيق.
    يُعيد نفس الكائن في كل مكان يُستدعى فيه Database().
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # تجنّب إعادة التهيئة عند استدعاء Database() أكثر من مرة
        if hasattr(self, '_initialized'):
            return

        db_config = load_db_config()
        ensure_database_exists(db_config)

        # ── المكوّنات الداخلية ──────────────────────────────────────────────
        self._conn_mgr   = ConnectionManager(db_config)
        self._schema     = SchemaInitializer(self._conn_mgr)
        self._backup     = BackupManager(self._conn_mgr)
        self._archive    = ArchiveViewManager(self._conn_mgr)

        # كشف مباشر لـ engine (يحتاجه بعض الـ managers القديمة مثل reports_manager)
        self.engine = self._conn_mgr.engine

        self._schema.initialize()
        self._initialized = True

    # ==========================================================
    # واجهة الاتصال (تُعاد كما كانت في base.py الأصلي)
    # ==========================================================
    def get_db_connection(self):
        """Context manager يُعيد اتصالاً من الـ Pool مع auto-commit/rollback."""
        return self._conn_mgr.get_db_connection()

    def get_raw_connection(self):
        """اتصال خام من الـ Pool (المستدعي مسؤول عن conn.close())."""
        return self._conn_mgr.get_raw_connection()

    # ==========================================================
    # واجهة النسخ الاحتياطي
    # ==========================================================
    def backup_database_csv(self, output_zip_path='backup_csv.zip'):
        return self._backup.backup_database_csv(output_zip_path)

    def restore_database_csv(self, input_zip_path):
        return self._backup.restore_database_csv(input_zip_path)

    def export_and_purge_tables(self, output_zip_path, days_to_keep=365):
        return self._backup.export_and_purge_tables(output_zip_path, days_to_keep)

    def restore_table_from_file(self, table_name, file_path):
        return self._backup.restore_table_from_file(table_name, file_path)

    # aliases للتوافق مع الكود القديم
    def export_all_tables_to_csv_zip(self, output_zip_path='backup_csv.zip'):
        return self._backup.backup_database_csv(output_zip_path)

    def restore_from_archive_zip_destructive(self, input_zip_path, tables_to_restore=None):
        return self._backup.restore_database_csv(input_zip_path)

    # ==========================================================
    # واجهة الأرشيف
    # ==========================================================
    def activate_archive_view(self, input_zip_path):
        return self._archive.activate_archive_view(input_zip_path)

    def deactivate_archive_view(self):
        return self._archive.deactivate_archive_view()

    def get_table(self, table_name):
        return self._archive.get_table(table_name)

    def is_archive_view_mode(self):
        return self._archive.is_archive_view_mode()

    def get_archive_view_tables(self):
        return self._archive.get_archive_view_tables()

    def get_archive_view_status(self):
        return self._archive.get_archive_view_status()

    def get_available_archives(self):
        return self._archive.get_available_archives()

    # ==========================================================
    # إعادة ضبط قاعدة البيانات
    # ==========================================================
    def hard_reset_database(self, password: str) -> tuple:
        if password != HARD_RESET_PASSWORD:
            return False, "كلمة المرور غير صحيحة. تم إلغاء العملية."
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

                cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
                for (table_name, _) in cursor.fetchall():
                    cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")

                cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
                for (view_name, _) in cursor.fetchall():
                    cursor.execute(f"DROP VIEW IF EXISTS `{view_name}`")

                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                conn.commit()

            self._schema.initialize(force=True)
            return True, "تم مسح جميع البيانات وإعادة تهيئة قاعدة البيانات بنجاح."
        except Exception as e:
            return False, f"حدث خطأ أثناء مسح البيانات: {e}"

    def truncate_all_tables(self, password: str) -> tuple:
        return self.hard_reset_database(password)
