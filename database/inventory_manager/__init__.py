from .base import InventoryBaseMixin
from .pricing import InventoryPricingMixin
from .queries import InventoryQueryMixin
from .writes import InventoryWriteMixin

class InventoryManager(
    InventoryWriteMixin,
    InventoryQueryMixin,
    InventoryPricingMixin,
    InventoryBaseMixin,
):
    """Manage Inventory rows, stock movements, search, and pricing updates."""

    def __init__(self, db_instance):
        self.db = db_instance

__all__ = ["InventoryManager"]