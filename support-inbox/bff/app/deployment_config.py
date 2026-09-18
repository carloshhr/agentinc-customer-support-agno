from typing import Any


def validate_railway_config(config: dict[str, Any]) -> list[str]:
    """Return actionable errors for the checked-in BFF Railway shape."""
    build = config.get("build", {})
    deploy = config.get("deploy", {})
    variables = config.get("variables", {})
    errors: list[str] = []
    if build.get("builder") != "DOCKERFILE" or build.get("dockerfilePath") != "Dockerfile":
        errors.append("build must use the BFF Dockerfile")
    if not str(deploy.get("startCommand", "")).startswith("uvicorn app.main:app"):
        errors.append("startCommand must run app.main:app")
    if deploy.get("healthcheckPath") != "/health":
        errors.append("healthcheckPath must be /health")
    if "${{agent-os.RAILWAY_PRIVATE_DOMAIN}}" not in str(variables.get("AGENTOS_BASE_URL", "")):
        errors.append("AGENTOS_BASE_URL must use Railway private networking")
    if "${{support-inbox-db.DATABASE_URL}}" not in str(variables.get("DATABASE_URL", "")):
        errors.append("DATABASE_URL must reference dedicated PostgreSQL")
    if errors and not config:
        raise ValueError(f"BFF Railway config invalid: {'; '.join(errors)}")
    return errors
