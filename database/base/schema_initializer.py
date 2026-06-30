"""
schema_initializer.py
---------------------
يُشغّل جميع استعلامات CREATE / ALTER / INSERT / VIEW / INDEX
لتهيئة قاعدة البيانات، ويُنشئ المستخدم الافتراضي Admin.
"""

import json
import hashlib
import logging
import mysql.connector

from .tables import (
    REFERENCE_TABLE_QUERIES,
    PARTNER_TABLE_QUERIES,
    TREASURY_SESSION_TABLE_QUERIES,
    INVENTORY_SALES_TABLE_QUERIES,
    PAYMENT_TABLE_QUERIES,
    FINANCIAL_TABLE_QUERIES,
    SERVICES_LOG_TABLE_QUERIES,
    DAILY_JOURNAL_TABLE_QUERIES,
    ACHAT_OC_TABLE_QUERIES,
    RH_TABLE_QUERIES,
    COFFRE_MAGASIN_TABLE_QUERIES,
    ARTISAN_WORK_TABLE_QUERIES,
)
from .views_indexes import VIEW_QUERIES, INDEX_QUERIES

logger = logging.getLogger("JEWELLERY_SYS")

ALL_SCHEMA_QUERIES = (
    REFERENCE_TABLE_QUERIES
    + PARTNER_TABLE_QUERIES
    + TREASURY_SESSION_TABLE_QUERIES
    + INVENTORY_SALES_TABLE_QUERIES
    + PAYMENT_TABLE_QUERIES
    + FINANCIAL_TABLE_QUERIES
    + SERVICES_LOG_TABLE_QUERIES
    + DAILY_JOURNAL_TABLE_QUERIES
    + ACHAT_OC_TABLE_QUERIES
    + RH_TABLE_QUERIES
    + COFFRE_MAGASIN_TABLE_QUERIES
    + ARTISAN_WORK_TABLE_QUERIES
)

SCHEMA_FINGERPRINT_KEY = "schema_fingerprint"



class SchemaInitializer:
    """ينفّذ تهيئة المخطط الكاملة على اتصال معطى."""

    def __init__(self, connection_manager):
        self._cm = connection_manager

    def initialize(self, force: bool = False) -> None:
        try:
            fingerprint = self._schema_fingerprint()
            with self._cm.get_db_connection() as conn:
                cursor = conn.cursor()
                if not force and self._is_schema_current(cursor, fingerprint):
                    self._create_default_admin(cursor)
                    logger.info("Schema already current; skipped startup checks.")
                    return
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                try:

                    self._run_queries(cursor, ALL_SCHEMA_QUERIES, "Schema")
                    self._run_queries(cursor, VIEW_QUERIES, "Views")
                    self._run_queries(cursor, INDEX_QUERIES, "Indexes", ignore_errors=True)

                    self._create_default_admin(cursor)
                    self._store_schema_fingerprint(cursor, fingerprint)

                finally:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                logger.info("✅ Schema initialized successfully.")

        except mysql.connector.Error as err:
            logger.error(f"❌ Failed to initialize schema: {err}")

    @staticmethod
    def _schema_fingerprint() -> str:
        payload = "\n".join(
            ALL_SCHEMA_QUERIES
            + VIEW_QUERIES
            + INDEX_QUERIES
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _is_schema_current(self, cursor, fingerprint: str) -> bool:
        self._ensure_metadata_table(cursor)
        cursor.execute(
            "SELECT meta_value FROM AppMetadata WHERE meta_key = %s",
            (SCHEMA_FINGERPRINT_KEY,),
        )
        row = cursor.fetchone()
        return bool(row and row[0] == fingerprint)

    @staticmethod
    def _ensure_metadata_table(cursor) -> None:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS AppMetadata (
                meta_key VARCHAR(100) PRIMARY KEY,
                meta_value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

    @staticmethod
    def _store_schema_fingerprint(cursor, fingerprint: str) -> None:
        cursor.execute(
            """
            INSERT INTO AppMetadata (meta_key, meta_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                meta_value = VALUES(meta_value),
                updated_at = CURRENT_TIMESTAMP
            """,
            (SCHEMA_FINGERPRINT_KEY, fingerprint),
        )

    @staticmethod
    def _run_queries(cursor, queries: list, label: str, ignore_errors: bool = False) -> None:
        logger.info(f"Running {label} queries ({len(queries)} total)…")
        for query in queries:
            try:
                cursor.execute(query)
                while cursor.nextset():
                    pass
            except mysql.connector.Error as err:
                if ignore_errors:
                    continue
                logger.warning(f"{label} warning (safe to ignore for ALTER): {err}")

    def _create_default_admin(self, cursor) -> None:
        try:
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute(
                """
                INSERT INTO Users (username, password_hash, full_name, role, permissions)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    role = VALUES(role),
                    permissions = VALUES(permissions)
                """,
                ("admin", password_hash, "Administrator", "Admin", "{}") # 👈 تمت إضافة هذه القيم هنا
            )
        except Exception as e:
            logger.error(f"Error creating default admin: {e}")
