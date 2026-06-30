"""Inventory count session creation, lifecycle, and summaries."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from .base import EXPECTED_STOCK_STATUSES, OPEN_SESSION_STATUSES


class InventoryCountSessionMixin:
    def create_session(
        self,
        user_id: Optional[int] = None,
        notes: str = "",
        started_at=None,
        auto_snapshot: bool = True,
        allow_parallel: bool = False,
        include_statuses: Optional[Sequence[str]] = None,
    ) -> Optional[int]:
        """Create a full stock-count session and optionally snapshot current stock."""
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)

            if not allow_parallel:
                cursor.execute(
                    """
                    SELECT id
                    FROM InventoryCountSessions
                    WHERE status IN ('DRAFT', 'COUNTING', 'REVIEW')
                    ORDER BY started_at DESC, id DESC
                    LIMIT 1
                    FOR UPDATE
                    """
                )
                if cursor.fetchone():
                    conn.rollback()
                    return None

            sequence, number = self._reserve_count_number(cursor)
            cursor.execute(
                """
                INSERT INTO InventoryCountSessions
                (count_sequence, count_number, scope, status, started_at,
                 created_by_user_id, notes, created_at, updated_at)
                VALUES (%s, %s, 'FULL', 'DRAFT', COALESCE(%s, NOW()), %s, %s, NOW(), NOW())
                """,
                (sequence, number, started_at, user_id, notes),
            )
            count_id = int(cursor.lastrowid)
            if auto_snapshot:
                self._insert_inventory_snapshot(cursor, count_id, include_statuses=include_statuses)
                self._refresh_session_summary(cursor, count_id)

            conn.commit()
            return count_id
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error creating inventory count session: %s", exc)
            return None
        finally:
            if conn:
                conn.close()

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT *
                    FROM InventoryCountSessions
                    WHERE status IN ('DRAFT', 'COUNTING', 'REVIEW')
                    ORDER BY started_at DESC, id DESC
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                return self.normalize_session_number(row) if row else None
        except Exception as exc:
            logging.error("Error retrieving active inventory count session: %s", exc)
            return None

    def get_session(
        self,
        count_id: int,
        include_items: bool = False,
        include_extras: bool = False,
        include_adjustments: bool = False,
    ) -> Optional[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT s.*, cu.username AS created_by_username,
                           cu.full_name AS created_by_name,
                           cl.username AS closed_by_username,
                           cl.full_name AS closed_by_name
                    FROM InventoryCountSessions s
                    LEFT JOIN Users cu ON cu.id = s.created_by_user_id
                    LEFT JOIN Users cl ON cl.id = s.closed_by_user_id
                    WHERE s.id = %s
                    """,
                    (count_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                self.normalize_session_number(row)
                if include_items:
                    row["items"] = self.get_count_items(count_id)
                if include_extras:
                    row["extra_items"] = self.get_extra_items(count_id)
                if include_adjustments:
                    row["adjustments"] = self.get_adjustments(count_id)
                return row
        except Exception as exc:
            logging.error("Error retrieving inventory count session %s: %s", count_id, exc)
            return None

    def list_sessions(
        self,
        status: Optional[str] = None,
        search_text: str = "",
        start_date=None,
        end_date=None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        filters = []
        params: List[Any] = []
        if status:
            filters.append("s.status = %s")
            params.append(self._normalize_session_status(status))
        if start_date:
            filters.append("DATE(s.started_at) >= %s")
            params.append(start_date)
        if end_date:
            filters.append("DATE(s.started_at) <= %s")
            params.append(end_date)
        search_text = str(search_text or "").strip()
        if search_text:
            like = f"%{search_text}%"
            filters.append("(s.count_number LIKE %s OR s.notes LIKE %s)")
            params.extend([like, like])
        where = "WHERE " + " AND ".join(filters) if filters else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT s.*, cu.username AS created_by_username, cl.username AS closed_by_username
                    FROM InventoryCountSessions s
                    LEFT JOIN Users cu ON cu.id = s.created_by_user_id
                    LEFT JOIN Users cl ON cl.id = s.closed_by_user_id
                    {where}
                    ORDER BY s.started_at DESC, s.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params + [int(limit), int(offset)]),
                )
                rows = cursor.fetchall() or []
                for row in rows:
                    self.normalize_session_number(row)
                return rows
        except Exception as exc:
            logging.error("Error listing inventory count sessions: %s", exc)
            return []

    def set_session_status(self, count_id: int, status: str, user_id: Optional[int] = None) -> bool:
        normalized = self._normalize_session_status(status)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE InventoryCountSessions
                    SET status = %s,
                        closed_at = CASE WHEN %s = 'CLOSED' THEN NOW() ELSE closed_at END,
                        cancelled_at = CASE WHEN %s = 'CANCELLED' THEN NOW() ELSE cancelled_at END,
                        closed_by_user_id = CASE WHEN %s = 'CLOSED' THEN %s ELSE closed_by_user_id END,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (normalized, normalized, normalized, normalized, user_id, count_id),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error changing inventory count session %s status: %s", count_id, exc)
            return False

    def start_session(self, count_id: int) -> bool:
        return self.set_session_status(count_id, "COUNTING")

    def send_to_review(self, count_id: int, mark_unscanned_missing: bool = True) -> bool:
        return self._finish_counting_state(count_id, "REVIEW", mark_unscanned_missing=mark_unscanned_missing)

    def close_session(
        self,
        count_id: int,
        user_id: Optional[int] = None,
        mark_unscanned_missing: bool = True,
    ) -> bool:
        return self._finish_counting_state(
            count_id,
            "CLOSED",
            user_id=user_id,
            mark_unscanned_missing=mark_unscanned_missing,
        )

    def cancel_session(self, count_id: int, user_id: Optional[int] = None) -> bool:
        return self.set_session_status(count_id, "CANCELLED", user_id=user_id)

    def delete_draft_session(self, count_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM InventoryCountSessions
                    WHERE id = %s AND status = 'DRAFT'
                    """,
                    (count_id,),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error deleting draft inventory count session %s: %s", count_id, exc)
            return False

    def refresh_session_summary(self, count_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                self._refresh_session_summary(cursor, count_id)
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error refreshing inventory count summary %s: %s", count_id, exc)
            return False

    def _finish_counting_state(
        self,
        count_id: int,
        status: str,
        user_id: Optional[int] = None,
        mark_unscanned_missing: bool = True,
    ) -> bool:
        conn = None
        try:
            normalized = self._normalize_session_status(status)
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            if mark_unscanned_missing:
                self._insert_inventory_snapshot(cursor, count_id)
                cursor.execute(
                    """
                    UPDATE InventoryCountItems
                    SET count_status = 'MISSING',
                        counted_weight = 0,
                        counted_quantity = 0,
                        counted_at = COALESCE(counted_at, NOW()),
                        updated_at = NOW()
                    WHERE count_id = %s
                      AND count_status = 'NOT_COUNTED'
                    """,
                    (count_id,),
                )
            self._refresh_session_summary(cursor, count_id)
            cursor.execute(
                """
                UPDATE InventoryCountSessions
                SET status = %s,
                    closed_at = CASE WHEN %s = 'CLOSED' THEN NOW() ELSE closed_at END,
                    closed_by_user_id = CASE WHEN %s = 'CLOSED' THEN %s ELSE closed_by_user_id END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (normalized, normalized, normalized, user_id, count_id),
            )
            conn.commit()
            return True
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error finishing inventory count session %s: %s", count_id, exc)
            return False
        finally:
            if conn:
                conn.close()

    def _insert_inventory_snapshot(
        self,
        cursor,
        count_id: int,
        include_statuses: Optional[Sequence[str]] = None,
    ) -> None:
        statuses = tuple(include_statuses or EXPECTED_STOCK_STATUSES)
        status_filter = ""
        params: List[Any] = [count_id]
        if statuses:
            placeholders = ", ".join(["%s"] * len(statuses))
            status_filter = f"WHERE i.status IN ({placeholders})"
            params.extend(statuses)
        cursor.execute(
            f"""
            INSERT IGNORE INTO InventoryCountItems
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
            {status_filter}
            """,
            tuple(params),
        )

    def _refresh_session_summary(self, cursor, count_id: int) -> None:
        statuses = tuple(EXPECTED_STOCK_STATUSES)
        placeholders = ", ".join(["%s"] * len(statuses))
        cursor.execute(
            f"""
            UPDATE InventoryCountSessions s
            SET expected_item_count = (
                    SELECT COUNT(*)
                    FROM Inventory inv
                    WHERE inv.status IN ({placeholders})
                ),
                counted_item_count = (
                    SELECT COUNT(*) FROM InventoryCountItems i
                    WHERE i.count_id = s.id AND i.count_status <> 'NOT_COUNTED'
                ),
                matched_item_count = (
                    SELECT COUNT(*) FROM InventoryCountItems i
                    WHERE i.count_id = s.id AND i.count_status = 'FOUND'
                ),
                missing_item_count = (
                    SELECT COUNT(*) FROM InventoryCountItems i
                    WHERE i.count_id = s.id AND i.count_status = 'MISSING'
                ),
                different_item_count = (
                    SELECT COUNT(*) FROM InventoryCountItems i
                    WHERE i.count_id = s.id AND i.count_status = 'DIFFERENT'
                ),
                extra_item_count = (
                    SELECT COUNT(*) FROM InventoryCountExtraItems e
                    WHERE e.count_id = s.id AND e.status = 'NEW'
                ),
                expected_weight = COALESCE((
                    SELECT SUM(
                        CASE
                            WHEN COALESCE(inv.item_type, 'WEIGHT') = 'WEIGHT'
                                THEN COALESCE(inv.remaining_weight, inv.weight, 0)
                            ELSE 0
                        END
                    )
                    FROM Inventory inv
                    WHERE inv.status IN ({placeholders})
                ), 0),
                counted_weight = COALESCE((
                    SELECT SUM(
                        CASE
                            WHEN i.snapshot_item_type = 'WEIGHT'
                             AND i.count_status IN ('FOUND', 'DIFFERENT')
                                THEN COALESCE(i.counted_weight, i.expected_remaining_weight)
                            ELSE 0
                        END
                    )
                    FROM InventoryCountItems i
                    WHERE i.count_id = s.id
                ), 0) + COALESCE((
                    SELECT SUM(
                        CASE
                            WHEN e.observed_item_type = 'WEIGHT' AND e.status <> 'IGNORED'
                                THEN e.observed_weight
                            ELSE 0
                        END
                    )
                    FROM InventoryCountExtraItems e
                    WHERE e.count_id = s.id
                ), 0),
                updated_at = NOW()
            WHERE s.id = %s
            """,
            tuple(list(statuses) + list(statuses) + [count_id]),
        )
