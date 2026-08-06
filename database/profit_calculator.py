"""Pure accounting helpers shared by sales and report views."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable


_VRS_REFERENCE_RE = re.compile(r"\bVRS[-\s]?(\d+)\b", re.IGNORECASE)


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def source_versement_id(receipt_number: Any = "", notes: Any = "") -> int | None:
    """Extract a source Versement id from a final or individual invoice."""
    for value in (receipt_number, notes):
        match = _VRS_REFERENCE_RE.search(str(value or ""))
        if match:
            return int(match.group(1))
    return None


def payment_amount_da(payment: dict[str, Any]) -> float:
    """Return the DA value actually paid by the customer for one payment.

    The Versement dialog fills montant_da with the DA equivalent when a
    payment uses euro, dollar, or old gold. That value must therefore not be
    added a second time. A deliberately entered cash amount remains
    distinguishable because it differs from the computed equivalent; in that
    case both the cash amount and foreign-currency equivalent are counted.
    """
    declared_da = number(payment.get("montant_da"))
    tpe_da = number(payment.get("tpe_da"))
    euro_equivalent = number(payment.get("montant_euro")) * number(payment.get("taux_change_euro"))
    dollar_equivalent = number(payment.get("montant_dollar")) * number(payment.get("taux_change_dollar"))
    old_gold_equivalent = number(payment.get("or_casse_g")) * number(payment.get("prix_gramme_jour_da"))
    computed_equivalent = euro_equivalent + dollar_equivalent + old_gold_equivalent

    if computed_equivalent > 0 and abs(declared_da - computed_equivalent) <= 0.01:
        main_payment = declared_da
    else:
        main_payment = declared_da + euro_equivalent + dollar_equivalent

    return main_payment + tpe_da


def allocation_shares(records: Iterable[dict[str, Any]]) -> list[float]:
    """Share an amount by sold weight, then quantity, then equally."""
    rows = list(records or [])
    if not rows:
        return []

    bases: list[float] = []
    for row in rows:
        weight = number(row.get("sold_weight_g", row.get("inventory_weight", row.get("weight"))))
        quantity = number(row.get("sold_quantity", row.get("inventory_quantity", row.get("quantity"))))
        bases.append(weight if weight > 0 else max(0.0, quantity))

    total = sum(bases)
    if total > 0:
        return [basis / total for basis in bases]
    return [1.0 / len(rows)] * len(rows)


def item_cost_da(item: dict[str, Any]) -> float:
    """Return the historical acquisition cost of a sold item.

    ``Inventory.initial_cost`` is retained when a product's current gold cost
    is edited. It is therefore the primary source. Older records without it
    fall back to the current cost values as the best available legacy value.
    """
    item_type = str(item.get("item_type") or "WEIGHT").upper()
    initial_cost = number(item.get("inventory_initial_cost", item.get("initial_cost")))
    sold_weight = number(item.get("sold_weight_g"))
    sold_quantity = number(item.get("sold_quantity"))
    inventory_weight = number(item.get("inventory_weight", item.get("weight")))
    inventory_quantity = number(item.get("inventory_quantity", item.get("quantity")))

    if initial_cost > 0:
        if item_type == "WEIGHT" and inventory_weight > 0:
            return initial_cost * sold_weight / inventory_weight
        if item_type != "WEIGHT" and inventory_quantity > 0:
            return initial_cost * sold_quantity / inventory_quantity
        if item_type == "WEIGHT" and sold_weight > 0:
            return initial_cost
        if item_type != "WEIGHT" and sold_quantity > 0:
            return initial_cost

    cost_per_unit = number(item.get("metal_cost_per_gram", item.get("m_cost"))) + number(
        item.get("labor_cost_per_gram", item.get("l_cost"))
    )
    return cost_per_unit * (sold_weight if item_type == "WEIGHT" else sold_quantity)


def direct_sale_revenues(items: Iterable[dict[str, Any]], discount_da: Any) -> list[float]:
    """Allocate a sale-level discount to its item revenues."""
    rows = list(items or [])
    gross = [number(row.get("total_price_da", row.get("cart_line_total"))) for row in rows]
    total_gross = sum(gross)
    if total_gross <= 0:
        return gross
    discount = max(0.0, min(number(discount_da), total_gross))
    return [value - discount * value / total_gross for value in gross]


def versement_revenues_by_inventory(
    source_items: Iterable[dict[str, Any]], payments: Iterable[dict[str, Any]]
) -> dict[Any, float]:
    """Map actual Versement payments to inventory products.

    A targeted payment follows its linked Versement item. A dossier-level
    payment is distributed only across non-cancelled products by weight (or
    quantity when no weight exists). A remise is deliberately excluded: it is
    not money received and must not inflate realised profit.
    """
    products = [row for row in (source_items or []) if row.get("inventory_id") is not None]
    if not products:
        return {}

    result: dict[Any, float] = defaultdict(float)
    valid_inventory_ids = {row.get("inventory_id") for row in products}
    unassigned = 0.0
    for payment in payments or []:
        amount = payment_amount_da(payment)
        target_inventory_id = payment.get("payment_inventory_id")
        if target_inventory_id in valid_inventory_ids:
            result[target_inventory_id] += amount
        else:
            unassigned += amount

    if unassigned:
        for row, share in zip(products, allocation_shares(products)):
            result[row.get("inventory_id")] += unassigned * share
    return dict(result)
