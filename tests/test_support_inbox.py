"""Deterministic safe DTO and HTTP boundary coverage for Support Inbox."""

import os
from typing import Any, cast

os.environ.setdefault("RUNTIME_ENV", "dev")

from agno.models.response import ToolExecution
from agno.os.middleware.jwt import AuthMiddleware
from agno.os.service_accounts import ServiceAccount, ServiceAccountVerification, VerificationStatus
from agno.run.base import RunStatus
from agno.run.requirement import RunRequirement
from agno.run.team import TeamRunInput, TeamRunOutput
from agno.session.team import TeamSession
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from app.support_inbox import map_threads
from app.support_inbox import router as support_inbox_router
from app.support_models import CustomerEmail, CustomerEmailReply, IssueCode, SupportCategory


def _run(
    *,
    session_id: str = "THREAD-1001",
    team_id: str = "customer-support",
    status: RunStatus = RunStatus.completed,
    created_at: int = 1_700_000_000,
) -> TeamRunOutput:
    email = CustomerEmail(
        message_id="EMAIL-1001",
        from_email="alice@example.test",
        subject="Where is my order?",
        body="Please share the tracking status.",
    )
    return TeamRunOutput(
        run_id="RUN-1001",
        team_id=team_id,
        session_id=session_id,
        input=TeamRunInput(input_content=email),
        content=CustomerEmailReply(
            message_id="EMAIL-1001",
            subject="Tracking update",
            body="Your order is in transit.",
            category=SupportCategory.ORDER,
            issue_code=IssueCode.TRACKING_REQUEST,
            outcome="answered",
            order_id="ORDER-PRIVATE",
            product_id="PRODUCT-PRIVATE",
        )
        if status is RunStatus.completed
        else None,
        status=status,
        created_at=created_at,
        member_responses=[TeamRunOutput(content="private output")],
        tools=[ToolExecution(tool_name="private_tool", tool_args={"secret": "no"})],
        reasoning_content="private reasoning",
        requirements=[RunRequirement(tool_execution=ToolExecution(approval_id="APR-1001"))],
    )


def _sessions() -> list[TeamSession]:
    return [
        TeamSession(session_id="THREAD-1001", team_id="customer-support", runs=[_run()]),
        TeamSession(session_id="OTHER-1001", team_id="other-team", runs=[_run(session_id="OTHER-1001")]),
    ]


def test_mapper_allow_lists_only_customer_support_email_fields() -> None:
    detail = map_threads(_sessions())

    assert len(detail) == 1
    payload = detail[0].model_dump_json()
    assert detail[0].status == "completed"
    assert [message.direction for message in detail[0].messages] == ["inbound", "outbound"]
    for forbidden in (
        "private output",
        "private_tool",
        "private reasoning",
        "APR-1001",
        "secret",
        "requirements",
        "ORDER-PRIVATE",
        "PRODUCT-PRIVATE",
        "member_responses",
        "tool_args",
        "reasoning_content",
        "approval_id",
    ):
        assert forbidden not in payload


def test_mapper_marks_paused_thread_without_approval_data() -> None:
    detail = map_threads(
        [
            TeamSession(
                session_id="THREAD-PAUSED",
                team_id="customer-support",
                runs=[_run(session_id="THREAD-PAUSED", status=RunStatus.paused)],
            )
        ]
    )[0]

    assert detail.status == "approval_pending"
    assert len(detail.messages) == 1
    assert "APR-1001" not in detail.model_dump_json()


def test_mapper_orders_safe_messages_and_rejects_foreign_or_malformed_runs() -> None:
    earlier = _run(session_id="THREAD-SAFE", created_at=1_700_000_000)
    later = _run(session_id="THREAD-SAFE", created_at=1_700_000_100)
    malformed = _run(session_id="THREAD-SAFE")
    malformed.input = TeamRunInput(input_content={"message_id": "EMAIL-BROKEN"})
    foreign = _run(session_id="THREAD-SAFE", team_id="other-team")

    mapped = map_threads(
        [TeamSession(session_id="THREAD-SAFE", team_id="customer-support", runs=[later, malformed, foreign, earlier])]
    )

    assert len(mapped) == 1
    assert [message.sent_at for message in mapped[0].messages] == [
        "2023-11-14T22:13:20Z",
        "2023-11-14T22:13:20Z",
        "2023-11-14T22:15:00Z",
        "2023-11-14T22:15:00Z",
    ]
    assert all(
        message.subject != "Tracking update" or message.from_email == "support@example.test"
        for message in mapped[0].messages
    )


