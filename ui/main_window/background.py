import inspect
import json
import logging
import os
import threading

from PySide6.QtCore import QTimer


RUNTIME_COMMAND_POLL_INTERVAL_MS = 2500


class MainWindowBackgroundMixin:
    """Background workers and periodically scheduled integrations."""

    def _start_auto_backup(self):
        if getattr(self, "auto_backup_thread", None):
            return
        from database.auto_backup_worker import AutoBackupWorker

        parameters = inspect.signature(AutoBackupWorker.__init__).parameters
        kwargs = {"parent": self} if "parent" in parameters else {}
        self.auto_backup_thread = AutoBackupWorker(self.data_manager, **kwargs)
        self.auto_backup_thread.start()

    def setup_duckdns_timer(self):
        from services.duckdns import normalize_duckdns_config

        config = self._load_json_config()
        duckdns_config = normalize_duckdns_config(config.get("duckdns"))
        if not duckdns_config.get("enabled") or not duckdns_config.get("domain") or not duckdns_config.get("token"):
            if hasattr(self, "duckdns_timer") and self.duckdns_timer.isActive():
                self.duckdns_timer.stop()
            return

        interval_ms = int(max(5.0, float(duckdns_config.get("interval_minutes", 30.0))) * 60 * 1000)
        if not hasattr(self, "duckdns_timer"):
            self.duckdns_timer = QTimer(self)
            self.duckdns_timer.timeout.connect(self._run_duckdns_update)

        if self.duckdns_timer.interval() != interval_ms or not self.duckdns_timer.isActive():
            self.duckdns_timer.start(interval_ms)

        QTimer.singleShot(1000, self._run_duckdns_update)

    def _run_duckdns_update(self):
        if getattr(self, "_duckdns_update_running", False):
            return

        from services.duckdns import normalize_duckdns_config

        duckdns_config = normalize_duckdns_config(self._load_json_config().get("duckdns"))
        if not duckdns_config.get("enabled") or not duckdns_config.get("domain") or not duckdns_config.get("token"):
            return

        self._duckdns_update_running = True
        thread = threading.Thread(
            target=self._duckdns_update_background,
            args=(duckdns_config,),
            name="DuckDNSUpdater",
            daemon=True,
        )
        thread.start()

    def _duckdns_update_background(self, duckdns_config):
        from services.duckdns import update_duckdns_record

        try:
            result = update_duckdns_record(duckdns_config)
            self._persist_duckdns_result(result)
            if result.get("success"):
                logging.info("DuckDNS updated successfully to %s", result.get("ip") or "-")
            else:
                logging.warning("DuckDNS update failed: %s", result.get("message") or result.get("status"))
        finally:
            self._duckdns_update_running = False

    def _load_json_config(self):
        if not os.path.exists(self.config_file):
            return {}
        try:
            with open(self.config_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}

    def _persist_duckdns_result(self, result):
        from services.duckdns import normalize_duckdns_config

        config = self._load_json_config()
        duckdns_config = normalize_duckdns_config(config.get("duckdns"))
        duckdns_config["last_status"] = result.get("status", "error")
        duckdns_config["last_message"] = result.get("message", "")
        duckdns_config["last_ip"] = result.get("ip") or duckdns_config.get("last_ip", "")
        duckdns_config["last_update_at"] = result.get("updated_at", "")
        config["duckdns"] = duckdns_config
        try:
            from config import save_full_config
            save_full_config(config)
        except Exception as exc:
            logging.warning("Could not persist DuckDNS update result: %s", exc)

    def setup_runtime_command_watcher(self):
        if hasattr(self, "runtime_command_timer"):
            return

        try:
            from services.runtime_control import remember_current_force_logout_command

            remember_current_force_logout_command(self.data_manager.db)
        except Exception as exc:
            logging.warning("Could not initialize runtime command watcher: %s", exc)

        self._runtime_command_check_running = False
        self.runtime_command_timer = QTimer(self)
        self.runtime_command_timer.timeout.connect(self._run_runtime_command_check)
        self.runtime_command_timer.start(RUNTIME_COMMAND_POLL_INTERVAL_MS)

    def _run_runtime_command_check(self):
        if getattr(self, "_runtime_command_check_running", False):
            return
        self._runtime_command_check_running = True
        thread = threading.Thread(
            target=self._runtime_command_check_background,
            name="RuntimeCommandWatcher",
            daemon=True,
        )
        thread.start()

    def _runtime_command_check_background(self):
        try:
            from services.runtime_control import (
                execute_force_logout_command,
                load_latest_force_logout_command,
                should_handle_force_logout_command,
            )

            command = load_latest_force_logout_command(self.data_manager.db)
            if should_handle_force_logout_command(command):
                logging.warning("Runtime force logout command received; closing this device.")
                execute_force_logout_command(command)
        except Exception as exc:
            logging.warning("Runtime command watcher failed: %s", exc)
        finally:
            self._runtime_command_check_running = False

    def _stop_background_workers(self):
        if hasattr(self, "runtime_command_timer"):
            self.runtime_command_timer.stop()
        if hasattr(self, "duckdns_timer"):
            self.duckdns_timer.stop()
        if hasattr(self, "auto_backup_thread") and self.auto_backup_thread.isRunning():
            self.auto_backup_thread.stop()
