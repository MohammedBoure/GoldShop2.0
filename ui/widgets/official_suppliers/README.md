# Official Suppliers UI

This package keeps the official supplier workflow split into focused widgets:

- `official_suppliers_view.py`: Small container that wires the supplier list to the selected supplier details.
- `supplier_list_view.py`: Header actions and tab container for the first screen.
- `supplier_registry_tab.py`: The suppliers tab with search, active/all filter, and touch-friendly supplier table.
- `global_statistics_tab.py`: Global official statistics, date-range totals, and unlinked outgoing operations.
- `supplier_detail_view.py`: Small coordinator for the selected supplier detail screen and operation actions.
- `supplier_identity_panel.py`: Selected supplier identity card.
- `supplier_operations_tab.py`: Supplier-linked incoming operations filters, table, selection, and loading logic.
- `supplier_summary_tab.py`: Supplier monthly summary filters, totals, and summary table.
- `supplier_editor_dialog.py`: Dialog shell for saving official supplier records.
- `supplier_editor_form.py`: Touch-friendly official supplier fields and linked supplier picker.
- `operation_dialog.py`: Dialog shell for saving official incoming/outgoing operations.
- `operation_form.py`: Touch-friendly official operation fields, metal loading, validation, and payload mapping.
- `helpers.py`: Formatting helpers and shared touch action button factory.
