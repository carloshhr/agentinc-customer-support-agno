"""Deterministic PostgreSQL coverage for the support-store boundary."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from inspect import signature

import pytest
from sqlalchemy import text

from app.store import (
    AUTO_REFUND_LIMIT,
    CATALOG_PRODUCT_IDS,
    ORDER_FIXTURES,
    RefundRejected,
    StoreRepository,
    ensure_store_schema,
)
from app.support_models import IssueCode, SupportCategory


def test_schema_and_seed_create_one_record_for_each_fixed_order(store: StoreRepository) -> None:
    rows = store.list_orders()

    assert tuple(order["order_id"] for order in rows) == tuple(item["order_id"] for item in ORDER_FIXTURES)
    assert CATALOG_PRODUCT_IDS == {
        "PRD-EMBER-MUG",
        "PRD-CLOUD-TOTE",
        "PRD-MOSS-TEE",
        "PRD-SOLSTICE-JOURNAL",
    }


def test_schema_enforces_unique_record_type_and_key(store_engine) -> None:
    ensure_store_schema(store_engine)
    with store_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO store_records (record_type, record_key, payload) "
                "VALUES ('order', 'unique-key', '{}'::jsonb)"
            )
        )
        with pytest.raises(Exception):
            connection.execute(
                text(
                    "INSERT INTO store_records (record_type, record_key, payload) "
                    "VALUES ('order', 'unique-key', '{}'::jsonb)"
                )
            )


def test_seed_rerun_does_not_replace_mutated_business_state(store: StoreRepository) -> None:
    result = store.refund_order_automatically("ORD-LUMEN-1001", "alice@example.test", "Changed my mind")
    store.seed_orders()

    order = store.get_order("ORD-LUMEN-1001", "alice@example.test")
    assert result.amount == Decimal("39.99")
    assert order is not None
    assert order["refund"]["status"] == "refunded"


def test_customer_cannot_read_foreign_order(store: StoreRepository) -> None:
    order = store.get_order("ORD-LUMEN-1001", "mallory@example.test")

    assert order is None


@pytest.mark.parametrize(
    ("order_id", "email", "expected"),
    [
        ("ORD-LUMEN-1001", "alice@example.test", Decimal("39.99")),
        ("ORD-LUMEN-1002", "bob@example.test", Decimal("50.00")),
    ],
)
def test_automatic_refund_uses_persisted_decimal_at_and_below_limit(
    store: StoreRepository, order_id: str, email: str, expected: Decimal
) -> None:
    result = store.refund_order_automatically(order_id, email, "Eligible return")

    assert AUTO_REFUND_LIMIT == Decimal("50.00")
    assert result.amount == expected
    assert result.outcome == "automatic"


@pytest.mark.parametrize(
    ("order_id", "email", "method"),
    [
        ("ORD-LUMEN-1003", "carol@example.test", "automatic"),
        ("ORD-LUMEN-1002", "bob@example.test", "approval"),
        ("ORD-LUMEN-1005", "erin@example.test", "automatic"),
        ("ORD-LUMEN-1006", "frank@example.test", "automatic"),
        ("ORD-LUMEN-1007", "grace@example.test", "automatic"),
    ],
)
def test_refund_route_rejects_wrong_threshold_or_ineligible_order(
    store: StoreRepository, order_id: str, email: str, method: str
) -> None:
    with pytest.raises(RefundRejected):
        if method == "approval":
            store.refund_order_after_approval(order_id, email, "Test refusal", approval_id="APR-1")
        else:
            store.refund_order_automatically(order_id, email, "Test refusal")

    order = store.get_order(order_id, email)
    assert order is not None
    assert order["refund"]["status"] != "refunded" or order_id == "ORD-LUMEN-1007"


def test_repeated_refund_cannot_create_a_second_mutation(store: StoreRepository) -> None:
    first = store.refund_order_automatically("ORD-LUMEN-1001", "alice@example.test", "First request")

    with pytest.raises(RefundRejected):
        store.refund_order_automatically("ORD-LUMEN-1001", "alice@example.test", "Second request")

    order = store.get_order("ORD-LUMEN-1001", "alice@example.test")
    assert first.amount == Decimal("39.99")
    assert order is not None
    assert order["refund"]["reason"] == "First request"


def test_refund_entrypoints_never_accept_a_model_supplied_amount() -> None:
    automatic = signature(StoreRepository.refund_order_automatically).parameters
    approval = signature(StoreRepository.refund_order_after_approval).parameters

    assert "amount" not in automatic
    assert "amount" not in approval


def test_interaction_upsert_and_sql_insights_count_a_retried_message_once(store: StoreRepository) -> None:
    created_at = datetime.now(UTC)
    payload = {
        "message_id": "EMAIL-INSIGHT-1",
        "team_run_id": "RUN-1",
        "category": SupportCategory.ORDER.value,
        "issue_code": IssueCode.TRACKING_REQUEST.value,
        "order_id": "ORD-LUMEN-1001",
        "product_id": "PRD-EMBER-MUG",
        "outcome": "answered",
        "refund_outcome": "not_applicable",
        "completed_at": created_at.isoformat(),
    }

    assert store.upsert_interaction(payload) is True
    assert store.upsert_interaction({**payload, "team_run_id": "RUN-RESUMED"}) is False
    report = store.insights(created_at.date() - timedelta(days=1), created_at.date() + timedelta(days=1))

    assert report.total_interactions == 1
    assert report.top_issues[0].issue_code is IssueCode.TRACKING_REQUEST
    assert report.refund_outcomes == {"not_applicable": 1}
