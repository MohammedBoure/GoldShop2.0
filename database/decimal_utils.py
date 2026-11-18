"""Shared Decimal conversion and quantization helpers for monetary and weight math."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

ZERO = Decimal("0")
MONEY_QUANT = Decimal("0.01")
WEIGHT_QUANT = Decimal("0.001")
WEIGHT_TOLERANCE = Decimal("0.005")
CONVERSION_TOLERANCE = Decimal("0.01")
EPSILON = Decimal("0.000001")


def to_decimal(value: Any, default: Decimal = ZERO) -> Decimal:
    """Convert numeric or string values to exact Decimal without float drift."""
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value if value.is_finite() else default
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, int):
        return Decimal(value)
    try:
        text_val = str(value).strip().replace(" ", "")
        if not text_val:
            return default
        dec = Decimal(text_val)
        return dec if dec.is_finite() else default
    except (InvalidOperation, ValueError, TypeError):
        return default


def quantize_money(value: Any) -> Decimal:
    """Round monetary amount to 2 decimal places using half-up accounting rounding."""
    return to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantize_weight(value: Any) -> Decimal:
    """Round weight in grams to 3 decimal places using half-up rounding."""
    return to_decimal(value).quantize(WEIGHT_QUANT, rounding=ROUND_HALF_UP)


def to_money_float(value: Any) -> float:
    return float(quantize_money(value))


def to_weight_float(value: Any) -> float:
    return float(quantize_weight(value))
