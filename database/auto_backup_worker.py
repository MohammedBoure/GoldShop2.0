# database/auto_backup_worker.py

import os
import json
import logging
import threading
from PySide6.QtCore import QThread

from database.base.backup_manager import (
    DEFAULT_AUTO_BACKUP_MAX_COPIES,
    normalize_max_backups,
)


class AutoBackupWorker(QThread):
    """
    مؤقت يعمل في الخلفية (Background Thread) للتحقق من إعدادات الحفظ التلقائي
    وتنفيذ النسخ الاحتياطي دون تجميد واجهة المستخدم.
    """

    def __init__(self, data_manager, config_file=None, parent=None):
        super().__init__(parent)
        if config_file is None:
            from config import get_config_path

            config_file = str(get_config_path())
        self.data_manager = data_manager
        self.config_file = config_file
        self.running = True
        self._wake_event = threading.Event()

    def _load_config(self) -> dict | None:
        from config import get_config_path, load_full_config

        if os.path.abspath(self.config_file) == os.path.abspath(str(get_config_path())):
            return load_full_config()
        if not os.path.exists(self.config_file):
            return None
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_once(self) -> int:
        """تنفيذ دورة فحص/نسخ واحدة وإرجاع مدة الانتظار بالثواني."""
        config = self._load_config()
        if not isinstance(config, dict):
            return 60

        is_enabled = bool(config.get("auto_backup_enabled", False))
        interval_mins = config.get("auto_backup_interval", 60)
        password = config.get("auto_backup_password", "")
        max_copies = normalize_max_backups(
            config.get("auto_backup_max_copies", DEFAULT_AUTO_BACKUP_MAX_COPIES),
            default=DEFAULT_AUTO_BACKUP_MAX_COPIES,
        )

        backup_paths = config.get("backup_paths", [])
        if not backup_paths and "backup_path" in config:
            backup_paths = [config["backup_path"]]

        if not is_enabled or not backup_paths:
            return 60

        self.data_manager.db._backup.create_multi_backup(
            backup_paths,
            password,
            is_auto=True,
            max_backups=max_copies,
        )

        try:
            sleep_seconds = max(1, int(float(interval_mins) * 60))
        except (TypeError, ValueError):
            sleep_seconds = 3600
        return sleep_seconds

    def run(self):
        while self.running:
            try:
                sleep_seconds = self.run_once()
                self._sleep_check(sleep_seconds)
            except Exception as e:
                logging.error(f"❌ Erreur critique dans le thread auto-backup: {e}")
                self._sleep_check(60)

    def wake(self):
        """إيقاظ الـ Thread فوراً عند تعديل إعدادات النسخ الاحتياطي."""
        self._wake_event.set()

    def _sleep_check(self, seconds):
        """انتظار قابل للإيقاظ الفوري عند الإيقاف أو تحديث الإعدادات."""
        self._wake_event.clear()
        self._wake_event.wait(timeout=max(1, int(seconds)))

    def stop(self):
        """إيقاف الـ Thread بأمان عند إغلاق البرنامج"""
        self.running = False
        self._wake_event.set()
        if self.isRunning():
            self.wait(5000)
