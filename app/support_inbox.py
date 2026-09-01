"""Safe Customer Support inbox DTOs and browser API."""

from collections.abc import Sequence
from datetime import UTC, datetime
from mimetypes import guess_type
from pathlib import Path
from typing import Literal

from agno.db.base import SessionType
from agno.run.base import RunStatus
from agno.run.team import TeamRunOutput
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field, model_serializer

from app.support_models import CustomerEmail, CustomerEmailReply
from db import get_postgres_db
from teams.customer_support import customer_support_team

router = APIRouter(tags=["support-inbox"])
frontend_directory = Path(__file__).parent.parent / "frontend" / "support-inbox" / "dist"

ThreadStatus = Literal["completed", "approval_pending", "incomplete"]


class ThreadSummary(BaseModel):
    """Safe list representation of a support conversation."""

    session_id: str
    subject: str
    customer_email: str
    preview: str
    last_message_at: str
    status: ThreadStatus


class InboxMessage(BaseModel):
    """Allow-listed inbound or completed outbound email."""

    message_id: str
    direction: Literal["inbound", "outbound"]
    from_email: str
    subject: str
    body: str
    sent_at: str
    category: str | None = None
    issue_code: str | None = None
    outcome: str | None = None

    @model_serializer
    def serialize_for_browser(self) -> dict[str, str]:
        """Emit metadata only for outbound messages at the browser boundary."""
        payload = {
            "message_id": self.message_id,
            "direction": self.direction,
            "from_email": self.from_email,
            "subject": self.subject,
            "body": self.body,
            "sent_at": self.sent_at,
        }
        if self.direction == "outbound":
            for name, value in (
                ("category", self.category),
                ("issue_code", self.issue_code),
                ("outcome", self.outcome),
            ):
                if value is not None:
                    payload[name] = value
        return payload


class ThreadDetail(BaseModel):
    """Safe conversation detail without AgentOS execution data."""

    session_id: str
    status: ThreadStatus
    messages: list[InboxMessage]


class ThreadList(BaseModel):
    """Response envelope for inbox summaries."""

    threads: list[ThreadSummary]


class SupportEmailRequest(CustomerEmail):
    """Browser send contract with a required canonical support session ID."""

    thread_id: str = Field(min_length=1, max_length=128)


class PendingSend(BaseModel):
    """Non-sensitive state returned when a support run pauses."""

    session_id: str
    run_id: str | None = None
    status: Literal["approval_pending"]


