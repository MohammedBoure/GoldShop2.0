"""Shared helpers for inventory count managers."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple


COUNT_NUMBER_PREFIX = "INV-CNT"

SESSION_STATUSES = {"DRAFT", "COUNTING", "REVIEW", "CLOSED", "CANCELLED"}
OPEN_SESSION_STATUSES = {"DRAFT", "COUNTING", "REVIEW"}
ITEM_STATUSES = {"NOT_COUNTED", "FOUND", "MISSING", "DIFFERENT", "IGNORED"}
EXTRA_STATUSES = {"NEW", "LINKED", "IGNORED"}
COUNT_METHODS = {"BARCODE", "MANUAL", "IMPORT"}
ADJUSTMENT_ACTIONS = {
    "MARK_LOST",
    "UPDATE_WEIGHT",
    "UPDATE_QUANTITY",
    "UPDATE_LOCATION",
    "CREATE_INVENTORY",
    "IGNORE",
}

EXPECTED_STOCK_STATUSES = ("Available", "Partially_Sold", "Reserved", "Scrap", "Repair")


class InventoryCountBaseMixin:
    @staticmethod
    def _decimal(value, places: str = "0.001") -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal(places))

    @staticmethod
    def _positive_id(value) -> Optional[int]:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _row_value(row, key: str, index: int, default=None):
        if not row:
            return default
        if isinstance(row, dict):
            return row.get(key, default)
        try:
            return row[index]
        except (TypeError, IndexError):
            return default

    @staticmethod
    def _json_payload(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _normalize_status(value: str, allowed: set, default: str) -> str:
        normalized = str(value or default).strip().upper()
        if normalized not in allowed:
            raise ValueError(f"Unsupported inventory count status: {value}")
        return normalized

    @classmethod
    def _normalize_session_status(cls, status: str, default: str = "DRAFT") -> str:
        return cls._normalize_status(status, SESSION_STATUSES, default)

    @classmethod
    def _normalize_item_status(cls, status: str, default: str = "NOT_COUNTED") -> str:
        return cls._normalize_status(status, ITEM_STATUSES, default)

    @classmethod
    def _normalize_extra_status(cls, status: str, default: str = "NEW") -> str:
        return cls._normalize_status(status, EXTRA_STATUSES, default)

    @classmethod
    def _normalize_count_method(cls, method: str, default: str = "MANUAL") -> str:
        return cls._normalize_status(method, COUNT_METHODS, default)

    @classmethod
    def _normalize_adjustment_action(cls, action: str) -> str:
        return cls._normalize_status(action, ADJUSTMENT_ACTIONS, "IGNORE")

    @staticmethod
    def _normalize_item_type(item_type: str) -> str:
        normalized = str(item_type or "WEIGHT").strip().upper()
        return "PIECE" if normalized in {"PIECE", "UNIT", "PCS"} else "WEIGHT"

    @staticmethod
    def format_count_number(sequence=None, count_number: str = "") -> str:
        text = str(count_number or "").strip()
        if text:
            return text
        try:
            seq = int(sequence or 0)
        except (TypeError, ValueError):
            return ""
        return f"{COUNT_NUMBER_PREFIX}-{seq:06d}" if seq > 0 else ""

    @classmethod
    def normalize_session_number(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(row, dict):
            row["count_number"] = cls.format_count_number(
                row.get("count_sequence"),
                row.get("count_number", ""),
            )
            row["display_number"] = row["count_number"]
        return row

    @classmethod
    def _reserve_count_number(cls, cursor) -> Tuple[int, str]:
        cursor.execute(
            """
            INSERT INTO InventoryCountDocumentSequence (id, last_value, updated_at)
            VALUES (1, LAST_INSERT_ID(1), NOW())
            ON DUPLICATE KEY UPDATE
                last_value = LAST_INSERT_ID(last_value + 1),
                updated_at = NOW()
            """
        )
        cursor.execute("SELECT LAST_INSERT_ID() AS count_sequence")
        row = cursor.fetchone()
        sequence = cls._row_value(row, "count_sequence", 0, None)
        if not sequence:
            sequence = getattr(cursor, "lastrowid", None)
        sequence = int(sequence or 1)
        return sequence, cls.format_count_number(sequence)

    @classmethod
    def _item_difference_status(cls, row: Dict[str, Any], counted_weight=None, counted_quantity=None) -> str:
        item_type = cls._normalize_item_type(row.get("snapshot_item_type"))
        if item_type == "PIECE":
            expected = int(row.get("expected_remaining_quantity") or 0)
            counted = int(counted_quantity if counted_quantity is not None else expected)
            return "FOUND" if counted == expected else "DIFFERENT"

        expected_weight = cls._decimal(row.get("expected_remaining_weight"))
        counted = cls._decimal(counted_weight if counted_weight is not None else expected_weight)
        return "FOUND" if abs(counted - expected_weight) <= Decimal("0.001") else "DIFFERENT"
