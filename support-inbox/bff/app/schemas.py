from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=12, max_length=256)


class OperatorResponse(BaseModel):
    id: str
    username: str
    display_name: str


class LoginResponse(BaseModel):
    operator: OperatorResponse
    csrf_token: str


class EmailSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    from_email: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=20_000)


class ThreadSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=128)
    subject: str = Field(max_length=500)
    customer_email: str = Field(min_length=3, max_length=320)
    preview: str = Field(max_length=240)
    last_message_at: str
    status: Literal["completed", "approval_pending", "incomplete"]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1, max_length=128)
    direction: Literal["inbound", "outbound"]
    from_email: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=10_000)
    sent_at: str
    category: Literal["order", "product", "sizing", "return", "refund", "other"] | None = None
    issue_code: (
        Literal[
            "tracking_request",
            "delivery_delay",
            "product_information",
            "size_recommendation",
            "return_policy",
            "refund_request",
            "product_defect",
            "other",
        ]
        | None
    ) = None
    outcome: Literal["answered", "needs_information", "refund_completed", "refund_rejected"] | None = None


class ThreadDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=128)
    status: Literal["completed", "approval_pending", "incomplete"]
    messages: list[Message] = Field(default_factory=list, max_length=200)


class ThreadList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threads: list[ThreadSummary] = Field(max_length=200)


class PendingSend(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=128)
    run_id: str | None = Field(default=None, max_length=128)
    status: Literal["approval_pending"]


SendResult = ThreadDetail | PendingSend


def safe_error(_detail: str, request_id: str) -> dict[str, str]:
    return {"code": "gateway_error", "message": "Support service unavailable", "request_id": request_id}


def validate_thread_summary(value: object) -> ThreadSummary:
    try:
        return ThreadSummary.model_validate(value)
    except Exception as exc:
        raise ValueError("invalid support response") from exc
