import unicodedata
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from sqlalchemy import select

from .audit import persist_audit
from .database import make_session_factory
from .models import Operator, OperatorSession
from .schemas import LoginRequest, LoginResponse, OperatorResponse
from .security import (
    SessionPolicy,
    csrf_matches,
    digest_token,
    is_session_expired,
    new_token,
    verify_password,
)

router = APIRouter(prefix="/auth")


def normalize_username(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().lower()


def _db(request: Request):
    if request.app.state.session_factory is None:
        _, request.app.state.session_factory = make_session_factory(request.app.state.settings.database_url)
    return request.app.state.session_factory()


def _safe_auth_error() -> HTTPException:
    return HTTPException(401, "Invalid username or password", headers={"Cache-Control": "no-store"})


def _audit_rejection(request: Request, event_type: str, outcome: str = "denied") -> None:
    with _db(request) as db:
        persist_audit(db, None, event_type, outcome, request.state.request_id, {})
        db.commit()


def _operator_response(operator: Operator) -> OperatorResponse:
    return OperatorResponse(id=str(operator.id), username=operator.username, display_name=operator.display_name)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    now = datetime.now(UTC)
    username = normalize_username(payload.username)
    with _db(request) as db:
        operator = db.scalar(select(Operator).where(Operator.username == username))
        locked = operator and operator.locked_until and operator.locked_until > now
        if (
            not operator
            or not operator.is_active
            or locked
            or not verify_password(operator.password_hash, payload.password)
        ):
            if operator and not locked:
                from .security import record_failed_attempt

                operator.failed_login_count, operator.locked_until = record_failed_attempt(
                    operator.failed_login_count, now
                )
            persist_audit(
                db,
                operator.id if operator else None,
                "auth.login",
                "failure",
                request.state.request_id,
                {"username": username},
            )
            db.commit()
            raise _safe_auth_error()
        token, csrf = new_token(), new_token()
        session = OperatorSession(
            operator_id=operator.id,
            token_digest=digest_token(token),
            csrf_token_digest=digest_token(csrf),
            created_at=now,
            last_seen_at=now,
            idle_expires_at=now + timedelta(seconds=SessionPolicy().idle_seconds),
            absolute_expires_at=now + timedelta(seconds=SessionPolicy().absolute_seconds),
        )
        operator.failed_login_count, operator.locked_until, operator.last_login_at = 0, None, now
        db.add(session)
        persist_audit(db, operator.id, "auth.login", "success", request.state.request_id, {})
        db.commit()
    response.set_cookie(
        request.app.state.settings.cookie_name,
        token,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="none" if request.app.state.settings.cookie_secure else "lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(operator=_operator_response(operator), csrf_token=csrf)


def _current_session(db, request: Request, session_cookie: str | None, csrf: str | None, audit_event: str):
    if not session_cookie:
        _audit_rejection(request, audit_event)
        raise HTTPException(401, "Authentication required")
    now = datetime.now(UTC)
    session = db.scalar(select(OperatorSession).where(OperatorSession.token_digest == digest_token(session_cookie)))
    if (
        not session
        or session.revoked_at
        or is_session_expired(
            session.created_at, session.idle_expires_at, session.absolute_expires_at, SessionPolicy(), now
        )
    ):
        _audit_rejection(request, audit_event)
        raise HTTPException(401, "Authentication required")
    if csrf is not None and not csrf_matches(session.csrf_token_digest, csrf):
        _audit_rejection(request, audit_event)
        raise HTTPException(403, "Forbidden")
    session.last_seen_at = now
    session.idle_expires_at = min(now + timedelta(seconds=SessionPolicy().idle_seconds), session.absolute_expires_at)
    operator = db.get(Operator, session.operator_id)
    return operator, session


def current_session(
    request: Request, session_cookie: str | None, csrf: str | None = None, audit_event: str = "auth.session"
):
    with _db(request) as db:
        result = _current_session(db, request, session_cookie, csrf, audit_event)
        db.commit()
        return result


@router.get("/session", response_model=LoginResponse)
def session(request: Request, response: Response, support_session: str | None = Cookie(default=None)) -> LoginResponse:
    with _db(request) as db:
        operator, stored = _current_session(db, request, support_session, None, "auth.session")
        csrf = new_token()
        stored.csrf_token_digest = digest_token(csrf)
        db.commit()
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(operator=_operator_response(operator), csrf_token=csrf)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    support_session: str | None = Cookie(default=None),
    origin: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    if not origin or origin not in request.app.state.settings.allowed_origins:
        _audit_rejection(request, "auth.logout")
        raise HTTPException(403, "Forbidden")
    current_session(request, support_session, x_csrf_token, "auth.logout")
    assert support_session is not None
    with _db(request) as db:
        stored = db.scalar(select(OperatorSession).where(OperatorSession.token_digest == digest_token(support_session)))
        if stored:
            stored.revoked_at = datetime.now(UTC)
            persist_audit(db, stored.operator_id, "auth.logout", "success", request.state.request_id, {})
            db.commit()
    response.delete_cookie(request.app.state.settings.cookie_name, path="/")
