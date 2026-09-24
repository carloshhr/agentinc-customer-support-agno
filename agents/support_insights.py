"""Trusted operator-facing support-insights agent."""

from datetime import date, timedelta

from agno.agent import Agent

from app.settings import default_model
from app.store import get_store_repository
from app.support_models import InsightsReport
from db import get_postgres_db


def get_support_insights(period_start: str | None = None, period_end: str | None = None) -> dict[str, object]:
    """Return SQL-derived aggregate facts for an inclusive ISO-date period."""
    end = date.fromisoformat(period_end) if period_end else date.today()
    start = date.fromisoformat(period_start) if period_start else end - timedelta(days=30)
    return get_store_repository().insights(start, end).model_dump(mode="json")


support_insights = Agent(
    id="support-insights",
    name="Support Insights",
    model=default_model(),
    db=get_postgres_db(),
    tools=[get_support_insights],
    output_schema=InsightsReport,
    instructions="""\
You are Support Insights, a trusted operator-facing on-demand reporting agent.

- Call get_support_insights before describing counts, rankings, products, or refund outcomes.
- Explain only patterns visible in the returned aggregate; do not invent counts or customer details.
- Keep recommendations tied to the observed issue counts.
- Never create scheduled reports and never draft customer email replies.\
""",
)
