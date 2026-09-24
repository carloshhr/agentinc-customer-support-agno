import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("RUNTIME_ENV", "test")

from app.deployment_config import validate_railway_config

from app.main import create_app
from app.settings import Settings

CONFIG_PATH = Path(__file__).parents[1] / "railway.json"


def test_railway_service_config_is_a_bff_only_deployment() -> None:
    config = json.loads(CONFIG_PATH.read_text())

    assert validate_railway_config(config) == []
    assert config["deploy"]["startCommand"].startswith("uvicorn app.main:app")
    assert config["deploy"]["healthcheckPath"] == "/health"


def test_railway_service_config_rejects_public_agentos_or_missing_healthcheck() -> None:
    config = json.loads(CONFIG_PATH.read_text())
    config["deploy"]["healthcheckPath"] = "/api/support/threads"
    config["variables"]["AGENTOS_BASE_URL"] = "https://agentos.example.com"

    errors = validate_railway_config(config)

    assert "healthcheckPath must be /health" in errors
    assert "AGENTOS_BASE_URL must use Railway private networking" in errors


def test_invalid_deployment_config_is_rejected() -> None:
    with pytest.raises(ValueError, match="BFF Railway config invalid"):
        validate_railway_config({})


def test_healthcheck_is_local_and_does_not_require_upstream_access() -> None:
    settings = Settings("sqlite:///test.db", "http://agent-os:8000", "test-pat", frozenset())

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
