import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.security import (  # noqa: E402
    LOCKOUT_ATTEMPTS,
    SessionPolicy,
    check_origin,
    digest_token,
    hash_password,
    is_session_expired,
    record_failed_attempt,
    verify_password,
)

from app.settings import Settings  # noqa: E402


def test_argon2id_hash_verifies_without_pepper_and_never_contains_password() -> None:
    password = "correct horse battery staple"
    encoded = hash_password(password)

    assert encoded.startswith("$argon2id$")
    assert password not in encoded
    assert verify_password(encoded, password)
    assert not verify_password(encoded, "wrong password")


def test_login_policy_is_indistinguishable_and_lockout_starts_at_fifth_failure() -> None:
    assert LOCKOUT_ATTEMPTS == 5
    assert hash_password("same") != hash_password("same")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert record_failed_attempt(3, now) == (4, None)
    count, locked_until = record_failed_attempt(4, now)
    assert count == 5
    assert locked_until == now + timedelta(minutes=15)


def test_session_digest_and_expiry_enforce_idle_and_absolute_deadlines() -> None:
    policy = SessionPolicy()
    token = "opaque-session-token"
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert digest_token(token) != token
    assert len(digest_token(token)) == 32
    assert not is_session_expired(now, now + timedelta(minutes=29), now + timedelta(hours=7), policy, now)
    assert is_session_expired(now, now - timedelta(seconds=1), now + timedelta(hours=7), policy, now)
    assert is_session_expired(now, now, now - timedelta(seconds=1), policy, now)


def test_origin_check_requires_exact_allowlisted_origin() -> None:
    allowed = {"https://support.example.com"}
    assert check_origin("https://support.example.com", allowed)
    assert not check_origin("https://support.example.com.attacker.test", allowed)
    assert not check_origin(None, allowed)


def test_production_settings_fail_closed_and_dev_allows_explicit_sqlite_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_ENV", "prd")
    for name in ("DATABASE_URL", "AGENTOS_BASE_URL", "AGENTOS_PAT", "SUPPORT_ALLOWED_ORIGINS"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError):
        Settings.from_env()

    monkeypatch.setenv("RUNTIME_ENV", "dev")
    config = Settings.from_env()
    assert config.database_url.startswith("sqlite:")
    assert config.agentos_base_url.startswith("http://")


def test_production_settings_reject_invalid_urls_and_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNTIME_ENV", "prd")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///not-production.db")
    monkeypatch.setenv("AGENTOS_BASE_URL", "not-a-url")
    monkeypatch.setenv("AGENTOS_PAT", "pat")
    monkeypatch.setenv("SUPPORT_ALLOWED_ORIGINS", "*")
    with pytest.raises(ValueError):
        Settings.from_env()


@pytest.mark.parametrize(
    ("agentos_base_url", "origins"),
    [
        ("http://agent-os.example", "https://support.example.com"),
        ("https://agent-os.example", "http://support.example.com"),
    ],
)
def test_production_settings_require_https_for_upstream_and_browser_origins(
    monkeypatch: pytest.MonkeyPatch, agentos_base_url: str, origins: str
) -> None:
    monkeypatch.setenv("RUNTIME_ENV", "prd")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db/support")
    monkeypatch.setenv("AGENTOS_BASE_URL", agentos_base_url)
    monkeypatch.setenv("AGENTOS_PAT", "pat")
    monkeypatch.setenv("SUPPORT_ALLOWED_ORIGINS", origins)
    with pytest.raises(ValueError, match="production BFF security settings are incomplete"):
        Settings.from_env()


def test_production_settings_accept_https_upstream_and_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNTIME_ENV", "prd")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db/support")
    monkeypatch.setenv("AGENTOS_BASE_URL", "https://agent-os.example")
    monkeypatch.setenv("AGENTOS_PAT", "pat")
    monkeypatch.setenv("SUPPORT_ALLOWED_ORIGINS", "https://support.example.com")
    config = Settings.from_env()
    assert config.agentos_base_url == "https://agent-os.example"
    assert config.allowed_origins == frozenset({"https://support.example.com"})


@pytest.mark.parametrize("runtime_env", ["dev", "test"])
def test_nonproduction_defaults_keep_http_internal_upstream_explicit(
    monkeypatch: pytest.MonkeyPatch, runtime_env: str
) -> None:
    monkeypatch.setenv("RUNTIME_ENV", runtime_env)
    for name in ("DATABASE_URL", "AGENTOS_BASE_URL", "AGENTOS_PAT", "SUPPORT_ALLOWED_ORIGINS"):
        monkeypatch.delenv(name, raising=False)
    config = Settings.from_env()
    assert config.agentos_base_url == "http://agent-os:8000"
    assert config.allowed_origins == frozenset()