def test_mapper_supports_serialized_team_runs_without_accepting_raw_run_dicts() -> None:
    stored = TeamSession(
        session_id="THREAD-RELOADED", team_id="customer-support", runs=[_run(session_id="THREAD-RELOADED")]
    )
    reloaded = TeamSession.from_dict(stored.to_dict())
    raw = TeamSession(session_id="THREAD-RAW", team_id="customer-support", runs=cast(Any, [_run().to_dict()]))

    assert reloaded is not None
    assert map_threads([reloaded])[0].session_id == "THREAD-RELOADED"
    assert map_threads([raw]) == []


def test_mapper_hides_private_reply_identifiers_and_drops_entirely_unsafe_threads() -> None:
    malformed = _run(session_id="THREAD-UNSAFE")
    malformed.input = TeamRunInput(input_content={"message_id": "EMAIL-BROKEN"})
    payload = map_threads(
        [
            TeamSession(session_id="THREAD-PRIVATE", team_id="customer-support", runs=[_run()]),
            TeamSession(session_id="THREAD-UNSAFE", team_id="customer-support", runs=[malformed]),
        ]
    )

    assert len(payload) == 1
    assert "ORDER-PRIVATE" not in payload[0].model_dump_json()
    assert "PRODUCT-PRIVATE" not in payload[0].model_dump_json()
    assert payload[0].messages[1].category == "order"


def test_mapper_normalizes_serialized_run_status_values() -> None:
    restored = _run(session_id="THREAD-STATUS")
    restored.status = "COMPLETED"  # type: ignore[assignment]

    detail = map_threads([TeamSession(session_id="THREAD-STATUS", team_id="customer-support", runs=[restored])])[0]

    assert detail.status == "completed"
    assert [message.direction for message in detail.messages] == ["inbound", "outbound"]


def test_routes_return_safe_dtos_and_scope_unknown_threads(monkeypatch) -> None:
    monkeypatch.setattr("app.support_inbox._read_threads", lambda: map_threads(_sessions()))
    client = TestClient(app, base_url="http://127.0.0.1:8000")

    listed = client.get("/api/support/threads")
    detail = client.get("/api/support/threads/THREAD-1001")

    assert listed.status_code == 200
    assert listed.json()["threads"][0]["session_id"] == "THREAD-1001"
    assert "body" not in listed.json()["threads"][0]
    assert detail.status_code == 200
    inbound = detail.json()["messages"][0]
    assert "category" not in inbound
    assert "issue_code" not in inbound
    assert "outcome" not in inbound
    assert client.get("/api/support/threads/OTHER-1001").status_code == 404


async def _completed_run(_: Any, *, session_id: str, **__: Any) -> TeamRunOutput:
    assert session_id == "THREAD-1001"
    return _run(session_id=session_id)


