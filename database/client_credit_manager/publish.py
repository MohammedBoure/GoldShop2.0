from decimal import Decimal
from typing import Any, Dict, Optional

from .security import CLIENT_CREDIT_PUBLISH, require_credit_permission


class ClientCreditPublishMixin:
    def publish_staged_credit_row(self, row_id: int, *, user_id: Optional[int] = None) -> int:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            require_credit_permission(cursor, user_id, CLIENT_CREDIT_PUBLISH)
            cursor.execute(
                """
                SELECT *
                FROM LegacyClientCreditRows
                WHERE id = %s
                LIMIT 1
                FOR UPDATE
                """,
                (row_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Client credit row was not found.")
            row = self._with_normalized_values(row)
            if self._row_value(row, "published_sale_id"):
                conn.commit()
                return int(self._row_value(row, "published_sale_id"))
            if self._row_value(row, "validation_status") not in {"READY", "NEEDS_REVIEW"}:
                raise ValueError("Only reviewed client credit rows can be published.")

            client_id = self._resolve_client(cursor, row)
            inventory = self._lock_inventory_for_credit(cursor, row, client_id)
            amount = self._decimal(self._row_value(row, "amount_da"), "credit amount")
            paid = self._decimal(self._row_value(row, "paid_amount_da"), "paid credit amount")
            remaining = self._decimal(self._row_value(row, "remaining_amount_da"), "remaining credit amount")
            if amount <= 0 and remaining > 0:
                amount = paid + remaining
            weight = self._decimal(self._row_value(row, "weight_g"), "credit weight")
            if inventory and amount <= 0:
                amount = self._decimal(inventory.get("selling_price"), "inventory selling price")
            if inventory and weight <= 0 and str(inventory.get("item_type") or "").upper() == "WEIGHT":
                weight = self._decimal(
                    inventory.get("remaining_weight") or inventory.get("weight"),
                    "inventory remaining weight",
                )
            normalized_values = row.get("normalized_values") or {}
            remaining_weight = self._decimal(
                normalized_values.get("remaining_weight_g"),
                "remaining credit weight",
            ) if normalized_values.get("remaining_weight_g") not in (None, "") else None
            balance = self._credit_balance(
                amount=amount,
                weight=weight,
                paid_amount=paid,
                remaining_amount=remaining,
                remaining_weight=remaining_weight,
                price_per_gram=normalized_values.get("price_per_gram_da"),
            )
            paid_weight = balance["paid_weight"]
            remaining = balance["remaining_amount"]
            remaining_weight = balance["remaining_weight"]
            status = "Paid" if amount > 0 and paid >= amount and remaining_weight <= 0 else "Partial" if paid > 0 else "Unpaid"
            description = (
                self._row_value(row, "object_description")
                or (inventory.get("name") if inventory else None)
                or self._row_value(row, "observation")
                or "Crédit client"
            )
            cursor.execute(
                """
                INSERT INTO Sales
                (
                    client_id, sale_date, currency_id, total_weight, total_cost,
                    total_amount, discount, total_facon, final_amount, paid_amount,
                    paid_weight, remaining_weight, payment_status, source_type,
                    legacy_import_batch_id, legacy_import_row_id, legacy_source_ref,
                    legacy_description, legacy_imported_at
                )
                VALUES (%s, %s, 1, %s, 0, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    client_id,
                    self._format_date(self._row_value(row, "credit_date")),
                    str(weight),
                    str(amount),
                    str(amount),
                    str(amount),
                    str(paid),
                    str(paid_weight),
                    str(remaining_weight),
                    status,
                    self.LEGACY_SOURCE,
                    self._row_value(row, "batch_id"),
                    self._row_value(row, "import_row_id"),
                    self._row_value(row, "row_identity"),
                    description,
                ),
            )
            sale_id = int(cursor.lastrowid)
            if inventory:
                self._insert_inventory_sale_item(
                    cursor,
                    sale_id=sale_id,
                    client_id=client_id,
                    inventory=inventory,
                    sold_amount=amount,
                    sold_weight=weight,
                    user_id=user_id,
                )
            payment_id = None
            if paid > 0:
                cursor.execute(
                    """
                    INSERT INTO ClientPayments
                    (
                        client_id, sale_id, amount, used_amount, payment_type,
                        user_id, notes, metal_rate_at_payment, purchased_weight
                    )
                    VALUES (%s, %s, %s, %s, 'LEGACY_CLIENT_CREDIT_PAYMENT', %s, %s, %s, %s)
                    """,
                    (
                        client_id,
                        sale_id,
                        str(paid),
                        str(paid),
                        user_id,
                        "Paiement historique lie au credit client ancien",
                        str(balance["price_per_gram"]),
                        str(paid_weight),
                    ),
                )
                payment_id = int(cursor.lastrowid)
            cursor.execute(
                """
                UPDATE LegacyClientCreditRows
                SET client_id = %s, published_sale_id = %s, published_payment_id = %s,
                    validation_status = 'PUBLISHED',
                    validation_message = 'Published as legacy client credit sale.',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (client_id, sale_id, payment_id, row_id),
            )
            import_row_id = self._row_value(row, "import_row_id")
            if import_row_id:
                cursor.execute(
                    """
                    UPDATE LegacyImportRows
                    SET published_sale_id = %s, published_payment_id = %s
                    WHERE id = %s
                    """,
                    (sale_id, payment_id, import_row_id),
                )
            conn.commit()
            return sale_id
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def _resolve_client(self, cursor, row) -> int:
        client_id = self._row_value(row, "client_id")
        if client_id:
            return int(client_id)
        client_name = str(self._row_value(row, "client_name") or "").strip()
        if not client_name:
            raise ValueError("Client credit row needs a client.")
        cursor.execute("SELECT id FROM Clients WHERE name = %s LIMIT 1 FOR UPDATE", (client_name,))
        stored = cursor.fetchone()
        if stored:
            return int(self._row_value(stored, "id", 0))
        cursor.execute("INSERT INTO Clients (name) VALUES (%s)", (client_name,))
        return int(cursor.lastrowid)

    def _lock_inventory_for_credit(self, cursor, row, client_id: int) -> Optional[Dict[str, Any]]:
        inventory_id = self._row_value(row, "inventory_id")
        if not inventory_id:
            return None
        cursor.execute(
            """
            SELECT *
            FROM Inventory
            WHERE id = %s
            FOR UPDATE
            """,
            (int(inventory_id),),
        )
        inventory = cursor.fetchone()
        if not inventory:
            raise ValueError("Article de stock introuvable pour ce Crédit client.")
        inventory = dict(inventory)
        status = str(inventory.get("status") or "").strip()
        reserved_for = inventory.get("reserved_for_client_id")
        if status not in {"Available", "Partially_Sold", "Reserved"}:
            raise ValueError("Cet article n'est plus disponible en stock.")
        if status == "Reserved" and reserved_for not in (None, client_id):
            raise ValueError("Cet article est réservé à un autre client.")
        item_type = str(inventory.get("item_type") or "WEIGHT").upper()
        remaining_weight = self._decimal(inventory.get("remaining_weight"), "inventory remaining weight")
        remaining_quantity = int(inventory.get("remaining_quantity") or 0)
        if item_type == "WEIGHT" and remaining_weight <= 0:
            raise ValueError("Cet article n'a plus de poids disponible.")
        if item_type != "WEIGHT" and remaining_quantity <= 0:
            raise ValueError("Cet article n'a plus de quantité disponible.")
        return inventory

    def _insert_inventory_sale_item(
        self,
        cursor,
        *,
        sale_id: int,
        client_id: int,
        inventory: Dict[str, Any],
        sold_amount: Decimal,
        sold_weight: Decimal,
        user_id: Optional[int],
    ) -> None:
        inventory_id = int(inventory["id"])
        item_type = str(inventory.get("item_type") or "WEIGHT").upper()
        remaining_weight = self._decimal(inventory.get("remaining_weight"), "inventory remaining weight")
        remaining_quantity = int(inventory.get("remaining_quantity") or 0)
        sold_weight = max(Decimal("0"), sold_weight)
        if item_type == "WEIGHT":
            if sold_weight <= 0:
                sold_weight = remaining_weight
            sold_weight = min(sold_weight, remaining_weight)
            new_remaining_weight = max(Decimal("0"), remaining_weight - sold_weight)
            new_remaining_quantity = 0 if new_remaining_weight <= Decimal("0.005") else max(1, remaining_quantity)
            new_status = "Sold" if new_remaining_weight <= Decimal("0.005") else "Partially_Sold"
        else:
            sold_weight = Decimal("0")
            new_remaining_weight = remaining_weight
            new_remaining_quantity = max(0, remaining_quantity - 1)
            new_status = "Sold" if new_remaining_quantity <= 0 else "Partially_Sold"

        metal_rate = self._decimal(inventory.get("metal_cost_per_gram"), "inventory metal cost")
        labor_rate = self._decimal(inventory.get("labor_cost_per_gram"), "inventory labor cost")
        if item_type == "WEIGHT":
            cost_price = (metal_rate + labor_rate) * sold_weight
        else:
            total_cost = self._decimal(inventory.get("total_cost") or inventory.get("initial_cost"), "inventory total cost")
            quantity = max(1, int(inventory.get("quantity") or 1))
            cost_price = total_cost / Decimal(quantity)

        cursor.execute(
            """
            INSERT INTO SaleItems
            (sale_id, inventory_id, sold_price, sold_weight, cost_price, metal_rate_at_sale, item_paid_weight, is_delivered, delivery_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, NOW())
            """,
            (
                sale_id,
                inventory_id,
                str(sold_amount),
                str(sold_weight),
                str(cost_price),
                str(metal_rate),
                str(sold_weight),
            ),
        )
        cursor.execute(
            """
            UPDATE Inventory
            SET remaining_weight = %s,
                remaining_quantity = %s,
                status = %s,
                sold_at = IF(%s = 'Sold', COALESCE(sold_at, NOW()), sold_at),
                sold_price = IF(%s = 'Sold', %s, sold_price),
                reserved_for_client_id = IF(%s = 'Sold', NULL, COALESCE(reserved_for_client_id, %s))
            WHERE id = %s
            """,
            (
                str(new_remaining_weight),
                new_remaining_quantity,
                new_status,
                new_status,
                new_status,
                str(sold_amount),
                new_status,
                client_id,
                inventory_id,
            ),
        )
        cursor.execute(
            """
            INSERT INTO ProductHistory
            (inventory_id, user_id, action_type, old_value, new_value, notes, action_date)
            VALUES (%s, %s, 'CLIENT_CREDIT', %s, %s, %s, NOW())
            """,
            (
                inventory_id,
                user_id,
                inventory.get("status") or "Available",
                new_status,
                f"Crédit client publié comme vente #{sale_id}",
            ),
        )
