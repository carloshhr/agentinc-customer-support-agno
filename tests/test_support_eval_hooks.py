"""Safe teardown contract for model-backed customer-support eval cases."""

from datetime import UTC, datetime

from app.support_models import IssueCode, SupportCategory
from evals.hooks import delete_new_support_interactions, snapshot_support_interactions


def test_support_eval_teardown_removes_only_new_interactions(store) -> None:
    store.upsert_interaction(
        {
            "message_id": "EMAIL-PRE-EXISTING",
            "team_run_id": "RUN-OLD",
            "category": SupportCategory.ORDER.value,
            "issue_code": IssueCode.TRACKING_REQUEST.value,
            "outcome": "answered",
            "refund_outcome": "not_applicable",
            "completed_at": datetime.now(UTC).isoformat(),
        }
    )
    snapshot = snapshot_support_interactions()
    store.upsert_interaction(
        {
            "message_id": "EMAIL-EVAL-NEW",
            "team_run_id": "RUN-NEW",
            "category": SupportCategory.ORDER.value,
            "issue_code": IssueCode.TRACKING_REQUEST.value,
            "outcome": "answered",
            "refund_outcome": "not_applicable",
            "completed_at": datetime.now(UTC).isoformat(),
        }
    )

    delete_new_support_interactions(snapshot)

    assert store.get_order("ORD-LUMEN-1001", "alice@example.test") is not None
    assert store.insights(datetime.now(UTC).date(), datetime.now(UTC).date()).total_interactions == 1
