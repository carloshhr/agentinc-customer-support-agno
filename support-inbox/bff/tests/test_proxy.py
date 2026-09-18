import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import Response

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.agentos_client import AgentOSClient  # noqa: E402
from app.schemas import (  # noqa: E402
    EmailSendRequest,
    ThreadDetail,
    ThreadList,
    ThreadSummary,
    safe_error,
    validate_thread_summary,
)


def test_message_accepts_exact_agentos_outbound_metadata_and_rejects_unknown_values() -> None:
    from app.schemas import Message

    message = Message.model_validate(
        {
            "message_id": "m-1",
            "direction": "outbound",
            "from_email": "support@example.test",
            "subject": "Reply",
            "body": "Done",
            "sent_at": "2026-01-01T00:00:00Z",
            "category": "order",
            "issue_code": "tracking_request",
            "outcome": "answered",
        }
    )
    assert message.category == "order"
    assert message.issue_code == "tracking_request"
    assert message.outcome == "answered"
    with pytest.raises(ValueError):
        Message.model_validate({**message.model_dump(), "outcome": "secret"})
    with pytest.raises(ValueError):
        Message.model_validate({**message.model_dump(), "raw_run": "secret"})


def test_browser_and_upstream_schemas_are_bounded_and_typed() -> None:
    request = EmailSendRequest.model_validate(
        {
            "thread_id": "abc",
            "message_id": "message-1",
            "from_email": "customer@example.test",
            "subject": "Help",
            "body": "hello",
        }
    )
    assert request.thread_id == "abc"
    assert request.body == "hello"
    summary = ThreadSummary.model_validate(
        {
            "session_id": "abc",
            "subject": "Help",
            "customer_email": "customer@example.test",
            "preview": "hello",
            "last_message_at": "2026-01-01T00:00:00Z",
            "status": "completed",
        }
    )
    envelope = ThreadList.model_validate({"threads": [summary.model_dump()]})
    detail = ThreadDetail.model_validate(
        {
            "session_id": "abc",
            "status": "completed",
            "messages": [
                {
                    "message_id": "message-1",
                    "direction": "inbound",
                    "from_email": "customer@example.test",
                    "subject": "Help",
                    "body": "hello",
                    "sent_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
    )
    assert summary.session_id == detail.session_id
    assert envelope.threads[0].preview == "hello"


def test_invalid_upstream_payload_fails_closed_and_errors_are_safe() -> None:
    try:
        validate_thread_summary({"session_id": "abc", "subject": "Help", "status": "open", "raw_run": "secret"})
    except Exception as exc:
        assert "secret" not in str(exc)
    else:
        raise AssertionError("unexpected upstream field was accepted")
    error = safe_error("upstream timeout", "req-123")
    assert error == {"code": "gateway_error", "message": "Support service unavailable", "request_id": "req-123"}
    assert "upstream timeout" not in str(error)


def test_audit_metadata_redacts_secret_names_and_content() -> None:
    from app.audit import redact_metadata

    result = redact_metadata(
        {"password": "secret", "AGENTOS_PAT": "agno_pat_secret", "body": "customer body", "id": "x"}
    )
    assert result == {"id": "x"}


def test_fake_agentos_server_preserves_pending_and_never_returns_pat() -> None:
    seen: list[dict[str, str]] = []
    payloads: list[dict[str, str]] = []

    def fake_agentos(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.headers))
        payloads.append(request.read() and __import__("json").loads(request.content))
        return httpx.Response(202, json={"session_id": "s-1", "run_id": "r-1", "status": "approval_pending"})

    client = AgentOSClient("https://agent-os.test", "agno_pat_server_only", httpx.MockTransport(fake_agentos))
    status, result = client.send(
        {
            "thread_id": "s-1",
            "message_id": "m-1",
            "from_email": "customer@example.test",
            "subject": "Help",
            "body": "hello",
        }
    )
    assert status == 202
    assert result.status == "approval_pending"
    assert "agno_pat_server_only" not in result.model_dump_json()
    assert seen[0]["authorization"] == "Bearer agno_pat_server_only"
    assert payloads == [
        {
            "thread_id": "s-1",
            "message_id": "m-1",
            "from_email": "customer@example.test",
            "subject": "Help",
            "body": "hello",
        }
    ]


def test_threads_consumes_agentos_envelope_and_detail_dto() -> None:
    def fake_agentos(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/threads"):
            return httpx.Response(
                200,
                json={
                    "threads": [
                        {
                            "session_id": "s-1",
                            "subject": "Help",
                            "customer_email": "customer@example.test",
                            "preview": "hello",
                            "last_message_at": "2026-01-01T00:00:00Z",
                            "status": "completed",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "session_id": "s-1",
                "status": "completed",
                "messages": [
                    {
                        "message_id": "m-1",
                        "direction": "inbound",
                        "from_email": "customer@example.test",
                        "subject": "Help",
                        "body": "hello",
                        "sent_at": "2026-01-01T00:00:00Z",
                    }
                ],
            },
        )

    client = AgentOSClient("https://agent-os.test", "pat", httpx.MockTransport(fake_agentos))
    assert client.threads()[0].customer_email == "customer@example.test"
    assert client.thread("s-1").messages[0].message_id == "m-1"


def test_send_validates_agentos_pending_dto() -> None:
    client = AgentOSClient(
        "https://agent-os.test",
        "pat",
        httpx.MockTransport(
            lambda _: httpx.Response(  # fmt: skip
                202, json={"session_id": "s-1", "run_id": "r-1", "status": "approval_pending"}
            )
        ),
    )
    status, result = client.send({"thread_id": "s-1"})
    assert status == 202
    assert result.session_id == "s-1"


def test_send_audits_the_browser_thread_id() -> None:
    from app import support

    audits: list[dict[str, str]] = []

    class FakeClient:
        def send(self, payload: dict[str, str]):
            return 200, ThreadDetail(session_id=payload["thread_id"], status="completed")

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace()),
        state=SimpleNamespace(request_id="request-1"),
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(support, "_guard", lambda *args: SimpleNamespace(id="operator-1"))
    monkeypatch.setattr(support, "_client", lambda _request: FakeClient())
    monkeypatch.setattr(
        support,
        "_audit",
        lambda _request, _operator, _event, _outcome, metadata: audits.append(metadata),
    )
    try:
        result = support.send(
            EmailSendRequest(
                thread_id="thread-1",
                message_id="message-1",
                from_email="operator@example.test",
                subject="Reply",
                body="Hello",
            ),
            request,
            Response(),
        )
    finally:
        monkeypatch.undo()

    assert result.session_id == "thread-1"
    assert audits[-1]["session_id"] == "thread-1"


def test_send_attempts_upstream_once_on_failure() -> None:
    attempts = 0

    def failing_agentos(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"detail": "private failure"})

    client = AgentOSClient("https://agent-os.test", "pat", httpx.MockTransport(failing_agentos))
    try:
        client.send(
            {
                "thread_id": "s-1",
                "message_id": "m-1",
                "from_email": "customer@example.test",
                "subject": "Help",
                "body": "hello",
            }
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502
    else:
        raise AssertionError("upstream failure was accepted")
    assert attempts == 1


def test_agentos_client_has_explicit_limits_and_rejects_oversized_payloads() -> None:
    client = AgentOSClient(
        "https://agent-os.test", "pat", httpx.MockTransport(lambda _: httpx.Response(200, text="x" * 2_000_000))
    )
    assert client.timeout.connect == 2
    assert client.timeout.read == 5
    assert client.timeout.write == 5
    assert client.timeout.pool == 2
    try:
        client.threads()
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 502
    else:
        raise AssertionError("oversized upstream response was accepted")


def test_audit_record_contains_attribution_outcome_request_id_and_redacted_metadata() -> None:
    from app.audit import build_audit_record

    record = build_audit_record("operator-1", "proxy.read", "success", "req-1", {"session_id": "s-1", "body": "secret"})
    assert record == {
        "operator_id": "operator-1",
        "event_type": "proxy.read",
        "outcome": "success",
        "request_id": "req-1",
        "metadata": {"session_id": "s-1"},
    }


def test_get_proxy_requires_an_allowlisted_origin() -> None:
    from app.support import origin_allowed

    assert origin_allowed("https://support.example.com", {"https://support.example.com"})
    assert not origin_allowed("https://evil.example", {"https://support.example.com"})
    assert not origin_allowed(None, {"https://support.example.com"})
