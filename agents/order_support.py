"""Private specialist for deterministic order, fulfillment, and tracking facts."""

import json

from agno.agent import Agent

from app.settings import default_model
from app.store import get_store_repository
from db import get_postgres_db


def lookup_order(order_id: str, customer_email: str) -> str:
    """Return only an order owned by the supplied simulated customer email."""
    order = get_store_repository().get_order(order_id, customer_email)
    if order is None:
        return json.dumps({"found": False, "message": "No matching order was found for this customer."})
    return json.dumps({"found": True, "order": order})


order_support = Agent(
    id="order-support",
    name="Order Support",
    role="Resolve order, fulfillment, and tracking questions from store records.",
    model=default_model(),
    db=get_postgres_db(),
    tools=[lookup_order],
    instructions="""\
You are Order Support, a private customer-support specialist.

- Use lookup_order for every order, delivery, and tracking fact.
- Never reveal an order that lookup_order did not return for the supplied customer email.
- Never use catalog knowledge for order state or tracking facts.
- For a tracking request, return only fulfillment, tracking, and delivery facts.
  Omit refund history and return eligibility.
- Return concise factual findings to the team, not a customer-facing email.\
""",
)
