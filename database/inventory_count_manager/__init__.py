from .adjustments import InventoryCountAdjustmentMixin
from .base import InventoryCountBaseMixin
from .items import InventoryCountItemMixin
from .sessions import InventoryCountSessionMixin


class InventoryCountManager(
    InventoryCountAdjustmentMixin,
    InventoryCountItemMixin,
    InventoryCountSessionMixin,
    InventoryCountBaseMixin,
):
    """Manage full inventory count sessions, counted rows, extras, and adjustments."""

    def __init__(self, db_instance):
        self.db = db_instance


__all__ = ["InventoryCountManager"]
