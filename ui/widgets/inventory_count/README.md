#  Count UI

This package contains the physical inventory count screen and its supporting UI pieces.

## Files

- `inventory_count_view.py` defines the public `InventoryCountView` widget and wires the mixins together.
- `helpers.py` contains display constants and formatting helpers shared by the UI modules.
- `dialogs.py` contains inventory-count dialogs, including adjustment and legacy new-session dialogs.
- `ui_builders.py` builds the overview page, counting page, tabs, tables, buttons, and touch-friendly controls.
- `session_data.py` loads sessions, handles session selection/navigation, and updates the session summary panel.
- `item_tables.py` loads scanned/remaining items, fills the statistics tab, renders scan results, and manages table row display.
- `actions.py` handles user actions such as creating a session, changing status, scanning barcodes, and applying corrections.

## Development Notes

- Keep `InventoryCountView` as the import entry point for the rest of the application.
- Put pure display formatting in `helpers.py`.
- Put UI construction code in `ui_builders.py`; put behavior and data refresh code in the other mixins.
- Keep database access behind the `manager.inventory_counts` service instead of querying from the UI directly.
