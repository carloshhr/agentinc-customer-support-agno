"""Application-owned, deterministic mock store repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from typing import Any

from sqlalchemy import Engine, create_engine, text

from app.support_models import InsightItem, InsightsReport, IssueCode
from db.url import db_url

AUTO_REFUND_LIMIT = Decimal("50.00")
CATALOG_PRODUCT_IDS = {
    "PRD-EMBER-MUG",
    "PRD-CLOUD-TOTE",
    "PRD-MOSS-TEE",
    "PRD-SOLSTICE-JOURNAL",
}


def _order(
    order_id: str,
    customer_email: str,
    total: str,
    fulfillment_status: str,
    *,
    return_eligible: bool = True,
    return_deadline: str = "2027-12-31",
    refunded: bool = False,
) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "customer_email": customer_email,
        "total": total,
        "currency": "USD",
        "items": [{"product_id": "PRD-EMBER-MUG", "quantity": 1}],
        "fulfillment_status": fulfillment_status,
        "tracking_number": f"TRK-LUMEN-{order_id[-4:]}",
        "tracking_url": f"https://tracking.example.test/TRK-LUMEN-{order_id[-4:]}",
        "estimated_delivery": "2026-09-15",
        "return_eligible": return_eligible,
        "return_deadline": return_deadline,
        "refund": {
            "status": "refunded" if refunded else "unrefunded",
            "reason": "Seeded previous refund" if refunded else None,
            "approval_id": "APR-SEED-1007" if refunded else None,
            "refunded_at": "2026-01-01T00:00:00+00:00" if refunded else None,
        },
    }


ORDER_FIXTURES = (
    _order("ORD-LUMEN-1001", "alice@example.test", "39.99", "delivered"),
    _order("ORD-LUMEN-1002", "bob@example.test", "50.00", "shipped"),
    _order("ORD-LUMEN-1003", "carol@example.test", "50.01", "delivered"),
    _order("ORD-LUMEN-1004", "dana@example.test", "120.00", "delivered"),
    _order("ORD-LUMEN-1005", "erin@example.test", "18.00", "canceled", return_eligible=False),
    _order(
        "ORD-LUMEN-1006",
        "frank@example.test",
        "24.00",
        "delivered",
        return_eligible=False,
        return_deadline="2020-01-01",
    ),
    _order("ORD-LUMEN-1007", "grace@example.test", "49.00", "delivered", refunded=True),
)


class RefundRejected(ValueError):
    """Raised when persisted order state cannot safely be refunded."""


@dataclass(frozen=True)
class RefundResult:
    order_id: str
    amount: Decimal
    outcome: str
    approval_id: str | None = None


def ensure_store_schema(engine: Engine | None = None) -> None:
    """Create application-owned business storage without framework migrations."""
    target = engine or get_store_repository().engine
    with target.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS store_records (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    record_type TEXT NOT NULL CHECK (record_type IN ('order', 'support_interaction')),
                    record_key TEXT NOT NULL,
                    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (record_type, record_key)
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS store_records_interaction_completed_idx "
                "ON store_records ((payload->>'completed_at')) WHERE record_type = 'support_interaction'"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS store_records_interaction_issue_idx "
                "ON store_records ((payload->>'issue_code')) WHERE record_type = 'support_interaction'"
            )
        )


class StoreRepository:
    """Narrow repository boundary: callers never provide SQL or refund amounts."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or create_engine(db_url)

    def seed_orders(self) -> None:
        """Insert the fixed data set once without overwriting mutable business state."""
        ensure_store_schema(self.engine)
        with self.engine.begin() as connection:
            for order in ORDER_FIXTURES:
                connection.execute(
                    text(
                        """
                        INSERT INTO store_records (record_type, record_key, payload)
                        VALUES ('order', :record_key, CAST(:payload AS jsonb))
                        ON CONFLICT (record_type, record_key) DO NOTHING
                        """
                    ),
                    {"record_key": order["order_id"], "payload": json.dumps(order)},
                )

    def list_orders(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text("SELECT payload FROM store_records WHERE record_type = 'order' ORDER BY record_key")
            ).mappings()
            return [dict(row["payload"]) for row in rows]

    def get_order(self, order_id: str, customer_email: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            payload = self._load_order(connection, order_id, lock=False)
        if payload is None or payload.get("customer_email") != customer_email:
            return None
        return payload

    def refund_order_automatically(self, order_id: str, customer_email: str, reason: str) -> RefundResult:
        return self._refund(order_id, customer_email, reason, approval_id=None, route="automatic")

    def refund_order_after_approval(
        self, order_id: str, customer_email: str, reason: str, approval_id: str
    ) -> RefundResult:
        return self._refund(order_id, customer_email, reason, approval_id=approval_id, route="approval")

    def _refund(
        self, order_id: str, customer_email: str, reason: str, *, approval_id: str | None, route: str
    ) -> RefundResult:
        with self.engine.begin() as connection:
            payload = self._load_order(connection, order_id, lock=True)
            self._validate_refund(payload, customer_email, route)
            assert payload is not None  # narrowed by _validate_refund
            amount = Decimal(str(payload["total"]))
            payload["refund"] = {
                "status": "refunded",
                "reason": reason,
                "approval_id": approval_id,
                "refunded_at": datetime.now(UTC).isoformat(),
            }
            connection.execute(
                text(
                    """
                    UPDATE store_records
                    SET payload = CAST(:payload AS jsonb), updated_at = NOW()
                    WHERE record_type = 'order' AND record_key = :order_id
                    """
                ),
                {"order_id": order_id, "payload": json.dumps(payload)},
            )
        return RefundResult(order_id=order_id, amount=amount, outcome=route, approval_id=approval_id)

    @staticmethod
    def _load_order(connection: Any, order_id: str, *, lock: bool) -> dict[str, Any] | None:
        suffix = " FOR UPDATE" if lock else ""
        row = (
            connection.execute(
                text(
                    "SELECT payload FROM store_records WHERE record_type = 'order' AND record_key = :order_id" + suffix
                ),
                {"order_id": order_id},
            )
            .mappings()
            .first()
        )
        return dict(row["payload"]) if row else None

    @staticmethod
    def _validate_refund(payload: dict[str, Any] | None, customer_email: str, route: str) -> None:
        if payload is None:
            raise RefundRejected("Order was not found.")
        if payload.get("customer_email") != customer_email:
            raise RefundRejected("The order is not owned by this customer.")
        if payload.get("currency") != "USD":
            raise RefundRejected("Only persisted USD orders are supported.")
        if not payload.get("return_eligible"):
            raise RefundRejected("This order is not eligible for a refund.")
        deadline = date.fromisoformat(str(payload.get("return_deadline")))
        if deadline < date.today():
            raise RefundRejected("The refund deadline has expired.")
        if payload.get("refund", {}).get("status") != "unrefunded":
            raise RefundRejected("This order was already refunded.")
        total = Decimal(str(payload.get("total")))
        if route == "automatic" and total > AUTO_REFUND_LIMIT:
            raise RefundRejected("This order requires administrator approval.")
        if route == "approval" and total <= AUTO_REFUND_LIMIT:
            raise RefundRejected("This order must use automatic refund processing.")

    def upsert_interaction(self, payload: dict[str, Any]) -> bool:
        """Persist one completed interaction keyed by the source email message ID."""
        message_id = str(payload["message_id"])
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    """
                    INSERT INTO store_records (record_type, record_key, payload)
                    VALUES ('support_interaction', :record_key, CAST(:payload AS jsonb))
                    ON CONFLICT (record_type, record_key) DO NOTHING
                    """
                ),
                {"record_key": message_id, "payload": json.dumps(payload)},
            )
        return result.rowcount == 1

    def insights(self, period_start: date, period_end: date) -> InsightsReport:
        """Calculate administrator report facts with SQL over persisted interactions."""
        params = {"period_start": period_start, "period_end": period_end}
        where = """
            record_type = 'support_interaction'
            AND (payload->>'completed_at')::timestamptz >= :period_start
            AND (payload->>'completed_at')::timestamptz < (:period_end + INTERVAL '1 day')
        """
        with self.engine.connect() as connection:
            total = int(
                connection.execute(text(f"SELECT COUNT(*) FROM store_records WHERE {where}"), params).scalar_one()
            )
            issue_rows = connection.execute(
                text(
                    f"""
                    SELECT payload->>'issue_code' AS issue_code,
                           COUNT(*) AS count,
                           ARRAY_REMOVE(ARRAY_AGG(DISTINCT payload->>'product_id'), NULL) AS affected_products
                    FROM store_records
                    WHERE {where}
                    GROUP BY payload->>'issue_code'
                    ORDER BY count DESC, issue_code ASC
                    """
                ),
                params,
            ).mappings()
            refund_rows = connection.execute(
                text(
                    f"""
                    SELECT payload->>'refund_outcome' AS outcome, COUNT(*) AS count
                    FROM store_records
                    WHERE {where}
                    GROUP BY payload->>'refund_outcome'
                    ORDER BY outcome ASC
                    """
                ),
                params,
            ).mappings()
            issues = [
                InsightItem(
                    issue_code=IssueCode(str(row["issue_code"])),
                    count=int(row["count"]),
                    affected_products=list(row["affected_products"] or []),
                    recommendation=f"Review the {row['issue_code']} pattern with its observed count.",
                )
                for row in issue_rows
            ]
            outcomes = {str(row["outcome"]): int(row["count"]) for row in refund_rows if row["outcome"]}
        return InsightsReport(
            period_start=period_start,
            period_end=period_end,
            total_interactions=total,
            top_issues=issues,
            refund_outcomes=outcomes,
        )


@cache
def get_store_repository() -> StoreRepository:
    """Return the process-wide repository used by agent tools and hooks."""
    return StoreRepository()
