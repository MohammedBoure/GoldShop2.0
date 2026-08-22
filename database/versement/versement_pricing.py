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


def _distribute_amount_equally(
    amount: float,
    item_records: list[dict[str, Any]],
    field_allocated: str,
    field_cap: str,
) -> None:
    """Distribute amount equally among candidate items up to each item's capacity, transferring surplus to the next incomplete items."""
    remaining_amount = max(0.0, float(amount or 0.0))
    if remaining_amount <= 1e-6:
        return

    while remaining_amount > 1e-6:
        candidates = [
            r for r in item_records
            if r.get("item_status") == "EN_COURS" and (r[field_cap] - r[field_allocated]) > 1e-6
        ]
        if not candidates:
            break

        equal_share = remaining_amount / len(candidates)
        capped = [
            r for r in candidates
            if (r[field_cap] - r[field_allocated]) < equal_share - 1e-6
        ]
        if not capped:
            for r in candidates:
                r[field_allocated] += equal_share
            remaining_amount = 0.0
            break
        else:
            for r in capped:
                capacity = r[field_cap] - r[field_allocated]
                r[field_allocated] += capacity
                remaining_amount -= capacity


def calculate_versement_item_balances(
    items: Iterable[dict[str, Any]],
    payments: Iterable[dict[str, Any]],
) -> dict[Any, dict[str, Any]]:
    """Calculate deducted weight, remaining weight, paid money, and balance for each item.

    Financial value and deducted weights for global payments are divided equally among
    active incomplete products. When an item reaches 100% completion, remaining amounts
    automatically transfer to the next incomplete products.
    """
    item_records = []
    item_map = {}

    for item in items or []:
        status = item.get("item_status", "EN_COURS")
        if status == "ANNULE":
            continue
        item_id = item.get("item_id", item.get("id"))
        weight = float(item.get("display_weight") or item.get("weight") or 0.0)
        price = float(item.get("display_price") or item.get("selling_price") or 0.0)

        record = {
            "item_id": item_id,
            "item_status": status,
            "weight": weight,
            "selling_price": price,
            "deducted_g": 0.0,
            "paid_da": 0.0,
            "has_shared": False,
        }
        item_records.append(record)
        if item_id is not None:
            item_map[item_id] = record
            item_map[str(item_id)] = record

    for p in payments or []:
        w_pay = max(0.0, number(p.get("poids_deduit_g")))
        m_pay = max(0.0, payment_value_da(p))
        target_id = p.get("versement_item_id")

        if target_id is not None and target_id in item_map:
            target = item_map[target_id]
            rem_w = max(0.0, target["weight"] - target["deducted_g"])
            rem_m = max(0.0, target["selling_price"] - target["paid_da"])

            w_alloc = min(w_pay, rem_w)
            m_alloc = min(m_pay, rem_m)
            target["deducted_g"] += w_alloc
            target["paid_da"] += m_alloc

            w_surplus = w_pay - w_alloc
            m_surplus = m_pay - m_alloc

            if w_surplus > 1e-6:
                other_candidates = [r for r in item_records if r["item_id"] != target["item_id"]]
                _distribute_amount_equally(w_surplus, other_candidates, "deducted_g", "weight")
            if m_surplus > 1e-6:
                other_candidates = [r for r in item_records if r["item_id"] != target["item_id"]]
                _distribute_amount_equally(m_surplus, other_candidates, "paid_da", "selling_price")
        else:
            if w_pay > 1e-6:
                _distribute_amount_equally(w_pay, item_records, "deducted_g", "weight")
                for r in item_records:
                    if r.get("item_status") == "EN_COURS":
                        r["has_shared"] = True
            if m_pay > 1e-6:
                _distribute_amount_equally(m_pay, item_records, "paid_da", "selling_price")
                for r in item_records:
                    if r.get("item_status") == "EN_COURS":
                        r["has_shared"] = True

    result = {}
    for r in item_records:
        r["deducted_g"] = min(r["weight"], r["deducted_g"])
        r["remaining_g"] = max(0.0, r["weight"] - r["deducted_g"])
        r["paid_da"] = min(r["selling_price"], r["paid_da"])
        r["remaining_da"] = max(0.0, r["selling_price"] - r["paid_da"])
        result[r["item_id"]] = r

    for item in items or []:
        if item.get("item_status") == "ANNULE":
            item_id = item.get("item_id", item.get("id"))
            if item_id is not None:
                result[item_id] = {
                    "item_id": item_id,
                    "item_status": "ANNULE",
                    "weight": 0.0,
                    "selling_price": 0.0,
                    "deducted_g": 0.0,
                    "remaining_g": 0.0,
                    "paid_da": 0.0,
                    "remaining_da": 0.0,
                    "has_shared": False,
                }

    return result

