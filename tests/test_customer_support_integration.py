"""Deterministic component, approval boundary, and public-registration coverage."""

import os
from typing import Any, cast

import pytest

# Registration construction must not require production JWT material in local tests.
os.environ.setdefault("RUNTIME_ENV", "dev")

from agno.agent import Agent
from agno.models.response import ToolExecution
from agno.run.base import RunStatus
from agno.run.requirement import RunRequirement
from agno.run.team import TeamRunInput, TeamRunOutput
from agno.team import Team, TeamMode
from fastapi.testclient import TestClient
from sqlalchemy import text

from agents.order_support import order_support
from agents.product_support import catalog_detail_unavailable, product_support
from agents.refund_support import refund_order_with_admin_approval, refund_support
from agents.support_insights import support_insights
from app.main import agent_os, app
from app.store_knowledge import store_knowledge
from app.support_continuations import complete_rejected_refund_continuation
from app.support_models import CustomerEmail, CustomerEmailReply, IssueCode, SupportCategory
from teams.customer_support import customer_support_team


def _paused_refund_run(email: CustomerEmail, approval_id: str, run_id: str) -> TeamRunOutput:
    return TeamRunOutput(
        run_id=run_id,
        team_id="customer-support",
        session_id=f"SESSION-{approval_id}",
        user_id="support-test",
        input=TeamRunInput(input_content=email),
        requirements=[
            RunRequirement(
                tool_execution=ToolExecution(
                    tool_call_id=f"CALL-{approval_id}",
                    tool_name="refund_order_with_admin_approval",
                    tool_args={
                        "order_id": "ORD-LUMEN-1004",
                        "customer_email": email.from_email,
                        "reason": "Arrived damaged",
                    },
                    approval_type="required",
                    approval_id=approval_id,
                )
            )
        ],
        status=RunStatus.paused,
    )


def test_customer_team_keeps_three_private_specialists_and_typed_contracts() -> None:
    members = cast(list[Agent], customer_support_team.members)

    assert customer_support_team.mode is TeamMode.coordinate
    assert len(members) == 3
    assert {member.role for member in members} == {
        "Resolve order, fulfillment, and tracking questions from store records.",
        "Answer product and sizing questions only from dedicated catalog knowledge.",
        "Validate refunds and execute the deterministic refund routes.",
    }
    assert customer_support_team.input_schema is CustomerEmail
    assert customer_support_team.output_schema is CustomerEmailReply
    assert all(member.learning is None for member in members)
    assert customer_support_team.learning is None


def test_over_threshold_member_tool_requires_blocking_admin_approval() -> None:
    assert refund_order_with_admin_approval.requires_confirmation is True
    assert refund_order_with_admin_approval.approval_type == "required"
    assert refund_support.learning is None


def test_invoked_team_validates_email_and_returns_a_typed_reply(monkeypatch) -> None:
    def completed_team_run(_: Team, run_response: TeamRunOutput, **__: Any) -> TeamRunOutput:
        assert run_response.input is not None
        assert isinstance(run_response.input.input_content, CustomerEmail)
        email = run_response.input.input_content
        run_response.content = CustomerEmailReply(
            message_id=email.message_id,
            subject="Tracking update",
            body="Your order is in transit.",
            category=SupportCategory.ORDER,
            issue_code=IssueCode.TRACKING_REQUEST,
            outcome="answered",
            order_id="ORD-LUMEN-1001",
        )
        run_response.status = RunStatus.completed
        return run_response

    monkeypatch.setattr(customer_support_team, "db", None)
    monkeypatch.setattr("agno.team._run._run", completed_team_run)

    completed = customer_support_team.run(
        {
            "message_id": "EMAIL-VALID-TEAM",
            "from_email": "alice@example.test",
            "subject": "Where is my order?",
            "body": "Please share the tracking status for ORD-LUMEN-1001.",
        }
    )

    assert completed.status is RunStatus.completed
    assert isinstance(completed.content, CustomerEmailReply)
    assert completed.content.message_id == "EMAIL-VALID-TEAM"
    assert completed.content.body == "Your order is in transit."
    assert not hasattr(completed.content, "total_interactions")
    assert "recommendation" not in completed.content.model_fields_set


def test_invoked_team_rejects_plain_text_without_heuristic_parsing() -> None:
    with pytest.raises(ValueError, match="Failed to parse"):
        customer_support_team.run("Please refund ORD-LUMEN-1004")


@pytest.mark.parametrize(
    "invalid_input",
    [
        {"message_id": "EMAIL-BAD", "from_email": "not-an-email", "subject": "Refund", "body": "Please help."},
        {"message_id": "EMAIL-MISSING", "from_email": "dana@example.test", "subject": "Refund"},
    ],
)
def test_invoked_team_rejects_invalid_email_json_without_heuristic_parsing(invalid_input) -> None:
    with pytest.raises(ValueError, match="Failed to parse"):
        customer_support_team.run(invalid_input)


