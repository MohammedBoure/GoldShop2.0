"""Pure accounting helpers shared by sales and report views."""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any, Iterable

from database.decimal_utils import CONVERSION_TOLERANCE, ZERO, to_decimal


_VRS_REFERENCE_RE = re.compile(r"\bVRS[-\s]?(\d+)\b", re.IGNORECASE)


def number(value: Any) -> float:
    return float(to_decimal(value))


def source_versement_id(receipt_number: Any = "", notes: Any = "") -> int | None:
    """Extract a source Versement id from a final or individual invoice."""
    for value in (receipt_number, notes):
        match = _VRS_REFERENCE_RE.search(str(value or ""))
        if match:
            return int(match.group(1))
    return None


def payment_amount_da(payment: dict[str, Any]) -> float:
    """Return the DA value actually paid by the customer for one payment."""
    declared_da = to_decimal(payment.get("montant_da"))
    tpe_da = to_decimal(payment.get("tpe_da"))
    euro_equivalent = to_decimal(payment.get("montant_euro")) * to_decimal(payment.get("taux_change_euro"))
    dollar_equivalent = to_decimal(payment.get("montant_dollar")) * to_decimal(payment.get("taux_change_dollar"))
    old_gold_equivalent = (
        to_decimal(payment.get("or_casse_g", payment.get("old_gold_weight_g")))
        * to_decimal(payment.get("prix_gramme_jour_da", payment.get("old_gold_price_da", payment.get("gold_price_da"))))
    )
    old_silver_equivalent = (
        to_decimal(payment.get("argent_casse_g", payment.get("old_silver_weight_g")))
        * to_decimal(payment.get("prix_gramme_argent_jour_da", payment.get("old_silver_price_da", payment.get("silver_price_da"))))
    )
    computed_equivalent = euro_equivalent + dollar_equivalent + old_gold_equivalent + old_silver_equivalent

    if computed_equivalent > ZERO and abs(declared_da - computed_equivalent) <= CONVERSION_TOLERANCE:
        main_payment = declared_da
    else:
        main_payment = declared_da + euro_equivalent + dollar_equivalent

    return float(main_payment + tpe_da)


def allocation_shares(records: Iterable[dict[str, Any]]) -> list[float]:
    """Share an amount by sold weight, then quantity, then equally."""
    rows = list(records or [])
    if not rows:
        return []

    bases: list[Decimal] = []
    for row in rows:
        weight = to_decimal(row.get("sold_weight_g", row.get("inventory_weight", row.get("weight"))))
        quantity = to_decimal(row.get("sold_quantity", row.get("inventory_quantity", row.get("quantity"))))
        bases.append(weight if weight > ZERO else max(ZERO, quantity))

    total = sum(bases, ZERO)
    if total > ZERO:
        return [float(basis / total) for basis in bases]
    share = Decimal(1) / Decimal(len(rows))
    return [float(share)] * len(rows)


def item_cost_da(item: dict[str, Any]) -> float:
    """Return the historical acquisition cost of a sold item."""
    item_type = str(item.get("item_type") or "WEIGHT").upper()
    initial_cost = to_decimal(item.get("inventory_initial_cost", item.get("initial_cost")))
    sold_weight = to_decimal(item.get("sold_weight_g"))
    sold_quantity = to_decimal(item.get("sold_quantity"))
    inventory_weight = to_decimal(item.get("inventory_weight", item.get("weight")))
    inventory_quantity = to_decimal(item.get("inventory_quantity", item.get("quantity")))

    if initial_cost > ZERO:
        if item_type == "WEIGHT" and inventory_weight > ZERO:
            return float(initial_cost * sold_weight / inventory_weight)
        if item_type != "WEIGHT" and inventory_quantity > ZERO:
            return float(initial_cost * sold_quantity / inventory_quantity)
        if item_type == "WEIGHT" and sold_weight > ZERO:
            return float(initial_cost)
        if item_type != "WEIGHT" and sold_quantity > ZERO:
            return float(initial_cost)

    cost_per_unit = to_decimal(item.get("metal_cost_per_gram", item.get("m_cost"))) + to_decimal(
        item.get("labor_cost_per_gram", item.get("l_cost"))
    )
    return float(cost_per_unit * (sold_weight if item_type == "WEIGHT" else sold_quantity))


def direct_sale_revenues(items: Iterable[dict[str, Any]], discount_da: Any) -> list[float]:
    """Allocate a sale-level discount to its item revenues."""
    rows = list(items or [])
    gross = [to_decimal(row.get("total_price_da", row.get("cart_line_total"))) for row in rows]
    total_gross = sum(gross, ZERO)
    if total_gross <= ZERO:
        return [float(v) for v in gross]
    discount = max(ZERO, min(to_decimal(discount_da), total_gross))
    return [float(value - (discount * value / total_gross)) for value in gross]


def versement_revenues_by_inventory(
    source_items: Iterable[dict[str, Any]], payments: Iterable[dict[str, Any]]
) -> dict[Any, float]:
    """Map actual Versement payments to inventory products."""
    products = [row for row in (source_items or []) if row.get("inventory_id") is not None]
    if not products:
        return {}

    result: dict[Any, Decimal] = defaultdict(lambda: ZERO)
    valid_inventory_ids = {row.get("inventory_id") for row in products}
    unassigned = ZERO
    for payment in payments or []:
        amount = to_decimal(payment_amount_da(payment))
        target_inventory_id = payment.get("payment_inventory_id")
        if target_inventory_id in valid_inventory_ids:
            result[target_inventory_id] += amount
        else:
            unassigned += amount

    if unassigned:
        for row, share in zip(products, allocation_shares(products)):
            result[row.get("inventory_id")] += unassigned * to_decimal(share)
    return {k: float(v) for k, v in result.items()}
