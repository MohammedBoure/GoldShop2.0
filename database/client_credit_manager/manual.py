import logging
from typing import Any, Dict, List, Optional

from .security import CLIENT_CREDIT_CREATE, require_credit_permission


class ClientCreditManualMixin:
    def create_credit(
        self,
        client_id: int,
        *,
        amount_da=0,
        weight_g=0,
        paid_amount_da=0,
        paid_weight_g=0,
        credit_date=None,
        source_ref: str = "",
        description: str = "",
        import_batch_id: Optional[int] = None,
        import_row_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> int:
        amount = self._decimal(amount_da, "credit amount")
        weight = self._decimal(weight_g, "credit weight")
        paid_amount = self._decimal(paid_amount_da, "paid credit amount")
        raw_paid_weight = self._decimal(paid_weight_g, "paid credit weight")
        if paid_amount > amount and amount > 0:
            raise ValueError("paid credit amount cannot exceed credit amount.")
        if raw_paid_weight > weight and weight > 0:
            raise ValueError("paid credit weight cannot exceed credit weight.")
        if amount <= 0 and weight <= 0:
            raise ValueError("Enter a DA amount or gold weight for the client credit.")
        if not client_id:
            raise ValueError("A client is required.")
        balance = self._credit_balance(
            amount=amount,
            weight=weight,
            paid_amount=paid_amount,
            paid_weight=raw_paid_weight if raw_paid_weight > 0 else None,
        )
        paid_weight = balance["paid_weight"]
        remaining_weight = balance["remaining_weight"]
        if (amount > 0 and paid_amount >= amount) and remaining_weight <= 0:
            payment_status = "Paid"
        elif paid_amount > 0 or paid_weight > 0:
            payment_status = "Partial"
        else:
            payment_status = "Unpaid"
        source_ref_text = self._text(source_ref)
        description_text = self._text(description)

        with self.db.get_db_connection() as conn:
            cursor = conn.cursor()
            require_credit_permission(cursor, user_id, CLIENT_CREDIT_CREATE)
            cursor.execute(
                """
                INSERT INTO Sales
                (
                    client_id, sale_date, currency_id,
                    total_weight, total_cost, total_amount, discount, total_facon,
                    final_amount, paid_amount, paid_weight, remaining_weight,
                    payment_status, source_type, legacy_import_batch_id,
                    legacy_import_row_id, legacy_source_ref,
                    legacy_description, legacy_imported_at
                )
                VALUES
                (%s, %s, 1, %s, 0, %s, 0, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    int(client_id),
                    self._format_date(credit_date),
                    str(weight),
                    str(amount),
                    str(amount),
                    str(amount),
                    str(paid_amount),
                    str(paid_weight),
                    str(remaining_weight),
                    payment_status,
                    self.LEGACY_SOURCE,
                    import_batch_id,
                    import_row_id,
                    source_ref_text or None,
                    description_text or "Credit client manuel",
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_or_create_manual_batch(self, user_id: Optional[int] = None) -> int:
        """Return the reusable in-app batch used for manually managed client credits."""
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            checksum = "manual-client-credit"
            cursor.execute(
                """
                SELECT id
                FROM LegacyImportBatches
                WHERE import_domain = 'CLIENT_CREDIT' AND source_checksum = %s
                LIMIT 1
                """,
                (checksum,),
            )
            batch = cursor.fetchone()
            if batch:
                return int(self._row_value(batch, "id", 0))
            cursor.execute(
                """
                INSERT INTO LegacyImportBatches
                (
                    source_file_name, source_checksum, import_domain,
                    workbook_year, source_sheet_count, analyzed_by_user_id,
                    status, total_rows, error_rows, scope_report_json
                )
                VALUES
                ('Crédit client manuel', %s, 'CLIENT_CREDIT', NULL, 0, %s,
                 'STAGED', 0, 0, JSON_OBJECT('source', 'in_app'))
                """,
                (checksum, user_id),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_credits(self, client_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                params: list[Any] = [self.LEGACY_SOURCE]
                where = "WHERE s.source_type = %s"
                if client_id:
                    where += " AND s.client_id = %s"
                    params.append(int(client_id))
                query = f"""
                    SELECT s.id, s.client_id, c.name AS client_name, s.sale_date,
                           s.final_amount, s.paid_amount, s.remaining_amount,
                           s.total_weight, s.paid_weight, s.remaining_weight,
                           s.payment_status, s.legacy_source_ref, s.legacy_description
                    FROM Sales s
                    LEFT JOIN Clients c ON c.id = s.client_id
                    {where}
                    ORDER BY s.sale_date DESC, s.id DESC
                    LIMIT {int(limit)}
                """
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except Exception as exc:
            logging.error("Unable to list client credits: %s", exc)
            return []
