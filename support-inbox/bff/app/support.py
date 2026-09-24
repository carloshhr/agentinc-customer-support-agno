from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response

from .agentos_client import AgentOSClient
from .audit import persist_audit
from .auth import current_session
from .database import make_session_factory
from .schemas import EmailSendRequest, SendResult, ThreadDetail, ThreadList

router = APIRouter(prefix="/api/support")


def _client(request: Request) -> AgentOSClient:
    return request.app.state.agentos_client


def _audit(request: Request, operator, event_type: str, outcome: str, metadata: dict[str, str]) -> None:
    if request.app.state.session_factory is None:
        _, request.app.state.session_factory = make_session_factory(request.app.state.settings.database_url)
    with request.app.state.session_factory() as db:
        persist_audit(db, operator.id if operator else None, event_type, outcome, request.state.request_id, metadata)
        db.commit()


def _guard(request: Request, session: str | None, origin: str | None, csrf: str | None, mutation: bool):
    if not origin_allowed(origin, request.app.state.settings.allowed_origins):
        _audit(request, None, "auth.request", "origin_denied", {})
        raise HTTPException(403, "Forbidden")
    try:
        operator, _ = current_session(request, session, csrf if mutation else None)
    except HTTPException:
        _audit(request, None, "auth.request", "denied", {})
        raise
    return operator


def origin_allowed(origin: str | None, allowed: frozenset[str] | set[str]) -> bool:
    return origin is not None and origin in allowed


@router.get("/threads", response_model=ThreadList)
def threads(
    request: Request, support_session: str | None = Cookie(default=None), origin: str | None = Header(default=None)
):
    operator = _guard(request, support_session, origin, None, False)
    try:
        result = _client(request).threads()
    except Exception:
        _audit(request, operator, "proxy.threads", "failure", {})
        raise
    _audit(request, operator, "proxy.threads", "success", {})
    return ThreadList(threads=result)


@router.get("/threads/{session_id}", response_model=ThreadDetail)
def thread(
    session_id: str,
    request: Request,
    support_session: str | None = Cookie(default=None),
    origin: str | None = Header(default=None),
):
    operator = _guard(request, support_session, origin, None, False)
    if len(session_id) > 128:
        raise HTTPException(400, "Invalid request")
    try:
        result = _client(request).thread(session_id)
    except Exception:
        _audit(request, operator, "proxy.thread", "failure", {"session_id": session_id})
        raise
    _audit(request, operator, "proxy.thread", "success", {"session_id": session_id})
    return result


@router.post("/emails", response_model=SendResult)
def send(
    payload: EmailSendRequest,
    request: Request,
    response: Response,
    support_session: str | None = Cookie(default=None),
    origin: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None),
):
    operator = _guard(request, support_session, origin, x_csrf_token, True)
    try:
        status, result = _client(request).send(payload.model_dump())
    except Exception:
        _audit(request, operator, "proxy.send", "failure", {"session_id": payload.thread_id})
        raise
    _audit(request, operator, "proxy.send", "success", {"session_id": payload.thread_id, "status": result.status})
    response.status_code = status
    return result
