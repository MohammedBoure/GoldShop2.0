"""Shared pricing calculations for Versement discounts and payment rates."""

from __future__ import annotations

from typing import Any, Iterable


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def payment_value_da(payment: dict[str, Any]) -> float:
    """Return one payment's DA equivalent without double-counting conversions."""
    declared_da = number(payment.get("montant_da"))
    tpe_da = number(payment.get("tpe_da"))
    euro_equivalent = number(payment.get("montant_euro")) * number(
        payment.get("taux_change_euro")
    )
    dollar_equivalent = number(payment.get("montant_dollar")) * number(
        payment.get("taux_change_dollar")
    )
    old_gold_equivalent = number(payment.get("or_casse_g")) * number(
        payment.get("prix_gramme_jour_da")
    )
    converted_equivalent = euro_equivalent + dollar_equivalent + old_gold_equivalent

    if converted_equivalent > 0 and abs(declared_da - converted_equivalent) <= 0.01:
        base_da = declared_da
    else:
        base_da = declared_da + converted_equivalent
    return base_da + tpe_da


def shop_price_per_gram(
    items: Iterable[dict[str, Any]], item_id: Any = None
) -> float:
    """Return the list/shop price per gram for one item or the active dossier."""
    rows = [row for row in (items or []) if row.get("item_status") != "ANNULE"]
    if item_id is not None:
        selected = next(
            (
                row
                for row in rows
                if row.get("item_id", row.get("id")) == item_id
            ),
            None,
        )
        if selected:
            weight = number(selected.get("weight"))
            price = number(selected.get("selling_price"))
            return price / weight if price > 0 and weight > 0 else 0.0

    total_weight = sum(number(row.get("weight")) for row in rows)
    total_price = sum(number(row.get("selling_price")) for row in rows)
    return total_price / total_weight if total_price > 0 and total_weight > 0 else 0.0


def discount_for_target_price(
    shop_price: Any,
    target_price: Any,
    payment_da: Any,
    available_weight: Any = None,
) -> tuple[float, float]:
    """Return ``(discount_da, deducted_weight_g)`` for a target DA/g price."""
    shop = number(shop_price)
    target = number(target_price)
    payment = max(0.0, number(payment_da))
    if shop <= 0 or target <= 0 or payment <= 0:
        return 0.0, 0.0

    target = min(target, shop)
    deducted_weight = payment / target
    if available_weight is not None:
        deducted_weight = min(deducted_weight, max(0.0, number(available_weight)))

    discount = max(0.0, shop * deducted_weight - payment)
    return discount, deducted_weight


def price_after_discount(shop_price: Any, payment_da: Any, discount_da: Any) -> float:
    """Return the effective DA/g rate implied by a stored monetary discount."""
    shop = number(shop_price)
    payment = max(0.0, number(payment_da))
    discount = max(0.0, number(discount_da))
    gross_equivalent = payment + discount
    if shop <= 0 or payment <= 0 or gross_equivalent <= 0:
        return 0.0
    return shop * payment / gross_equivalent
