# Inventory Manager

This package manages inventory rows, stock state, lookup queries, and pricing updates.

- `__init__.py`: Exposes `InventoryManager` by composing the package mixins.
- `base.py`: Shared inventory helpers such as stock availability conditions.
- `pricing.py`: Gold price, margin, and reference-price update operations.
- `queries.py`: Inventory lookup, barcode search, listing, and pagination queries.
- `writes.py`: Inventory creation, update, reservation, release, stock, and deletion writes.

