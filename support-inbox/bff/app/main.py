from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agentos_client import AgentOSClient
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.agentos_client.close()

    app = FastAPI(title="Support Inbox BFF", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.state.settings = config
    app.state.session_factory = None
    app.state.agentos_client = AgentOSClient(config.agentos_base_url, config.agentos_pat)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    def request_id_value(request: Request) -> str:
        supplied = request.headers.get("X-Request-ID", "")
        try:
            UUID(supplied)
        except ValueError:
            return str(uuid4())
        return supplied

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request_id_value(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError):
        return JSONResponse(
            {"code": "invalid_request", "message": "Invalid request", "request_id": request.state.request_id},
            status_code=400,
            headers={"X-Request-ID": request.state.request_id},
        )

    @app.exception_handler(HTTPException)
    async def safe_http_error(request: Request, exc: HTTPException):
        code = {
            401: "unauthorized",
            403: "forbidden",
            429: "rate_limited",
            502: "gateway_error",
            504: "gateway_timeout",
        }.get(exc.status_code, "request_error")
        message = (
            "Support service unavailable"
            if exc.status_code >= 500
            else (
                "Authentication required"
                if exc.status_code == 401
                else "Forbidden"
                if exc.status_code == 403
                else "Invalid request"
            )
        )
        return JSONResponse(
            {"code": code, "message": message, "request_id": request.state.request_id},
            status_code=exc.status_code,
            headers={"X-Request-ID": request.state.request_id},
        )

    @app.exception_handler(Exception)
    async def safe_internal_error(request: Request, _: Exception):
        return JSONResponse(
            {
                "code": "internal_error",
                "message": "Support service unavailable",
                "request_id": request.state.request_id,
            },
            status_code=500,
            headers={"X-Request-ID": request.state.request_id},
        )

    from .auth import router as auth_router
    from .support import router as support_router

    app.include_router(auth_router)
    app.include_router(support_router)
    return app


app = create_app()
