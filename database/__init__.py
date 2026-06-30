# database/__init__.py

from importlib import import_module
from contextvars import ContextVar

from .base import Database

active_user_id = ContextVar("active_user_id", default=None)

def log_methods(cls):
    return cls

_MANAGER_EXPORTS = {
    "UserManager": ("user_manager", "UserManager"),
    "MetalTypeManager": ("metal_type_manager", "MetalTypeManager"),
    "CategoryManager": ("category_manager", "CategoryManager"),
    "ProductNameManager": ("product_name_manager", "ProductNameManager"),
    "StorageLocationManager": ("storage_location_manager", "StorageLocationManager"),
    "CurrencyManager": ("currency_manager", "CurrencyManager"),
    "TreasuryManager": ("treasury_manager", "TreasuryManager"),
    "ExpenseCategoryManager": ("expense_category_manager", "ExpenseCategoryManager"),
    "SupplierManager": ("supplier_manager", "SupplierManager"),
    "OfficialSupplierManager": ("official_supplier_manager", "OfficialSupplierManager"),
    "ClientManager": ("client_manager", "ClientManager"),
    "ClientCreditManager": ("client_credit_manager", "ClientCreditManager"),
    "SupplierCreditManager": ("supplier_credit_manager", "SupplierCreditManager"),
    "SupplierTransactionManager": ("supplier_transaction_manager", "SupplierTransactionManager"),
    "SupplierOperationManager": ("supplier_operation_manager", "SupplierOperationManager"),
    "LegacySupplierImportManager": ("legacy_supplier_import_manager", "LegacySupplierImportManager"),
    "LegacySupplierPublishManager": ("legacy_supplier_publish_manager", "LegacySupplierPublishManager"),
    "SupplierStatementManager": ("supplier_statement_manager", "SupplierStatementManager"),
    "ClientPaymentManager": ("client_payment_manager", "ClientPaymentManager"),
    "ClientVersementsManager": ("client_versements_manager", "ClientVersementsManager"),
    "ClientVersementItemsManager": ("client_versement_items_manager", "ClientVersementItemsManager"),
    "ClientVersementPaymentsManager": ("client_versement_payments_manager", "ClientVersementPaymentsManager"),
    "ClientCommandsManager": ("client_commands_manager", "ClientCommandsManager"),
    "ClientCommandPaymentsManager": ("client_command_payments_manager", "ClientCommandPaymentsManager"),
    "InventoryManager": ("inventory_manager", "InventoryManager"),
    "InventoryCountManager": ("inventory_count_manager", "InventoryCountManager"),
    "GoldDepositManager": ("gold_deposit_manager", "GoldDepositManager"),
    "SalesManager": ("sales_manager", "SalesManager"),
    "SaleItemManager": ("sale_item_manager", "SaleItemManager"),
    "RepairManager": ("repair_manager", "RepairManager"),
    "ExpenseManager": ("expense_manager", "ExpenseManager"),
    "CashBoxManager": ("cash_box_manager", "CashBoxManager"),
    "SessionManager": ("session_manager", "SessionManager"),
    "ReconciliationManager": ("reconciliation_manager", "ReconciliationManager"),
    "ReportsManager": ("reports_manager", "ReportsManager"),
    "StatisticsManager": ("statistics_manager", "StatisticsManager"),
    "HistoryManager": ("history_manager", "HistoryManager"),
    "MarketRatesManager": ("market_rates_manager", "MarketRatesManager"),
    "CustomerManager": ("customer_manager", "CustomerManager"),
    "TreasuryMetalsManager": ("treasury_metals_manager", "TreasuryMetalsManager"),
    "InvoiceNoteManager": ("invoice_note_manager", "InvoiceNoteManager"),
    "SystemLogManager": ("system_log_manager", "SystemLogManager"),
    "VersementManager": ("versement_manager", "VersementManager"),
    "AchatOCManager": ("achat_oc_manager", "AchatOCManager"),
    "RHManager": ("rh_manager", "RHManager"),
    "CoffreManager": ("coffre_manager", "CoffreManager"),
    "ArtisanWorkManager": ("artisan_work_manager", "ArtisanWorkManager"),
}

_MANAGER_ATTRS = {
    "users": "UserManager",
    "metal_types": "MetalTypeManager",
    "categories": "CategoryManager",
    "product_names": "ProductNameManager",
    "storage_locations": "StorageLocationManager",
    "currencies": "CurrencyManager",
    "treasury": "TreasuryManager",
    "expense_categories": "ExpenseCategoryManager",
    "suppliers": "SupplierManager",
    "official_suppliers": "OfficialSupplierManager",
    "clients": "ClientManager",
    "client_credits": "ClientCreditManager",
    "supplier_credits": "SupplierCreditManager",
    "supplier_transactions": "SupplierTransactionManager",
    "supplier_operations": "SupplierOperationManager",
    "legacy_supplier_imports": "LegacySupplierImportManager",
    "legacy_supplier_publish": "LegacySupplierPublishManager",
    "supplier_statements": "SupplierStatementManager",
    "client_payments": "ClientPaymentManager",
    "client_versements": "ClientVersementsManager",
    "client_versement_items": "ClientVersementItemsManager",
    "client_versement_payments": "ClientVersementPaymentsManager",
    "client_commands": "ClientCommandsManager",
    "client_command_payments": "ClientCommandPaymentsManager",
    "inventory": "InventoryManager",
    "inventory_counts": "InventoryCountManager",
    "gold_deposits": "GoldDepositManager",
    "sales": "SalesManager",
    "sale_items": "SaleItemManager",
    "repairs": "RepairManager",
    "expenses": "ExpenseManager",
    "cash_box": "CashBoxManager",
    "sessions": "SessionManager",
    "reconciliation": "ReconciliationManager",
    "reports": "ReportsManager",
    "stats": "StatisticsManager",
    "history": "HistoryManager",
    "market": "MarketRatesManager",
    "customers": "CustomerManager",
    "treasury_metals": "TreasuryMetalsManager",
    "invoice_notes": "InvoiceNoteManager",
    "system_log": "SystemLogManager",
    "versements": "VersementManager",
    "achat_oc": "AchatOCManager",
    "rh": "RHManager",
    "coffre": "CoffreManager",
    "artisan_work": "ArtisanWorkManager",
}


def _load_export(export_name):
    module_name, attr_name = _MANAGER_EXPORTS[export_name]
    value = getattr(import_module(f"{__name__}.{module_name}"), attr_name)
    globals()[export_name] = value
    return value


def __getattr__(name):
    if name in _MANAGER_EXPORTS:
        return _load_export(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class LabDataManager:
    """Central access point for database managers, loaded only when first used."""

    def __init__(self, db_instance: Database):
        self.db = db_instance

    def __getattr__(self, name):
        manager_export = _MANAGER_ATTRS.get(name)
        if manager_export is None:
            raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

        manager_cls = _load_export(manager_export)
        manager = manager_cls(self.db)
        setattr(self, name, manager)
        return manager


__all__ = [
    "Database",
    "LabDataManager",
    "active_user_id",
    "log_methods",
    *_MANAGER_EXPORTS,
]