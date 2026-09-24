import configparser
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import create_engine

BFF_ROOT = Path(__file__).parents[1]
EXPECTED_TABLES = {
    "support_operators",
    "support_operator_sessions",
    "support_operator_audit_log",
}


def _postgres_url() -> str:
    url = os.getenv("BFF_POSTGRES_URL", "")
    if not url or url.startswith("sqlite"):
        pytest.skip("BFF_POSTGRES_URL must point to the repository PostgreSQL service")
    return url


def _run_alembic(*arguments: str, database_url: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BFF_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_alembic_default_is_postgresql() -> None:
    parser = configparser.ConfigParser()
    parser.read(BFF_ROOT / "alembic.ini")
    assert parser["alembic"]["sqlalchemy.url"].startswith("postgresql+psycopg://")


def test_postgresql_migration_upgrade_current_downgrade_inspects_live_database() -> None:
    database_url = _postgres_url()
    engine = create_engine(database_url, future=True)
    upgraded = False
    try:
        with engine.connect() as connection:
            assert not connection.dialect.has_schema(connection, "support_inbox")

        upgraded_result = _run_alembic("upgrade", "head", database_url=database_url)
        assert upgraded_result.returncode == 0, upgraded_result.stderr
        upgraded = True

        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names(schema="support_inbox"))
            assert tables == EXPECTED_TABLES | {"alembic_version"}
            assert (
                connection.execute(text("SELECT version_num FROM support_inbox.alembic_version")).scalar_one()
                == "0001_support_inbox"
            )

        current_result = _run_alembic("current", database_url=database_url)
        assert current_result.returncode == 0, current_result.stderr
        assert "0001_support_inbox" in current_result.stdout

        downgraded_result = _run_alembic("downgrade", "base", database_url=database_url)
        assert downgraded_result.returncode == 0, downgraded_result.stderr
        upgraded = False

        with engine.connect() as connection:
            assert not connection.dialect.has_schema(connection, "support_inbox")
    finally:
        if upgraded:
            _run_alembic("downgrade", "base", database_url=database_url)
        engine.dispose()
