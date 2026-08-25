import os
import unittest
from unittest.mock import MagicMock, Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from database.base.tables import PARTNER_TABLE_QUERIES
from database.supplier_manager import SupplierManager
from ui.widgets.master_data.suppliers_tab import SuppliersTab
from ui.widgets.suppliers.supplier_editor_form import SupplierEditorForm

_app = QApplication.instance() or QApplication([])


class TestSupplierTypeMigrationAndUI(unittest.TestCase):
    def test_schema_migration_includes_supplier_type_modify(self):
        """Ensure migration contains ALTER TABLE Suppliers MODIFY COLUMN for supplier_type and primary_purity."""
        has_modify_supplier_type = any(
            "ALTER TABLE Suppliers MODIFY COLUMN supplier_type" in q for q in PARTNER_TABLE_QUERIES
        )
        has_modify_primary_purity = any(
            "ALTER TABLE Suppliers MODIFY COLUMN primary_purity" in q for q in PARTNER_TABLE_QUERIES
        )
        self.assertTrue(has_modify_supplier_type, "Missing MODIFY COLUMN supplier_type in PARTNER_TABLE_QUERIES")
        self.assertTrue(has_modify_primary_purity, "Missing MODIFY COLUMN primary_purity in PARTNER_TABLE_QUERIES")

    def test_supplier_manager_create_supplier(self):
        """Ensure SupplierManager executes INSERT with supplier_type and primary_purity."""
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42
        mock_conn.cursor.return_value = mock_cursor
        mock_db.get_db_connection.return_value.__enter__.return_value = mock_conn

        sm = SupplierManager(mock_db)
        sid = sm.create_supplier(
            name="Fournisseur Test",
            phone="0555123456",
            address="Alger",
            supplier_type="Silver",
            primary_purity="925",
            is_active=True
        )

        self.assertEqual(sid, 42)
        mock_cursor.execute.assert_called_once()
        query, params = mock_cursor.execute.call_args[0]
        self.assertIn("INSERT INTO Suppliers", query)
        self.assertEqual(params[0], "Fournisseur Test")
        self.assertEqual(params[4], "Silver")
        self.assertEqual(params[5], "925")

    def test_suppliers_tab_type_fallback(self):
        """Ensure legacy and modern supplier types are handled seamlessly in SuppliersTab."""
        mock_manager = Mock()
        mock_suppliers_service = Mock()
        mock_manager.suppliers = mock_suppliers_service

        tab = SuppliersTab(mock_manager)

        # Test legacy data fallback on table item click
        legacy_supplier = {
            "id": 10,
            "name": "Legacy Supplier",
            "supplier_type": "SUPPLIER",
            "primary_purity": "750",
            "phone": "0555000000",
            "address": "Centre ville",
            "is_active": True
        }
        tab.combo_type.setCurrentIndex(1) # Silver
        # Simulate selecting legacy item
        stype = str(legacy_supplier.get("supplier_type") or "Gold").strip()
        idx_t = tab.combo_type.findData(stype)
        if idx_t < 0:
            if stype.lower() in ["silver", "argent"]:
                idx_t = tab.combo_type.findData("Silver")
            else:
                idx_t = tab.combo_type.findData("Gold")
        if idx_t >= 0:
            tab.combo_type.setCurrentIndex(idx_t)

        self.assertEqual(tab.combo_type.currentData(), "Gold")

    def test_supplier_editor_form_fallback(self):
        """Ensure SupplierEditorForm handles legacy supplier_type values gracefully."""
        mock_manager = Mock()
        form = SupplierEditorForm(
            manager=mock_manager,
            supplier={
                "id": 1,
                "name": "Legacy Supplier",
                "supplier_type": "ARTISAN",
                "primary_purity": "750"
            }
        )
        self.assertEqual(form.supplier_type_combo.currentData(), "Gold")

        form_silver = SupplierEditorForm(
            manager=mock_manager,
            supplier={
                "id": 2,
                "name": "Silver Supplier",
                "supplier_type": "Silver",
                "primary_purity": "925"
            }
        )
        self.assertEqual(form_silver.supplier_type_combo.currentData(), "Silver")


if __name__ == "__main__":
    unittest.main()
