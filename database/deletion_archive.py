"""
Operational deletion archive.

Rows removed from the active sales/payment workflow are stored here first so a
technical restore remains possible without keeping deleted documents visible in
the application screens.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional


ARCHIVE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS OperationalDeletionArchive (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    entity_type VARCHAR(40) NOT NULL,
    entity_id BIGINT NULL,
    document_number VARCHAR(80) NULL,
    client_id BIGINT NULL,
    deleted_by_user_id BIGINT NULL,
    reason TEXT NULL,
    payload_json LONGTEXT NOT NULL,
    metadata_json LONGTEXT NULL,
    restore_status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    restored_at DATETIME NULL,
    restored_by_user_id BIGINT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_operational_deletion_entity (entity_type, entity_id),
    INDEX idx_operational_deletion_client (client_id),
    INDEX idx_operational_deletion_created (created_at),
    INDEX idx_operational_deletion_status (restore_status)
)
"""


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)


def ensure_operational_deletion_archive(cursor) -> None:
    cursor.execute(ARCHIVE_TABLE_DDL)


def archive_operational_deletion(
    cursor,
    entity_type: str,
    entity_id: Optional[int],
    payload: Dict[str, Any],
    *,
    document_number: Optional[str] = None,
    client_id: Optional[int] = None,
    deleted_by_user_id: Optional[int] = None,
    reason: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    cursor.execute(
        """
        INSERT INTO OperationalDeletionArchive
        (entity_type, entity_id, document_number, client_id, deleted_by_user_id,
         reason, payload_json, metadata_json, restore_status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'AVAILABLE', NOW(), NOW())
        """,
        (
            entity_type,
            entity_id,
            document_number,
            client_id,
            deleted_by_user_id,
            reason or "",
            _dump_json(payload),
            _dump_json(metadata or {}),
        ),
    )
    return int(cursor.lastrowid or 0)


def fetch_archived_deletion(cursor, archive_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT *
        FROM OperationalDeletionArchive
        WHERE id = %s
        """,
        (archive_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    for key in ("payload_json", "metadata_json"):
        raw_value = row.get(key)
        if isinstance(raw_value, str) and raw_value:
            row[key] = json.loads(raw_value)
    return row


def mark_archived_deletion_restored(
    cursor,
    archive_id: int,
    restored_by_user_id: Optional[int] = None,
) -> None:
    cursor.execute(
        """
        UPDATE OperationalDeletionArchive
        SET restore_status = 'RESTORED',
            restored_at = NOW(),
            restored_by_user_id = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (restored_by_user_id, archive_id),
    )
