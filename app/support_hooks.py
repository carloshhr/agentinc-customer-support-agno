"""Fail-soft post-hook persistence for completed support-team replies."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from agno.run.base import RunStatus

from app.store import StoreRepository, get_store_repository
from app.support_models import CustomerEmailReply

logger = logging.getLogger(__name__)


def record_interaction_from_output(repository: StoreRepository, run_output: Any) -> bool:
    """Persist a completed typed reply once; malformed and paused output is ignored."""
    if getattr(run_output, "status", None) != RunStatus.completed:
        return False
    reply = getattr(run_output, "content", None)
    if not isinstance(reply, CustomerEmailReply):
        return False
    metadata = getattr(run_output, "metadata", None) or {}
    approval = metadata.get("approval") if isinstance(metadata, dict) else None
    approval_id = approval.get("id") if isinstance(approval, dict) else None
    if reply.outcome == "refund_completed":
        refund_outcome = "approved" if approval_id else "automatic"
    elif reply.outcome == "refund_rejected":
        refund_outcome = "rejected"
    else:
        refund_outcome = "not_applicable"
    return repository.upsert_interaction(
        {
            "message_id": reply.message_id,
            "team_run_id": getattr(run_output, "run_id", None),
            "category": reply.category.value,
            "issue_code": reply.issue_code.value,
            "order_id": reply.order_id,
            "product_id": reply.product_id,
            "outcome": reply.outcome,
            "refund_outcome": refund_outcome,
            "approval_id": approval_id,
            "completed_at": datetime.now(UTC).isoformat(),
        }
    )


def persist_customer_support_interaction(run_output: Any, **_: Any) -> None:
    """Team post-hook that never lets analytics persistence suppress a valid reply."""
    try:
        record_interaction_from_output(get_store_repository(), run_output)
    except Exception:
        logger.exception(
            "Customer-support interaction persistence failed for run_id=%s", getattr(run_output, "run_id", None)
        )
