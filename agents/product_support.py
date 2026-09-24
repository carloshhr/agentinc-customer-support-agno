"""Private specialist for dedicated product and sizing retrieval."""

from agno.agent import Agent
from agno.tools import tool

from app.settings import default_model
from app.store_knowledge import store_knowledge
from db import get_postgres_db


@tool
def catalog_detail_unavailable(_: str) -> str:
    """Return the fixed customer-safe fallback for unsupported catalog details."""
    return "That product detail is unavailable in the store catalog."


product_support = Agent(
    id="product-support",
    name="Product Support",
    role="Answer product and sizing questions only from dedicated catalog knowledge.",
    model=default_model(),
    db=get_postgres_db(),
    knowledge=store_knowledge,
    search_knowledge=True,
    tools=[catalog_detail_unavailable],
    instructions="""\
You are Product Support, a private catalog and sizing specialist.

- Search the dedicated store-product-knowledge base before giving product, material, sizing, care, or policy facts.
    - Report only facts explicitly supported by the retrieved passage and needed for the question.
    - Do not infer availability, variants, or regional pricing unless the passage explicitly states them.
    - Do not volunteer promotions, discounts, or other details unless the passage explicitly states them.
    - If retrieval does not support a requested detail, call catalog_detail_unavailable instead of inventing it.
- Never answer order status, ownership, or tracking questions; those belong to Order Support.
- Return concise factual findings to the team, not a customer-facing email.\
""",
)
