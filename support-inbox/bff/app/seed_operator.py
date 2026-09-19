"""Seed the local Support Inbox operator without changing existing credentials."""

import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import normalize_username
from .database import make_session_factory
from .models import Operator
from .security import hash_password


def seed_operator(session: Session, *, username: str, password: str, display_name: str) -> Operator:
    """Create one operator, preserving an existing operator and its password."""
    normalized_username = normalize_username(username)
    if not normalized_username:
        raise ValueError("SUPPORT_OPERATOR_USERNAME must not be blank")
    if not password or not password.strip():
        raise ValueError("SUPPORT_OPERATOR_PASSWORD must not be blank")
    normalized_display_name = display_name.strip()
    if not normalized_display_name:
        raise ValueError("SUPPORT_OPERATOR_DISPLAY_NAME must not be blank")

    existing = session.scalar(select(Operator).where(Operator.username == normalized_username))
    if existing is not None:
        return existing

    now = datetime.now(UTC)
    operator = Operator(
        username=normalized_username,
        password_hash=hash_password(password),
        display_name=normalized_display_name,
        password_changed_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(operator)
    session.commit()
    return operator


def seed_from_environment() -> Operator:
    """Seed the operator configured by environment variables."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise ValueError("DATABASE_URL must be set")

    username = os.getenv("SUPPORT_OPERATOR_USERNAME", "")
    password = os.getenv("SUPPORT_OPERATOR_PASSWORD", "")
    display_name = os.getenv("SUPPORT_OPERATOR_DISPLAY_NAME", "")
    _, session_factory = make_session_factory(database_url)
    with session_factory() as session:
        return seed_operator(session, username=username, password=password, display_name=display_name)


if __name__ == "__main__":
    operator = seed_from_environment()
    print(f"Seeded local Support Inbox operator: {operator.username}")
