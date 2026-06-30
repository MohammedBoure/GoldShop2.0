# database/supplier_manager.py

import logging
import math
from typing import Dict, List, Optional, Tuple


class SupplierManager:
    """
    Supplier and artisan accounting manager.

    The ledger supports both the old storage model:
        amount + currency_id/metal_type_id + type
    and the newer debit/credit model:
        amount_debit/amount_credit + accounted_weight_debit/accounted_weight_credit

    All public reads normalize both models into the same money/weight deltas so
    legacy rows and new rows produce one consistent balance.
    """

    MONEY_EPSILON = 0.000001
    WEIGHT_EPSILON = 0.000001
    DEFAULT_ACCOUNT_CODE = "DEFAULT"
    DEFAULT_ACCOUNT_NAME = "Default"

    def __init__(self, db_instance):
        self.db = db_instance

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _is_silver_asset(metal_id=None, asset_name: str = "", metal_category: str = "") -> bool:
        if str(metal_category or "").upper() == "SILVER":
            return True
        name = str(asset_name or "").upper()
        return "ARG" in name or "SILVER" in name or "ARGENT" in name or metal_id in (6, 7, 8, 9)

    @staticmethod
    def _is_purchase_type(trans_type: str) -> bool:
        return str(trans_type or "").upper().startswith("PURCHASE")

    @staticmethod
    def _is_debit_type(trans_type: str) -> bool:
        t_type = str(trans_type or "").upper()
        return t_type.startswith("PAYMENT") or t_type.startswith("RETURN")

    def _legacy_sign(self, trans_type: str) -> int:
        if self._is_purchase_type(trans_type):
            return 1
        if self._is_debit_type(trans_type):
            return -1
        return 0

    def _normalize_transaction_row(self, row: Dict) -> Dict:
        normalized = dict(row)
        trans_type = str(row.get("type") or "").upper()
        legacy_amount = self._to_float(row.get("amount"))
        legacy_sign = self._legacy_sign(trans_type)

        amount_debit = self._to_float(row.get("amount_debit"))
        amount_credit = self._to_float(row.get("amount_credit"))
        weight_debit = self._to_float(row.get("accounted_weight_debit"))
        weight_credit = self._to_float(row.get("accounted_weight_credit"))

        has_money_columns = abs(amount_debit) > self.MONEY_EPSILON or abs(amount_credit) > self.MONEY_EPSILON
        has_weight_columns = abs(weight_debit) > self.WEIGHT_EPSILON or abs(weight_credit) > self.WEIGHT_EPSILON

        money_delta = 0.0
        weight_delta = 0.0

        if has_money_columns:
            money_delta = amount_credit - amount_debit
        elif row.get("currency_id") is not None and legacy_sign:
            money_delta = legacy_amount * legacy_sign

        if has_weight_columns:
            weight_delta = weight_credit - weight_debit
        elif row.get("metal_type_id") is not None and legacy_sign:
            weight_delta = legacy_amount * legacy_sign

        metal_id = row.get("resolved_metal_type_id") or row.get("input_metal_type_id") or row.get("metal_type_id")
        metal_name = row.get("metal_name") or row.get("asset_name") or ""
        metal_category = row.get("metal_category") or ""
        is_silver = self._is_silver_asset(metal_id, metal_name, metal_category)
        metal_code = "ARG" if is_silver else "OR"

        if abs(weight_delta) > self.WEIGHT_EPSILON and abs(money_delta) > self.MONEY_EPSILON:
            asset_type = "MIXED"
            asset_name = f"{metal_code}+DZD"
        elif abs(weight_delta) > self.WEIGHT_EPSILON:
            asset_type = "METAL"
            asset_name = metal_code
        else:
            asset_type = "CURRENCY"
            asset_name = row.get("currency_code") or row.get("asset_name") or "DZD"

        normalized.update(
            {
                "money_delta": money_delta,
                "weight_delta": weight_delta,
                "money_amount": abs(money_delta),
                "weight_amount": abs(weight_delta),
                "asset_type": asset_type,
                "asset_name": asset_name,
                "asset_code": asset_name,
                "is_silver": is_silver,
                "supplier_account_code": row.get("supplier_account_code") or self.DEFAULT_ACCOUNT_CODE,
                "supplier_account_name": row.get("supplier_account_name") or self.DEFAULT_ACCOUNT_NAME,
                "supplier_account_type": row.get("supplier_account_type") or self.DEFAULT_ACCOUNT_CODE,
                # Compatibility: old dialogs expect a positive amount field.
                "amount": abs(weight_delta) if asset_type == "METAL" else abs(money_delta),
            }
        )
        return normalized

    def _get_base_currency(self, cursor) -> Tuple[int, float]:
        cursor.execute("SELECT id, exchange_rate FROM Currencies WHERE is_base = TRUE LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return 1, 1.0
        if isinstance(row, dict):
            return int(row.get("id") or 1), self._to_float(row.get("exchange_rate")) or 1.0
        return int(row[0] or 1), self._to_float(row[1]) or 1.0

    def _get_supplier_base_metal_id(self, cursor, supplier_id: int, default_id: int = 1) -> int:
        cursor.execute("SELECT base_metal_type_id FROM Suppliers WHERE id = %s", (supplier_id,))
        row = cursor.fetchone()
        if isinstance(row, dict):
            return int(row.get("base_metal_type_id") or default_id)
        return int(row[0] or default_id) if row else default_id

    def _currency_code_to_metal_type_id(self, cursor, supplier_id: int, source_code: str) -> int:
        source_code = str(source_code or "").upper()
        if source_code == "ARG":
            return 6
        return self._get_supplier_base_metal_id(cursor, supplier_id, 1)

    def add_supplier(
        self,
        name: str,
        phone: str = "",
        address: str = "",
        base_metal_id: int = None,
        bal_gold: float = 0.0,
        bal_money: float = 0.0,
        bal_silver: float = 0.0,
    ) -> Optional[int]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO Suppliers (name, phone, address, base_metal_type_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (name, phone, address, base_metal_id),
                )
                supplier_id = cursor.lastrowid
                self._save_initial_balances(cursor, supplier_id, base_metal_id, bal_gold, bal_money, bal_silver)
                conn.commit()
                return supplier_id
        except Exception as exc:
            logging.error(f"Error adding supplier: {exc}")
            return None

    def update_supplier(
        self,
        sid: int,
        name: str,
        phone: str = "",
        address: str = "",
        base_metal_id: int = None,
        bal_gold: float = 0.0,
        bal_money: float = 0.0,
        bal_silver: float = 0.0,
    ) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE Suppliers
                    SET name=%s, phone=%s, address=%s, base_metal_type_id=%s
                    WHERE id=%s
                    """,
                    (name, phone, address, base_metal_id, sid),
                )
                # Historical opening balances are immutable here. Financial
                # corrections must be represented by audited ledger documents.
                conn.commit()
                return True
        except Exception as exc:
            logging.error(f"Error updating supplier: {exc}")
            return False

    def _save_initial_balances(
        self,
        cursor,
        supplier_id: int,
        base_metal_id: int,
        bal_gold: float,
        bal_money: float,
        bal_silver: float,
    ) -> None:
        if float(bal_money or 0) != 0:
            cursor.execute(
                """
                INSERT INTO PartnerInitialBalances (partner_type, partner_id, currency_id, initial_amount)
                VALUES ('SUPPLIER', %s, 1, %s)
                """,
                (supplier_id, float(bal_money)),
            )
        if float(bal_gold or 0) != 0 and base_metal_id:
            cursor.execute(
                """
                INSERT INTO PartnerInitialBalances (partner_type, partner_id, metal_type_id, initial_amount)
                VALUES ('SUPPLIER', %s, %s, %s)
                """,
                (supplier_id, base_metal_id, float(bal_gold)),
            )
        if float(bal_silver or 0) != 0:
            cursor.execute(
                """
                INSERT INTO PartnerInitialBalances (partner_type, partner_id, metal_type_id, initial_amount)
                VALUES ('SUPPLIER', %s, 6, %s)
                """,
                (supplier_id, float(bal_silver)),
            )

    def delete_supplier(self, sid: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM SupplierTransactions WHERE supplier_id=%s", (sid,))
                if cursor.fetchone()[0] > 0:
                    return False
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM PartnerInitialBalances
                    WHERE partner_id=%s AND partner_type='SUPPLIER'
                      AND ABS(initial_amount) > 0
                    """,
                    (sid,),
                )
                if cursor.fetchone()[0] > 0:
                    return False
                cursor.execute(
                    "DELETE FROM PartnerInitialBalances WHERE partner_id=%s AND partner_type='SUPPLIER'",
                    (sid,),
                )
                cursor.execute("DELETE FROM Suppliers WHERE id=%s", (sid,))
                conn.commit()
                return True
        except Exception as exc:
            logging.error(f"Error deleting supplier: {exc}")
            return False

    def get_all_suppliers(self) -> List[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        s.*,
                        (
                            SELECT metal_type_id
                            FROM PartnerInitialBalances
                            WHERE partner_id = s.id
                              AND partner_type = 'SUPPLIER'
                              AND metal_type_id IS NOT NULL
                            LIMIT 1
                        ) AS base_metal_type_id_from_initial,
                        (
                            SELECT COALESCE(SUM(initial_amount), 0)
                            FROM PartnerInitialBalances
                            WHERE partner_id = s.id
                              AND partner_type = 'SUPPLIER'
                              AND currency_id IS NOT NULL
                        ) AS initial_balance_money,
                        (
                            SELECT COALESCE(SUM(pib.initial_amount), 0)
                            FROM PartnerInitialBalances pib
                            LEFT JOIN MetalTypes mt ON mt.id = pib.metal_type_id
                            WHERE pib.partner_id = s.id
                              AND pib.partner_type = 'SUPPLIER'
                              AND pib.metal_type_id IS NOT NULL
                              AND (
                                  mt.metal_category = 'GOLD'
                                  OR (
                                      COALESCE(mt.metal_category, '') <> 'SILVER'
                                      AND LOWER(COALESCE(mt.name, '')) NOT LIKE '%argent%'
                                      AND pib.metal_type_id NOT IN (6,7,8,9)
                                  )
                              )
                        ) AS initial_balance_gold,
                        (
                            SELECT COALESCE(SUM(pib.initial_amount), 0)
                            FROM PartnerInitialBalances pib
                            LEFT JOIN MetalTypes mt ON mt.id = pib.metal_type_id
                            WHERE pib.partner_id = s.id
                              AND pib.partner_type = 'SUPPLIER'
                              AND pib.metal_type_id IS NOT NULL
                              AND (
                                  mt.metal_category = 'SILVER'
                                  OR LOWER(COALESCE(mt.name, '')) LIKE '%argent%'
                                  OR pib.metal_type_id IN (6,7,8,9)
                              )
                        ) AS initial_balance_silver
                    FROM Suppliers s
                    ORDER BY s.name ASC
                    """
                )
                suppliers = cursor.fetchall()
                for supplier in suppliers:
                    fallback_metal_id = supplier.pop("base_metal_type_id_from_initial", None)
                    if not supplier.get("base_metal_type_id"):
                        supplier["base_metal_type_id"] = fallback_metal_id
                return suppliers
        except Exception as exc:
            logging.error(f"Error getting suppliers: {exc}")
            return []

    def get_suppliers_with_current_balances(self) -> List[Dict]:
        suppliers = self.get_all_suppliers()
        if not suppliers:
            return suppliers

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        supplier_id,
                        money_balance_dzd,
                        gold_balance_grams,
                        silver_balance_grams
                    FROM SupplierBalanceView
                    """
                )
                balances_by_supplier = {
                    int(row["supplier_id"]): row for row in cursor.fetchall()
                }

            for supplier in suppliers:
                balances = balances_by_supplier.get(int(supplier["id"]), {})
                supplier["live_money"] = self._to_float(balances.get("money_balance_dzd"))
                supplier["live_gold"] = self._to_float(balances.get("gold_balance_grams"))
                supplier["live_silver"] = self._to_float(balances.get("silver_balance_grams"))
            return suppliers
        except Exception as exc:
            logging.error(f"Error getting supplier balance summary: {exc}")
            for supplier in suppliers:
                totals = {"DZD": 0.0, "OR": 0.0, "ARG": 0.0}
                for balance in self.get_supplier_current_balances(supplier["id"]):
                    code = str(balance.get("code") or "").upper()
                    if code in totals:
                        totals[code] += self._to_float(balance.get("balance"))
                supplier["live_money"] = totals["DZD"]
                supplier["live_gold"] = totals["OR"]
                supplier["live_silver"] = totals["ARG"]
            return suppliers

    def get_supplier_current_balances(self, supplier_id: int) -> List[Dict]:
        money_bal = 0.0
        gold_bal = 0.0
        silver_bal = 0.0

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT pib.*, mt.name AS metal_name, mt.metal_category
                    FROM PartnerInitialBalances pib
                    LEFT JOIN MetalTypes mt ON mt.id = pib.metal_type_id
                    WHERE pib.partner_id=%s AND pib.partner_type='SUPPLIER'
                    """,
                    (supplier_id,),
                )
                for row in cursor.fetchall():
                    if row.get("currency_id"):
                        money_bal += self._to_float(row.get("initial_amount"))
                    elif self._is_silver_asset(row.get("metal_type_id"), row.get("metal_name", ""), row.get("metal_category", "")):
                        silver_bal += self._to_float(row.get("initial_amount"))
                    else:
                        gold_bal += self._to_float(row.get("initial_amount"))

            for trans in self.get_supplier_history(supplier_id):
                money_bal += self._to_float(trans.get("money_delta"))
                if abs(self._to_float(trans.get("weight_delta"))) <= self.WEIGHT_EPSILON:
                    continue
                if trans.get("is_silver"):
                    silver_bal += self._to_float(trans.get("weight_delta"))
                else:
                    gold_bal += self._to_float(trans.get("weight_delta"))
        except Exception as exc:
            logging.error(f"Error calculating supplier balances: {exc}")

        return [
            {"type": "CURRENCY", "name": "DZD", "code": "DZD", "balance": money_bal},
            {"type": "METAL", "name": "OR", "code": "OR", "balance": gold_bal},
            {"type": "METAL", "name": "ARG", "code": "ARG", "balance": silver_bal},
        ]

    def get_supplier_history(self, supplier_id, start_date=None, end_date=None) -> List[Dict]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT
                        t.*,
                        c.code AS currency_code,
                        c.name AS currency_name,
                        c.symbol AS currency_symbol,
                        mt.id AS resolved_metal_type_id,
                        mt.name AS metal_name,
                        mt.metal_category,
                        mt.purity_value,
                        sa.code AS supplier_account_code,
                        sa.name AS supplier_account_name,
                        sa.account_type AS supplier_account_type,
                        so.status AS supplier_operation_status,
                        so.operation_type AS supplier_operation_type
                    FROM SupplierTransactions t
                    LEFT JOIN Currencies c ON t.currency_id = c.id
                    LEFT JOIN MetalTypes mt ON mt.id = COALESCE(t.input_metal_type_id, t.metal_type_id)
                    LEFT JOIN SupplierAccounts sa ON sa.id = t.supplier_account_id
                    LEFT JOIN SupplierOperations so ON so.id = t.operation_id
                    WHERE t.supplier_id = %s
                      AND (t.operation_id IS NULL OR so.status = 'POSTED')
                """
                params = [supplier_id]
                if start_date and end_date:
                    query += " AND DATE(t.transaction_date) BETWEEN %s AND %s"
                    params.extend([start_date, end_date])
                query += " ORDER BY t.transaction_date DESC, t.id DESC"
                cursor.execute(query, tuple(params))
                return [self._normalize_transaction_row(row) for row in cursor.fetchall()]
        except Exception as exc:
            logging.error(f"Error getting supplier history: {exc}")
            return []

    def get_supplier_balance(self, supplier_id: int) -> Tuple[float, float]:
        balances = self.get_supplier_current_balances(supplier_id)
        gold = next((self._to_float(b["balance"]) for b in balances if b.get("code") == "OR"), 0.0)
        money = next((self._to_float(b["balance"]) for b in balances if b.get("code") == "DZD"), 0.0)
        return gold, money

    def delete_transaction(self, trans_id: int) -> bool:
        logging.warning(
            "Direct deletion of supplier transaction %s was refused; use an audited reversal.",
            trans_id,
        )
        return False

    def update_transaction(
        self,
        trans_id: int,
        new_amount: float = None,
        new_notes: str = None,
        new_weight: float = None,
        new_money: float = None,
    ) -> bool:
        logging.warning(
            "Direct update of supplier transaction %s was refused; use an audited reversal/correction.",
            trans_id,
        )
        return False

    def process_multi_mode_settlement(
        self, supplier_id: int, data: Dict, user_id: int, *, artisan_compatibility: bool = False
    ) -> tuple:
        """Compatibility settlement path retained only for artisan workflows."""
        try:
            if not user_id:
                return False, "Une session utilisateur authentifiee est requise."
            if not artisan_compatibility:
                return (
                    False,
                    "Direct supplier ledger posting is disabled; use the audited supplier operation service.",
                )
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()

                items = data.get("items", [])
                coffre_id = data.get("coffre_id")
                apply_to_coffre = bool(data.get("apply_to_coffre", True))
                is_purchase = bool(data.get("is_purchase", False))

                if not items:
                    return False, "Aucun reglement fournisseur a enregistrer."

                for item in items:
                    val = self._to_float(item.get("value"))
                    paid_val = self._to_float(item.get("paid_value", val))
                    if not math.isfinite(val) or val <= 0:
                        return False, "Le montant ou poids doit etre superieur a zero."
                    if apply_to_coffre and coffre_id and (
                        not math.isfinite(paid_val) or paid_val <= 0
                    ):
                        return False, "Le mouvement de caisse doit etre superieur a zero."

                base_curr_id, base_rate = self._get_base_currency(cursor)

                for item in items:
                    val = self._to_float(item.get("value"))
                    paid_val = self._to_float(item.get("paid_value", val))
                    source_id = item.get("source_id")
                    source_name = str(item.get("source_name", "")).upper()
                    mode = str(item.get("mode", "")).upper()
                    custom_note = item.get("note", "")
                    is_fixing = bool(item.get("is_fixing", False))
                    fixing_price = self._to_float(item.get("fixing_price"))
                    is_metal = mode == "METAL"

                    description = custom_note or f"Source: {source_name}"
                    trans_type = "PURCHASE" if is_purchase else "PAYMENT"

                    currency_id = None
                    metal_type_id = None
                    legacy_amount = val
                    raw_weight = 0.0
                    amount_debit = amount_credit = 0.0
                    weight_debit = weight_credit = 0.0

                    if is_metal:
                        metal_type_id = self._currency_code_to_metal_type_id(cursor, supplier_id, source_name)
                        legacy_amount = val
                        raw_weight = val if is_fixing else paid_val
                        if is_purchase:
                            trans_type = "PURCHASE_GOODS"
                            weight_credit = val
                        else:
                            trans_type = "PAYMENT_FIXING" if is_fixing else "PAYMENT_METAL"
                            weight_debit = val
                    else:
                        supplier_val = val
                        currency_id = source_id or base_curr_id
                        if currency_id != base_curr_id:
                            cursor.execute("SELECT exchange_rate FROM Currencies WHERE id=%s", (currency_id,))
                            src_curr = cursor.fetchone()
                            src_rate = self._to_float(src_curr[0] if src_curr else 1.0) or 1.0
                            supplier_val = round((val * src_rate) / base_rate, 2)
                            if not custom_note:
                                description += f" (Equiv: {supplier_val:,.2f} DA)"
                            currency_id = base_curr_id

                        legacy_amount = supplier_val
                        if is_purchase:
                            trans_type = "PURCHASE_MONEY"
                            amount_credit = supplier_val
                        else:
                            trans_type = "PAYMENT_CASH"
                            amount_debit = supplier_val

                    cursor.execute(
                        """
                        INSERT INTO SupplierTransactions
                        (
                            supplier_id, type, amount, currency_id, metal_type_id, description,
                            amount_debit, amount_credit,
                            accounted_weight_debit, accounted_weight_credit,
                            labor_price_per_gram, fixing_price_per_gram,
                            input_metal_type_id, raw_weight,
                            transaction_date
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            supplier_id,
                            trans_type,
                            legacy_amount,
                            currency_id,
                            metal_type_id,
                            description,
                            amount_debit,
                            amount_credit,
                            weight_debit,
                            weight_credit,
                            0.0,
                            fixing_price,
                            metal_type_id,
                            raw_weight,
                        ),
                    )
                    trans_id = cursor.lastrowid

                    if apply_to_coffre and coffre_id and paid_val > 0:
                        vault_currency_id = base_curr_id if is_fixing else (source_id or base_curr_id)
                        vault_amount = paid_val if is_purchase else -paid_val
                        vault_type = "SUPPLIER_PURCHASE" if is_purchase else "SUPPLIER_PAYMENT"
                        if is_fixing:
                            vault_type = "SUPPLIER_FIXING"
                        cursor.execute(
                            """
                            INSERT INTO MoneyTransactions
                            (
                                location_id, currency_id, amount, transaction_type,
                                description, user_id, related_supplier_transaction_id, transaction_date
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                            """,
                            (
                                coffre_id,
                                vault_currency_id,
                                vault_amount,
                                vault_type,
                                f"Fournisseur ID: {supplier_id} | {description}",
                                user_id,
                                trans_id,
                            ),
                        )

                conn.commit()
                return True, "Operation fournisseur enregistree avec succes."
        except Exception as exc:
            if "conn" in locals() and conn:
                conn.rollback()
            logging.error(f"Error in supplier settlement: {exc}", exc_info=True)
            return False, f"Erreur de base de donnees : {exc}"
