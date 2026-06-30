"""
connection.py
-------------
إدارة Connection Pool (mysql-connector) و SQLAlchemy Engine.
هذا الملف مسؤول حصرياً عن الاتصال بقاعدة البيانات وإنشاء الجلسات.
"""

import os
import logging
import urllib.parse
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

from .config import get_external_path

logger = logging.getLogger("JEWELLERY_SYS")


class ConnectionManager:
    """
    يدير Connection Pool و SQLAlchemy Engine.
    يُستخدم داخل كلاس Database فقط.
    """

    _pool  = None
    _engine = None

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self._init_pool()
        self._init_engine()

    # ── Pool ──────────────────────────────────────────────────────────────────
    def _init_pool(self) -> None:
        if ConnectionManager._pool is not None:
            return
        try:
            ConnectionManager._pool = pooling.MySQLConnectionPool(
                pool_name="jewel_pool",
                pool_size=10,
                pool_reset_session=True,
                use_pure=True,
                auth_plugin='mysql_native_password',
                **self.db_config,
            )
            logger.info("🚀 Connection Pool initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Connection Pool: {e}")
            raise

    # ── SQLAlchemy Engine ─────────────────────────────────────────────────────
    def _init_engine(self) -> None:
        if ConnectionManager._engine is not None:
            self.engine = ConnectionManager._engine
            return
        try:
            pw  = urllib.parse.quote_plus(self.db_config['password'])
            url = (
                f"mysql+mysqlconnector://{self.db_config['user']}:{pw}"
                f"@{self.db_config['host']}:{self.db_config['port']}"
                f"/{self.db_config['database']}"
            )
            self.engine = ConnectionManager._engine
        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            raise

    # ── Context Manager ───────────────────────────────────────────────────────
    @contextmanager
    def get_db_connection(self):
        """Context manager مع auto-commit / auto-rollback."""
        conn = None
        try:
            conn = ConnectionManager._pool.get_connection()
            yield conn
            conn.commit()
        except mysql.connector.Error as err:
            logger.error(f"Database error: {err}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_raw_connection(self):
        """اتصال خام — المستدعي مسؤول عن conn.close()."""
        return ConnectionManager._pool.get_connection()


# ── دوال مساعدة مستقلة ────────────────────────────────────────────────────────

def load_db_config() -> dict:
    """قراءة إعدادات الاتصال من ملف .env."""
    env_path = get_external_path(".env")
    load_dotenv(env_path)
    return {
        'host':     os.getenv('DB_HOST', 'localhost'),
        'user':     os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'JewelleryDB'),
        'port':     int(os.getenv('DB_PORT', 3306)),
    }


def ensure_database_exists(db_config: dict) -> None:
    """ينشئ قاعدة البيانات إن لم تكن موجودة."""
    conn_cfg           = {k: v for k, v in db_config.items() if k != 'database'}
    conn_cfg['use_pure']    = True
    conn_cfg['auth_plugin'] = 'mysql_native_password'
    db_name = db_config['database']
    try:
        with mysql.connector.connect(**conn_cfg) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {db_name} "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            logger.info(f"✅ Database '{db_name}' verified/created.")
    except mysql.connector.Error as err:
        logger.error(f"❌ Could not verify/create database: {err}")
        raise
