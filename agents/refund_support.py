"""Private specialist for deterministic automatic and approval-gated refunds."""

import json

from agno.agent import Agent
from agno.approval import approval
from agno.run import RunContext
from agno.tools import tool

from app.settings import default_model
from app.store import RefundRejected, get_store_repository
from db import get_postgres_db


@tool
def refund_order_automatically(order_id: str, customer_email: str, reason: str) -> str:
    """Refund an eligible persisted USD order at or below USD 50.00; no amount is accepted."""
    try:
        result = get_store_repository().refund_order_automatically(order_id, customer_email, reason)
    except RefundRejected as error:
        return json.dumps({"refunded": False, "reason": str(error)})
    return json.dumps({"refunded": True, "order_id": result.order_id, "outcome": result.outcome})


@approval(type="required")
@tool(requires_confirmation=True)
def refund_order_with_admin_approval(run_context: RunContext, order_id: str, customer_email: str, reason: str) -> str:
    """Refund an eligible persisted USD order above USD 50.00 after administrator approval."""
    approval = (run_context.metadata or {}).get("approval")
    approval_id = approval.get("id") if isinstance(approval, dict) else None
    if not approval_id:
        return json.dumps({"refunded": False, "reason": "The resolved approval record is unavailable."})
    try:
        result = get_store_repository().refund_order_after_approval(
            order_id, customer_email, reason, approval_id=str(approval_id)
        )
    except RefundRejected as error:
        return json.dumps({"refunded": False, "reason": str(error)})
    return json.dumps({"refunded": True, "order_id": result.order_id, "outcome": result.outcome})


refund_support = Agent(
    id="refund-support",
    name="Returns & Refunds Support",
    role="Validate refunds and execute the deterministic refund routes.",
    model=default_model(),
    db=get_postgres_db(),
    tools=[refund_order_automatically, refund_order_with_admin_approval],
    instructions="""\
You are Returns & Refunds Support, a private specialist.

- Never calculate, accept, or request a refund amount; the tools reload the persisted total.
- For a complete request with order_id, customer_email, and reason, call refund_order_automatically first.
- If refund_order_automatically says administrator approval is required, call refund_order_with_admin_approval.
  That tool pauses before mutation and revalidates the persisted total after continuation.
- If the administrator rejects that confirmation, report the refund as rejected.
  Do not call either refund tool again.
- Report a tool refusal plainly and never claim that a paused approval has refunded an order.
- Return concise findings to the team, not a customer-facing email.\
""",
)
