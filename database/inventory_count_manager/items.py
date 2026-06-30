"""Inventory count item and extra-item operations."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from .base import EXPECTED_STOCK_STATUSES


class InventoryCountItemMixin:
    def snapshot_inventory(
        self,
        count_id: int,
        include_statuses: Optional[Sequence[str]] = None,
    ) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                self._insert_inventory_snapshot(cursor, count_id, include_statuses=include_statuses)
                self._refresh_session_summary(cursor, count_id)
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error snapshotting inventory count %s: %s", count_id, exc)
            return False

    def get_count_items(
        self,
        count_id: int,
        status: Optional[str] = None,
        search_text: str = "",
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        filters = ["ici.count_id = %s"]
        params: List[Any] = [count_id]
        if status:
            if str(status or "").upper() == "__CHECKED__":
                filters.append("ici.count_status IN ('FOUND', 'MISSING', 'DIFFERENT', 'IGNORED')")
            elif isinstance(status, (list, tuple, set)):
                values = [self._normalize_item_status(value) for value in status]
                placeholders = ", ".join(["%s"] * len(values))
                filters.append(f"ici.count_status IN ({placeholders})")
                params.extend(values)
            else:
                filters.append("ici.count_status = %s")
                params.append(self._normalize_item_status(status))
        search_text = str(search_text or "").strip()
        if search_text:
            like = f"%{search_text}%"
            filters.append("(ici.snapshot_barcode LIKE %s OR ici.snapshot_name LIKE %s)")
            params.extend([like, like])
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT ici.*, i.status AS current_inventory_status,
                           i.remaining_weight AS current_remaining_weight,
                           i.remaining_quantity AS current_remaining_quantity,
                           i.supplier_id,
                           i.metal_cost_per_gram,
                           i.labor_cost_per_gram,
                           i.profit_margin,
                           i.margin_type,
                           i.total_cost,
                           i.selling_price,
                           c.name AS category_name,
                           mt.name AS metal_type_name,
                           mt.purity_value AS metal_purity_value,
                           s.name AS supplier_name,
                           l.name AS location_name,
                           u.username AS counted_by_username
                    FROM InventoryCountItems ici
                    LEFT JOIN Inventory i ON i.id = ici.inventory_id
                    LEFT JOIN Categories c ON c.id = ici.snapshot_category_id
                    LEFT JOIN MetalTypes mt ON mt.id = ici.snapshot_metal_type_id
                    LEFT JOIN Suppliers s ON s.id = i.supplier_id
                    LEFT JOIN StorageLocations l ON l.id = ici.snapshot_location_id
                    LEFT JOIN Users u ON u.id = ici.counted_by_user_id
                    WHERE {" AND ".join(filters)}
                    ORDER BY
                        CASE WHEN ici.count_status = 'NOT_COUNTED' THEN 1 ELSE 0 END ASC,
                        COALESCE(ici.counted_at, ici.updated_at, ici.created_at) DESC,
                        ici.snapshot_name ASC,
                        ici.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params + [int(limit), int(offset)]),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error listing inventory count items %s: %s", count_id, exc)
            return []

    def get_remaining_inventory_items(
        self,
        count_id: int,
        search_text: str = "",
        limit: int = 500,
        offset: int = 0,
        include_statuses: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List not-counted snapshot rows plus current stock rows not yet scanned."""
        statuses = tuple(include_statuses or EXPECTED_STOCK_STATUSES)
        snapshot_filters = ["ici.count_id = %s", "ici.count_status = 'NOT_COUNTED'"]
        snapshot_params: List[Any] = [count_id]
        inventory_filters = [
            """
            NOT EXISTS (
                SELECT 1
                FROM InventoryCountItems ici
                WHERE ici.count_id = %s AND ici.inventory_id = i.id
            )
            """
        ]
        inventory_params: List[Any] = [count_id]
        if statuses:
            placeholders = ", ".join(["%s"] * len(statuses))
            inventory_filters.append(f"i.status IN ({placeholders})")
            inventory_params.extend(statuses)
        search_text = str(search_text or "").strip()
        if search_text:
            like = f"%{search_text}%"
            snapshot_filters.append("(ici.snapshot_barcode LIKE %s OR ici.snapshot_name LIKE %s OR s.name LIKE %s)")
            snapshot_params.extend([like, like, like])
            inventory_filters.append("(i.barcode LIKE %s OR i.name LIKE %s OR s.name LIKE %s)")
            inventory_params.extend([like, like, like])
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT *
                    FROM (
                        SELECT ici.id,
                               ici.count_id,
                               ici.inventory_id,
                               ici.snapshot_barcode,
                               ici.snapshot_name,
                               ici.snapshot_status,
                               ici.snapshot_item_type,
                               ici.snapshot_category_id,
                               ici.snapshot_metal_type_id,
                               ici.snapshot_location_id,
                               ici.expected_weight,
                               ici.expected_quantity,
                               ici.expected_remaining_weight,
                               ici.expected_remaining_quantity,
                               ici.count_status,
                               ici.counted_weight,
                               ici.counted_quantity,
                               ici.difference_weight,
                               ici.difference_quantity,
                               i.status AS current_inventory_status,
                               i.remaining_weight AS current_remaining_weight,
                               i.remaining_quantity AS current_remaining_quantity,
                               i.supplier_id,
                               i.metal_cost_per_gram,
                               i.labor_cost_per_gram,
                               i.profit_margin,
                               i.margin_type,
                               i.total_cost,
                               i.selling_price,
                               c.name AS category_name,
                               mt.name AS metal_type_name,
                               mt.purity_value AS metal_purity_value,
                               s.name AS supplier_name,
                               l.name AS location_name,
                               u.username AS counted_by_username
                        FROM InventoryCountItems ici
                        LEFT JOIN Inventory i ON i.id = ici.inventory_id
                        LEFT JOIN Categories c ON c.id = ici.snapshot_category_id
                        LEFT JOIN MetalTypes mt ON mt.id = ici.snapshot_metal_type_id
                        LEFT JOIN Suppliers s ON s.id = i.supplier_id
                        LEFT JOIN StorageLocations l ON l.id = ici.snapshot_location_id
                        LEFT JOIN Users u ON u.id = ici.counted_by_user_id
                        WHERE {" AND ".join(snapshot_filters)}

                        UNION ALL

                        SELECT NULL AS id,
                               %s AS count_id,
                               i.id AS inventory_id,
                               i.barcode AS snapshot_barcode,
                               i.name AS snapshot_name,
                               i.status AS snapshot_status,
                               COALESCE(i.item_type, 'WEIGHT') AS snapshot_item_type,
                               i.category_id AS snapshot_category_id,
                               i.metal_type_id AS snapshot_metal_type_id,
                               i.location_id AS snapshot_location_id,
                               COALESCE(i.weight, 0) AS expected_weight,
                               COALESCE(i.quantity, 0) AS expected_quantity,
                               CASE WHEN COALESCE(i.item_type, 'WEIGHT') = 'WEIGHT'
                                    THEN COALESCE(i.remaining_weight, i.weight, 0) ELSE 0 END AS expected_remaining_weight,
                               CASE WHEN COALESCE(i.item_type, 'WEIGHT') = 'PIECE'
                                    THEN COALESCE(i.remaining_quantity, i.quantity, 0) ELSE 0 END AS expected_remaining_quantity,
                               'NOT_COUNTED' AS count_status,
                               NULL AS counted_weight,
                               NULL AS counted_quantity,
                               CASE WHEN COALESCE(i.item_type, 'WEIGHT') = 'WEIGHT'
                                    THEN -COALESCE(i.remaining_weight, i.weight, 0) ELSE 0 END AS difference_weight,
                               CASE WHEN COALESCE(i.item_type, 'WEIGHT') = 'PIECE'
                                    THEN -COALESCE(i.remaining_quantity, i.quantity, 0) ELSE 0 END AS difference_quantity,
                               i.status AS current_inventory_status,
                               i.remaining_weight AS current_remaining_weight,
                               i.remaining_quantity AS current_remaining_quantity,
                               i.supplier_id,
                               i.metal_cost_per_gram,
                               i.labor_cost_per_gram,
                               i.profit_margin,
                               i.margin_type,
                               i.total_cost,
                               i.selling_price,
                               c.name AS category_name,
                               mt.name AS metal_type_name,
                               mt.purity_value AS metal_purity_value,
                               s.name AS supplier_name,
                               l.name AS location_name,
                               NULL AS counted_by_username
                        FROM Inventory i
                        LEFT JOIN Categories c ON c.id = i.category_id
                        LEFT JOIN MetalTypes mt ON mt.id = i.metal_type_id
                        LEFT JOIN Suppliers s ON s.id = i.supplier_id
                        LEFT JOIN StorageLocations l ON l.id = i.location_id
                        WHERE {" AND ".join(inventory_filters)}
                    ) remaining
                    ORDER BY snapshot_name ASC, inventory_id ASC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(
                        snapshot_params
                        + [count_id]
                        + inventory_params
                        + [int(limit), int(offset)]
                    ),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error listing remaining inventory count items %s: %s", count_id, exc)
            return []

    def get_count_statistics(self, count_id: int) -> Dict[str, Any]:
        """Aggregate scanned count rows by supplier, purity, category, and total."""

        base_metric_sql = """
            COALESCE(SUM(weight_counted), 0) AS total_weight,
            COALESCE(SUM(quantity_counted), 0) AS total_quantity,
            COALESCE(SUM(estimated_value), 0) AS total_value,
            COUNT(*) AS item_count
        """
        source_sql = """
            FROM (
                SELECT ici.inventory_id,
                       ici.snapshot_category_id,
                       ici.snapshot_metal_type_id,
                       i.supplier_id,
                       CASE WHEN COALESCE(ici.snapshot_item_type, 'WEIGHT') = 'WEIGHT'
                            THEN COALESCE(ici.counted_weight, ici.expected_remaining_weight, 0)
                            ELSE 0 END AS weight_counted,
                       CASE WHEN COALESCE(ici.snapshot_item_type, 'WEIGHT') = 'PIECE'
                            THEN COALESCE(ici.counted_quantity, ici.expected_remaining_quantity, 0)
                            ELSE 0 END AS quantity_counted,
                       CASE
                            WHEN COALESCE(ici.snapshot_item_type, 'WEIGHT') = 'WEIGHT'
                             AND COALESCE(ici.expected_remaining_weight, 0) > 0
                                THEN COALESCE(i.selling_price, 0)
                                     * COALESCE(ici.counted_weight, ici.expected_remaining_weight, 0)
                                     / ici.expected_remaining_weight
                            WHEN COALESCE(ici.snapshot_item_type, 'WEIGHT') = 'PIECE'
                             AND COALESCE(ici.expected_remaining_quantity, 0) > 0
                                THEN COALESCE(i.selling_price, 0)
                                     * COALESCE(ici.counted_quantity, ici.expected_remaining_quantity, 0)
                                     / ici.expected_remaining_quantity
                            ELSE COALESCE(i.selling_price, 0)
                       END AS estimated_value
                FROM InventoryCountItems ici
                LEFT JOIN Inventory i ON i.id = ici.inventory_id
                WHERE ici.count_id = %s
                  AND ici.count_status IN ('FOUND', 'DIFFERENT')
            ) counted
        """

        def fetch_group(cursor, label_sql: str, joins_sql: str = "", group_sql: str = "") -> List[Dict[str, Any]]:
            cursor.execute(
                f"""
                SELECT {label_sql} AS label,
                       {base_metric_sql}
                {source_sql}
                {joins_sql}
                {group_sql}
                ORDER BY total_weight DESC, total_value DESC, label ASC
                """,
                (count_id,),
            )
            return cursor.fetchall() or []

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT {base_metric_sql}
                    {source_sql}
                    """,
                    (count_id,),
                )
                totals = cursor.fetchone() or {}
                by_supplier = fetch_group(
                    cursor,
                    "COALESCE(s.name, 'Sans fournisseur')",
                    "LEFT JOIN Suppliers s ON s.id = counted.supplier_id",
                    "GROUP BY counted.supplier_id, s.name",
                )
                by_metal = fetch_group(
                    cursor,
                    """
                    CASE
                        WHEN mt.id IS NULL THEN 'Sans titre'
                        WHEN mt.purity_value IS NULL THEN mt.name
                        ELSE CONCAT(mt.name, ' (', CAST(mt.purity_value AS CHAR), ')')
                    END
                    """,
                    "LEFT JOIN MetalTypes mt ON mt.id = counted.snapshot_metal_type_id",
                    "GROUP BY counted.snapshot_metal_type_id, mt.name, mt.purity_value",
                )
                by_category = fetch_group(
                    cursor,
                    "COALESCE(c.name, 'Sans categorie')",
                    "LEFT JOIN Categories c ON c.id = counted.snapshot_category_id",
                    "GROUP BY counted.snapshot_category_id, c.name",
                )
                return {
                    "totals": totals,
                    "by_supplier": by_supplier,
                    "by_metal": by_metal,
                    "by_category": by_category,
                }
        except Exception as exc:
            logging.error("Error building inventory count statistics %s: %s", count_id, exc)
            return {"totals": {}, "by_supplier": [], "by_metal": [], "by_category": []}

    def get_count_item(self, count_item_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT *
                    FROM InventoryCountItems
                    WHERE id = %s
                    """,
                    (count_item_id,),
                )
                return cursor.fetchone()
        except Exception as exc:
            logging.error("Error retrieving inventory count item %s: %s", count_item_id, exc)
            return None

    def count_item(
        self,
        count_item_id: int,
        counted_weight=None,
        counted_quantity=None,
        method: str = "MANUAL",
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> bool:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT *
                FROM InventoryCountItems
                WHERE id = %s
                FOR UPDATE
                """,
                (count_item_id,),
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False
            self._count_item_with_cursor(
                cursor,
                row,
                counted_weight=counted_weight,
                counted_quantity=counted_quantity,
                method=method,
                user_id=user_id,
                notes=notes,
            )
            self._refresh_session_summary(cursor, row.get("count_id"))
            conn.commit()
            return True
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error counting inventory count item %s: %s", count_item_id, exc)
            return False
        finally:
            if conn:
                conn.close()

    def count_inventory_item(
        self,
        count_id: int,
        inventory_id: int,
        counted_weight=None,
        counted_quantity=None,
        method: str = "MANUAL",
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> bool:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT *
                FROM InventoryCountItems
                WHERE count_id = %s AND inventory_id = %s
                FOR UPDATE
                """,
                (count_id, inventory_id),
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False
            self._count_item_with_cursor(
                cursor,
                row,
                counted_weight=counted_weight,
                counted_quantity=counted_quantity,
                method=method,
                user_id=user_id,
                notes=notes,
            )
            self._refresh_session_summary(cursor, count_id)
            conn.commit()
            return True
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error counting inventory item %s in count %s: %s", inventory_id, count_id, exc)
            return False
        finally:
            if conn:
                conn.close()

    def count_barcode(
        self,
        count_id: int,
        barcode: str,
        counted_weight=None,
        counted_quantity=None,
        method: str = "BARCODE",
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
        create_extra: bool = True,
        observed_name: Optional[str] = None,
    ) -> Optional[str]:
        """Count a stock barcode, creating the count row lazily when needed."""
        conn = None
        try:
            barcode = str(barcode or "").strip()
            if not barcode:
                return None
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT *
                FROM InventoryCountItems
                WHERE count_id = %s AND snapshot_barcode = %s
                FOR UPDATE
                """,
                (count_id, barcode),
            )
            row = cursor.fetchone()
            if not row:
                self._insert_count_item_from_inventory_barcode(cursor, count_id, barcode)
                cursor.execute(
                    """
                    SELECT *
                    FROM InventoryCountItems
                    WHERE count_id = %s AND snapshot_barcode = %s
                    FOR UPDATE
                    """,
                    (count_id, barcode),
                )
                row = cursor.fetchone()
            if row:
                self._count_item_with_cursor(
                    cursor,
                    row,
                    counted_weight=counted_weight,
                    counted_quantity=counted_quantity,
                    method=method,
                    user_id=user_id,
                    notes=notes,
                )
                result = "COUNTED"
            elif create_extra:
                cursor.execute(
                    """
                    SELECT id, name, item_type, category_id, metal_type_id, location_id,
                           remaining_weight, remaining_quantity
                    FROM Inventory
                    WHERE barcode = %s
                    LIMIT 1
                    """,
                    (barcode,),
                )
                inventory = cursor.fetchone() or {}
                self._insert_extra_item(
                    cursor,
                    count_id=count_id,
                    observed_barcode=barcode,
                    observed_name=observed_name or inventory.get("name"),
                    observed_item_type=inventory.get("item_type") or "WEIGHT",
                    observed_weight=counted_weight if counted_weight is not None else inventory.get("remaining_weight"),
                    observed_quantity=counted_quantity if counted_quantity is not None else inventory.get("remaining_quantity") or 1,
                    category_id=inventory.get("category_id"),
                    metal_type_id=inventory.get("metal_type_id"),
                    location_id=inventory.get("location_id"),
                    linked_inventory_id=inventory.get("id"),
                    user_id=user_id,
                    notes=notes,
                )
                result = "EXTRA"
            else:
                result = "NOT_FOUND"
            self._refresh_session_summary(cursor, count_id)
            conn.commit()
            return result
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error counting barcode %s in count %s: %s", barcode, count_id, exc)
            return None
        finally:
            if conn:
                conn.close()

    def _insert_count_item_from_inventory_barcode(self, cursor, count_id: int, barcode: str) -> None:
        statuses = tuple(EXPECTED_STOCK_STATUSES)
        placeholders = ", ".join(["%s"] * len(statuses))
        cursor.execute(
            f"""
            INSERT INTO InventoryCountItems
            (count_id, inventory_id, snapshot_barcode, snapshot_name, snapshot_status,
             snapshot_item_type, snapshot_category_id, snapshot_metal_type_id,
             snapshot_location_id, expected_weight, expected_quantity,
             expected_remaining_weight, expected_remaining_quantity, count_status,
             created_at, updated_at)
            SELECT %s, i.id, i.barcode, i.name, i.status,
                   COALESCE(i.item_type, 'WEIGHT'), i.category_id, i.metal_type_id,
                   i.location_id, COALESCE(i.weight, 0), COALESCE(i.quantity, 0),
                   CASE WHEN COALESCE(i.item_type, 'WEIGHT') = 'WEIGHT'
                        THEN COALESCE(i.remaining_weight, i.weight, 0) ELSE 0 END,
                   CASE WHEN COALESCE(i.item_type, 'WEIGHT') = 'PIECE'
                        THEN COALESCE(i.remaining_quantity, i.quantity, 0) ELSE 0 END,
                   'NOT_COUNTED', NOW(), NOW()
            FROM Inventory i
            WHERE i.barcode = %s
              AND i.status IN ({placeholders})
            LIMIT 1
            ON DUPLICATE KEY UPDATE
                snapshot_barcode = VALUES(snapshot_barcode),
                snapshot_name = VALUES(snapshot_name),
                snapshot_status = VALUES(snapshot_status),
                snapshot_item_type = VALUES(snapshot_item_type),
                snapshot_category_id = VALUES(snapshot_category_id),
                snapshot_metal_type_id = VALUES(snapshot_metal_type_id),
                snapshot_location_id = VALUES(snapshot_location_id),
                expected_weight = VALUES(expected_weight),
                expected_quantity = VALUES(expected_quantity),
                expected_remaining_weight = VALUES(expected_remaining_weight),
                expected_remaining_quantity = VALUES(expected_remaining_quantity),
                updated_at = NOW(),
                id = LAST_INSERT_ID(id)
            """,
            tuple([count_id, barcode] + list(statuses)),
        )

    def mark_item_missing(self, count_item_id: int, user_id: Optional[int] = None, notes: Optional[str] = None) -> bool:
        return self._set_count_item_status(
            count_item_id,
            "MISSING",
            counted_weight=0,
            counted_quantity=0,
            user_id=user_id,
            notes=notes,
        )

    def ignore_count_item(self, count_item_id: int, user_id: Optional[int] = None, notes: Optional[str] = None) -> bool:
        return self._set_count_item_status(count_item_id, "IGNORED", user_id=user_id, notes=notes)

    def reset_count_item(self, count_item_id: int) -> bool:
        return self._set_count_item_status(
            count_item_id,
            "NOT_COUNTED",
            counted_weight=None,
            counted_quantity=None,
            user_id=None,
            notes=None,
            reset=True,
        )

    def add_extra_item(
        self,
        count_id: int,
        observed_barcode: Optional[str] = None,
        observed_name: Optional[str] = None,
        observed_item_type: str = "WEIGHT",
        observed_weight=0,
        observed_quantity: int = 1,
        category_id: Optional[int] = None,
        metal_type_id: Optional[int] = None,
        location_id: Optional[int] = None,
        linked_inventory_id: Optional[int] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[int]:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            extra_id = self._insert_extra_item(
                cursor,
                count_id=count_id,
                observed_barcode=observed_barcode,
                observed_name=observed_name,
                observed_item_type=observed_item_type,
                observed_weight=observed_weight,
                observed_quantity=observed_quantity,
                category_id=category_id,
                metal_type_id=metal_type_id,
                location_id=location_id,
                linked_inventory_id=linked_inventory_id,
                user_id=user_id,
                notes=notes,
            )
            self._refresh_session_summary(cursor, count_id)
            conn.commit()
            return extra_id
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error adding extra inventory count item %s: %s", count_id, exc)
            return None
        finally:
            if conn:
                conn.close()

    def get_extra_items(
        self,
        count_id: int,
        status: Optional[str] = None,
        search_text: str = "",
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        filters = ["e.count_id = %s"]
        params: List[Any] = [count_id]
        if status:
            filters.append("e.status = %s")
            params.append(self._normalize_extra_status(status))
        search_text = str(search_text or "").strip()
        if search_text:
            like = f"%{search_text}%"
            filters.append("(e.observed_barcode LIKE %s OR e.observed_name LIKE %s)")
            params.extend([like, like])
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT e.*, i.name AS linked_inventory_name,
                           c.name AS category_name,
                           mt.name AS metal_type_name,
                           l.name AS location_name,
                           u.username AS recorded_by_username
                    FROM InventoryCountExtraItems e
                    LEFT JOIN Inventory i ON i.id = e.linked_inventory_id
                    LEFT JOIN Categories c ON c.id = e.category_id
                    LEFT JOIN MetalTypes mt ON mt.id = e.metal_type_id
                    LEFT JOIN StorageLocations l ON l.id = e.location_id
                    LEFT JOIN Users u ON u.id = e.recorded_by_user_id
                    WHERE {" AND ".join(filters)}
                    ORDER BY e.status ASC, e.recorded_at DESC, e.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params + [int(limit), int(offset)]),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error listing extra inventory count items %s: %s", count_id, exc)
            return []

    def link_extra_item(self, extra_item_id: int, inventory_id: int, status: str = "LINKED") -> bool:
        return self.update_extra_item(extra_item_id, linked_inventory_id=inventory_id, status=status)

    def ignore_extra_item(self, extra_item_id: int, notes: Optional[str] = None) -> bool:
        return self.update_extra_item(extra_item_id, status="IGNORED", notes=notes)

    def update_extra_item(self, extra_item_id: int, **fields) -> bool:
        allowed = {
            "observed_barcode",
            "observed_name",
            "observed_item_type",
            "observed_weight",
            "observed_quantity",
            "category_id",
            "metal_type_id",
            "location_id",
            "status",
            "linked_inventory_id",
            "notes",
        }
        updates = []
        params = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "observed_item_type":
                value = self._normalize_item_type(value)
            elif key == "status":
                value = self._normalize_extra_status(value)
            updates.append(f"{key} = %s")
            params.append(value)
        if not updates:
            return True
        params.append(extra_item_id)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    UPDATE InventoryCountExtraItems
                    SET {", ".join(updates)}
                    WHERE id = %s
                    """,
                    tuple(params),
                )
                cursor.execute("SELECT count_id FROM InventoryCountExtraItems WHERE id = %s", (extra_item_id,))
                row = cursor.fetchone()
                if row:
                    self._refresh_session_summary(cursor, row.get("count_id"))
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error updating extra inventory count item %s: %s", extra_item_id, exc)
            return False

    def _count_item_with_cursor(
        self,
        cursor,
        row: Dict[str, Any],
        counted_weight=None,
        counted_quantity=None,
        method: str = "MANUAL",
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> None:
        status = self._item_difference_status(row, counted_weight=counted_weight, counted_quantity=counted_quantity)
        item_type = self._normalize_item_type(row.get("snapshot_item_type"))
        if item_type == "PIECE":
            counted_quantity = int(
                counted_quantity if counted_quantity is not None else row.get("expected_remaining_quantity") or 0
            )
            counted_weight = 0
        else:
            counted_weight = float(
                self._decimal(counted_weight if counted_weight is not None else row.get("expected_remaining_weight"))
            )
            counted_quantity = 0
        cursor.execute(
            """
            UPDATE InventoryCountItems
            SET count_status = %s,
                counted_weight = %s,
                counted_quantity = %s,
                count_method = %s,
                counted_at = NOW(),
                counted_by_user_id = %s,
                notes = CASE
                    WHEN %s IS NULL THEN notes
                    ELSE %s
                END,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                counted_weight,
                counted_quantity,
                self._normalize_count_method(method),
                user_id,
                notes,
                notes,
                row.get("id"),
            ),
        )

    def _set_count_item_status(
        self,
        count_item_id: int,
        status: str,
        counted_weight=None,
        counted_quantity=None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
        reset: bool = False,
    ) -> bool:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT count_id FROM InventoryCountItems WHERE id = %s FOR UPDATE",
                (count_item_id,),
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False
            cursor.execute(
                """
                UPDATE InventoryCountItems
                SET count_status = %s,
                    counted_weight = %s,
                    counted_quantity = %s,
                    count_method = CASE WHEN %s THEN NULL ELSE count_method END,
                    counted_at = CASE WHEN %s THEN NULL ELSE COALESCE(counted_at, NOW()) END,
                    counted_by_user_id = %s,
                    notes = CASE WHEN %s IS NULL THEN notes ELSE %s END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    self._normalize_item_status(status),
                    counted_weight,
                    counted_quantity,
                    reset,
                    reset,
                    user_id,
                    notes,
                    notes,
                    count_item_id,
                ),
            )
            self._refresh_session_summary(cursor, row.get("count_id"))
            conn.commit()
            return True
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error setting inventory count item %s status: %s", count_item_id, exc)
            return False
        finally:
            if conn:
                conn.close()

    def _insert_extra_item(
        self,
        cursor,
        count_id: int,
        observed_barcode: Optional[str] = None,
        observed_name: Optional[str] = None,
        observed_item_type: str = "WEIGHT",
        observed_weight=0,
        observed_quantity: int = 1,
        category_id: Optional[int] = None,
        metal_type_id: Optional[int] = None,
        location_id: Optional[int] = None,
        linked_inventory_id: Optional[int] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> int:
        item_type = self._normalize_item_type(observed_item_type)
        weight = float(self._decimal(observed_weight)) if item_type == "WEIGHT" else 0
        quantity = max(1, int(observed_quantity or 1))
        cursor.execute(
            """
            INSERT INTO InventoryCountExtraItems
            (count_id, observed_barcode, observed_name, observed_item_type,
             observed_weight, observed_quantity, category_id, metal_type_id,
             location_id, status, linked_inventory_id, recorded_by_user_id,
             recorded_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'NEW', %s, %s, NOW(), %s)
            ON DUPLICATE KEY UPDATE
                observed_name = VALUES(observed_name),
                observed_item_type = VALUES(observed_item_type),
                observed_weight = VALUES(observed_weight),
                observed_quantity = VALUES(observed_quantity),
                category_id = VALUES(category_id),
                metal_type_id = VALUES(metal_type_id),
                location_id = VALUES(location_id),
                linked_inventory_id = VALUES(linked_inventory_id),
                recorded_by_user_id = VALUES(recorded_by_user_id),
                recorded_at = NOW(),
                notes = VALUES(notes),
                id = LAST_INSERT_ID(id)
            """,
            (
                count_id,
                observed_barcode,
                observed_name,
                item_type,
                weight,
                quantity,
                category_id,
                metal_type_id,
                location_id,
                linked_inventory_id,
                user_id,
                notes,
            ),
        )
        return int(cursor.lastrowid)
