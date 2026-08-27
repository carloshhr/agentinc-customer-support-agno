"""Interaction post-hook behavior remains idempotent and fail-soft."""

from types import SimpleNamespace

from agno.run.base import RunStatus

from app.support_hooks import record_interaction_from_output
from app.support_models import CustomerEmailReply, IssueCode, SupportCategory


def _reply() -> CustomerEmailReply:
    return CustomerEmailReply(
        message_id="EMAIL-HOOK-1",
        subject="Order update",
        body="Your order is in transit.",
        category=SupportCategory.ORDER,
        issue_code=IssueCode.TRACKING_REQUEST,
        outcome="answered",
        order_id="ORD-LUMEN-1001",
    )


def test_paused_or_malformed_output_is_not_recorded(store) -> None:
    paused = SimpleNamespace(status=RunStatus.paused, content=_reply(), run_id="RUN-PAUSED", metadata={})
    malformed = SimpleNamespace(status=RunStatus.completed, content="not a typed reply", run_id="RUN-BAD", metadata={})

    assert record_interaction_from_output(store, paused) is False
    assert record_interaction_from_output(store, malformed) is False
    assert (
        store.insights(
            __import__("datetime").date(2026, 1, 1), __import__("datetime").date(2027, 1, 1)
        ).total_interactions
        == 0
    )


def test_completed_hook_retry_upserts_one_interaction(store) -> None:
    output = SimpleNamespace(status=RunStatus.completed, content=_reply(), run_id="RUN-COMPLETE", metadata={})

    assert record_interaction_from_output(store, output) is True
    assert record_interaction_from_output(store, output) is False
    assert (
        store.insights(
            __import__("datetime").date(2026, 1, 1), __import__("datetime").date(2027, 1, 1)
        ).total_interactions
        == 1
    )
