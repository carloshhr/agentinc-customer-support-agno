"""
AgentOS Entrypoint
==================
"""

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from agno.os import AgentOS
from agno.utils.log import log_info
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from agents.builder import platform_builder
from agents.engineer import platform_engineer
from agents.manager import platform_manager
from agents.support_insights import support_insights
from app.knowledge import shared_knowledge
from app.registry import registry
from app.schedules import register_schedules
from app.store import ensure_store_schema
from app.store_knowledge import store_knowledge
from app.support_inbox import router as support_inbox_router
from app.support_inbox import support_inbox_asset, support_inbox_frontend
from db import get_postgres_db
from teams.customer_support import customer_support_team
from teams.lead import agno_team
from workflows.deployment_check import deployment_check
from workflows.run_evals import run_evals

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "prd")
# Used by the scheduler and the OAuth server when MCP OAuth is enabled.
agentos_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Interfaces
# - Agno becomes available on Slack when both env vars are set
# ---------------------------------------------------------------------------
SLACK_BOT_TOKEN = getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = getenv("SLACK_SIGNING_SECRET", "")

interfaces: list = []
if SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET:
    from agno.os.interfaces.slack import Slack

    interfaces.append(
        Slack(
            team=agno_team,
            streaming=True,
            token=SLACK_BOT_TOKEN,
            signing_secret=SLACK_SIGNING_SECRET,
            resolve_user_identity=True,
            loading_text="Pulling the thread...",
        )
    )


# ---------------------------------------------------------------------------
# MCP OAuth — enabled by setting the MCP_CONNECT_SECRET environment variable.
# Connect your favorite AI apps and coding agents to a secure /mcp using OAuth.
# ---------------------------------------------------------------------------
MCP_CONNECT_SECRET = getenv("MCP_CONNECT_SECRET", "")

mcp_auth = None
if MCP_CONNECT_SECRET:
    from agno.os import AgentOSBuiltinAuth

    mcp_auth = AgentOSBuiltinAuth(
        url=agentos_url,
        secret=MCP_CONNECT_SECRET,
        signing_key_material=getenv("AGENTOS_MCP_SIGNING_KEY"),
    )


# ---------------------------------------------------------------------------
# Lifespan — app-level startup / teardown.
#
# AgentOS handles the MCP lifecycle (connect on startup, close on shutdown)
# for agent-attached and registry tools. Keep this hook to plug in your own setup.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    log_info("AgentOS lifespan: startup")
    # Application-owned mock-store tables must exist before any schedule or run can use them.
    ensure_store_schema()
    # Register schedules on startup. Idempotent and fail-soft.
    register_schedules()
    try:
        yield
    finally:
        log_info("AgentOS lifespan: shutdown")


# ---------------------------------------------------------------------------
# Create AgentOS
# ---------------------------------------------------------------------------
agent_os = AgentOS(
    name="AgentOS",
    tracing=True,
    scheduler=True,
    scheduler_base_url=agentos_url,
    authorization=runtime_env != "dev",
    mcp_server=True,
    mcp_auth=mcp_auth,
    lifespan=lifespan,
    db=get_postgres_db(),
    knowledge=[shared_knowledge, store_knowledge],
    agents=[support_insights, platform_builder, platform_manager, platform_engineer],
    teams=[customer_support_team, agno_team],
    workflows=[deployment_check, run_evals],
    interfaces=interfaces,
    registry=registry,
    config=str(Path(__file__).parent / "config.yaml"),
)
app = agent_os.get_app()
app.state.support_inbox_authorization_enabled = runtime_env != "dev"
app.include_router(support_inbox_router)
# AgentOS installs its catch-all UI mount before application extensions. Keep the
# narrowly scoped API router ahead of it so `/api/support/*` remains reachable.
app.routes.insert(0, app.routes.pop())


@app.middleware("http")
async def serve_support_inbox(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Serve built inbox files before AgentOS's root UI mount handles the request."""
    path = request.url.path
    if path == "/support-inbox":
        return RedirectResponse("/support-inbox/")
    if path == "/support-inbox/":
        return support_inbox_frontend()
    if path.startswith("/support-inbox/assets/"):
        try:
            return support_inbox_asset(path.removeprefix("/support-inbox/assets/"))
        except HTTPException as error:
            return JSONResponse(status_code=error.status_code, content={"detail": error.detail})
    return await call_next(request)


if __name__ == "__main__":
    agent_os.serve(app="app.main:app", reload=False)