@pytest.mark.parametrize("detail", ["the mug's unsupported heat limit", "the tote's unavailable stock count"])
def test_unsupported_catalog_fallback_returns_only_an_unavailable_notice(detail: str) -> None:
    assert catalog_detail_unavailable.entrypoint is not None
    response = catalog_detail_unavailable.entrypoint(detail)

    assert response == "That product detail is unavailable in the store catalog."
    assert "heat limit" not in response


def test_approved_required_approval_completes_with_the_resolved_audit_id(store, monkeypatch) -> None:
    email = CustomerEmail(
        message_id="EMAIL-APPROVED-120",
        from_email="dana@example.test",
        subject="Refund request",
        body="Please refund order ORD-LUMEN-1004 because it arrived damaged.",
    )
    approval = {
        "id": "APR-APPROVED-120",
        "approval_type": "required",
        "status": "approved",
        "run_id": "RUN-APPROVED-120",
    }
    paused = _paused_refund_run(email, approval_id="APR-APPROVED-120", run_id="RUN-APPROVED-120")
    monkeypatch.setattr(customer_support_team.db, "get_approval", lambda _: approval)
    monkeypatch.setattr("app.support_continuations.get_store_repository", lambda: store)
    monkeypatch.setattr("app.support_hooks.get_store_repository", lambda: store)

    def unexpected_model_continuation(*args, **kwargs):
        raise AssertionError("An approved continuation must not return to the model loop.")

    monkeypatch.setattr(Team, "continue_run", unexpected_model_continuation)

    completed = customer_support_team.continue_run(run_response=paused)

    assert completed.status is RunStatus.completed
    assert isinstance(completed.content, CustomerEmailReply)
    assert completed.content.outcome == "refund_completed"
    assert completed.metadata == {"approval": approval}
    order = store.get_order("ORD-LUMEN-1004", "dana@example.test")
    assert order is not None
    assert order["refund"]["approval_id"] == "APR-APPROVED-120"


