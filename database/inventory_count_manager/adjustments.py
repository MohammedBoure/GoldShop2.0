"""Inventory count adjustment recording and application."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


class InventoryCountAdjustmentMixin:
    def get_adjustments(self, count_id: int) -> List[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT a.*, u.username AS applied_by_username,
                           i.barcode AS inventory_barcode,
                           i.name AS inventory_name
                    FROM InventoryCountAdjustments a
                    LEFT JOIN Users u ON u.id = a.applied_by_user_id
                    LEFT JOIN Inventory i ON i.id = a.inventory_id
                    WHERE a.count_id = %s
                    ORDER BY a.created_at DESC, a.id DESC
                    """,
                    (count_id,),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error listing inventory count adjustments %s: %s", count_id, exc)
            return []

    def create_adjustment(
        self,
        count_id: int,
        action_type: str,
        count_item_id: Optional[int] = None,
        extra_item_id: Optional[int] = None,
        inventory_id: Optional[int] = None,
        previous_payload: Optional[Dict[str, Any]] = None,
        new_payload: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
        applied: bool = False,
    ) -> Optional[int]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                adjustment_id = self._insert_adjustment(
                    cursor,
                    count_id=count_id,
                    action_type=action_type,
                    count_item_id=count_item_id,
                    extra_item_id=extra_item_id,
                    inventory_id=inventory_id,
                    previous_payload=previous_payload,
                    new_payload=new_payload,
                    user_id=user_id,
                    notes=notes,
                    applied=applied,
                )
                conn.commit()
                return adjustment_id
        except Exception as exc:
            logging.error("Error creating inventory count adjustment %s: %s", count_id, exc)
            return None

    def apply_adjustment(
        self,
        count_id: int,
        action_type: str,
        count_item_id: Optional[int] = None,
        extra_item_id: Optional[int] = None,
        inventory_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[int]:
        """Apply a supported reconciliation action and record the audit row."""
        conn = None
        try:
            action = self._normalize_adjustment_action(action_type)
            payload = dict(payload or {})
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            count_item = None
            extra_item = None
            if count_item_id:
                cursor.execute(
                    "SELECT * FROM InventoryCountItems WHERE id = %s FOR UPDATE",
                    (count_item_id,),
                )
                count_item = cursor.fetchone()
                if count_item and not inventory_id:
                    inventory_id = count_item.get("inventory_id")
            if extra_item_id:
                cursor.execute(
                    "SELECT * FROM InventoryCountExtraItems WHERE id = %s FOR UPDATE",
                    (extra_item_id,),
                )
                extra_item = cursor.fetchone()
                if extra_item and not inventory_id:
                    inventory_id = extra_item.get("linked_inventory_id")

            previous_payload = None
            if inventory_id:
                previous_payload = self._fetch_inventory_payload(cursor, inventory_id)

            new_payload = dict(payload)
            if action == "MARK_LOST":
                if not inventory_id:
                    raise ValueError("MARK_LOST requires an inventory item.")
                cursor.execute(
                    """
                    UPDATE Inventory
                    SET status = 'Lost',
                        remaining_weight = 0,
                        remaining_quantity = 0
                    WHERE id = %s
                    """,
                    (inventory_id,),
                )
                if count_item_id:
                    cursor.execute(
                        """
                        UPDATE InventoryCountItems
                        SET count_status = 'MISSING',
                            counted_weight = 0,
                            counted_quantity = 0,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (count_item_id,),
                    )

            elif action == "UPDATE_WEIGHT":
                if not inventory_id:
                    raise ValueError("UPDATE_WEIGHT requires an inventory item.")
                weight = self._decimal(payload.get("weight", payload.get("remaining_weight")))
                remaining = self._decimal(payload.get("remaining_weight", weight))
                cursor.execute(
                    """
                    UPDATE Inventory
                    SET item_type = 'WEIGHT',
                        weight = %s,
                        remaining_weight = %s,
                        quantity = 1,
                        remaining_quantity = 1
                    WHERE id = %s
                    """,
                    (float(weight), float(remaining), inventory_id),
                )
                new_payload.update({"weight": float(weight), "remaining_weight": float(remaining)})

            elif action == "UPDATE_QUANTITY":
                if not inventory_id:
                    raise ValueError("UPDATE_QUANTITY requires an inventory item.")
                quantity = max(0, int(payload.get("quantity", payload.get("remaining_quantity", 0)) or 0))
                remaining = max(0, int(payload.get("remaining_quantity", quantity) or 0))
                cursor.execute(
                    """
                    UPDATE Inventory
                    SET item_type = 'PIECE',
                        quantity = %s,
                        remaining_quantity = %s,
                        weight = NULL,
                        remaining_weight = NULL
                    WHERE id = %s
                    """,
                    (quantity, remaining, inventory_id),
                )
                new_payload.update({"quantity": quantity, "remaining_quantity": remaining})

            elif action == "UPDATE_LOCATION":
                if not inventory_id:
                    raise ValueError("UPDATE_LOCATION requires an inventory item.")
                location_id = self._positive_id(payload.get("location_id"))
                cursor.execute(
                    "UPDATE Inventory SET location_id = %s WHERE id = %s",
                    (location_id, inventory_id),
                )
                new_payload.update({"location_id": location_id})

            elif action == "CREATE_INVENTORY":
                if not extra_item:
                    raise ValueError("CREATE_INVENTORY requires an extra physical item.")
                inventory_id = self._create_inventory_from_extra(cursor, extra_item, payload)
                cursor.execute(
                    """
                    UPDATE InventoryCountExtraItems
                    SET status = 'LINKED',
                        linked_inventory_id = %s
                    WHERE id = %s
                    """,
                    (inventory_id, extra_item_id),
                )
                new_payload.update({"created_inventory_id": inventory_id})

            elif action == "IGNORE":
                if extra_item_id:
                    cursor.execute(
                        "UPDATE InventoryCountExtraItems SET status = 'IGNORED' WHERE id = %s",
                        (extra_item_id,),
                    )
                if count_item_id:
                    cursor.execute(
                        """
                        UPDATE InventoryCountItems
                        SET count_status = 'IGNORED',
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (count_item_id,),
                    )

            adjustment_id = self._insert_adjustment(
                cursor,
                count_id=count_id,
                action_type=action,
                count_item_id=count_item_id,
                extra_item_id=extra_item_id,
                inventory_id=inventory_id,
                previous_payload=previous_payload,
                new_payload=new_payload,
                user_id=user_id,
                notes=notes,
                applied=True,
            )
            self._refresh_session_summary(cursor, count_id)
            conn.commit()
            return adjustment_id
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error applying inventory count adjustment %s: %s", count_id, exc)
            return None
        finally:
            if conn:
                conn.close()

    def _insert_adjustment(
        self,
        cursor,
        count_id: int,
        action_type: str,
        count_item_id: Optional[int] = None,
        extra_item_id: Optional[int] = None,
        inventory_id: Optional[int] = None,
        previous_payload: Optional[Dict[str, Any]] = None,
        new_payload: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        notes: Optional[str] = None,
        applied: bool = False,
    ) -> int:
        cursor.execute(
            """
            INSERT INTO InventoryCountAdjustments
            (count_id, count_item_id, extra_item_id, inventory_id, action_type,
             previous_payload_json, new_payload_json, applied_by_user_id,
             applied_at, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s THEN NOW() ELSE NULL END, %s, NOW())
            """,
            (
                count_id,
                count_item_id,
                extra_item_id,
                inventory_id,
                self._normalize_adjustment_action(action_type),
                self._json_payload(previous_payload),
                self._json_payload(new_payload),
                user_id,
                applied,
                notes,
            ),
        )
        return int(cursor.lastrowid)

    def _fetch_inventory_payload(self, cursor, inventory_id: int) -> Optional[Dict[str, Any]]:
        cursor.execute(
            """
            SELECT id, barcode, name, category_id, metal_type_id, item_type,
                   weight, remaining_weight, quantity, remaining_quantity,
                   status, location_id, supplier_id
            FROM Inventory
            WHERE id = %s
            """,
            (inventory_id,),
        )
        return cursor.fetchone()

    def _create_inventory_from_extra(self, cursor, extra_item: Dict[str, Any], payload: Dict[str, Any]) -> int:
        item_type = self._normalize_item_type(payload.get("item_type") or extra_item.get("observed_item_type"))
        weight = None
        remaining_weight = None
        quantity = max(1, int(payload.get("quantity") or extra_item.get("observed_quantity") or 1))
        remaining_quantity = quantity
        if item_type == "WEIGHT":
            weight = float(self._decimal(payload.get("weight", extra_item.get("observed_weight"))))
            remaining_weight = float(self._decimal(payload.get("remaining_weight", weight)))
            quantity = 1
            remaining_quantity = 1
        cursor.execute(
            """
            INSERT INTO Inventory
            (barcode, name, category_id, metal_type_id, item_type, weight,
             remaining_weight, quantity, remaining_quantity, metal_cost_per_gram,
             labor_cost_per_gram, total_cost, initial_cost, profit_margin,
             margin_type, selling_price, location_id, supplier_id, image_url, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Available')
            """,
            (
                payload.get("barcode") or extra_item.get("observed_barcode"),
                payload.get("name") or extra_item.get("observed_name") or "Article inventaire",
                payload.get("category_id") or extra_item.get("category_id"),
                payload.get("metal_type_id") or extra_item.get("metal_type_id"),
                item_type,
                weight,
                remaining_weight,
                quantity,
                remaining_quantity,
                float(payload.get("metal_cost_per_gram") or 0),
                float(payload.get("labor_cost_per_gram") or 0),
                float(payload.get("total_cost") or 0),
                float(payload.get("initial_cost") or payload.get("total_cost") or 0),
                float(payload.get("profit_margin") or 0),
                payload.get("margin_type") or "FIXED",
                float(payload.get("selling_price") or 0),
                payload.get("location_id") or extra_item.get("location_id"),
                payload.get("supplier_id"),
                payload.get("image_url"),
            ),
        )
        return int(cursor.lastrowid)
