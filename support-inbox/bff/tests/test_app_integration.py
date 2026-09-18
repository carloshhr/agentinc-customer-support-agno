import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

os.environ.setdefault("RUNTIME_ENV", "test")

from app.agentos_client import AgentOSClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.settings import Settings  # noqa: E402


def _settings() -> Settings:
    return Settings(
        "sqlite:///unused.db",
        "http://agent-os:8000",
        "server-pat",
        frozenset({"https://support.example.com"}),
        False,
        False,
        "test",
    )


def test_actual_app_mounts_auth_and_support_routes() -> None:
    app = create_app(_settings())

    def routes(router):
        for route in router.routes:
            if hasattr(route, "original_router"):
                yield from routes(route.original_router)
                continue
            if hasattr(route, "routes"):
                yield from routes(route)
            elif hasattr(route, "path"):
                yield route

    paths = {(route.path, tuple(sorted(route.methods or ()))) for route in routes(app)}
    assert ("/auth/login", ("POST",)) in paths
    assert ("/auth/session", ("GET",)) in paths
    assert ("/auth/logout", ("POST",)) in paths
    assert ("/api/support/threads", ("GET",)) in paths
    assert ("/api/support/threads/{session_id}", ("GET",)) in paths
    assert ("/api/support/emails", ("POST",)) in paths


def test_actual_app_proves_auth_csrf_cors_error_mapping_and_202(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import support

    def fake_upstream(_: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"session_id": "thread-1", "run_id": "run-1", "status": "approval_pending"})

    app = create_app(_settings())
    app.state.agentos_client.close()
    app.state.agentos_client = AgentOSClient("http://agent-os:8000", "server-pat", httpx.MockTransport(fake_upstream))
    monkeypatch.setattr(support, "_audit", lambda *args: None)
    from app import auth

    monkeypatch.setattr(auth, "_audit_rejection", lambda *args: None)
    monkeypatch.setattr(
        support,
        "current_session",
        lambda _request, _session, csrf=None: (
            (None, None) if csrf == "csrf-ok" else (_ for _ in ()).throw(HTTPException(403, "Forbidden"))
        ),
    )
    client = TestClient(app)

    unauthorized = client.get("/auth/session", headers={"Origin": "https://support.example.com"})
    assert unauthorized.status_code == 401
    assert unauthorized.json()["code"] == "unauthorized"

    preflight = client.options(
        "/api/support/emails",
        headers={
            "Origin": "https://support.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://support.example.com"
    assert preflight.headers["access-control-allow-credentials"] == "true"

    rejected = client.post(
        "/api/support/emails",
        cookies={"support_session": "session"},
        headers={"Origin": "https://support.example.com", "X-CSRF-Token": "wrong"},
        json={
            "thread_id": "thread-1",
            "message_id": "message-1",
            "from_email": "operator@example.test",
            "subject": "Reply",
            "body": "Hello",
        },
    )
    assert rejected.status_code == 403
    assert rejected.json() == {
        "code": "forbidden",
        "message": "Forbidden",
        "request_id": rejected.json()["request_id"],
    }

    accepted = client.post(
        "/api/support/emails",
        cookies={"support_session": "session"},
        headers={"Origin": "https://support.example.com", "X-CSRF-Token": "csrf-ok"},
        json={
            "thread_id": "thread-1",
            "message_id": "message-1",
            "from_email": "operator@example.test",
            "subject": "Reply",
            "body": "Hello",
        },
    )
    assert accepted.status_code == 202
    assert accepted.json() == {"session_id": "thread-1", "run_id": "run-1", "status": "approval_pending"}