class _AuditDB:
    def __init__(self, stored_session=None) -> None:
        self.stored_session = stored_session
        self.records = []

    def scalar(self, _query):
        return self.stored_session

    def add(self, record) -> None:
        self.records.append(record)

    def commit(self) -> None:
        pass


@contextmanager
def _database(db: _AuditDB):
    yield db


@pytest.mark.parametrize("stored_session", [None, "expired"])
def test_invalid_or_expired_session_is_audited_with_request_id_and_redaction(
    monkeypatch: pytest.MonkeyPatch, stored_session
) -> None:
    monkeypatch.setenv("RUNTIME_ENV", "test")
    from app import auth
    from app.main import create_app

    session = None
    if stored_session == "expired":
        session = type(
            "ExpiredSession",
            (),
            {
                "revoked_at": None,
                "operator_id": "operator-1",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                "idle_expires_at": datetime(2026, 1, 1, tzinfo=UTC),
                "absolute_expires_at": datetime(2026, 1, 2, tzinfo=UTC),
            },
        )()
    db = _AuditDB(session)
    monkeypatch.setattr(auth, "_db", lambda _request: _database(db))
    client = TestClient(
        create_app(
            Settings(
                "sqlite:///unused.db",
                "http://agent-os:8000",
                "server-pat",
                frozenset({"https://support.example.com"}),
                False,
                False,
                "test",
            )
        )
    )

    request_id = "00000000-0000-0000-0000-000000000001"
    response = client.get(
        "/auth/session",
        cookies={"support_session": "invalid-session"},
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == request_id
    assert len(db.records) == 1
    record = db.records[0]
    assert record.event_type == "auth.session"
    assert record.outcome == "denied"
    assert record.operator_id is None
    assert record.request_id == request_id
    assert "invalid-session" not in str(record.metadata_json)
    assert "server-pat" not in str(record.metadata_json)


def test_rejected_logout_is_audited_with_nullable_actor_and_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_ENV", "test")
    from app import auth
    from app.main import create_app

    db = _AuditDB()
    monkeypatch.setattr(auth, "_db", lambda _request: _database(db))
    client = TestClient(
        create_app(
            Settings(
                "sqlite:///unused.db",
                "http://agent-os:8000",
                "server-pat",
                frozenset({"https://support.example.com"}),
                False,
                False,
                "test",
            )
        )
    )

    request_id = "00000000-0000-0000-0000-000000000002"
    response = client.post(
        "/auth/logout",
        cookies={"support_session": "logout-session"},
        headers={"Origin": "https://evil.example", "X-Request-ID": request_id},
    )

    assert response.status_code == 403
    assert response.headers["X-Request-ID"] == request_id
    assert len(db.records) == 1
    record = db.records[0]
    assert record.event_type == "auth.logout"
    assert record.outcome == "denied"
    assert record.operator_id is None
    assert record.request_id == request_id
    assert "logout-session" not in str(record.metadata_json)


def test_session_refresh_persists_csrf_digest_while_session_is_attached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNTIME_ENV", "test")
    from app import auth
    from app.main import create_app

    class AttachedSession:
        def __init__(self) -> None:
            object.__setattr__(self, "attached", False)
            self.token_digest = digest_token("session")
            object.__setattr__(self, "csrf_token_digest", digest_token("old-csrf"))
            self.revoked_at = None
            self.operator_id = "operator-1"
            self.created_at = datetime.now(UTC)
            self.idle_expires_at = datetime.now(UTC) + timedelta(minutes=30)
            self.absolute_expires_at = datetime.now(UTC) + timedelta(hours=8)
            self.last_seen_at = self.created_at

        def __setattr__(self, name, value) -> None:
            if name == "csrf_token_digest" and not self.attached:
                raise AssertionError("CSRF digest was changed on a detached session")
            object.__setattr__(self, name, value)

    stored = AttachedSession()

    @contextmanager
    def database():
        class DB:
            def scalar(self, _query):
                return stored

            def get(self, _model, _identifier):
                return type("Operator", (), {"id": "operator-1", "username": "agent", "display_name": "Agent"})()

            def commit(self) -> None:
                pass

        stored.attached = True
        try:
            yield DB()
        finally:
            stored.attached = False

    monkeypatch.setattr(auth, "_db", lambda _request: database())
    client = TestClient(
        create_app(
            Settings(
                "sqlite:///unused.db",
                "http://agent-os:8000",
                "server-pat",
                frozenset(),
                False,
                False,
                "test",
            )
        )
    )

    response = client.get("/auth/session", cookies={"support_session": "session"})

    assert response.status_code == 200
    assert response.json()["csrf_token"]
    assert stored.csrf_token_digest != digest_token("old-csrf")
