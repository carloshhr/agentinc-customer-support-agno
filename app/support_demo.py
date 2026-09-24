"""Deterministic, model-free Customer Support demo data for local evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agno.run.base import RunStatus
from agno.run.team import TeamRunInput, TeamRunOutput
from agno.session.team import TeamSession

from app.store import get_store_repository
from app.support_models import CustomerEmail, CustomerEmailReply, IssueCode, SupportCategory
from teams.customer_support import customer_support_team

_DEMO_CREATED_AT = 1_735_689_600


def _completed_run(
    *,
    session_id: str,
    run_id: str,
    email: CustomerEmail,
    reply: CustomerEmailReply,
    created_at: int,
) -> TeamRunOutput:
    return TeamRunOutput(
        run_id=run_id,
        team_id="customer-support",
        session_id=session_id,
        input=TeamRunInput(input_content=email),
        content=reply,
        status=RunStatus.completed,
        created_at=created_at,
    )


def demo_support_runs() -> tuple[TeamRunOutput, ...]:
    """Return fixed public-safe runs without invoking agents, tools, or models."""
    tracking_email = CustomerEmail(
        message_id="DEMO-SUPPORT-EMAIL-TRACKING-001",
        thread_id="DEMO-SUPPORT-TRACKING-001",
        from_email="alex@example.test",
        subject="Where is my order?",
        body="Please share the tracking status for ORD-LUMEN-1001.",
    )
    sizing_email = CustomerEmail(
        message_id="DEMO-SUPPORT-EMAIL-SIZING-001",
        thread_id="DEMO-SUPPORT-SIZING-001",
        from_email="sam@example.test",
        subject="Mosslight Tee sizing",
        body="What is the chest width for size XL?",
    )
    refund_email = CustomerEmail(
        message_id="DEMO-SUPPORT-EMAIL-REFUND-001",
        thread_id="DEMO-SUPPORT-REFUND-001",
        from_email="dana@example.test",
        subject="Refund request",
        body="Please refund ORD-LUMEN-1004 because it did not meet my expectations.",
    )

    return (
        _completed_run(
            session_id="DEMO-SUPPORT-TRACKING-001",
            run_id="DEMO-SUPPORT-RUN-TRACKING-001",
            email=tracking_email,
            reply=CustomerEmailReply(
                message_id=tracking_email.message_id,
                subject="Tracking update",
                body="Your order is in transit. Its tracking information is available in the order record.",
                category=SupportCategory.ORDER,
                issue_code=IssueCode.TRACKING_REQUEST,
                outcome="answered",
                order_id="ORD-LUMEN-1001",
            ),
            created_at=_DEMO_CREATED_AT,
        ),
        _completed_run(
            session_id="DEMO-SUPPORT-SIZING-001",
            run_id="DEMO-SUPPORT-RUN-SIZING-001",
            email=sizing_email,
            reply=CustomerEmailReply(
                message_id=sizing_email.message_id,
                subject="Mosslight Tee size guide",
                body="The chest width for size XL is 58 cm.",
                category=SupportCategory.SIZING,
                issue_code=IssueCode.SIZE_RECOMMENDATION,
                outcome="answered",
                product_id="PRD-MOSS-TEE",
            ),
            created_at=_DEMO_CREATED_AT + 60,
        ),
        TeamRunOutput(
            run_id="DEMO-SUPPORT-RUN-REFUND-001",
            team_id="customer-support",
            session_id="DEMO-SUPPORT-REFUND-001",
            input=TeamRunInput(input_content=refund_email),
            status=RunStatus.paused,
            created_at=_DEMO_CREATED_AT + 120,
        ),
    )


def _persist_run(team: Any, run: TeamRunOutput) -> None:
    """Persist one new demo run through the framework's session and run APIs."""
    assert run.session_id is not None
    session = TeamSession(
        session_id=run.session_id,
        team_id=team.id,
        created_at=run.created_at,
        updated_at=run.created_at,
    )
    session.upsert_run(run_response=run)
    team.save_session(session)
    if team.db is None:
        raise RuntimeError("Customer Support requires a database to seed demo data.")
    team.db.upsert_run(run, session_id=run.session_id, user_id=run.user_id)  # type: ignore[attr-defined]


def seed_support_demo_threads(
    *,
    team: Any = customer_support_team,
    repository: Any = None,
    runs: Iterable[TeamRunOutput] | None = None,
) -> None:
    """Seed local Customer Support fixtures once without changing existing sessions."""
    (repository or get_store_repository()).seed_orders()
    for run in runs or demo_support_runs():
        if run.session_id is None:
            raise ValueError("Demo Customer Support runs require a session ID.")
        if team.get_session(session_id=run.session_id, user_id=None) is not None:
            continue
        _persist_run(team, run)
