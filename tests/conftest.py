"""PostgreSQL fixtures for deterministic customer-support tests."""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from db.url import db_url


@pytest.fixture()
def store_engine() -> Iterator[Engine]:
    """Provide an isolated empty store table on the configured PostgreSQL service."""
    from app.store import ensure_store_schema

    engine = create_engine(db_url)
    ensure_store_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("TRUNCATE TABLE store_records")
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql("TRUNCATE TABLE store_records")
        engine.dispose()


@pytest.fixture()
def store(store_engine: Engine):
    """Seed the deterministic support dataset without replacing mutated records."""
    from app.store import StoreRepository

    repository = StoreRepository(store_engine)
    repository.seed_orders()
    return repository
