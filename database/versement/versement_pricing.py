"""Shared pricing calculations for Versement discounts and payment rates."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from database.decimal_utils import CONVERSION_TOLERANCE, EPSILON, ZERO, to_decimal


def number(value: Any) -> float:
    return float(to_decimal(value))


def payment_value_da(payment: dict[str, Any]) -> float:
    """Return one payment's DA equivalent without double-counting conversions."""
    declared_da = to_decimal(payment.get("montant_da"))
    tpe_da = to_decimal(payment.get("tpe_da"))
    euro_equivalent = to_decimal(payment.get("montant_euro")) * to_decimal(
        payment.get("taux_change_euro")
    )
    dollar_equivalent = to_decimal(payment.get("montant_dollar")) * to_decimal(
        payment.get("taux_change_dollar")
    )
    old_gold_equivalent = to_decimal(payment.get("or_casse_g")) * to_decimal(
        payment.get("prix_gramme_jour_da")
    )
    old_silver_equivalent = to_decimal(payment.get("argent_casse_g")) * to_decimal(
        payment.get("prix_gramme_argent_jour_da")
    )
    converted_equivalent = (
        euro_equivalent + dollar_equivalent + old_gold_equivalent + old_silver_equivalent
    )

    if converted_equivalent > ZERO and abs(declared_da - converted_equivalent) <= CONVERSION_TOLERANCE:
        base_da = declared_da
    else:
        base_da = declared_da + converted_equivalent
    return float(base_da + tpe_da)


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
            weight = to_decimal(selected.get("weight"))
            price = to_decimal(selected.get("selling_price"))
            return float(price / weight) if price > ZERO and weight > ZERO else 0.0

    total_weight = sum((to_decimal(row.get("weight")) for row in rows), ZERO)
    total_price = sum((to_decimal(row.get("selling_price")) for row in rows), ZERO)
    return float(total_price / total_weight) if total_price > ZERO and total_weight > ZERO else 0.0


def discount_for_target_price(
    shop_price: Any,
    target_price: Any,
    payment_da: Any,
    available_weight: Any = None,
) -> tuple[float, float]:
    """Return ``(discount_da, deducted_weight_g)`` for a target DA/g price."""
    shop = to_decimal(shop_price)
    target = to_decimal(target_price)
    payment = max(ZERO, to_decimal(payment_da))
    if shop <= ZERO or target <= ZERO or payment <= ZERO:
        return 0.0, 0.0

    target = min(target, shop)
    deducted_weight = payment / target
    if available_weight is not None:
        deducted_weight = min(deducted_weight, max(ZERO, to_decimal(available_weight)))

    discount = max(ZERO, (shop * deducted_weight) - payment)
    return float(discount), float(deducted_weight)


def price_after_discount(shop_price: Any, payment_da: Any, discount_da: Any) -> float:
    """Return the effective DA/g rate implied by a stored monetary discount."""
    shop = to_decimal(shop_price)
    payment = max(ZERO, to_decimal(payment_da))
    discount = max(ZERO, to_decimal(discount_da))
    gross_equivalent = payment + discount
    if shop <= ZERO or payment <= ZERO or gross_equivalent <= ZERO:
        return 0.0
    return float(shop * payment / gross_equivalent)


def _distribute_amount_equally(
    amount: Decimal,
    item_records: list[dict[str, Any]],
    field_allocated: str,
    field_cap: str,
) -> None:
    """Distribute amount equally among candidate items up to each item's capacity using exact Decimal."""
    remaining_amount = max(ZERO, to_decimal(amount))
    if remaining_amount <= EPSILON:
        return

    while remaining_amount > EPSILON:
        candidates = [
            r for r in item_records
            if r.get("item_status") == "EN_COURS" and (r[field_cap] - r[field_allocated]) > EPSILON
        ]
        if not candidates:
            break

        equal_share = remaining_amount / Decimal(len(candidates))
        capped = [
            r for r in candidates
            if (r[field_cap] - r[field_allocated]) < equal_share - EPSILON
        ]
        if not capped:
            for r in candidates:
                r[field_allocated] += equal_share
            remaining_amount = ZERO
            break
        for r in capped:
            capacity = r[field_cap] - r[field_allocated]
            r[field_allocated] += capacity
            remaining_amount -= capacity


