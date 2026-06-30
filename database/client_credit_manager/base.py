import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Optional


class ClientCreditBaseMixin:
    @staticmethod
    def _decimal(value, field_name: str) -> Decimal:
        try:
            amount = Decimal(str(value or 0))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {field_name}.") from exc
        if amount < 0:
            raise ValueError(f"{field_name} must be positive or zero.")
        return amount

    @staticmethod
    def _row_value(row, key: str, position: int = 0):
        if isinstance(row, dict):
            return row.get(key)
        return row[position] if row else None

    @staticmethod
    def _text(value) -> str:
        return "" if value is None else str(value).strip()

    @staticmethod
    def _json_payload(payload: Any) -> str:
        return json.dumps(payload or {}, ensure_ascii=False, default=str, sort_keys=True)

    @staticmethod
    def _json_object(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return dict(payload)
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def _normalized_payload(cls, row: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = dict(existing or cls._json_object(row.get("normalized_values")) or {})
        for key in ("inventory_id", "inventory_label", "inventory_barcode", "inventory_item_type"):
            if key in row:
                value = row.get(key)
                if key == "inventory_id" and value in (None, "", 0, "0"):
                    payload.pop(key, None)
                elif value not in (None, ""):
                    payload[key] = value
        return payload

    @classmethod
    def _with_normalized_values(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(row or {})
        normalized = cls._json_object(data.get("normalized_values_json"))
        data["normalized_values"] = normalized
        for key in (
            "inventory_id",
            "inventory_label",
            "inventory_barcode",
            "inventory_item_type",
            "price_per_gram_da",
            "paid_weight_g",
            "remaining_weight_g",
        ):
            if key in normalized and key not in data:
                data[key] = normalized.get(key)
        return data

    @classmethod
    def _with_live_published_balance(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        data = cls._with_normalized_values(row)
        if not data.get("published_sale_id"):
            return data

        live_final = data.get("live_final_amount_da")
        live_paid = data.get("live_paid_amount_da")
        live_paid_weight = data.get("live_paid_weight_g")
        live_remaining_weight = data.get("live_remaining_weight_g")
        live_total_weight = data.get("live_total_weight_g")
        if live_final is None and live_paid is None and live_remaining_weight is None:
            return data

        final_amount = cls._money(cls._decimal(live_final, "published credit total"))
        paid_amount = cls._money(cls._decimal(live_paid, "published credit paid amount"))
        remaining_amount = cls._money(max(final_amount - paid_amount, Decimal("0")))
        remaining_weight = cls._weight(cls._decimal(live_remaining_weight, "published credit remaining weight"))
        paid_weight = cls._weight(cls._decimal(live_paid_weight, "published credit paid weight"))
        total_weight = cls._weight(cls._decimal(live_total_weight, "published credit total weight"))

        data["amount_da"] = str(final_amount)
        data["paid_amount_da"] = str(paid_amount)
        data["remaining_amount_da"] = str(remaining_amount)
        data["weight_g"] = str(total_weight)
        data["paid_weight_g"] = str(paid_weight)
        data["remaining_weight_g"] = str(remaining_weight)
        data["payment_status"] = data.get("live_payment_status") or data.get("payment_status")

        normalized = dict(data.get("normalized_values") or {})
        normalized.update({
            "amount_da": str(final_amount),
            "paid_amount_da": str(paid_amount),
            "remaining_amount_da": str(remaining_amount),
            "weight_g": str(total_weight),
            "paid_weight_g": str(paid_weight),
            "remaining_weight_g": str(remaining_weight),
        })
        if total_weight > 0 and final_amount > 0:
            normalized["price_per_gram_da"] = str(cls._money(final_amount / total_weight))
        data["normalized_values"] = normalized
        for key in (
            "live_final_amount_da",
            "live_paid_amount_da",
            "live_paid_weight_g",
            "live_remaining_weight_g",
            "live_total_weight_g",
            "live_payment_status",
        ):
            data.pop(key, None)
        return data

    @staticmethod
    def _row_identity(row: Dict[str, Any]) -> str:
        identity = "{client}\x1f{date}\x1f{ref}\x1f{row}".format(
            client=row.get("client_id") or row.get("client_name") or row.get("Nom") or "",
            date=row.get("credit_date") or row.get("Dates") or "",
            ref=(
                row.get("source_ref")
                or row.get("legacy_source_ref")
                or row.get("NO")
                or row.get("object_description")
                or row.get("Objets")
                or ""
            ),
            row=row.get("row_number") or "",
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _format_date(value) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d 00:00:00")
        if value:
            return str(value)
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _weight(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def _price_per_gram(cls, amount: Decimal, weight: Decimal, fallback=None) -> Decimal:
        fallback_price = cls._decimal(fallback, "credit price per gram") if fallback not in (None, "") else Decimal("0")
        if fallback_price > 0:
            return fallback_price
        if amount > 0 and weight > 0:
            return cls._money(amount / weight)
        return Decimal("0")

    @classmethod
    def _credit_balance(
        cls,
        *,
        amount: Decimal,
        weight: Decimal,
        paid_amount: Decimal,
        paid_weight: Optional[Decimal] = None,
        remaining_amount: Optional[Decimal] = None,
        remaining_weight: Optional[Decimal] = None,
        price_per_gram: Optional[Decimal] = None,
    ) -> Dict[str, Decimal]:
        price = cls._price_per_gram(amount, weight, price_per_gram)
        remaining_amount = (
            cls._money(max(amount - paid_amount, Decimal("0")))
            if remaining_amount is None
            else cls._money(max(remaining_amount, Decimal("0")))
        )
        if paid_weight is None:
            paid_weight = (
                cls._weight(paid_amount / price)
                if price > 0 and paid_amount > 0
                else Decimal("0.000")
            )
        else:
            paid_weight = cls._weight(max(paid_weight, Decimal("0")))

        if remaining_weight is None:
            if price > 0 and remaining_amount > 0:
                remaining_weight = cls._weight(remaining_amount / price)
            else:
                remaining_weight = cls._weight(max(weight - paid_weight, Decimal("0")))
        else:
            remaining_weight = cls._weight(max(remaining_weight, Decimal("0")))

        if weight > 0:
            paid_weight = min(paid_weight, cls._weight(weight))
            remaining_weight = min(remaining_weight, cls._weight(weight))
        return {
            "price_per_gram": price,
            "paid_weight": paid_weight,
            "remaining_amount": remaining_amount,
            "remaining_weight": remaining_weight,
        }
