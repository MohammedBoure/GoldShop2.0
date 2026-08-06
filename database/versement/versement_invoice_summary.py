"""Shared, side-effect-free payment data for completed Versement invoices."""

from __future__ import annotations

import re
from typing import Any, Iterable


_VERSEMENT_RECEIPT_RE = re.compile(r"^VRS-(\d+)$", re.IGNORECASE)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def versement_id_from_receipt_number(receipt_number: Any) -> int | None:
    """Return the source Versement id for its final-invoice receipt number."""
    match = _VERSEMENT_RECEIPT_RE.fullmatch(str(receipt_number or "").strip())
    return int(match.group(1)) if match else None


def build_versement_payment_summary(payments: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Normalize all payment methods into the invoice amounts and history.

    Foreign-currency payments are kept in their original currency and also
    converted to DA using the rate captured at the time of the payment.
    """
    totals = {
        "cash_paid_da": 0.0,
        "tpe_paid_da": 0.0,
        "euro_paid": 0.0,
        "euro_equivalent_da": 0.0,
        "dollar_paid": 0.0,
        "dollar_equivalent_da": 0.0,
        "old_gold_weight_g": 0.0,
        "deducted_weight_g": 0.0,
        "total_remise_da": 0.0,
        "payment_history": [],
    }

    for payment in payments or []:
        cash = _number(payment.get("montant_da"))
        tpe = _number(payment.get("tpe_da"))
        euro = _number(payment.get("montant_euro"))
        euro_rate = _number(payment.get("taux_change_euro"))
        dollar = _number(payment.get("montant_dollar"))
        dollar_rate = _number(payment.get("taux_change_dollar"))
        old_gold = _number(payment.get("or_casse_g"))
        deducted_weight = _number(payment.get("poids_deduit_g"))
        remise = _number(payment.get("remise_da"))
        euro_equivalent = euro * euro_rate
        dollar_equivalent = dollar * dollar_rate
        paid_equivalent = cash + tpe + euro_equivalent + dollar_equivalent

        totals["cash_paid_da"] += cash
        totals["tpe_paid_da"] += tpe
        totals["euro_paid"] += euro
        totals["euro_equivalent_da"] += euro_equivalent
        totals["dollar_paid"] += dollar
        totals["dollar_equivalent_da"] += dollar_equivalent
        totals["old_gold_weight_g"] += old_gold
        totals["deducted_weight_g"] += deducted_weight
        totals["total_remise_da"] += remise
        totals["payment_history"].append({
            "id": payment.get("id"),
            "payment_date": payment.get("payment_date"),
            "cash_paid_da": cash,
            "tpe_paid_da": tpe,
            "euro_paid": euro,
            "euro_rate": euro_rate,
            "euro_equivalent_da": euro_equivalent,
            "dollar_paid": dollar,
            "dollar_rate": dollar_rate,
            "dollar_equivalent_da": dollar_equivalent,
            "old_gold_weight_g": old_gold,
            "deducted_weight_g": deducted_weight,
            "remise_da": remise,
            "amount": paid_equivalent,
            "notes": str(payment.get("notes") or "").strip(),
            "product_name": str(payment.get("item_designation") or "").strip(),
        })

    totals["total_paid_da"] = (
        totals["cash_paid_da"]
        + totals["tpe_paid_da"]
        + totals["euro_equivalent_da"]
        + totals["dollar_equivalent_da"]
    )
    totals["total_brut_da"] = totals["total_paid_da"] + totals["total_remise_da"]
    totals["net_to_pay_da"] = totals["total_paid_da"]
    totals["payment_count"] = len(totals["payment_history"])
    return totals
