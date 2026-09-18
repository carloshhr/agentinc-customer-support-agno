import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from .models import AuditLog

FORBIDDEN_KEYS = {
    "password",
    "password_hash",
    "session",
    "cookie",
    "csrf",
    "token",
    "pat",
    "authorization",
    "body",
    "content",
    "payload",
    "response",
}


def redact_metadata(metadata: Mapping[str, Any]) -> dict[str, str]:
    return {
        key: str(value)
        for key, value in metadata.items()
        if key.lower() not in FORBIDDEN_KEYS and "token" not in key.lower() and not key.lower().endswith("_pat")
    }


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_audit_record(
    operator_id: str | None, event_type: str, outcome: str, request_id: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "operator_id": operator_id,
        "event_type": event_type,
        "outcome": outcome,
        "request_id": request_id,
        "metadata": redact_metadata(metadata),
    }


def persist_audit(
    db: Session,
    operator_id: Any,
    event_type: str,
    outcome: str,
    request_id: str,
    metadata: Mapping[str, Any],
) -> None:
    record = build_audit_record(operator_id, event_type, outcome, request_id, metadata)
    db.add(
        AuditLog(
            operator_id=record["operator_id"],
            event_type=record["event_type"],
            outcome=record["outcome"],
            request_id=record["request_id"],
            metadata_json=record["metadata"],
            created_at=datetime.now(UTC),
        )
    )
