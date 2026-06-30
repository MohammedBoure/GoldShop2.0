"""
config.py
---------
إعدادات النظام العامة: الترميز، السجلات، الثوابت، والمشفر المخصص.
يُستورد من جميع الملفات الأخرى.
"""

import sys
import codecs
import logging
import os
import json
import time
from datetime import datetime, date
from decimal import Decimal
from logging.handlers import RotatingFileHandler


# ─── Force UTF-8 Encoding ────────────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, TypeError):
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception as e:
        print(f"Warning: Could not force console to UTF-8. {e}")


# ─── Logging Setup ────────────────────────────────────────────────────────────
def get_external_path(filename: str) -> str:
    """يعيد مسار الملف سواء كان التطبيق مجمّعاً (PyInstaller) أو لا."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.abspath("."), filename)


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """Keep logging alive if Windows blocks log rotation while another process holds the file."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rollover_blocked_until = 0.0

    def shouldRollover(self, record):
        if self._rollover_blocked_until and time.monotonic() < self._rollover_blocked_until:
            return False
        return super().shouldRollover(record)

    def doRollover(self):
        try:
            super().doRollover()
            self._rollover_blocked_until = 0.0
        except PermissionError:
            self._rollover_blocked_until = time.monotonic() + 60.0
            if self.stream is None:
                self.stream = self._open()
            try:
                self.stream.seek(0, os.SEEK_END)
            except OSError:
                pass


root_logger = logging.getLogger()
if root_logger.hasHandlers():
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

log_file = get_external_path("app.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        WindowsSafeRotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    ]
)
for noisy_logger in ("urllib3", "charset_normalizer", "werkzeug"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger("JEWELLERY_SYS")


# ─── Constants ────────────────────────────────────────────────────────────────
TABLE_IMPORT_ORDER = [
    'Users', 'MetalTypes', 'Categories', 'ProductNames', 'StorageLocations',
    'Currencies', 'TreasuryLocations', 'ExpenseCategories', 'InvoiceNotes',
    'Suppliers', 'OfficialSuppliers', 'Clients', 'SupplierAccounts', 'OfficialSupplierOperations',
    'LegacyImportBatches', 'LegacyImportRows',
    'LegacyClientCreditRows', 'LegacySupplierCreditRows',
    'PartnerInitialBalances',
    'SupplierOperations', 'SupplierOperationLines', 'TreasuryMetals',
    'RegisterSessions', 'SessionAudits', 'SessionAuditDetails', 'SessionReconciliations',
    'Inventory', 'InventoryCountDocumentSequence', 'InventoryCountSessions',
    'InventoryCountItems', 'InventoryCountExtraItems', 'InventoryCountAdjustments',
    'Sales', 'SaleItems', 'ClientCommands',
    'VersementOperations', 'ClientPayments', 'ClientCommandPayments',
    'ClientWalletTransactions',
    'Repairs', 'SupplierTransactions', 'Expenses', 'MoneyTransactions',
    'ClientGoldDeposits', 'ProductHistory', 'SystemLogs', 'BlackMarketRates'
]

ARCHIVE_VIEW_FLAG_FILE = 'archive_view.flag'

HARD_RESET_PASSWORD = "MySuperSecretPassword123!"


# ─── Custom JSON Encoder ──────────────────────────────────────────────────────
class CustomJSONEncoder(json.JSONEncoder):
    """يحوّل datetime وDecimal إلى أنواع قابلة للتسلسل JSON."""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)