def test_send_uses_thread_id_as_session_id(monkeypatch) -> None:
    monkeypatch.setattr("app.support_inbox.customer_support_team.arun", _completed_run)
    monkeypatch.setattr("app.support_inbox._read_threads", lambda: [])

    response = TestClient(app, base_url="http://127.0.0.1:8000").post(
        "/api/support/emails",
        json={
            "thread_id": "THREAD-1001",
            "message_id": "EMAIL-1001",
            "from_email": "alice@example.test",
            "subject": "Where is my order?",
            "body": "Please share the tracking status.",
        },
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "THREAD-1001"


async def _paused_run(_: Any, **__: Any) -> TeamRunOutput:
    return _run(status=RunStatus.paused)


def test_send_paused_response_exposes_only_safe_pending_state(monkeypatch) -> None:
    monkeypatch.setattr("app.support_inbox.customer_support_team.arun", _paused_run)

    response = TestClient(app, base_url="http://127.0.0.1:8000").post(
        "/api/support/emails",
        json={
            "thread_id": "THREAD-1001",
            "message_id": "EMAIL-1001",
            "from_email": "alice@example.test",
            "subject": "Refund",
            "body": "Please refund my order.",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"session_id": "THREAD-1001", "run_id": "RUN-1001", "status": "approval_pending"}


def test_send_rejects_invalid_input_without_dispatching(monkeypatch) -> None:
    called = False

    async def should_not_run(*_: Any, **__: Any) -> TeamRunOutput:
        nonlocal called
        called = True
        return _run()

    monkeypatch.setattr("app.support_inbox.customer_support_team.arun", should_not_run)

    response = TestClient(app, base_url="http://127.0.0.1:8000").post(
        "/api/support/emails",
        json={
            "thread_id": "",
            "message_id": "EMAIL-1001",
            "from_email": "not-an-email",
            "subject": "",
            "body": "",
        },
    )

    assert response.status_code == 422
    assert called is False


def test_send_hides_projection_failures_behind_the_generic_error(monkeypatch) -> None:
    monkeypatch.setattr("app.support_inbox.customer_support_team.arun", _completed_run)

    def unavailable_threads() -> list[Any]:
        raise RuntimeError("private persistence failure")

    monkeypatch.setattr("app.support_inbox._read_threads", unavailable_threads)

    response = TestClient(app, base_url="http://127.0.0.1:8000", raise_server_exceptions=False).post(
        "/api/support/emails",
        json={
            "thread_id": "THREAD-1001",
            "message_id": "EMAIL-1001",
            "from_email": "alice@example.test",
            "subject": "Where is my order?",
            "body": "Please share the tracking status.",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Support email could not be processed"}


def test_fastapi_serves_only_safe_inbox_paths_and_base_path_assets() -> None:
    client = TestClient(app, base_url="http://127.0.0.1:8000")

    inbox = client.get("/support-inbox/")
    redirect = client.get("/support-inbox", follow_redirects=False)
    asset_path = inbox.text.split("/support-inbox/assets/")[1].split('"')[0]
    asset = client.get(f"/support-inbox/assets/{asset_path}")
    traversal = client.get("/support-inbox/assets/%2E%2E/%2E%2E/app/main.py")
    inbox_paths = [route.path for route in support_inbox_router.routes if isinstance(route, APIRoute)]

    assert inbox.status_code == 200
    assert "/support-inbox/assets/" in inbox.text
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "/support-inbox/"
    assert asset.status_code == 200
    assert traversal.status_code == 404
    assert inbox_paths == ["/api/support/threads", "/api/support/threads/{session_id}", "/api/support/emails"]


class _SupportAccountVerifier:
    def __init__(self) -> None:
        self.accounts = {
            "agno_pat_unrelated": ServiceAccount(
                id="unrelated",
                name="other-service",
                token_hash="hash",
                token_prefix="agno_pat_",
                scopes=["support_inbox:read"],
            ),
            "agno_pat_read_only": ServiceAccount(
                id="read-only",
                name="support-inbox-bff",
                token_hash="hash",
                token_prefix="agno_pat_",
                scopes=["support_inbox:read"],
            ),
            "agno_pat_send_only": ServiceAccount(
                id="send-only",
                name="support-inbox-bff",
                token_hash="hash",
                token_prefix="agno_pat_",
                scopes=["support_inbox:send"],
            ),
            "agno_pat_scoped": ServiceAccount(
                id="scoped",
                name="support-inbox-bff",
                token_hash="hash",
                token_prefix="agno_pat_",
                scopes=["support_inbox:read", "support_inbox:send"],
            ),
        }

    async def verify(self, token: str, client_key: str | None = None) -> ServiceAccountVerification:
        account = self.accounts.get(token)
        if account is None:
            return ServiceAccountVerification(status=VerificationStatus.INVALID)
        return ServiceAccountVerification(status=VerificationStatus.OK, account=account)


def _production_support_app() -> FastAPI:
    production_app = FastAPI()
    production_app.state.support_inbox_authorization_enabled = True
    production_app.include_router(support_inbox_router)
    production_app.add_middleware(
        AuthMiddleware,
        authorization=False,
        security_key="not-a-support-pat",
        service_account_verifier=cast(Any, _SupportAccountVerifier()),
    )
    return production_app


def test_production_support_routes_enforce_bff_credential_matrix(monkeypatch) -> None:
    monkeypatch.setattr("app.support_inbox._read_threads", lambda: map_threads(_sessions()))
    client = TestClient(_production_support_app(), base_url="http://127.0.0.1:8000")
    cases = (
        (None, 401),
        ("Bearer invalid", 401),
        ("Bearer agno_pat_unrelated", 403),
        ("Bearer agno_pat_send_only", 403),
        ("Bearer agno_pat_scoped", 200),
    )

    for authorization, expected_status in cases:
        headers = {} if authorization is None else {"Authorization": authorization}
        response = client.get("/api/support/threads", headers=headers)
        assert response.status_code == expected_status


def test_production_support_send_requires_send_scope_and_returns_safe_pending_dto(monkeypatch) -> None:
    monkeypatch.setattr("app.support_inbox.customer_support_team.arun", _paused_run)
    client = TestClient(_production_support_app(), base_url="http://127.0.0.1:8000")
    payload = {
        "thread_id": "THREAD-1001",
        "message_id": "EMAIL-1001",
        "from_email": "alice@example.test",
        "subject": "Refund",
        "body": "Please refund my order.",
    }

    denied = client.post("/api/support/emails", headers={"Authorization": "Bearer agno_pat_read_only"}, json=payload)
    allowed = client.post("/api/support/emails", headers={"Authorization": "Bearer agno_pat_scoped"}, json=payload)

    assert denied.status_code == 403
    assert allowed.status_code == 202
    assert allowed.json() == {"session_id": "THREAD-1001", "run_id": "RUN-1001", "status": "approval_pending"}
