import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .security import CLIENT_CREDIT_CREATE, CLIENT_CREDIT_UPDATE, require_credit_permission


class ClientCreditStagingMixin:
    def stage_credit_rows(
        self,
        batch_id: int,
        rows: List[Dict[str, Any]],
        *,
        replace: bool = False,
        user_id: Optional[int] = None,
    ) -> int:
        """Store reviewed client credit rows before publishing them to Sales."""
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor()
            require_credit_permission(cursor, user_id, CLIENT_CREDIT_CREATE)
            if replace:
                cursor.execute("DELETE FROM LegacyClientCreditRows WHERE batch_id = %s", (batch_id,))
            count = 0
            for row in rows:
                self._insert_staged_credit_row(cursor, batch_id, row)
                count += 1
            conn.commit()
            return count
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    @classmethod
    def _insert_staged_credit_row(cls, cursor, batch_id: int, row: Dict[str, Any]) -> int:
        row = dict(row)
        if not row.get("row_identity") and not row.get("import_row_id") and not row.get("row_number"):
            identity_seed = cls._json_payload(row) + "\x1f" + datetime.now().isoformat(timespec="microseconds")
            row["row_identity"] = hashlib.sha256(identity_seed.encode("utf-8")).hexdigest()
        amount = cls._decimal(row.get("amount_da") or row.get("Prix"), "credit amount")
        paid = cls._decimal(row.get("paid_amount_da") or row.get("Vers"), "paid credit amount")
        weight = cls._decimal(row.get("weight_g") or row.get("Poids"), "credit weight")
        remaining = row.get("remaining_amount_da")
        if remaining is None:
            remaining = row.get("Reste_DA")
        if remaining is None:
            remaining = max(amount - paid, Decimal("0"))
        remaining = cls._decimal(remaining, "remaining credit amount")
        remaining_weight = row.get("remaining_weight_g")
        if remaining_weight is None:
            remaining_weight = row.get("Reste_g")
        remaining_weight = (
            cls._decimal(remaining_weight, "remaining credit weight")
            if remaining_weight not in (None, "")
            else None
        )
        balance = cls._credit_balance(
            amount=amount,
            weight=weight,
            paid_amount=paid,
            remaining_amount=remaining,
            remaining_weight=remaining_weight,
            price_per_gram=row.get("price_per_gram_da"),
        )
        normalized = cls._normalized_payload(row)
        normalized.update({
            "price_per_gram_da": str(balance["price_per_gram"]),
            "paid_weight_g": str(balance["paid_weight"]),
            "remaining_weight_g": str(balance["remaining_weight"]),
        })
        cursor.execute(
            """
            INSERT INTO LegacyClientCreditRows
            (
                batch_id, import_row_id, row_number, row_identity, client_id,
                client_name, credit_date, object_description, weight_g, amount_da,
                paid_amount_da, remaining_amount_da, observation,
                raw_values_json, normalized_values_json,
                validation_status, validation_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                batch_id,
                row.get("import_row_id"),
                int(row.get("row_number") or 0),
                row.get("row_identity") or cls._row_identity(row),
                row.get("client_id"),
                row.get("client_name") or row.get("Nom"),
                cls._format_date(row.get("credit_date") or row.get("Dates")),
                row.get("object_description") or row.get("Objets"),
                str(weight),
                str(amount),
                str(paid),
                str(remaining),
                row.get("observation") or row.get("Observation"),
                cls._json_payload(row.get("raw_values") or row),
                cls._json_payload(normalized),
                row.get("validation_status") or "NEEDS_REVIEW",
                row.get("validation_message"),
            ),
        )
        return int(cursor.lastrowid)

    def list_staged_credit_rows(
        self,
        batch_id: Optional[int] = None,
        *,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            clauses = []
            params: list[Any] = []
            if batch_id is not None:
                clauses.append("l.batch_id = %s")
                params.append(int(batch_id))
            if status:
                clauses.append("l.validation_status = %s")
                params.append(status)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            cursor.execute(
                f"""
                SELECT l.*,
                       s.final_amount AS live_final_amount_da,
                       s.paid_amount AS live_paid_amount_da,
                       s.paid_weight AS live_paid_weight_g,
                       s.remaining_weight AS live_remaining_weight_g,
                       s.total_weight AS live_total_weight_g,
                       s.payment_status AS live_payment_status
                FROM LegacyClientCreditRows l
                LEFT JOIN Sales s ON s.id = l.published_sale_id
                {where}
                ORDER BY l.credit_date DESC, l.id DESC
                LIMIT {int(limit)}
                """,
                tuple(params),
            )
            return [self._with_live_published_balance(row) for row in cursor.fetchall()]

    def update_staged_credit_row(
        self,
        row_id: int,
        *,
        client_id: Optional[int] = None,
        client_name: str = "",
        credit_date=None,
        object_description: str = "",
        weight_g=None,
        amount_da=None,
        paid_amount_da=None,
        remaining_amount_da=None,
        observation: str = "",
        validation_status: str = "READY",
        validation_message: str = "",
        inventory_id: Optional[int] = None,
        inventory_label: str = "",
        inventory_barcode: str = "",
        inventory_item_type: str = "",
        user_id: Optional[int] = None,
    ) -> bool:
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            require_credit_permission(cursor, user_id, CLIENT_CREDIT_UPDATE)
            cursor.execute(
                """
                SELECT validation_status, published_sale_id, normalized_values_json
                FROM LegacyClientCreditRows
                WHERE id = %s
                LIMIT 1
                """,
                (row_id,),
            )
            stored = cursor.fetchone()
            if not stored:
                return False
            if self._row_value(stored, "published_sale_id") or self._row_value(stored, "validation_status") == "PUBLISHED":
                raise ValueError("Published client credit cannot be edited directly.")
            amount = self._decimal(amount_da, "credit amount")
            paid = self._decimal(paid_amount_da, "paid credit amount")
            weight = self._decimal(weight_g, "credit weight")
            if amount <= 0 and weight <= 0:
                raise ValueError("Enter a DA amount or gold weight for the client credit.")
            if paid > amount and amount > 0:
                raise ValueError("paid credit amount cannot exceed credit amount.")
            requested_remaining = (
                None
                if remaining_amount_da is None
                else self._decimal(remaining_amount_da, "remaining credit amount")
            )
            balance = self._credit_balance(
                amount=amount,
                weight=weight,
                paid_amount=paid,
                remaining_amount=requested_remaining,
                price_per_gram=None,
            )
            remaining = balance["remaining_amount"]
            normalized = self._normalized_payload({
                "inventory_id": inventory_id,
                "inventory_label": inventory_label,
                "inventory_barcode": inventory_barcode,
                "inventory_item_type": inventory_item_type,
            }, existing=self._json_object(self._row_value(stored, "normalized_values_json")))
            normalized.update({
                "source": "in_app",
                "amount_da": str(amount),
                "paid_amount_da": str(paid),
                "remaining_amount_da": str(remaining),
                "weight_g": str(weight),
                "price_per_gram_da": str(balance["price_per_gram"]),
                "paid_weight_g": str(balance["paid_weight"]),
                "remaining_weight_g": str(balance["remaining_weight"]),
            })
            client_name_text = self._text(client_name)
            object_description_text = self._text(object_description)
            observation_text = self._text(observation)
            validation_status_text = self._text(validation_status) or "READY"
            validation_message_text = self._text(validation_message)
            cursor.execute(
                """
                UPDATE LegacyClientCreditRows
                SET client_id = %s, client_name = COALESCE(NULLIF(%s, ''), client_name),
                    credit_date = %s, object_description = %s,
                    weight_g = %s, amount_da = %s, paid_amount_da = %s,
                    remaining_amount_da = %s, observation = %s,
                    validation_status = %s, validation_message = %s,
                    normalized_values_json = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    client_id,
                    client_name_text,
                    self._format_date(credit_date),
                    object_description_text or None,
                    str(weight),
                    str(amount),
                    str(paid),
                    str(remaining),
                    observation_text or None,
                    validation_status_text,
                    validation_message_text or None,
                    self._json_payload(normalized),
                    row_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