def _frontend_asset(asset_path: str) -> Path:
    candidate = (frontend_directory / "assets" / asset_path).resolve()
    try:
        candidate.relative_to((frontend_directory / "assets").resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return candidate


def support_inbox_frontend() -> HTMLResponse:
    """Serve the built SPA through the existing FastAPI process."""
    return HTMLResponse((frontend_directory / "index.html").read_text())


def support_inbox_asset(asset_path: str) -> Response:
    """Serve Vite assets while rejecting traversal outside the build output."""
    asset = _frontend_asset(asset_path)
    return Response(asset.read_bytes(), media_type=guess_type(asset.name)[0] or "application/octet-stream")


def _timestamp(value: int | float | None) -> str:
    """Normalize persisted Unix timestamps to browser-safe UTC strings."""
    return datetime.fromtimestamp(value or 0, UTC).isoformat().replace("+00:00", "Z")


def _customer_email(run: TeamRunOutput) -> CustomerEmail | None:
    input_content = run.input.input_content if run.input else None
    try:
        return CustomerEmail.model_validate(input_content)
    except TypeError, ValueError:
        return None


def _customer_reply(run: TeamRunOutput) -> CustomerEmailReply | None:
    try:
        return CustomerEmailReply.model_validate(run.content)
    except TypeError, ValueError:
        return None


def _has_status(run: TeamRunOutput, expected: RunStatus) -> bool:
    """Compare in-memory and deserialized status representations safely."""
    status_value = getattr(run.status, "value", run.status)
    return str(status_value).lower() == expected.value.lower()


def _thread_status(runs: list[TeamRunOutput]) -> ThreadStatus:
    if any(_has_status(run, RunStatus.paused) for run in runs):
        return "approval_pending"
    if runs and all(_has_status(run, RunStatus.completed) and _customer_reply(run) is not None for run in runs):
        return "completed"
    return "incomplete"


def _support_runs(runs: Sequence[object]) -> list[TeamRunOutput]:
    """Keep only typed persisted runs that belong to Customer Support."""
    return [run for run in runs if isinstance(run, TeamRunOutput) and run.team_id == "customer-support"]


def map_thread(session_id: str, runs: Sequence[object]) -> ThreadDetail | None:
    """Map validated public support input/output only into inbox messages."""
    support_runs = _support_runs(runs)
    messages: list[InboxMessage] = []
    for run in sorted(support_runs, key=lambda item: item.created_at or 0):
        email = _customer_email(run)
        if email is None:
            continue
        sent_at = _timestamp(run.created_at)
        messages.append(
            InboxMessage(
                message_id=email.message_id,
                direction="inbound",
                from_email=email.from_email,
                subject=email.subject,
                body=email.body,
                sent_at=sent_at,
            )
        )
        reply = _customer_reply(run) if _has_status(run, RunStatus.completed) else None
        if reply is not None:
            messages.append(
                InboxMessage(
                    message_id=reply.message_id,
                    direction="outbound",
                    from_email="support@example.test",
                    subject=reply.subject,
                    body=reply.body,
                    sent_at=sent_at,
                    category=reply.category.value,
                    issue_code=reply.issue_code.value,
                    outcome=reply.outcome,
                )
            )
    if not messages:
        return None
    return ThreadDetail(session_id=session_id, status=_thread_status(support_runs), messages=messages)


def map_threads(sessions: Sequence[object]) -> list[ThreadDetail]:
    """Select only persisted Customer Support team sessions with safe messages."""
    details: list[ThreadDetail] = []
    for session in sessions:
        if getattr(session, "team_id", None) != "customer-support":
            continue
        session_id = getattr(session, "session_id", None)
        runs = getattr(session, "runs", None) or []
        if isinstance(session_id, str):
            detail = map_thread(session_id, runs)
            if detail is not None:
                details.append(detail)
    return details


def _read_threads() -> list[ThreadDetail]:
    sessions = get_postgres_db().get_sessions(
        session_type=SessionType.TEAM,
        component_id="customer-support",
        include_runs=True,
    )
    return map_threads(list(sessions))


def _summary(detail: ThreadDetail) -> ThreadSummary:
    latest = detail.messages[-1]
    inbound = next(message for message in detail.messages if message.direction == "inbound")
    return ThreadSummary(
        session_id=detail.session_id,
        subject=inbound.subject,
        customer_email=inbound.from_email,
        preview=latest.body[:240],
        last_message_at=latest.sent_at,
        status=detail.status,
    )


@router.get("/api/support/threads", response_model=ThreadList)
def list_threads() -> ThreadList:
    """Return safely mappable Customer Support threads, newest first."""
    return ThreadList(
        threads=sorted(
            (_summary(detail) for detail in _read_threads()), key=lambda item: item.last_message_at, reverse=True
        )
    )


@router.get("/api/support/threads/{session_id}", response_model=ThreadDetail)
def get_thread(session_id: str) -> ThreadDetail:
    """Return one safely mappable thread, never a raw session or run."""
    for detail in _read_threads():
        if detail.session_id == session_id:
            return detail
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support thread not found")


@router.post("/api/support/emails", response_model=ThreadDetail | PendingSend)
async def send_email(request: SupportEmailRequest):
    """Run one validated simulated email using its thread ID as the session ID."""
    try:
        result = await customer_support_team.arun(request, session_id=request.thread_id)
        if not isinstance(result, TeamRunOutput):
            raise TypeError("Customer Support did not return a team run")
        if result.status is RunStatus.paused:
            pending = PendingSend(session_id=request.thread_id, run_id=result.run_id, status="approval_pending")
            return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=pending.model_dump())
        for detail in _read_threads():
            if detail.session_id == request.thread_id:
                return detail
        fallback_detail = map_thread(request.thread_id, [result])
        if fallback_detail is None:
            raise ValueError("Customer Support result could not be mapped")
        return fallback_detail
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Support email could not be processed"
        ) from error
