"""Database manager for official suppliers and official stock operations."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple



OFFICIAL_OPERATION_TYPES = {"INCOMING", "OUTGOING"}
OFFICIAL_SOURCE_KINDS = {"MANUAL", "IMPORT", "SALE", "ADJUSTMENT"}


class OfficialSupplierManager:
    """Manage the official supplier register and monthly IN/OUT operations."""

    def __init__(self, db_instance):
        self.db = db_instance

    @staticmethod
    def _money(value) -> Decimal:
        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _weight(value) -> Decimal:
        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.001"))
        except (InvalidOperation, ValueError):
            return Decimal("0.000")

    @staticmethod
    def _positive_id(value) -> Optional[int]:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _clean_text(value) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

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

    @classmethod
    def _normalize_operation_type(cls, operation_type: str = None, signed_weight=None) -> str:
        raw = str(operation_type or "").strip().upper()
        if not raw and signed_weight is not None:
            raw = "OUTGOING" if cls._weight(signed_weight) < 0 else "INCOMING"
        aliases = {
            "IN": "INCOMING",
            "ENTRY": "INCOMING",
            "ENTREE": "INCOMING",
            "ENTREE_OFFICIELLE": "INCOMING",
            "ACHAT": "INCOMING",
            "PURCHASE": "INCOMING",
            "OUT": "OUTGOING",
            "EXIT": "OUTGOING",
            "SORTIE": "OUTGOING",
            "VENTE": "OUTGOING",
            "SALE": "OUTGOING",
        }
        normalized = aliases.get(raw, raw or "INCOMING")
        if normalized not in OFFICIAL_OPERATION_TYPES:
            raise ValueError(f"Unsupported official operation type: {operation_type}")
        return normalized

    @staticmethod
    def _normalize_source_kind(source_kind: str = None) -> str:
        normalized = str(source_kind or "MANUAL").strip().upper()
        if normalized not in OFFICIAL_SOURCE_KINDS:
            normalized = "MANUAL"
        return normalized

    @staticmethod
    def _date_param(value):
        if isinstance(value, (datetime, date)):
            return value
        text = str(value or "").strip()
        return text or None

    def create_official_supplier(
        self,
        name: str,
        supplier_id: Optional[int] = None,
        official_code: str = None,
        phone: str = None,
        tax_identifier: str = None,
        register_number: str = None,
        address: str = None,
        notes: str = None,
        user_id: Optional[int] = None,
        is_active: bool = True,
    ) -> Optional[int]:
        """Create one official supplier row and return its id."""
        if not self._clean_text(name):
            return None
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO OfficialSuppliers
                    (supplier_id, official_code, name, phone, tax_identifier,
                     register_number, address, notes, is_active, created_by_user_id,
                     created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """,
                    (
                        self._positive_id(supplier_id),
                        self._clean_text(official_code),
                        self._clean_text(name),
                        self._clean_text(phone),
                        self._clean_text(tax_identifier),
                        self._clean_text(register_number),
                        self._clean_text(address),
                        self._clean_text(notes),
                        bool(is_active),
                        self._positive_id(user_id),
                    ),
                )
                supplier_id = cursor.lastrowid
                conn.commit()
                return supplier_id
        except Exception as exc:
            logging.error("Error creating official supplier: %s", exc)
            return None

    def update_official_supplier(self, official_supplier_id: int, **fields) -> bool:
        """Update editable official supplier fields."""
        allowed = {
            "supplier_id": self._positive_id,
            "official_code": self._clean_text,
            "name": self._clean_text,
            "phone": self._clean_text,
            "tax_identifier": self._clean_text,
            "register_number": self._clean_text,
            "address": self._clean_text,
            "notes": self._clean_text,
            "is_active": bool,
        }
        assignments = []
        params: List[Any] = []
        for key, normalizer in allowed.items():
            if key not in fields:
                continue
            value = normalizer(fields[key])
            if key == "name" and not value:
                return False
            assignments.append(f"{key} = %s")
            params.append(value)
        if not assignments:
            return True
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE OfficialSuppliers
                    SET {', '.join(assignments)}, updated_at = NOW()
                    WHERE id = %s
                    """,
                    tuple(params + [int(official_supplier_id)]),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error updating official supplier %s: %s", official_supplier_id, exc)
            return False

    def set_official_supplier_active(self, official_supplier_id: int, is_active: bool = True) -> bool:
        return self.update_official_supplier(official_supplier_id, is_active=is_active)

    def get_official_supplier(self, official_supplier_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT os.*, s.name AS linked_supplier_name, u.username AS created_by_username
                    FROM OfficialSuppliers os
                    LEFT JOIN Suppliers s ON s.id = os.supplier_id
                    LEFT JOIN Users u ON u.id = os.created_by_user_id
                    WHERE os.id = %s
                    """,
                    (int(official_supplier_id),),
                )
                return cursor.fetchone()
        except Exception as exc:
            logging.error("Error loading official supplier %s: %s", official_supplier_id, exc)
            return None

    def get_official_supplier_by_supplier_id(self, supplier_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT *
                    FROM OfficialSuppliers
                    WHERE supplier_id = %s
                    LIMIT 1
                    """,
                    (int(supplier_id),),
                )
                return cursor.fetchone()
        except Exception as exc:
            logging.error("Error loading official supplier for supplier %s: %s", supplier_id, exc)
            return None

    def list_official_suppliers(
        self,
        search_text: str = "",
        active_only: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        filters = []
        params: List[Any] = []
        if active_only:
            filters.append("os.is_active = TRUE")
        search_text = str(search_text or "").strip()
        if search_text:
            like = f"%{search_text}%"
            filters.append(
                "(os.name LIKE %s OR os.official_code LIKE %s OR "
                "os.tax_identifier LIKE %s OR os.register_number LIKE %s)"
            )
            params.extend([like, like, like, like])
        where = "WHERE " + " AND ".join(filters) if filters else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT os.*, s.name AS linked_supplier_name
                    FROM OfficialSuppliers os
                    LEFT JOIN Suppliers s ON s.id = os.supplier_id
                    {where}
                    ORDER BY os.is_active DESC, os.name ASC, os.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params + [int(limit), int(offset)]),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error listing official suppliers: %s", exc)
            return []

    def record_operation(
        self,
        official_supplier_id: int = None,
        operation_type: str = None,
        weight_g=0,
        amount_da=0,
        operation_date=None,
        metal_type_id: Optional[int] = None,
        document_number: str = None,
        description: str = None,
        notes: str = None,
        source_kind: str = "MANUAL",
        user_id: Optional[int] = None,
    ) -> Optional[int]:
        """Record one official operation. Weight is stored positive; type carries direction."""
        signed_weight = self._weight(weight_g)
        operation_type = self._normalize_operation_type(operation_type, signed_weight)
        supplier_id = self._positive_id(official_supplier_id)
        if operation_type == "INCOMING" and not supplier_id:
            return None
        if operation_type == "OUTGOING":
            supplier_id = None
        weight = abs(signed_weight)
        amount = abs(self._money(amount_da))
        if weight <= 0 and amount <= 0:
            return None
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO OfficialSupplierOperations
                    (official_supplier_id, operation_date, operation_type, metal_type_id,
                     weight_g, amount_da, document_number, description, notes,
                     source_kind, created_by_user_id, created_at, updated_at)
                    VALUES (%s, COALESCE(%s, NOW()), %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """,
                    (
                        supplier_id,
                        self._date_param(operation_date),
                        operation_type,
                        self._positive_id(metal_type_id),
                        weight,
                        amount,
                        self._clean_text(document_number),
                        self._clean_text(description),
                        self._clean_text(notes),
                        self._normalize_source_kind(source_kind),
                        self._positive_id(user_id),
                    ),
                )
                operation_id = cursor.lastrowid
                conn.commit()
                return operation_id
        except Exception as exc:
            logging.error("Error recording official supplier operation: %s", exc)
            return None

    def record_incoming(self, official_supplier_id: int, weight_g, amount_da=0, **kwargs) -> Optional[int]:
        return self.record_operation(
            official_supplier_id,
            operation_type="INCOMING",
            weight_g=weight_g,
            amount_da=amount_da,
            **kwargs,
        )

    def record_outgoing(self, official_supplier_id: int = None, weight_g=0, amount_da=0, **kwargs) -> Optional[int]:
        return self.record_operation(
            official_supplier_id,
            operation_type="OUTGOING",
            weight_g=weight_g,
            amount_da=amount_da,
            **kwargs,
        )

    def get_operation(self, operation_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT oso.*, os.name AS official_supplier_name, mt.name AS metal_type_name,
                           u.username AS created_by_username
                    FROM OfficialSupplierOperations oso
                    LEFT JOIN OfficialSuppliers os ON os.id = oso.official_supplier_id
                    LEFT JOIN MetalTypes mt ON mt.id = oso.metal_type_id
                    LEFT JOIN Users u ON u.id = oso.created_by_user_id
                    WHERE oso.id = %s
                    """,
                    (int(operation_id),),
                )
                return cursor.fetchone()
        except Exception as exc:
            logging.error("Error loading official supplier operation %s: %s", operation_id, exc)
            return None

    def list_operations(
        self,
        official_supplier_id: Optional[int] = None,
        operation_type: Optional[str] = None,
        source_kind: Optional[str] = None,
        start_date=None,
        end_date=None,
        search_text: str = "",
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        filters = []
        params: List[Any] = []
        if official_supplier_id:
            filters.append("oso.official_supplier_id = %s")
            params.append(int(official_supplier_id))
        if operation_type:
            filters.append("oso.operation_type = %s")
            params.append(self._normalize_operation_type(operation_type))
        if source_kind:
            filters.append("oso.source_kind = %s")
            params.append(self._normalize_source_kind(source_kind))
        if start_date:
            filters.append("DATE(oso.operation_date) >= %s")
            params.append(self._date_param(start_date))
        if end_date:
            filters.append("DATE(oso.operation_date) <= %s")
            params.append(self._date_param(end_date))
        search_text = str(search_text or "").strip()
        if search_text:
            like = f"%{search_text}%"
            filters.append(
                "(oso.document_number LIKE %s OR oso.description LIKE %s OR "
                "oso.notes LIKE %s OR os.name LIKE %s)"
            )
            params.extend([like, like, like, like])
        where = "WHERE " + " AND ".join(filters) if filters else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT oso.*, os.name AS official_supplier_name, mt.name AS metal_type_name
                    FROM OfficialSupplierOperations oso
                    LEFT JOIN OfficialSuppliers os ON os.id = oso.official_supplier_id
                    LEFT JOIN MetalTypes mt ON mt.id = oso.metal_type_id
                    {where}
                    ORDER BY oso.operation_date DESC, oso.id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params + [int(limit), int(offset)]),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error listing official supplier operations: %s", exc)
            return []

    def update_operation(self, operation_id: int, **fields) -> bool:
        allowed = {
            "official_supplier_id": self._positive_id,
            "operation_date": self._date_param,
            "operation_type": self._normalize_operation_type,
            "metal_type_id": self._positive_id,
            "weight_g": lambda value: abs(self._weight(value)),
            "amount_da": lambda value: abs(self._money(value)),
            "document_number": self._clean_text,
            "description": self._clean_text,
            "notes": self._clean_text,
            "source_kind": self._normalize_source_kind,
            "created_by_user_id": self._positive_id,
        }
        if fields.get("operation_type") is not None:
            normalized_type = self._normalize_operation_type(fields.get("operation_type"))
            fields["operation_type"] = normalized_type
            if normalized_type == "OUTGOING":
                fields["official_supplier_id"] = None
        assignments = []
        params: List[Any] = []
        for key, normalizer in allowed.items():
            if key not in fields:
                continue
            value = normalizer(fields[key])
            assignments.append(f"{key} = %s")
            params.append(value)
        if not assignments:
            return True
        if "weight_g" in fields and self._weight(fields["weight_g"]) <= 0 and self._money(fields.get("amount_da")) <= 0:
            return False
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    UPDATE OfficialSupplierOperations
                    SET {', '.join(assignments)}, updated_at = NOW()
                    WHERE id = %s
                    """,
                    tuple(params + [int(operation_id)]),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error updating official supplier operation %s: %s", operation_id, exc)
            return False

    def delete_operation(self, operation_id: int) -> bool:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM OfficialSupplierOperations WHERE id = %s",
                    (int(operation_id),),
                )
                conn.commit()
                return True
        except Exception as exc:
            logging.error("Error deleting official supplier operation %s: %s", operation_id, exc)
            return False

    def get_monthly_summary(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        official_supplier_id: Optional[int] = None,
        start_date=None,
        end_date=None,
    ) -> List[Dict[str, Any]]:
        filters = []
        params: List[Any] = []
        if official_supplier_id:
            filters.append("oso.official_supplier_id = %s")
            params.append(int(official_supplier_id))
        if year:
            filters.append("YEAR(oso.operation_date) = %s")
            params.append(int(year))
        if month:
            filters.append("MONTH(oso.operation_date) = %s")
            params.append(int(month))
        if start_date:
            filters.append("DATE(oso.operation_date) >= %s")
            params.append(self._date_param(start_date))
        if end_date:
            filters.append("DATE(oso.operation_date) <= %s")
            params.append(self._date_param(end_date))
        where = "WHERE " + " AND ".join(filters) if filters else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT
                        oso.official_supplier_id,
                        COALESCE(os.name, 'Operation globale') AS official_supplier_name,
                        YEAR(oso.operation_date) AS summary_year,
                        MONTH(oso.operation_date) AS summary_month,
                        SUM(CASE WHEN oso.operation_type = 'INCOMING' THEN oso.weight_g ELSE 0 END)
                            AS incoming_weight_g,
                        SUM(CASE WHEN oso.operation_type = 'OUTGOING' THEN oso.weight_g ELSE 0 END)
                            AS outgoing_weight_g,
                        SUM(CASE WHEN oso.operation_type = 'INCOMING' THEN oso.amount_da ELSE 0 END)
                            AS incoming_amount_da,
                        SUM(CASE WHEN oso.operation_type = 'OUTGOING' THEN oso.amount_da ELSE 0 END)
                            AS outgoing_amount_da,
                        SUM(CASE
                            WHEN oso.operation_type = 'INCOMING' THEN oso.weight_g
                            ELSE -oso.weight_g
                        END) AS net_weight_g,
                        SUM(CASE
                            WHEN oso.operation_type = 'INCOMING' THEN oso.amount_da
                            ELSE -oso.amount_da
                        END) AS net_amount_da,
                        COUNT(*) AS operation_count
                    FROM OfficialSupplierOperations oso
                    LEFT JOIN OfficialSuppliers os ON os.id = oso.official_supplier_id
                    {where}
                    GROUP BY oso.official_supplier_id, os.name,
                             YEAR(oso.operation_date), MONTH(oso.operation_date)
                    ORDER BY summary_year DESC, summary_month DESC, os.name ASC
                    """,
                    tuple(params),
                )
                return cursor.fetchall() or []
        except Exception as exc:
            logging.error("Error loading official supplier monthly summary: %s", exc)
            return []

    def get_totals(
        self,
        official_supplier_id: Optional[int] = None,
        start_date=None,
        end_date=None,
    ) -> Dict[str, Any]:
        filters = []
        params: List[Any] = []
        if official_supplier_id:
            filters.append("official_supplier_id = %s")
            params.append(int(official_supplier_id))
        if start_date:
            filters.append("DATE(operation_date) >= %s")
            params.append(self._date_param(start_date))
        if end_date:
            filters.append("DATE(operation_date) <= %s")
            params.append(self._date_param(end_date))
        where = "WHERE " + " AND ".join(filters) if filters else ""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    f"""
                    SELECT
                        SUM(CASE WHEN operation_type = 'INCOMING' THEN weight_g ELSE 0 END)
                            AS incoming_weight_g,
                        SUM(CASE WHEN operation_type = 'OUTGOING' THEN weight_g ELSE 0 END)
                            AS outgoing_weight_g,
                        SUM(CASE WHEN operation_type = 'INCOMING' THEN amount_da ELSE 0 END)
                            AS incoming_amount_da,
                        SUM(CASE WHEN operation_type = 'OUTGOING' THEN amount_da ELSE 0 END)
                            AS outgoing_amount_da,
                        SUM(CASE WHEN operation_type = 'INCOMING' THEN weight_g ELSE -weight_g END)
                            AS net_weight_g,
                        SUM(CASE WHEN operation_type = 'INCOMING' THEN amount_da ELSE -amount_da END)
                            AS net_amount_da,
                        COUNT(*) AS operation_count
                    FROM OfficialSupplierOperations
                    {where}
                    """,
                    tuple(params),
                )
                row = cursor.fetchone() or {}
                return row
        except Exception as exc:
            logging.error("Error loading official supplier totals: %s", exc)
            return {}

    @staticmethod
    def _coerce_excel_date(value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        try:
            if value != value:
                return None
        except TypeError:
            pass
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
            return parsed
        except ValueError:
            return None

    @classmethod
    def parse_ps_workbook(cls, file_path: str, sheet_name: str = None) -> List[Dict[str, Any]]:
        """Parse the legacy Ps workbook into unsigned official operation payloads."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is required to import official supplier workbooks.") from exc

        workbook = pd.ExcelFile(file_path)
        target_sheet = sheet_name or workbook.sheet_names[0]
        frame = pd.read_excel(file_path, sheet_name=target_sheet, header=None)
        return cls.parse_ps_dataframe(frame, source_label=f"{Path(file_path).name}:{target_sheet}")

    @classmethod
    def parse_ps_dataframe(cls, frame, source_label: str = "workbook") -> List[Dict[str, Any]]:
        """Parse rows shaped like Date / Poids / Observation from the legacy sheet."""
        rows = []
        for row_index, row in frame.iterrows():
            operation_date = cls._coerce_excel_date(row.iloc[1] if len(row) > 1 else None)
            weight = cls._weight(row.iloc[2] if len(row) > 2 else None)
            if not operation_date or weight == 0:
                continue
            description = cls._clean_text(row.iloc[3] if len(row) > 3 else None)
            operation_type = cls._normalize_operation_type(signed_weight=weight)
            rows.append(
                {
                    "operation_date": operation_date,
                    "operation_type": operation_type,
                    "weight_g": abs(weight),
                    "amount_da": Decimal("0.00"),
                    "description": description,
                    "source_kind": "IMPORT",
                    "notes": f"Imported from {source_label}, row {int(row_index) + 1}; raw_weight={weight}",
                }
            )
        return rows

    def import_ps_workbook(
        self,
        file_path: str,
        official_supplier_id: int,
        sheet_name: str = None,
        metal_type_id: Optional[int] = None,
        user_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Import legacy Ps workbook rows as official supplier operations."""
        parsed_rows = self.parse_ps_workbook(file_path, sheet_name=sheet_name)
        if dry_run:
            return {
                "imported": 0,
                "skipped": 0,
                "operation_ids": [],
                "rows": parsed_rows,
            }
        return self.import_operations(
            official_supplier_id,
            parsed_rows,
            metal_type_id=metal_type_id,
            user_id=user_id,
            default_source_kind="IMPORT",
        )

    def import_operations(
        self,
        official_supplier_id: int,
        operations: Sequence[Dict[str, Any]],
        metal_type_id: Optional[int] = None,
        user_id: Optional[int] = None,
        default_source_kind: str = "IMPORT",
    ) -> Dict[str, Any]:
        operation_ids: List[int] = []
        skipped = 0
        for operation in operations:
            operation_id = self.record_operation(
                official_supplier_id,
                operation_type=operation.get("operation_type"),
                weight_g=operation.get("weight_g"),
                amount_da=operation.get("amount_da", 0),
                operation_date=operation.get("operation_date"),
                metal_type_id=operation.get("metal_type_id") or metal_type_id,
                document_number=operation.get("document_number"),
                description=operation.get("description"),
                notes=operation.get("notes"),
                source_kind=operation.get("source_kind") or default_source_kind,
                user_id=operation.get("user_id") or user_id,
            )
            if operation_id:
                operation_ids.append(operation_id)
            else:
                skipped += 1
        return {
            "imported": len(operation_ids),
            "skipped": skipped,
            "operation_ids": operation_ids,
        }

    def bulk_record_operations(
        self,
        official_supplier_id: int,
        operations: Iterable[Dict[str, Any]],
        metal_type_id: Optional[int] = None,
        user_id: Optional[int] = None,
        source_kind: str = "MANUAL",
    ) -> Dict[str, Any]:
        """Compatibility wrapper for batch inserts through the public API."""
        return self.import_operations(
            official_supplier_id,
            list(operations),
            metal_type_id=metal_type_id,
            user_id=user_id,
            default_source_kind=source_kind,
        )
