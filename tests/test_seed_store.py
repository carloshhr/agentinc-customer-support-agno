"""Deterministic coverage for the catalog seed refresh policy."""

import importlib.util
from pathlib import Path

_SEED_MODULE_SPEC = importlib.util.spec_from_file_location(
    "seed_store", Path(__file__).parents[1] / "scripts" / "seed_store.py"
)
assert _SEED_MODULE_SPEC is not None
assert _SEED_MODULE_SPEC.loader is not None
seed_module = importlib.util.module_from_spec(_SEED_MODULE_SPEC)
_SEED_MODULE_SPEC.loader.exec_module(seed_module)


def test_seed_store_upserts_catalog_without_skipping_existing_content(monkeypatch) -> None:
    insert_calls = []

    class FakeKnowledge:
        def insert(self, **kwargs) -> None:
            insert_calls.append(kwargs)

    monkeypatch.setattr(seed_module, "ensure_store_schema", lambda _: None)
    monkeypatch.setattr(seed_module.store_knowledge, "insert", FakeKnowledge().insert)

    class FakeRepository:
        engine = object()

        def seed_orders(self) -> None:
            pass

    monkeypatch.setattr(seed_module, "get_store_repository", lambda: FakeRepository())

    seed_module.seed_store()

    assert len(insert_calls) == 1
    assert insert_calls[0]["skip_if_exists"] is False
