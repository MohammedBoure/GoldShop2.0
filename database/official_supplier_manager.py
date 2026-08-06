"""
Deprecated / Removed: OfficialSupplierManager has been merged into standard SupplierManager.
"""

from database.supplier_manager import SupplierManager as OfficialSupplierManager

__all__ = ["OfficialSupplierManager"]
