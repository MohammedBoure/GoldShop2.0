"""
ui/widgets/sales/
Package exports — استيراد واحد يكفي:
    from ui.widgets.sales import POSInterfaceWidget
"""

from .pos_interface_widget      import POSInterfaceWidget
from .pos_ui_builder            import POSUIBuilder
from .pos_client_manager        import POSClientManager
from .pos_inventory_loader      import POSInventoryLoader
from .pos_cart_manager          import POSCartManager
from .pos_discount_manager      import POSDiscountManager

__all__ = [
    "POSInterfaceWidget",
    "POSUIBuilder",
    "POSClientManager",
    "POSInventoryLoader",
    "POSCartManager",
    "POSDiscountManager",
]
