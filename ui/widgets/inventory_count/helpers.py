from __future__ import annotations

from typing import Any, Dict

SESSION_STATUSES = [
    ("Tous", None),
    ("Brouillon", "DRAFT"),
    ("Comptage", "COUNTING"),
    ("Revue", "REVIEW"),
    ("Cloture", "CLOSED"),
    ("Annule", "CANCELLED"),
]

SESSION_TARGET_STATUSES = [
    ("Brouillon", "DRAFT"),
    ("Comptage", "COUNTING"),
    ("Revue", "REVIEW"),
    ("Cloture", "CLOSED"),
    ("Annule", "CANCELLED"),
]

ITEM_STATUSES = [
    ("Tous", None),
    ("Deja controles", "__CHECKED__"),
    ("Non compte", "NOT_COUNTED"),
    ("Trouve", "FOUND"),
    ("Manquant", "MISSING"),
    ("Different", "DIFFERENT"),
    ("Ignore", "IGNORED"),
]

EXTRA_STATUSES = [
    ("Tous", None),
    ("Nouveau", "NEW"),
    ("Lie au stock", "LINKED"),
    ("Ignore", "IGNORED"),
]

ITEM_TYPE_LABELS = {"WEIGHT": "Poids", "PIECE": "Piece"}
SESSION_STATUS_LABELS = {
    "DRAFT": "Brouillon",
    "COUNTING": "Comptage",
    "REVIEW": "Revue",
    "CLOSED": "Cloture",
    "CANCELLED": "Annule",
}
ITEM_STATUS_LABELS = {
    "NOT_COUNTED": "Non compte",
    "FOUND": "Trouve",
    "MISSING": "Manquant",
    "DIFFERENT": "Different",
    "IGNORED": "Ignore",
}
CHECKED_ITEM_STATUSES = {"FOUND", "MISSING", "DIFFERENT", "IGNORED"}


def _as_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_weight(value) -> str:
    return f"{_as_float(value):,.3f} g"


def _fmt_qty(value) -> str:
    return f"{_as_int(value)} pcs"


def _fmt_money(value) -> str:
    return f"{_as_float(value):,.2f} DA"


def _fmt_margin(value, margin_type=None) -> str:
    if str(margin_type or "").upper() == "PERCENTAGE":
        return f"{_as_float(value):,.2f} %"
    return _fmt_money(value)


def _item_measure(row: Dict[str, Any], prefix: str) -> str:
    item_type = str(row.get(f"{prefix}_item_type") or row.get("snapshot_item_type") or "WEIGHT").upper()
    if item_type == "PIECE":
        return _fmt_qty(row.get(f"{prefix}_quantity") or row.get("expected_remaining_quantity"))
    return _fmt_weight(row.get(f"{prefix}_weight") or row.get("expected_remaining_weight"))


def _metal_label(row: Dict[str, Any]) -> str:
    name = str(row.get("metal_type_name") or "").strip()
    purity = row.get("metal_purity_value")
    if name and purity not in (None, ""):
        return f"{name} ({_as_float(purity):.1f})"
    return name or str(row.get("snapshot_metal_type_id") or row.get("metal_type_id") or "-")
