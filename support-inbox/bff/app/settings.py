import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    database_url: str
    agentos_base_url: str
    agentos_pat: str
    allowed_origins: frozenset[str]
    cookie_name: str = "support_session"
    cookie_secure: bool = True
    runtime_env: str = "prd"

    @classmethod
    def from_env(cls) -> Settings:
        runtime_env = os.getenv("RUNTIME_ENV", "prd").lower()
        non_production = runtime_env in {"dev", "test"}
        origins = frozenset(x.strip() for x in os.getenv("SUPPORT_ALLOWED_ORIGINS", "").split(",") if x.strip())
        secure = os.getenv("SUPPORT_COOKIE_SECURE", "true").lower() == "true"
        database_url = os.getenv("DATABASE_URL", "sqlite:///support-inbox.db" if non_production else "")
        agentos_base_url = os.getenv("AGENTOS_BASE_URL", "http://agent-os:8000" if non_production else "").rstrip("/")
        agentos_pat = os.getenv("AGENTOS_PAT", "")
        if not non_production and (
            not database_url
            or not agentos_pat
            or not origins
            or not secure
            or not _valid_database_url(database_url)
            or not _valid_http_url(agentos_base_url, require_https=True)
            or any(not _valid_http_url(origin, require_https=True) for origin in origins)
        ):
            raise ValueError("production BFF security settings are incomplete")
        return cls(
            database_url=database_url,
            agentos_base_url=agentos_base_url,
            agentos_pat=agentos_pat,
            allowed_origins=origins,
            cookie_name=os.getenv("SUPPORT_COOKIE_NAME", "support_session"),
            cookie_secure=secure,
            runtime_env=runtime_env,
        )


def _valid_database_url(value: str) -> bool:
    return value.startswith(
        ("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://", "postgresql+asyncpg://")
    )


def _valid_http_url(value: str, *, require_https: bool = False) -> bool:
    parsed = urlparse(value)
    return (
        (parsed.scheme == "https" if require_https else parsed.scheme in {"http", "https"})
        and bool(parsed.netloc)
        and parsed.path in {"", "/"}
        and parsed.query == ""
        and parsed.fragment == ""
    )
