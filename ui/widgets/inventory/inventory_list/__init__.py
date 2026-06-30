# ui/widgets/inventory/__init__.py
"""
حزمة واجهة المخزون.

الاستخدام:
    from ui.widgets.inventory import InventoryListTab, InventoryFormTab
"""

from .inventory_list_tab import InventoryListTab
from ._helpers import SortableTableWidgetItem, ProductNameSelectionDialog

__all__ = [
    "InventoryListTab",
    "InventoryFormTab",
    "SortableTableWidgetItem",
    "ProductNameSelectionDialog",
]


def __getattr__(name):
    if name == "InventoryFormTab":
        from .inventory_form_tab import InventoryFormTab

        return InventoryFormTab
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
