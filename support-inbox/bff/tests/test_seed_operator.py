import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.security import verify_password  # noqa: E402
from app.seed_operator import seed_operator  # noqa: E402  # pyright: ignore[reportMissingImports]


@dataclass
class FakeSession:
    operator: object | None = None
    added: object | None = None
    commits: int = 0

    def scalar(self, _query):
        return self.operator

    def add(self, operator):
        self.added = operator
        self.operator = operator

    def commit(self):
        self.commits += 1


def test_seed_normalizes_username_and_hashes_password():
    session = FakeSession()

    operator = seed_operator(
        cast(Session, session),
        username="  Local.Operator ",
        password="correct horse battery staple",
        display_name=" Local Operator ",
    )

    assert operator.username == "local.operator"
    assert operator.display_name == "Local Operator"
    assert verify_password(operator.password_hash, "correct horse battery staple")
    assert operator.password_hash != "correct horse battery staple"


def test_seed_is_idempotent_and_does_not_overwrite_password():
    session = FakeSession()
    first = seed_operator(
        cast(Session, session),
        username="LOCAL",
        password="first-password",
        display_name="Local",
    )
    original_hash = first.password_hash

    second = seed_operator(
        cast(Session, session),
        username=" local ",
        password="replacement-password",
        display_name="Changed",
    )

    assert second is first
    assert second.password_hash == original_hash
    assert second.display_name == "Local"
    assert session.commits == 1


def test_seed_rejects_blank_password():
    with pytest.raises(ValueError, match="PASSWORD"):
        seed_operator(cast(Session, FakeSession()), username="local", password="  ", display_name="Local")
