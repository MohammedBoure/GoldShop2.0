"""
connection.py
-------------
إدارة Connection Pool (mysql-connector) و SQLAlchemy Engine.
هذا الملف مسؤول حصرياً عن الاتصال بقاعدة البيانات وإنشاء الجلسات.
"""

import os
import re
import logging
import threading
import urllib.parse
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv
from sqlalchemy import create_engine

from .config import get_external_path

logger = logging.getLogger("JEWELLERY_SYS")
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class ConnectionManager:
    """
    يدير Connection Pool و SQLAlchemy Engine.
    يُستخدم داخل كلاس Database فقط.
    """

    _pool = None
    _engine = None
    _init_lock = threading.Lock()

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self._init_pool()
        self._init_engine()

    # ── Pool ──────────────────────────────────────────────────────────────────
    def _init_pool(self) -> None:
        if ConnectionManager._pool is not None:
            return
        with ConnectionManager._init_lock:
            if ConnectionManager._pool is not None:
                return
            try:
                ConnectionManager._pool = pooling.MySQLConnectionPool(
                    pool_name="jewel_pool",
                    pool_size=15,
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
        with ConnectionManager._init_lock:
            if ConnectionManager._engine is None:
                try:
                    user = urllib.parse.quote_plus(str(self.db_config.get('user', '')))
                    pw = urllib.parse.quote_plus(str(self.db_config.get('password', '')))
                    url = (
                        f"mysql+mysqlconnector://{user}:{pw}"
                        f"@{self.db_config['host']}:{self.db_config['port']}"
                        f"/{self.db_config['database']}"
                    )
                    ConnectionManager._engine = create_engine(
                        url,
                        pool_pre_ping=True,
                        pool_recycle=1800,
                    )
                    logger.info("🚀 SQLAlchemy Engine initialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to create SQLAlchemy engine: {e}")
                    raise
            self.engine = ConnectionManager._engine

    # ── Context Manager ───────────────────────────────────────────────────────
    @contextmanager
    def get_db_connection(self):
        """Context manager مع auto-commit / auto-rollback."""
        conn = None
        try:
            conn = ConnectionManager._pool.get_connection()
            yield conn
            conn.commit()
        except Exception as err:
            logger.error(f"Database error: {err}")
            if conn is not None:
                try:
                    conn.rollback()
                except Exception as rb_err:
                    logger.warning(f"Rollback failed: {rb_err}")
            raise
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

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
    db_name = str(db_config['database']).strip()
    if not _DB_NAME_RE.match(db_name):
        raise ValueError(f"Invalid database name: {db_name!r}")
    try:
        with mysql.connector.connect(**conn_cfg) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            logger.info(f"✅ Database '{db_name}' verified/created.")
    except mysql.connector.Error as err:
        logger.error(f"❌ Could not verify/create database: {err}")
        raise
