"""Typed contracts and bounded taxonomy for customer support."""

from datetime import date
from enum import StrEnum
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_validator


class SupportCategory(StrEnum):
    """Stable reporting categories shared by replies and interactions."""

    ORDER = "order"
    PRODUCT = "product"
    SIZING = "sizing"
    RETURN = "return"
    REFUND = "refund"
    OTHER = "other"


class IssueCode(StrEnum):
    """Stable issue codes that prevent fragmented analytics."""

    TRACKING_REQUEST = "tracking_request"
    DELIVERY_DELAY = "delivery_delay"
    PRODUCT_INFORMATION = "product_information"
    SIZE_RECOMMENDATION = "size_recommendation"
    RETURN_POLICY = "return_policy"
    REFUND_REQUEST = "refund_request"
    PRODUCT_DEFECT = "product_defect"
    OTHER = "other"


class CustomerEmail(BaseModel):
    """Validated simulated customer email accepted by the support team."""

    message_id: str = Field(min_length=1, max_length=128)
    thread_id: str | None = Field(default=None, max_length=128)
    from_email: str
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=10_000)

    @field_validator("from_email")
    @classmethod
    def validate_simulated_email(cls, value: str) -> str:
        """Accept syntactically valid fictional ``@example.test`` senders too."""
        try:
            return validate_email(value, check_deliverability=False, test_environment=True).normalized
        except EmailNotValidError as error:
            raise ValueError("from_email must be a valid email address") from error


class CustomerEmailReply(BaseModel):
    """Structured final output from the customer-facing support team."""

    message_id: str = Field(min_length=1, max_length=128)
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=10_000)
    category: SupportCategory
    issue_code: IssueCode
    outcome: Literal["answered", "needs_information", "refund_completed", "refund_rejected"]
    order_id: str | None = Field(default=None, max_length=128)
    product_id: str | None = Field(default=None, max_length=128)


class InsightItem(BaseModel):
    """One ranked, SQL-derived support issue."""

    issue_code: IssueCode
    count: int = Field(ge=0)
    affected_products: list[str]
    recommendation: str = Field(default="Review the observed issue pattern.")


class InsightsReport(BaseModel):
    """Operator-facing aggregate of completed support interactions."""

    period_start: date
    period_end: date
    total_interactions: int = Field(ge=0)
    top_issues: list[InsightItem]
    refund_outcomes: dict[str, int]
