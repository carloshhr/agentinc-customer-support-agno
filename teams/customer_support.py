"""Public typed customer-support team with three private specialists."""

from typing import Any, cast

from agno.run.team import TeamRunOutput
from agno.team import Team, TeamMode

from agents.order_support import order_support
from agents.product_support import product_support
from agents.refund_support import refund_support
from app.settings import default_model
from app.support_continuations import (
    complete_approved_refund_continuation,
    complete_rejected_refund_continuation,
)
from app.support_hooks import persist_customer_support_interaction
from app.support_models import CustomerEmail, CustomerEmailReply
from db import get_postgres_db


class CustomerSupportTeam(Team):
    """Complete rejected required refunds without another model-driven tool call."""

    def continue_run(
        self,
        run_response: TeamRunOutput | None = None,
        *,
        run_id: str | None = None,
        stream: bool | None = None,
        **kwargs: Any,
    ) -> Any:  # type: ignore[override]
        paused = run_response or (self.db.get_run(run_id) if self.db and run_id else None)
        approval = self._resolved_refund_approval(paused)
        if approval is None or not isinstance(paused, TeamRunOutput):
            return super().continue_run(run_response, run_id=run_id, stream=stream, **kwargs)  # type: ignore[call-overload]
        if approval["status"] == "approved":
            completed = complete_approved_refund_continuation(paused, approval)
        else:
            completed = complete_rejected_refund_continuation(paused, approval)
        persist_customer_support_interaction(completed)
        self._persist_resolved_completion(completed)
        return iter([completed]) if stream else completed

    def acontinue_run(  # type: ignore[override]
        self,
        run_response: TeamRunOutput | None = None,
        *,
        run_id: str | None = None,
        stream: bool | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if stream:
            return self._acontinue_resolved_refund_stream(
                run_response,
                run_id=run_id,
                session_id=session_id,
                user_id=user_id,
                **kwargs,
            )
        return self._acontinue_resolved_refund(
            run_response,
            run_id=run_id,
            stream=stream,
            session_id=session_id,
            user_id=user_id,
            **kwargs,
        )

    async def _acontinue_resolved_refund(
        self,
        run_response: TeamRunOutput | None = None,
        *,
        run_id: str | None = None,
        stream: bool | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        completed = await self._aresolve_refund_continuation(
            run_response,
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
        )
        if completed is not None:
            return completed
        return await super().acontinue_run(  # type: ignore[call-overload,misc]
            run_response,
            run_id=run_id,
            stream=stream,
            session_id=session_id,
            user_id=user_id,
            **kwargs,
        )

    async def _aresolve_refund_continuation(
        self,
        run_response: TeamRunOutput | None = None,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> TeamRunOutput | None:
        paused = run_response or (
            await self.aget_run_output(run_id, session_id=session_id, user_id=user_id) if run_id else None
        )
        approval = self._resolved_refund_approval(paused)
        if approval is None or not isinstance(paused, TeamRunOutput):
            return None
        if approval["status"] == "approved":
            completed = complete_approved_refund_continuation(paused, approval)
        else:
            completed = complete_rejected_refund_continuation(paused, approval)
        persist_customer_support_interaction(completed)
        await self._apersist_resolved_completion(completed)
        return completed

    async def _acontinue_resolved_refund_stream(
        self,
        run_response: TeamRunOutput | None = None,
        *,
        run_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ):
        completed = await self._aresolve_refund_continuation(
            run_response,
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
        )
        if isinstance(completed, TeamRunOutput):
            from agno.utils.events import create_team_run_completed_event

            yield create_team_run_completed_event(completed)
            return
        continue_response = super().acontinue_run(
            run_response,
            run_id=run_id,
            stream=True,
            session_id=session_id,
            user_id=user_id,
            **kwargs,
        )
        async for event in continue_response:
            yield event

    def _resolved_refund_approval(self, run_output: Any) -> dict[str, Any] | None:
        for requirement in getattr(run_output, "requirements", None) or []:
            tool = requirement.tool_execution
            if tool and tool.tool_name == "refund_order_with_admin_approval" and tool.approval_id:
                approval = cast(dict[str, Any] | None, self.db.get_approval(tool.approval_id) if self.db else None)
                if (
                    approval
                    and approval.get("approval_type") == "required"
                    and approval.get("status")
                    in {
                        "approved",
                        "rejected",
                    }
                ):
                    return approval
        return None

    def _persist_resolved_completion(self, run_output: TeamRunOutput) -> None:
        session = self.get_session(session_id=run_output.session_id, user_id=run_output.user_id)
        if session is None or self.db is None or run_output.session_id is None:
            return
        session.upsert_run(run_response=run_output)
        self.save_session(session)
        self.db.upsert_run(run_output, session_id=run_output.session_id, user_id=run_output.user_id)

    async def _apersist_resolved_completion(self, run_output: TeamRunOutput) -> None:
        session = await self.aget_session(session_id=run_output.session_id, user_id=run_output.user_id)
        if session is None or self.db is None or run_output.session_id is None:
            return
        session.upsert_run(run_response=run_output)
        await self.asave_session(session)
        self.db.upsert_run(run_output, session_id=run_output.session_id, user_id=run_output.user_id)


customer_support_team = CustomerSupportTeam(
    id="customer-support",
    name="Customer Support",
    model=default_model(),
    db=get_postgres_db(),
    mode=TeamMode.coordinate,
    members=[order_support, product_support, refund_support],
    input_schema=CustomerEmail,
    output_schema=CustomerEmailReply,
    post_hooks=[persist_customer_support_interaction],
    instructions="""\
You are Customer Support for a fictional store. Process only the validated customer email input.

How you work:
1. Route order, fulfillment, and tracking questions to Order Support.
2. Route product, material, sizing, and supported policy questions to Product Support.
3. For product replies, answer only the customer's actual question with needed Product Support facts.
   Do not add sales or order-help offers or volunteer claims about absent variants,
   regional prices, promotions, discounts, or availability.
4. Route return and refund requests to Returns & Refunds Support.
5. Combine only validated input and specialist facts into one concise, professional, empathetic English reply.
6. For every refund delegation, include the exact order_id, from_email, and customer-stated reason.
   Take all three values from the validated input.
   Never ask a specialist to estimate payment method, amount, or timing.

Safety boundaries:
- Do not expose internal taxonomy, tools, reasoning, approvals, or another customer's data.
- Use the structured category and issue_code only as metadata, never in the email body.
- Return the same message_id from the validated input; never invent or replace it.
- Do not claim an approval-gated refund is complete while its run is paused.
- Return CustomerEmailReply only; never include administrator insights.\
""",
)
