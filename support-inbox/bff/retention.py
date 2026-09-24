"""Deterministic retention hook for the migration/cleanup role."""

from datetime import UTC, datetime, timedelta
from typing import cast

from app.models import AuditLog, OperatorSession
from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session


def purge_retained_data(db: Session, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=90)
    result = cast(CursorResult[tuple[object, ...]], db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff)))
    db.execute(
        delete(OperatorSession).where(OperatorSession.revoked_at.is_not(None), OperatorSession.revoked_at < cutoff)
    )
    db.commit()
    return result.rowcount or 0
