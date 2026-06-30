"""Database manager for ClientCommands and their payments."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector



COMMAND_NUMBER_PREFIX = "CMD"
COMMAND_STATUSES = {
    "PENDING",
    "CONFIRMED",
    "IN_PROGRESS",
    "READY",
    "DELIVERED",
    "CANCELLED",
}
PAYMENT_STATUSES = {"UNPAID", "PARTIAL", "PAID"}
COMMAND_PAYMENT_SOURCE_TYPES = {
    "CASH",
    "MULTI_CURRENCY",
    "VERSEMENT_LIBRE",
    "TPE",
    "CORRECTION",
    "OTHER",
}


class ClientCommandsManager:
    """Create, pay, track, and close customer orders for future products."""

    def __init__(self, db_instance):
        self.db = db_instance

    @staticmethod
    def _money(value) -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))

    @staticmethod
    def _weight(value) -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal("0.001"))

    @staticmethod
    def _positive_id(value) -> Optional[int]:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _row_value(row, key: str, index: int, default=None):
        if not row:
            return default
        if isinstance(row, dict):
            return row.get(key, default)
        try:
            return row[index]
        except (TypeError, IndexError):
            return default

    @staticmethod
    def format_command_number(sequence=None, command_number: str = "") -> str:
        text = str(command_number or "").strip()
        if text:
            return text
        try:
            seq = int(sequence or 0)
        except (TypeError, ValueError):
            return ""
        return f"{COMMAND_NUMBER_PREFIX}-{seq:06d}" if seq > 0 else ""

    @classmethod
    def normalize_command_number(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(row, dict):
            row["command_number"] = cls.format_command_number(
                row.get("command_sequence"),
                row.get("command_number", ""),
            )
            row["display_number"] = row["command_number"]
        return row

    @classmethod
    def _reserve_command_number(cls, cursor) -> Tuple[int, str]:
        cursor.execute(
            """
            INSERT INTO ClientCommandDocumentSequence (id, last_value, updated_at)
            VALUES (1, LAST_INSERT_ID(1), NOW())
            ON DUPLICATE KEY UPDATE
                last_value = LAST_INSERT_ID(last_value + 1),
                updated_at = NOW()
            """
        )
        cursor.execute("SELECT LAST_INSERT_ID() AS command_sequence")
        row = cursor.fetchone()
        sequence = cls._row_value(row, "command_sequence", 0, None)
        if not sequence:
            sequence = getattr(cursor, "lastrowid", None)
        sequence = int(sequence or 1)
        return sequence, cls.format_command_number(sequence)

    @staticmethod
    def _normalize_status(status: str, default: str = "PENDING") -> str:
        normalized = str(status or default).strip().upper()
        if normalized not in COMMAND_STATUSES:
            raise ValueError(f"Unsupported client command status: {status}")
        return normalized

    @staticmethod
    def _normalize_item_type(item_type: str) -> str:
        normalized = str(item_type or "WEIGHT").strip().upper()
        return "PIECE" if normalized in {"PIECE", "UNIT", "PCS"} else "WEIGHT"

    @staticmethod
    def _normalize_margin_type(margin_type: str) -> str:
        normalized = str(margin_type or "FIXED").strip().upper()
        return "PERCENTAGE" if normalized == "PERCENTAGE" else "FIXED"

    @staticmethod
    def _normalize_source_type(source_type: str = None,
                               source_free_versement_id: int = None,
                               source_client_payment_id: int = None,
                               payment_method: str = None) -> str:
        if source_free_versement_id or source_client_payment_id:
            return "VERSEMENT_LIBRE"
        raw = str(source_type or payment_method or "CASH").strip().upper()
        if raw in {"CARD", "CB"}:
            raw = "TPE"
        if raw not in COMMAND_PAYMENT_SOURCE_TYPES:
            raw = "OTHER"
        return raw

    @classmethod
    def _payment_status(cls, total_amount, paid_amount) -> str:
        total = cls._money(total_amount)
        paid = cls._money(paid_amount)
        if paid <= 0:
            return "UNPAID"
        if total <= 0 or paid >= (total - Decimal("0.05")):
            return "PAID"
        return "PARTIAL"

    def _product_payload(self, product_data: Optional[Dict[str, Any]], overrides: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(product_data or {})
        for key, value in overrides.items():
            if value is not None:
                data[key] = value

        name = (
            data.get("product_name")
            or data.get("name")
            or data.get("description")
            or data.get("item_name")
        )
        if not str(name or "").strip():
            raise ValueError("Client command requires a product name.")

        item_type = self._normalize_item_type(data.get("item_type"))
        quantity = int(data.get("quantity") or data.get("remaining_quantity") or 1)
        weight = self._weight(data.get("weight") or 0)
        metal_cost = self._money(data.get("metal_cost_per_gram"))
        labor_cost = self._money(data.get("labor_cost_per_gram"))
        profit_margin = self._money(data.get("profit_margin"))
        margin_type = self._normalize_margin_type(data.get("margin_type"))

        total_cost = self._money(data.get("total_cost"))
        selling_price = self._money(data.get("selling_price") or data.get("total_amount"))
        if item_type == "WEIGHT" and selling_price <= 0 and weight > 0:
            profit_per_gram = (
                (metal_cost + labor_cost) * (profit_margin / Decimal("100"))
                if margin_type == "PERCENTAGE"
                else profit_margin
            )
            total_cost = (metal_cost + labor_cost) * weight
            selling_price = total_cost + (profit_per_gram * weight)

        return {
            "barcode": data.get("barcode"),
            "product_name": str(name).strip(),
            "product_name_id": self._positive_id(data.get("product_name_id")),
            "category_id": self._positive_id(data.get("category_id")),
            "metal_type_id": self._positive_id(data.get("metal_type_id")),
            "item_type": item_type,
            "weight": float(weight) if item_type == "WEIGHT" else None,
            "quantity": max(1, quantity),
            "metal_cost_per_gram": float(metal_cost),
            "labor_cost_per_gram": float(labor_cost),
            "total_cost": float(total_cost),
            "initial_cost": float(self._money(data.get("initial_cost") or total_cost)),
            "profit_margin": float(profit_margin),
            "margin_type": margin_type,
            "selling_price": float(selling_price),
            "supplier_id": self._positive_id(data.get("supplier_id")),
            "location_id": self._positive_id(data.get("location_id")),
            "image_url": data.get("image_url"),
            "product_description": data.get("product_description") or data.get("description"),
            "product_payload_json": self._json_payload(data.get("product_payload_json") or data),
        }

    @staticmethod
    def _json_payload(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            return json.dumps(str(value), ensure_ascii=False)

    def create_command(self, client_id: int, product_data: Optional[Dict[str, Any]] = None,
                       expected_delivery_date=None, command_date=None,
                       total_amount: float = None, initial_payment_amount: float = 0.0,
                       currency_id: int = 1, user_id: Optional[int] = None,
                       notes: str = "", status: str = "PENDING",
                       cash_transaction: Optional[Dict[str, Any]] = None,
                       payment_method: Optional[str] = None,
                       source_free_versement_id: Optional[int] = None,
                       source_client_payment_id: Optional[int] = None,
                       source_amount_to_use: Optional[float] = None,
                       **product_fields) -> Optional[int]:
        """Create a client command and optionally record the first payment."""
        conn = None
        try:
            client_id = int(client_id)
            payload = self._product_payload(product_data, product_fields)
            command_total = self._money(total_amount if total_amount is not None else payload["selling_price"])
            initial_payment = self._money(initial_payment_amount)
            if command_total <= 0 and initial_payment > 0:
                command_total = initial_payment
            if initial_payment < 0:
                return None
            if command_total > 0 and initial_payment > (command_total + Decimal("0.05")):
                return None

            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            sequence, number = self._reserve_command_number(cursor)
            cursor.execute(
                """
                INSERT INTO ClientCommands
                (command_sequence, command_number, client_id, command_date,
                 expected_delivery_date, status, currency_id, total_amount,
                 paid_amount, payment_status, barcode, product_name, product_name_id,
                 category_id, metal_type_id, item_type, weight, quantity,
                 metal_cost_per_gram, labor_cost_per_gram, total_cost, initial_cost,
                 profit_margin, margin_type, selling_price, supplier_id, location_id,
                 image_url, product_description, product_payload_json, notes, user_id,
                 created_at, updated_at)
                VALUES
                (%s, %s, %s, COALESCE(%s, NOW()), %s, %s, %s, %s,
                 0, 'UNPAID', %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    sequence, number, client_id, command_date, expected_delivery_date,
                    self._normalize_status(status), currency_id or 1, float(command_total),
                    payload["barcode"], payload["product_name"], payload["product_name_id"],
                    payload["category_id"], payload["metal_type_id"], payload["item_type"],
                    payload["weight"], payload["quantity"], payload["metal_cost_per_gram"],
                    payload["labor_cost_per_gram"], payload["total_cost"],
                    payload["initial_cost"], payload["profit_margin"], payload["margin_type"],
                    payload["selling_price"], payload["supplier_id"], payload["location_id"],
                    payload["image_url"], payload["product_description"],
                    payload["product_payload_json"], notes, user_id,
                ),
            )
            command_id = int(cursor.lastrowid)
            if initial_payment > 0:
                self._insert_command_payment(
                    cursor,
                    command_id,
                    float(initial_payment),
                    currency_id=currency_id,
                    user_id=user_id,
                    notes=notes,
                    payment_method=payment_method,
                    cash_transaction=cash_transaction,
                    source_free_versement_id=source_free_versement_id,
                    source_client_payment_id=source_client_payment_id,
                    source_amount_to_use=source_amount_to_use,
                )
            conn.commit()
            return command_id
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error creating client command for client %s: %s", client_id, exc)
            return None
        finally:
            if conn:
                conn.close()

    def add_command_payment(self, command_id: int, amount: float, currency_id: int = 1,
                            exchange_rate_at_time: float = 1.0,
                            payment_method: Optional[str] = None,
                            source_type: Optional[str] = None,
                            source_free_versement_id: Optional[int] = None,
                            source_client_payment_id: Optional[int] = None,
                            source_amount_to_use: Optional[float] = None,
                            cash_transaction: Optional[Dict[str, Any]] = None,
                            user_id: Optional[int] = None, notes: str = "") -> Optional[int]:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            payment_id = self._insert_command_payment(
                cursor,
                command_id,
                amount,
                currency_id=currency_id,
                exchange_rate_at_time=exchange_rate_at_time,
                payment_method=payment_method,
                source_type=source_type,
                source_free_versement_id=source_free_versement_id,
                source_client_payment_id=source_client_payment_id,
                source_amount_to_use=source_amount_to_use,
                cash_transaction=cash_transaction,
                user_id=user_id,
                notes=notes,
            )
            conn.commit()
            return payment_id
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error adding client command payment %s: %s", command_id, exc)
            return None
        finally:
            if conn:
                conn.close()

    def _insert_command_payment(self, cursor, command_id: int, amount: float,
                                currency_id: int = 1,
                                exchange_rate_at_time: float = 1.0,
                                payment_method: Optional[str] = None,
                                source_type: Optional[str] = None,
                                source_free_versement_id: Optional[int] = None,
                                source_client_payment_id: Optional[int] = None,
                                source_amount_to_use: Optional[float] = None,
                                cash_transaction: Optional[Dict[str, Any]] = None,
                                user_id: Optional[int] = None,
                                notes: str = "") -> int:
        amount_dec = self._money(amount)
        if amount_dec <= 0:
            raise ValueError("Client command payment amount must be positive.")

        cursor.execute(
            """
            SELECT id, client_id, status, total_amount, paid_amount
            FROM ClientCommands
            WHERE id = %s
            FOR UPDATE
            """,
            (command_id,),
        )
        command = cursor.fetchone()
        if not command:
            raise ValueError(f"Client command not found: {command_id}")
        if str(command.get("status") or "").upper() in {"CANCELLED", "DELIVERED"}:
            raise ValueError(f"Client command is not payable: {command_id}")

        total_amount = self._money(command.get("total_amount"))
        current_paid = self._money(command.get("paid_amount"))
        if total_amount > 0 and current_paid + amount_dec > (total_amount + Decimal("0.05")):
            raise ValueError("Client command payment exceeds remaining amount.")
        source_amount_dec = self._money(source_amount_to_use if source_amount_to_use is not None else amount_dec)

        source_free_versement_id = self._positive_id(source_free_versement_id)
        source_client_payment_id = self._positive_id(source_client_payment_id)
        if source_free_versement_id and not ClientPaymentManager._reserve_source_free_versement(
            cursor,
            source_free_versement_id,
            float(source_amount_dec),
        ):
            raise ValueError(f"Free versement balance is not available: {source_free_versement_id}")
        if source_client_payment_id and not ClientPaymentManager._reserve_source_free_payment(
            cursor,
            source_client_payment_id,
            float(source_amount_dec),
        ):
            raise ValueError(f"Legacy free payment balance is not available: {source_client_payment_id}")

        rate_dec = self._money(exchange_rate_at_time or 1)
        amount_base = (amount_dec * rate_dec).quantize(Decimal("0.01"))
        final_source_type = self._normalize_source_type(
            source_type=source_type,
            source_free_versement_id=source_free_versement_id,
            source_client_payment_id=source_client_payment_id,
            payment_method=payment_method,
        )
        cursor.execute(
            """
            INSERT INTO ClientCommandPayments
            (command_id, payment_date, amount, currency_id, exchange_rate_at_time,
             amount_base, payment_method, source_type, source_free_versement_id,
             source_client_payment_id, money_transaction_id, notes, user_id,
             created_at, updated_at)
            VALUES (%s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, NOW(), NOW())
            """,
            (
                command_id,
                float(amount_dec),
                currency_id or 1,
                float(rate_dec),
                float(amount_base),
                payment_method,
                final_source_type,
                source_free_versement_id,
                source_client_payment_id,
                notes,
                user_id,
            ),
        )
        payment_id = int(cursor.lastrowid)
        new_paid = current_paid + amount_dec
        if total_amount > 0 and new_paid > total_amount:
            new_paid = total_amount
        payment_status = self._payment_status(total_amount, new_paid)
        cursor.execute(
            """
            UPDATE ClientCommands
            SET paid_amount = %s,
                payment_status = %s,
                status = IF(status = 'PENDING' AND %s > 0, 'CONFIRMED', status),
                updated_at = NOW()
            WHERE id = %s
            """,
            (float(new_paid), payment_status, float(new_paid), command_id),
        )

        if cash_transaction is not None:
            money_id = self._insert_money_transaction(
                cursor,
                command,
                payment_id,
                amount_dec,
                currency_id=currency_id,
                cash_transaction=cash_transaction,
                user_id=user_id,
            )
            cursor.execute(
                """
                UPDATE ClientCommandPayments
                SET money_transaction_id = %s
                WHERE id = %s
                """,
                (money_id, payment_id),
            )
        return payment_id

    def _insert_money_transaction(self, cursor, command: Dict[str, Any], payment_id: int,
                                  amount_dec: Decimal, currency_id: int,
                                  cash_transaction: Dict[str, Any],
                                  user_id: Optional[int]) -> int:
        location_id = cash_transaction.get("location_id")
        if not location_id:
            raise ValueError("Cash-linked command payment requires location_id.")
        command_id = int(command.get("id"))
        cursor.execute(
            """
            INSERT INTO MoneyTransactions
            (transaction_date, client_id, location_id, currency_id, amount,
             transaction_type, client_operation_type, description, session_id,
             related_client_command_id, related_client_command_payment_id, user_id)
            VALUES (NOW(), %s, %s, %s, %s, %s, 'CLIENT_COMMAND', %s, %s, %s, %s, %s)
            """,
            (
                command.get("client_id"),
                location_id,
                cash_transaction.get("currency_id") or currency_id or 1,
                float(Decimal(str(cash_transaction.get("amount") or amount_dec))),
                cash_transaction.get("transaction_type") or "CLIENT_COMMAND_PAYMENT",
                cash_transaction.get("description") or f"Paiement commande client #{command_id}",
                cash_transaction.get("session_id"),
                command_id,
                payment_id,
                user_id,
            ),
        )
        return int(cursor.lastrowid)

    def get_command_payments(self, command_id: int) -> List[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT p.*, mt.location_id, mt.transaction_type, mt.description AS cash_description
                    FROM ClientCommandPayments p
                    LEFT JOIN MoneyTransactions mt ON mt.id = p.money_transaction_id
                    WHERE p.command_id = %s
                    ORDER BY p.payment_date ASC, p.id ASC
                    """,
                    (command_id,),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error retrieving client command payments %s: %s", command_id, exc)
            return []

    def get_command_by_id(self, command_id: int, include_payments: bool = True) -> Optional[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT cc.*, c.name AS client_name, c.phone AS client_phone,
                           sup.name AS supplier_name, sup.phone AS supplier_phone,
                           i.barcode AS linked_inventory_barcode,
                           s.facture_number AS linked_facture_number,
                           s.facture_sequence AS linked_facture_sequence
                    FROM ClientCommands cc
                    LEFT JOIN Clients c ON c.id = cc.client_id
                    LEFT JOIN Suppliers sup ON sup.id = cc.supplier_id
                    LEFT JOIN Inventory i ON i.id = cc.linked_inventory_id
                    LEFT JOIN Sales s ON s.id = cc.linked_sale_id
                    WHERE cc.id = %s
                    """,
                    (command_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                self.normalize_command_number(row)
                if include_payments:
                    row["payments"] = self.get_command_payments(command_id)
                return row
        except Exception as exc:
            logging.error("Error retrieving client command %s: %s", command_id, exc)
            return None

    def get_command(self, command_id: int, include_payments: bool = True) -> Optional[Dict[str, Any]]:
        return self.get_command_by_id(command_id, include_payments=include_payments)

    def get_commands(self, client_id: Optional[int] = None, status: Optional[str] = None,
                     payment_status: Optional[str] = None, search_text: str = "",
                     start_date=None, end_date=None, due_before=None,
                     limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        filters = []
        params: List[Any] = []
        if client_id:
            filters.append("cc.client_id = %s")
            params.append(client_id)
        if status:
            filters.append("cc.status = %s")
            params.append(self._normalize_status(status))
        if payment_status:
            normalized_payment_status = str(payment_status or "").strip().upper()
            if normalized_payment_status not in PAYMENT_STATUSES:
                raise ValueError(f"Unsupported command payment status: {payment_status}")
            filters.append("cc.payment_status = %s")
            params.append(normalized_payment_status)
        if start_date:
            filters.append("DATE(cc.command_date) >= %s")
            params.append(start_date)
        if end_date:
            filters.append("DATE(cc.command_date) <= %s")
            params.append(end_date)
        if due_before:
            filters.append("cc.expected_delivery_date <= %s")
            params.append(due_before)
        search_text = str(search_text or "").strip()
        if search_text:
            like = f"%{search_text}%"
            filters.append(
                "(cc.command_number LIKE %s OR cc.product_name LIKE %s OR "
                "cc.barcode LIKE %s OR c.name LIKE %s OR c.phone LIKE %s)"
            )
            params.extend([like, like, like, like, like])
        where = "WHERE " + " AND ".join(filters) if filters else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT cc.*, c.name AS client_name, c.phone AS client_phone,
                           sup.name AS supplier_name, sup.phone AS supplier_phone
                    FROM ClientCommands cc
                    LEFT JOIN Clients c ON c.id = cc.client_id
                    LEFT JOIN Suppliers sup ON sup.id = cc.supplier_id
                    {where}
                    ORDER BY
                        cc.expected_delivery_date IS NULL,
                        cc.expected_delivery_date ASC,
                        cc.command_date DESC,
                        cc.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params + [int(limit), int(offset)]),
                )
                rows = cursor.fetchall() or []
                for row in rows:
                    self.normalize_command_number(row)
                return rows
        except Exception as exc:
            logging.error("Error listing client commands: %s", exc)
            return []

    def update_command(self, command_id: int, **fields) -> bool:
        allowed = {
            "command_date", "expected_delivery_date", "status", "total_amount", "barcode",
            "product_name", "product_name_id", "category_id", "metal_type_id",
            "item_type", "weight", "quantity", "metal_cost_per_gram",
            "labor_cost_per_gram", "total_cost", "initial_cost", "profit_margin",
            "margin_type", "selling_price", "supplier_id", "location_id",
            "image_url", "product_description", "product_payload_json", "notes",
            "user_id",
        }
        updates = []
        params = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "status":
                value = self._normalize_status(value)
            elif key == "item_type":
                value = self._normalize_item_type(value)
            elif key == "margin_type":
                value = self._normalize_margin_type(value)
            elif key == "product_payload_json":
                value = self._json_payload(value)
            updates.append(f"{key} = %s")
            params.append(value)
        if not updates:
            return True
        params.append(command_id)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE ClientCommands
                    SET {", ".join(updates)}, updated_at = NOW()
                    WHERE id = %s
                    """,
                    tuple(params),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error updating client command %s: %s", command_id, exc)
            return False

    def set_command_status(self, command_id: int, status: str,
                           delivered_at=None, cancelled_at=None,
                           notes: Optional[str] = None) -> bool:
        normalized = self._normalize_status(status)
        extra = []
        params: List[Any] = [normalized]
        if normalized == "DELIVERED":
            extra.append("delivered_at = COALESCE(%s, NOW())")
            params.append(delivered_at)
        if normalized == "CANCELLED":
            extra.append("cancelled_at = COALESCE(%s, NOW())")
            params.append(cancelled_at)
        if notes is not None:
            extra.append("notes = %s")
            params.append(notes)
        params.append(command_id)
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE ClientCommands
                    SET status = %s,
                        {", ".join(extra) + "," if extra else ""}
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    tuple(params),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error changing client command status %s: %s", command_id, exc)
            return False

    def mark_in_progress(self, command_id: int) -> bool:
        return self.set_command_status(command_id, "IN_PROGRESS")

    def mark_ready(self, command_id: int) -> bool:
        return self.set_command_status(command_id, "READY")

    def mark_delivered(self, command_id: int, sale_id: int = None) -> bool:
        if sale_id:
            return self.link_sale(command_id, sale_id, mark_delivered=True)
        return self.set_command_status(command_id, "DELIVERED")

    def cancel_command(self, command_id: int, reason: str = "",
                       allow_paid: bool = False) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT paid_amount FROM ClientCommands WHERE id = %s FOR UPDATE",
                    (command_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return False
                if self._money(row.get("paid_amount")) > 0 and not allow_paid:
                    return False
                cursor.execute(
                    """
                    UPDATE ClientCommands
                    SET status = 'CANCELLED',
                        cancelled_at = NOW(),
                        notes = CASE
                            WHEN %s = '' THEN notes
                            WHEN notes IS NULL OR notes = '' THEN %s
                            ELSE CONCAT(notes, '\n', %s)
                        END,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (reason or "", reason or "", reason or "", command_id),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error cancelling client command %s: %s", command_id, exc)
            return False

    def sync_paid_amount(self, command_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT total_amount,
                           COALESCE((SELECT SUM(amount)
                                     FROM ClientCommandPayments
                                     WHERE command_id = ClientCommands.id), 0) AS paid
                    FROM ClientCommands
                    WHERE id = %s
                    """,
                    (command_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return False
                paid = self._money(row.get("paid"))
                total = self._money(row.get("total_amount"))
                cursor.execute(
                    """
                    UPDATE ClientCommands
                    SET paid_amount = %s,
                        payment_status = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (float(paid), self._payment_status(total, paid), command_id),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error syncing client command paid amount %s: %s", command_id, exc)
            return False

    def create_inventory_from_command(self, command_id: int, barcode: str = None,
                                      location_id: int = None, supplier_id: int = None,
                                      image_url: str = None) -> Optional[int]:
        conn = None
        try:
            conn = self.db.get_raw_connection()
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT *
                FROM ClientCommands
                WHERE id = %s
                FOR UPDATE
                """,
                (command_id,),
            )
            command = cursor.fetchone()
            if not command:
                conn.rollback()
                return None
            existing_inventory_id = self._positive_id(command.get("linked_inventory_id"))
            if existing_inventory_id:
                conn.commit()
                return existing_inventory_id
            item_type = self._normalize_item_type(command.get("item_type"))
            weight = float(command.get("weight") or 0.0) if item_type == "WEIGHT" else None
            quantity = int(command.get("quantity") or 1)
            cursor.execute(
                """
                INSERT INTO Inventory
                (barcode, name, category_id, metal_type_id, item_type, weight,
                 remaining_weight, quantity, remaining_quantity, metal_cost_per_gram,
                 labor_cost_per_gram, total_cost, initial_cost, profit_margin,
                 margin_type, selling_price, location_id, supplier_id, image_url, status,
                 reserved_for_client_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Reserved', %s)
                """,
                (
                    barcode or command.get("barcode"),
                    command.get("product_name"),
                    command.get("category_id"),
                    command.get("metal_type_id"),
                    item_type,
                    weight,
                    weight if item_type == "WEIGHT" else None,
                    quantity,
                    quantity,
                    float(command.get("metal_cost_per_gram") or 0.0),
                    float(command.get("labor_cost_per_gram") or 0.0),
                    float(command.get("total_cost") or 0.0),
                    float(command.get("initial_cost") or 0.0),
                    float(command.get("profit_margin") or 0.0),
                    command.get("margin_type") or "FIXED",
                    float(command.get("selling_price") or 0.0),
                    location_id or command.get("location_id"),
                    supplier_id or command.get("supplier_id"),
                    image_url or command.get("image_url"),
                    command.get("client_id"),
                ),
            )
            inventory_id = int(cursor.lastrowid)
            cursor.execute(
                """
                UPDATE ClientCommands
                SET linked_inventory_id = %s,
                    status = CASE WHEN status IN ('PENDING', 'CONFIRMED', 'IN_PROGRESS')
                                  THEN 'READY' ELSE status END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (inventory_id, command_id),
            )
            conn.commit()
            return inventory_id
        except Exception as exc:
            if conn:
                conn.rollback()
            logging.error("Error creating inventory from client command %s: %s", command_id, exc)
            return None
        finally:
            if conn:
                conn.close()

    def link_inventory(self, command_id: int, inventory_id: int, mark_ready: bool = True) -> bool:
        status_expr = ", status = 'READY'" if mark_ready else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE ClientCommands
                    SET linked_inventory_id = %s{status_expr}, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (inventory_id, command_id),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error linking inventory to client command %s: %s", command_id, exc)
            return False

    def link_sale(self, command_id: int, sale_id: int, mark_delivered: bool = True) -> bool:
        status_expr = ", status = 'DELIVERED', delivered_at = COALESCE(delivered_at, NOW())" if mark_delivered else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE ClientCommands
                    SET linked_sale_id = %s{status_expr}, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (sale_id, command_id),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error linking sale to client command %s: %s", command_id, exc)
            return False

    def delete_command(self, command_id: int) -> bool:
        """Delete only unused commands without payments or operational links."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT linked_inventory_id, linked_sale_id,
                           (SELECT COUNT(*) FROM ClientCommandPayments WHERE command_id = ClientCommands.id) AS payment_count
                    FROM ClientCommands
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (command_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return False
                if (
                    self._positive_id(row.get("linked_inventory_id"))
                    or self._positive_id(row.get("linked_sale_id"))
                    or int(row.get("payment_count") or 0) > 0
                ):
                    return False
                cursor.execute("DELETE FROM ClientCommands WHERE id = %s", (command_id,))
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error deleting client command %s: %s", command_id, exc)
            return False
