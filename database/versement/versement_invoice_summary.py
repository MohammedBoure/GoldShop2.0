"""Shared, side-effect-free payment data for completed Versement invoices."""

from __future__ import annotations

import re
from typing import Any, Iterable

from database.decimal_utils import CONVERSION_TOLERANCE, ZERO, to_decimal


_VERSEMENT_RECEIPT_RE = re.compile(r"^VRS-(\d+)$", re.IGNORECASE)


def _number(value: Any) -> float:
    return float(to_decimal(value))


def versement_id_from_receipt_number(receipt_number: Any) -> int | None:
    """Return the source Versement id for its final-invoice receipt number."""
    match = _VERSEMENT_RECEIPT_RE.fullmatch(str(receipt_number or "").strip())
    return int(match.group(1)) if match else None


def build_versement_payment_summary(
    payments: Iterable[dict[str, Any]],
    items_brut_total: float | None = None,
) -> dict[str, Any]:
    """Normalize all payment methods into the invoice amounts and history using exact Decimal."""
    dec_totals = {
        "cash_paid_da": ZERO,
        "tpe_paid_da": ZERO,
        "euro_paid": ZERO,
        "euro_equivalent_da": ZERO,
        "dollar_paid": ZERO,
        "dollar_equivalent_da": ZERO,
        "old_gold_weight_g": ZERO,
        "old_gold_equivalent_da": ZERO,
        "old_silver_weight_g": ZERO,
        "old_silver_equivalent_da": ZERO,
        "deducted_weight_g": ZERO,
        "total_remise_da": ZERO,
    }
    payment_history = []

    for payment in payments or []:
        raw_da = to_decimal(payment.get("montant_da"))
        tpe = to_decimal(payment.get("tpe_da"))
        euro = to_decimal(payment.get("montant_euro"))
        euro_rate = to_decimal(payment.get("taux_change_euro"))
        dollar = to_decimal(payment.get("montant_dollar"))
        dollar_rate = to_decimal(payment.get("taux_change_dollar"))
        old_gold = to_decimal(payment.get("or_casse_g"))
        old_gold_price = to_decimal(payment.get("prix_gramme_jour_da"))
        old_silver = to_decimal(payment.get("argent_casse_g"))
        old_silver_price = to_decimal(payment.get("prix_gramme_argent_jour_da"))
        deducted_weight = to_decimal(payment.get("poids_deduit_g"))
        remise = to_decimal(payment.get("remise_da"))

        euro_equivalent = euro * euro_rate
        dollar_equivalent = dollar * dollar_rate
        old_gold_equivalent = old_gold * old_gold_price
        old_silver_equivalent = old_silver * old_silver_price
        converted_sum = euro_equivalent + dollar_equivalent + old_gold_equivalent + old_silver_equivalent

        if converted_sum > ZERO and abs(raw_da - converted_sum) <= CONVERSION_TOLERANCE:
            pure_cash = ZERO
        elif converted_sum > ZERO and raw_da > converted_sum:
            pure_cash = raw_da - converted_sum
        elif converted_sum > ZERO:
            pure_cash = ZERO
        else:
            pure_cash = raw_da

        single_payment_total = (
            pure_cash + tpe + euro_equivalent + dollar_equivalent + old_gold_equivalent + old_silver_equivalent
        )

        dec_totals["cash_paid_da"] += pure_cash
        dec_totals["tpe_paid_da"] += tpe
        dec_totals["euro_paid"] += euro
        dec_totals["euro_equivalent_da"] += euro_equivalent
        dec_totals["dollar_paid"] += dollar
        dec_totals["dollar_equivalent_da"] += dollar_equivalent
        dec_totals["old_gold_weight_g"] += old_gold
        dec_totals["old_gold_equivalent_da"] += old_gold_equivalent
        dec_totals["old_silver_weight_g"] += old_silver
        dec_totals["old_silver_equivalent_da"] += old_silver_equivalent
        dec_totals["deducted_weight_g"] += deducted_weight
        dec_totals["total_remise_da"] += remise

        payment_history.append({
            "id": payment.get("id"),
            "payment_date": payment.get("payment_date"),
            "cash_paid_da": float(pure_cash),
            "tpe_paid_da": float(tpe),
            "euro_paid": float(euro),
            "euro_rate": float(euro_rate),
            "euro_equivalent_da": float(euro_equivalent),
            "dollar_paid": float(dollar),
            "dollar_rate": float(dollar_rate),
            "dollar_equivalent_da": float(dollar_equivalent),
            "old_gold_weight_g": float(old_gold),
            "old_gold_equivalent_da": float(old_gold_equivalent),
            "old_silver_weight_g": float(old_silver),
            "old_silver_equivalent_da": float(old_silver_equivalent),
            "deducted_weight_g": float(deducted_weight),
            "remise_da": float(remise),
            "amount": float(single_payment_total),
            "notes": str(payment.get("notes") or "").strip(),
            "product_name": str(payment.get("item_designation") or "").strip(),
        })

    total_paid_da = (
        dec_totals["cash_paid_da"]
        + dec_totals["tpe_paid_da"]
        + dec_totals["euro_equivalent_da"]
        + dec_totals["dollar_equivalent_da"]
        + dec_totals["old_gold_equivalent_da"]
        + dec_totals["old_silver_equivalent_da"]
    )
    items_total = to_decimal(items_brut_total)
    total_remise_da = dec_totals["total_remise_da"]
    if items_total > ZERO and total_remise_da > ZERO:
        if total_paid_da <= items_total:
            total_remise_da = min(total_remise_da, max(ZERO, items_total - total_paid_da))
        else:
            total_remise_da = ZERO

    result = {k: float(v) for k, v in dec_totals.items()}
    result["total_remise_da"] = float(total_remise_da)
    result["total_paid_da"] = float(total_paid_da)
    result["total_brut_da"] = float(total_paid_da + total_remise_da)
    result["net_to_pay_da"] = float(total_paid_da)
    result["payment_history"] = payment_history
    result["payment_count"] = len(payment_history)
    return result
