"""Deterministic completion helpers for resolved customer-support approvals."""

from __future__ import annotations

from typing import Any

from agno.run.base import RunStatus
from agno.run.team import TeamRunOutput

from app.store import RefundRejected, get_store_repository
from app.support_models import CustomerEmail, CustomerEmailReply, IssueCode, SupportCategory


def complete_rejected_refund_continuation(run_output: TeamRunOutput, approval: dict[str, Any]) -> TeamRunOutput:
    """Finish a rejected required refund approval without returning to the model loop."""
    email = _customer_email(run_output)
    order_id = _rejected_order_id(run_output)
    metadata = dict(run_output.metadata or {})
    metadata["approval"] = approval

    run_output.content = CustomerEmailReply(
        message_id=email.message_id,
        subject="Refund request update",
        body="We could not process your refund request. Your order remains unchanged.",
        category=SupportCategory.REFUND,
        issue_code=IssueCode.REFUND_REQUEST,
        outcome="refund_rejected",
        order_id=order_id,
    )
    run_output.metadata = metadata
    run_output.requirements = []
    run_output.status = RunStatus.completed
    return run_output


def complete_approved_refund_continuation(run_output: TeamRunOutput, approval: dict[str, Any]) -> TeamRunOutput:
    """Finish an approved refund with its persisted approval audit identifier."""
    email = _customer_email(run_output)
    tool_args = _approval_tool_args(run_output)
    try:
        result = get_store_repository().refund_order_after_approval(
            str(tool_args["order_id"]),
            str(tool_args["customer_email"]),
            str(tool_args["reason"]),
            approval_id=str(approval["id"]),
        )
    except KeyError, RefundRejected:
        return complete_rejected_refund_continuation(run_output, approval)

    metadata = dict(run_output.metadata or {})
    metadata["approval"] = approval
    run_output.content = CustomerEmailReply(
        message_id=email.message_id,
        subject="Refund request update",
        body="We have processed your refund request.",
        category=SupportCategory.REFUND,
        issue_code=IssueCode.REFUND_REQUEST,
        outcome="refund_completed",
        order_id=result.order_id,
    )
    run_output.metadata = metadata
    run_output.requirements = []
    run_output.status = RunStatus.completed
    return run_output


def _customer_email(run_output: TeamRunOutput) -> CustomerEmail:
    """Recover the typed original input preserved by the paused team run."""
    input_data = run_output.input.input_content if run_output.input else None
    if isinstance(input_data, CustomerEmail):
        return input_data
    if isinstance(input_data, str):
        return CustomerEmail.model_validate_json(input_data)
    return CustomerEmail.model_validate(input_data)


def _rejected_order_id(run_output: TeamRunOutput) -> str | None:
    """Read the exact order ID from the approval-gated tool invocation."""
    order_id = _approval_tool_args(run_output).get("order_id")
    return str(order_id) if order_id is not None else None


def _approval_tool_args(run_output: TeamRunOutput) -> dict[str, Any]:
    """Read the exact arguments from the approval-gated tool invocation."""
    for requirement in run_output.requirements or []:
        tool = requirement.tool_execution
        if tool and tool.tool_name == "refund_order_with_admin_approval":
            return dict(tool.tool_args or {})
    return {}