def calculate_versement_item_balances(
    items: Iterable[dict[str, Any]],
    payments: Iterable[dict[str, Any]],
) -> dict[Any, dict[str, Any]]:
    """Calculate deducted weight, remaining weight, paid money, and balance for each item."""
    item_records = []
    item_map = {}

    for item in items or []:
        status = item.get("item_status", "EN_COURS")
        if status == "ANNULE":
            continue
        item_id = item.get("item_id", item.get("id"))
        weight = to_decimal(item.get("display_weight") or item.get("weight"))
        price = to_decimal(item.get("display_price") or item.get("selling_price"))

        record = {
            "item_id": item_id,
            "item_status": status,
            "weight": weight,
            "selling_price": price,
            "deducted_g": ZERO,
            "paid_da": ZERO,
            "has_shared": False,
        }
        item_records.append(record)
        if item_id is not None:
            item_map[item_id] = record
            item_map[str(item_id)] = record

    for p in payments or []:
        w_pay = max(ZERO, to_decimal(p.get("poids_deduit_g")))
        m_pay = max(ZERO, to_decimal(payment_value_da(p)))
        target_id = p.get("versement_item_id")

        if target_id is not None and target_id in item_map:
            target = item_map[target_id]
            rem_w = max(ZERO, target["weight"] - target["deducted_g"])
            rem_m = max(ZERO, target["selling_price"] - target["paid_da"])

            w_alloc = min(w_pay, rem_w)
            m_alloc = min(m_pay, rem_m)
            target["deducted_g"] += w_alloc
            target["paid_da"] += m_alloc

            w_surplus = w_pay - w_alloc
            m_surplus = m_pay - m_alloc

            if w_surplus > EPSILON:
                other_candidates = [r for r in item_records if r["item_id"] != target["item_id"]]
                _distribute_amount_equally(w_surplus, other_candidates, "deducted_g", "weight")
            if m_surplus > EPSILON:
                other_candidates = [r for r in item_records if r["item_id"] != target["item_id"]]
                _distribute_amount_equally(m_surplus, other_candidates, "paid_da", "selling_price")
        else:
            if w_pay > EPSILON:
                _distribute_amount_equally(w_pay, item_records, "deducted_g", "weight")
                for r in item_records:
                    if r.get("item_status") == "EN_COURS":
                        r["has_shared"] = True
            if m_pay > EPSILON:
                _distribute_amount_equally(m_pay, item_records, "paid_da", "selling_price")
                for r in item_records:
                    if r.get("item_status") == "EN_COURS":
                        r["has_shared"] = True

    result = {}
    for r in item_records:
        deducted_g = min(r["weight"], r["deducted_g"])
        remaining_g = max(ZERO, r["weight"] - deducted_g)
        paid_da = min(r["selling_price"], r["paid_da"])
        remaining_da = max(ZERO, r["selling_price"] - paid_da)
        result[r["item_id"]] = {
            "item_id": r["item_id"],
            "item_status": r["item_status"],
            "weight": float(r["weight"]),
            "selling_price": float(r["selling_price"]),
            "deducted_g": float(deducted_g),
            "remaining_g": float(remaining_g),
            "paid_da": float(paid_da),
            "remaining_da": float(remaining_da),
            "has_shared": r["has_shared"],
        }

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


def calculate_versement_financial_summary(
    items: Iterable[dict[str, Any]],
    payments: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Compute dossier-level totals, net due, customer surplus/credit, and per-payment allocation."""
    active_items = [row for row in (items or []) if row.get("item_status") != "ANNULE"]
    total_weight_g = ZERO
    total_estimated_price_da = ZERO
    for item in active_items:
        item_type = str(item.get("item_type") or "WEIGHT").upper()
        qty = max(1, int(item.get("reserved_quantity") or 1)) if item_type == "PIECE" else 1
        w = to_decimal(item.get("display_weight"))
        if w <= ZERO:
            w = to_decimal(item.get("weight")) * (qty if item_type == "PIECE" else 1)
        p = to_decimal(item.get("display_price"))
        if p <= ZERO:
            p = to_decimal(item.get("selling_price")) * (qty if item_type == "PIECE" else 1)
        total_weight_g += max(ZERO, w)
        total_estimated_price_da += max(ZERO, p)

    payment_list = list(payments or [])
    total_paid_da = sum((to_decimal(payment_value_da(p)) for p in payment_list), ZERO)
    raw_remise_da = sum((to_decimal(p.get("remise_da")) for p in payment_list), ZERO)

    if total_estimated_price_da > ZERO:
        if raw_remise_da > ZERO and total_paid_da <= total_estimated_price_da:
            effective_remise_da = min(raw_remise_da, max(ZERO, total_estimated_price_da - total_paid_da))
        else:
            effective_remise_da = ZERO
        net_due_da = max(ZERO, total_estimated_price_da - effective_remise_da)
        allocated_paid_da = min(max(ZERO, total_paid_da), net_due_da)
        remaining_due_da = max(ZERO, net_due_da - max(ZERO, total_paid_da))
        surplus_da = max(ZERO, total_paid_da - net_due_da)
    else:
        effective_remise_da = raw_remise_da
        net_due_da = max(ZERO, total_paid_da)
        allocated_paid_da = max(ZERO, total_paid_da)
        remaining_due_da = ZERO
        surplus_da = ZERO

    per_payment: list[dict[str, Any]] = []
    remaining_net = net_due_da
    cum_surplus = ZERO
    for p in payment_list:
        val = to_decimal(payment_value_da(p))
        if total_estimated_price_da > ZERO:
            if val >= ZERO:
                alloc = min(val, remaining_net)
                surp = max(ZERO, val - alloc)
                remaining_net = max(ZERO, remaining_net - alloc)
                cum_surplus += surp
            else:
                refund = abs(val)
                from_surplus = min(refund, cum_surplus)
                from_alloc = refund - from_surplus
                cum_surplus -= from_surplus
                remaining_net += from_alloc
                alloc = -from_alloc
                surp = -from_surplus
        else:
            alloc = val
            surp = ZERO
        per_payment.append({
            "payment_id": p.get("id"),
            "value_da": float(val),
            "allocated_da": float(alloc),
            "surplus_da": float(surp),
        })

    return {
        "total_weight_g": float(total_weight_g),
        "total_estimated_price_da": float(total_estimated_price_da),
        "total_paid_da": float(total_paid_da),
        "raw_remise_da": float(raw_remise_da),
        "effective_remise_da": float(effective_remise_da),
        "net_due_da": float(net_due_da),
        "allocated_paid_da": float(allocated_paid_da),
        "remaining_due_da": float(remaining_due_da),
        "surplus_da": float(surplus_da),
        "per_payment": per_payment,
    }
