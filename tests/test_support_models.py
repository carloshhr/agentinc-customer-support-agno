"""Behavioral contracts for typed customer-support requests and reports."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.support_models import (
    CustomerEmail,
    CustomerEmailReply,
    InsightItem,
    InsightsReport,
    IssueCode,
    SupportCategory,
)


def test_customer_email_accepts_valid_simulated_customer_json() -> None:
    email = CustomerEmail.model_validate(
        {
            "message_id": "EMAIL-1001",
            "thread_id": "THREAD-1001",
            "from_email": "alice@example.test",
            "subject": "Where is my order?",
            "body": "Please share the tracking status for ORD-LUMEN-1001.",
        }
    )

    assert email.message_id == "EMAIL-1001"
    assert email.from_email == "alice@example.test"


@pytest.mark.parametrize(
    "payload",
    [
        {"message_id": "EMAIL-1002", "from_email": "not-an-email", "subject": "Hi", "body": "Help"},
        {"message_id": "", "from_email": "alice@example.test", "subject": "Hi", "body": "Help"},
    ],
)
def test_customer_email_rejects_invalid_identity_or_email(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        CustomerEmail.model_validate(payload)


def test_reply_and_insights_keep_taxonomy_bounded() -> None:
    reply = CustomerEmailReply(
        message_id="EMAIL-1003",
        subject="Your order update",
        body="I can confirm that your order is on its way.",
        category=SupportCategory.ORDER,
        issue_code=IssueCode.TRACKING_REQUEST,
        outcome="answered",
        order_id="ORD-LUMEN-1001",
    )
    report = InsightsReport(
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        total_interactions=1,
        top_issues=[InsightItem(issue_code=IssueCode.TRACKING_REQUEST, count=1, affected_products=[])],
        refund_outcomes={"not_applicable": 1},
    )

    assert reply.issue_code is IssueCode.TRACKING_REQUEST
    assert report.top_issues[0].count == 1


def test_reply_rejects_model_invented_taxonomy() -> None:
    with pytest.raises(ValidationError):
        CustomerEmailReply.model_validate(
            {
                "message_id": "EMAIL-1004",
                "subject": "Update",
                "body": "I can help.",
                "category": "shipping_magic",
                "issue_code": "unbounded_code",
                "outcome": "answered",
            }
        )
