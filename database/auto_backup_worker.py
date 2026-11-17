# database/auto_backup_worker.py

import os
import json
import time
import logging
from PySide6.QtCore import QThread

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

    def run(self):
        while self.running:
            try:
                from config import get_config_path, load_full_config
                if os.path.abspath(self.config_file) == os.path.abspath(str(get_config_path())):
                    config = load_full_config()
                else:
                    if not os.path.exists(self.config_file):
                        self._sleep_check(60)
                        continue
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                is_enabled = config.get("auto_backup_enabled", False)
                interval_mins = config.get("auto_backup_interval", 60)
                password = config.get("auto_backup_password", "")
                
                # 🟢 جلب القائمة الجديدة
                backup_paths = config.get("backup_paths", [])
                # دعم التوافق مع الإعدادات القديمة
                if not backup_paths and "backup_path" in config:
                    backup_paths = [config["backup_path"]]

                if not is_enabled or not backup_paths:
                    self._sleep_check(60)
                    continue

                # 🟢 تمرير القائمة للدالة
                self.data_manager.db._backup.create_multi_backup(backup_paths, password, is_auto=True)

                sleep_seconds = int(float(interval_mins) * 60)
                self._sleep_check(sleep_seconds)

            except Exception as e:
                logging.error(f"❌ Erreur critique dans le thread auto-backup: {e}")
                self._sleep_check(60)
                
    def _sleep_check(self, seconds):
        """دالة انتظار ذكية تسمح بإيقاف الـ Thread فوراً عند إغلاق البرنامج"""
        for _ in range(seconds):
            if not self.running:
                break
            time.sleep(1)

    def stop(self):
        """إيقاف الـ Thread بأمان عند إغلاق البرنامج"""
        self.running = False
        if self.isRunning():
            self.wait(5000)
