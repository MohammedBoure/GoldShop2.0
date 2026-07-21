"""Shared reservation calculations for inventory and product versements."""

from __future__ import annotations

from typing import Any


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def normalize_reserved_quantity(item_type: Any, value: Any = 1) -> int:
    """Return a valid reservation quantity; weighted products always reserve one item."""
    if str(item_type or "WEIGHT").upper() != "PIECE":
        return 1
    quantity = as_int(value, 1)
    if quantity <= 0:
        raise ValueError("La quantité réservée doit être supérieure à zéro.")
    return quantity


def available_piece_quantity(remaining_quantity: Any, active_reserved_quantity: Any) -> int:
    return max(0, as_int(remaining_quantity) - as_int(active_reserved_quantity))


def is_piece_sellable(remaining_quantity: Any, active_reserved_quantity: Any) -> bool:
    return available_piece_quantity(remaining_quantity, active_reserved_quantity) > 0


def is_weight_sellable(remaining_weight: Any, active_reservation_count: Any) -> bool:
    return as_float(remaining_weight) > 0 and as_int(active_reservation_count) <= 0


def derived_inventory_status(
    item_type: Any,
    remaining_weight: Any,
    original_weight: Any,
    remaining_quantity: Any,
    original_quantity: Any,
) -> str:
    """Derive the stock status without using Reserved as a versement marker."""
    if str(item_type or "WEIGHT").upper() == "PIECE":
        remaining = as_int(remaining_quantity)
        original = as_int(original_quantity)
    else:
        remaining = as_float(remaining_weight)
        original = as_float(original_weight)

    if remaining <= 0:
        return "Sold"
    if original > 0 and remaining < original:
        return "Partially_Sold"
    return "Available"


def active_reserved_quantity_sql(alias: str = "i") -> str:
    return (
        "(SELECT COALESCE(SUM(COALESCE(vi.reserved_quantity, 1)), 0) "
        "FROM Versement_Items vi "
        f"WHERE vi.inventory_id = {alias}.id AND vi.item_status = 'EN_COURS')"
    )


def active_reservation_count_sql(alias: str = "i") -> str:
    return (
        "(SELECT COUNT(*) FROM Versement_Items vi "
        f"WHERE vi.inventory_id = {alias}.id AND vi.item_status = 'EN_COURS')"
    )


def sellable_stock_condition_sql(alias: str = "i") -> str:
    reserved_quantity = active_reserved_quantity_sql(alias)
    reservation_count = active_reservation_count_sql(alias)
    return f"""(
        (
            {alias}.item_type = 'PIECE'
            AND COALESCE({alias}.remaining_quantity, 0) - {reserved_quantity} > 0
        )
        OR
        (
            {alias}.item_type = 'WEIGHT'
            AND COALESCE({alias}.remaining_weight, 0) > 0
            AND {reservation_count} = 0
        )
    )
    AND (
        {alias}.status IN ('Available', 'Partially_Sold')
        OR (
            {alias}.status = 'Reserved'
            AND {alias}.reserved_for_client_id IS NULL
            AND {reservation_count} > 0
            AND {alias}.item_type = 'PIECE'
        )
    )"""
