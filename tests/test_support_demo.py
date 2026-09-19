from __future__ import annotations

from typing import Any

from agno.session.team import TeamSession

from app.support_demo import demo_support_runs, seed_support_demo_threads
from app.support_inbox import map_threads


class FakeRepository:
    def __init__(self) -> None:
        self.seed_calls = 0

    def seed_orders(self) -> None:
        self.seed_calls += 1


class FakeDatabase:
    def __init__(self) -> None:
        self.runs: list[tuple[Any, str | None, str | None]] = []

    def upsert_run(self, run: Any, *, session_id: str | None, user_id: str | None) -> None:
        self.runs.append((run, session_id, user_id))


class FakeTeam:
    id = "customer-support"

    def __init__(self) -> None:
        self.db = FakeDatabase()
        self.sessions: dict[str, Any] = {}
        self.saved_sessions: list[Any] = []

    def get_session(self, *, session_id: str, user_id: str | None = None) -> Any | None:
        return self.sessions.get(session_id)

    def save_session(self, session: Any) -> None:
        self.sessions[session.session_id] = session
        self.saved_sessions.append(session)


def test_demo_runs_are_safe_and_mappable() -> None:
    runs = demo_support_runs()

    assert [run.session_id for run in runs] == [
        "DEMO-SUPPORT-TRACKING-001",
        "DEMO-SUPPORT-SIZING-001",
        "DEMO-SUPPORT-REFUND-001",
    ]
    assert all(run.team_id == "customer-support" for run in runs)
    assert runs[-1].content is None
    assert runs[-1].requirements in (None, [])
    assert runs[-1].tools in (None, [])
    assert runs[-1].member_responses in (None, [])
    assert runs[-1].reasoning_content is None

    sessions = []
    for run in runs:
        assert run.session_id is not None
        sessions.append(
            TeamSession(
                session_id=run.session_id,
                team_id="customer-support",
                runs=[run],
            )
        )

    details = map_threads(sessions)

    assert [detail.session_id for detail in details] == [
        "DEMO-SUPPORT-TRACKING-001",
        "DEMO-SUPPORT-SIZING-001",
        "DEMO-SUPPORT-REFUND-001",
    ]
    assert [detail.status for detail in details] == ["completed", "completed", "approval_pending"]
    assert [len(detail.messages) for detail in details] == [2, 2, 1]


def test_demo_seed_is_idempotent_without_models_or_knowledge() -> None:
    team = FakeTeam()
    repository = FakeRepository()

    seed_support_demo_threads(team=team, repository=repository)
    seed_support_demo_threads(team=team, repository=repository)

    assert repository.seed_calls == 2
    assert len(team.saved_sessions) == 3
    assert len(team.db.runs) == 3
    assert set(team.sessions) == {
        "DEMO-SUPPORT-TRACKING-001",
        "DEMO-SUPPORT-SIZING-001",
        "DEMO-SUPPORT-REFUND-001",
    }