@pytest.mark.parametrize("stream", ["false", "true"])
def test_public_team_rest_continuation_completes_resolved_member_approval(store, monkeypatch, stream: str) -> None:
    email = CustomerEmail(
        message_id="EMAIL-REST-APPROVED-120",
        from_email="dana@example.test",
        subject="Refund request",
        body="Please refund order ORD-LUMEN-1004 because it arrived damaged.",
    )
    approval = {
        "id": "APR-REST-APPROVED-120",
        "approval_type": "required",
        "status": "approved",
        "run_id": "RUN-REST-APPROVED-120",
    }
    paused = _paused_refund_run(email, approval_id=approval["id"], run_id=approval["run_id"])
    assert paused.requirements is not None
    paused.requirements[0].member_agent_id = "refund-support"

    async def get_paused_run(*_: Any, **__: Any) -> TeamRunOutput:
        return paused

    async def skip_run_persistence(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr("agno.os.routers.teams.router.get_team_by_id", lambda **_: customer_support_team)
    monkeypatch.setattr(customer_support_team, "aget_run_output", get_paused_run)
    monkeypatch.setattr(customer_support_team, "_apersist_resolved_completion", skip_run_persistence)
    monkeypatch.setattr(customer_support_team.db, "get_approval", lambda _: approval)
    monkeypatch.setattr("app.support_continuations.get_store_repository", lambda: store)
    monkeypatch.setattr("app.support_hooks.get_store_repository", lambda: store)

    assert paused.session_id is not None
    assert paused.user_id is not None
    response = TestClient(app).post(
        f"/teams/customer-support/runs/{paused.run_id}/continue",
        data={"session_id": paused.session_id, "user_id": paused.user_id, "stream": stream},
    )

    assert response.status_code == 200
    if stream == "false":
        body = response.json()
        assert body["content"]["outcome"] == "refund_completed"
        assert body["metadata"]["approval"]["id"] == approval["id"]
    else:
        assert "refund_completed" in response.text
        assert approval["id"] in response.text
    order = store.get_order("ORD-LUMEN-1004", "dana@example.test")
    assert order is not None
    assert order["refund"]["approval_id"] == approval["id"]


def test_rejected_required_approval_completes_once_without_a_second_pause(store, monkeypatch) -> None:
    email = CustomerEmail(
        message_id="EMAIL-REJECTED-120",
        from_email="dana@example.test",
        subject="Refund request",
        body="Please refund order ORD-LUMEN-1004 because it arrived damaged.",
    )
    approval = {
        "id": "APR-REJECTED-120",
        "approval_type": "required",
        "status": "rejected",
        "run_id": "RUN-REJECTED-120",
    }
    paused = _paused_refund_run(email, approval_id="APR-REJECTED-120", run_id="RUN-REJECTED-120")
    monkeypatch.setattr(customer_support_team.db, "get_approval", lambda _: approval)
    monkeypatch.setattr("app.support_hooks.get_store_repository", lambda: store)

    def unexpected_model_continuation(*args, **kwargs):
        raise AssertionError("A rejected approval must not return to the model loop.")

    monkeypatch.setattr(Team, "continue_run", unexpected_model_continuation)
    completed = customer_support_team.continue_run(run_response=paused)
    assert completed.status is RunStatus.completed
    assert completed.requirements == []
    assert isinstance(completed.content, CustomerEmailReply)
    assert completed.content.message_id == email.message_id
    assert completed.content.outcome == "refund_rejected"
    assert completed.content.category is SupportCategory.REFUND
    assert completed.content.issue_code is IssueCode.REFUND_REQUEST
    assert completed.content.order_id == "ORD-LUMEN-1004"
    assert completed.content.body == "We could not process your refund request. Your order remains unchanged."
    assert completed.metadata == {"approval": approval}

    report = store.insights(__import__("datetime").date(2026, 1, 1), __import__("datetime").date(2027, 1, 1))
    assert report.total_interactions == 1
    assert report.refund_outcomes == {"rejected": 1}
    with store.engine.connect() as connection:
        interaction = connection.execute(
            text("SELECT payload FROM store_records WHERE record_type = 'support_interaction'"),
        ).scalar_one()
    assert interaction["approval_id"] == approval["id"]


def test_rejected_required_approval_recovers_serialized_original_input() -> None:
    email = CustomerEmail(
        message_id="EMAIL-REJECTED-JSON",
        from_email="dana@example.test",
        subject="Refund request",
        body="Please refund order ORD-LUMEN-1004.",
    )
    approval = {"id": "APR-REJECTED-JSON", "approval_type": "required", "status": "rejected"}
    paused = TeamRunOutput(
        run_id="RUN-REJECTED-JSON",
        team_id="customer-support",
        session_id="SESSION-REJECTED-JSON",
        input=TeamRunInput(input_content=email.model_dump_json()),
        requirements=[
            RunRequirement(
                tool_execution=ToolExecution(
                    tool_name="refund_order_with_admin_approval",
                    tool_args={"order_id": "ORD-LUMEN-1004"},
                    approval_type="required",
                    approval_id="APR-REJECTED-JSON",
                )
            )
        ],
        status=RunStatus.paused,
    )

    completed = complete_rejected_refund_continuation(paused, approval)

    assert completed.status is RunStatus.completed
    assert isinstance(completed.content, CustomerEmailReply)
    assert isinstance(completed.metadata, dict)
    assert completed.content.message_id == "EMAIL-REJECTED-JSON"
    assert completed.content.outcome == "refund_rejected"
    assert completed.content.order_id == "ORD-LUMEN-1004"
    assert completed.metadata["approval"]["id"] == "APR-REJECTED-JSON"


def test_rejected_continuation_without_a_refund_tool_keeps_order_id_empty() -> None:
    email = CustomerEmail(
        message_id="EMAIL-REJECTED-NO-TOOL",
        from_email="dana@example.test",
        subject="Refund request",
        body="Please help with my refund.",
    )
    paused = TeamRunOutput(
        run_id="RUN-REJECTED-NO-TOOL",
        team_id="customer-support",
        input=TeamRunInput(input_content=email),
        status=RunStatus.paused,
    )

    completed = complete_rejected_refund_continuation(
        paused, {"id": "APR-REJECTED-NO-TOOL", "approval_type": "required", "status": "rejected"}
    )

    assert isinstance(completed.content, CustomerEmailReply)
    assert completed.content.order_id is None


def test_refund_delegation_instruction_forwards_validated_identity_and_reason() -> None:
    instructions = str(customer_support_team.instructions)

    assert "from_email" in instructions
    assert "reason" in instructions


def test_refund_specialist_instruction_uses_deterministic_route_tools_without_amounts() -> None:
    instructions = str(refund_support.instructions)

    assert "refund_order_automatically" in instructions
    assert "refund_order_with_admin_approval" in instructions


def test_refund_specialist_instruction_stops_after_an_admin_rejection() -> None:
    instructions = str(refund_support.instructions)

    assert "rejected" in instructions
    assert "Do not call either refund tool again" in instructions


def test_order_specialist_instruction_avoids_unrelated_refund_details() -> None:
    instructions = str(order_support.instructions)

    assert "refund history" in instructions


def test_team_instruction_preserves_the_validated_message_id() -> None:
    instructions = str(customer_support_team.instructions)

    assert "same message_id" in instructions


def test_product_support_uses_only_dedicated_knowledge_and_no_learning() -> None:
    assert product_support.knowledge is store_knowledge
    assert product_support.search_knowledge is True
    assert product_support.learning is None


def test_only_public_support_surfaces_are_registered() -> None:
    agents = agent_os.agents or []
    teams = agent_os.teams or []
    knowledge = agent_os.knowledge or []

    assert support_insights in agents
    assert customer_support_team in teams
    assert store_knowledge in knowledge
    assert refund_support not in agents
    assert product_support not in agents
