# Inventory Count Manager

Database access layer for full stock-count operations.

- `__init__.py` exposes `InventoryCountManager` by composing the mixins.
- `base.py` contains shared constants, normalization helpers, JSON helpers, and document-number reservation.
- `sessions.py` creates inventory count sessions, snapshots expected stock, updates summaries, and manages lifecycle states.
- `items.py` counts expected inventory rows, counts by barcode, records extra physical items, and updates item states.
- `adjustments.py` records reconciliation decisions and can apply supported inventory corrections.
