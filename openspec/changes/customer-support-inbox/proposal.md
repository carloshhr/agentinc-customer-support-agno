# Proposal: Customer Support Inbox

## Intent

Provide a local-development inbox for safely inspecting persisted Customer Support conversations and sending simulated emails from the existing AgentOS/FastAPI service. The accepted plan in `docs/customer-support-inbox-plan.md` takes precedence over stale inbox-unrelated config context.

## Scope

### In Scope
- React/TypeScript/Vite SPA served at `/support-inbox/` by the existing process.
- Three allow-listed `/api/support/` endpoints backed by typed inbox DTOs derived only from `customer-support` sessions/runs.
- Responsive list/detail and compose/reply UX, with exactly Email and JSON views.
- Reconcile, test, and harden existing uncommitted inbox work; do not assume it is correct.

### Out of Scope
- Production browser auth, a second service, raw AgentOS/session/run proxying, or `support_interaction` as the conversation store.
- HITL continuation, approval details/actions, rich HTML, attachments, search, pagination, delivery, or collaboration.

## Capabilities

### New Capabilities
- `customer-support-inbox`: Safe browser inbox DTOs, routes, static SPA serving, and simulated-email workflow.

### Modified Capabilities
None. The existing `customer-support` typed team contract is reused without changing its requirements.

## Approach

Complete the allow-listed DTO mapper over persisted `TeamRunOutput` records; expose only normalized email fields and coarse status. Reuse `thread_id` unchanged as the team `session_id`; return only safe pending state for paused runs. Reconcile current backend, SPA, tests, generated assets, Docker ignore rules, and mount ordering against the accepted plan. Require forbidden-field and PostgreSQL-deserialization coverage plus `npm ci && npm run build` before packaging assets.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `app/support_inbox.py`, `app/main.py` | Modified | DTO routes and static mount/order |
| `frontend/support-inbox/` | Modified | Typed SPA and reproducible build |
| `tests/test_support_inbox.py` | Modified | Boundary and serving regressions |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Deserialized runs fail `TeamRunOutput` filtering | Med | Persistence-backed mapper test |
| Stale/missing static assets | Med | Rebuild gate and image validation |
| Raw internals or approval controls leak | Low | DTO allow-list and regression tests |
| Pre-existing work exceeds the 800-line single-PR budget (exploration: >=3,204 lines) | High | **BLOCKER:** before apply, explicitly accept `size:exception` or change delivery strategy; no silent exception |

## Rollback Plan

Revert inbox router/middleware, SPA assets, and related tests as one work unit; no schema migration or persisted-data rollback is required.

## Dependencies

- Existing typed `customer-support` team and an exclusive-writer window for any model-backed smoke test.

## Success Criteria

- [ ] Only the three documented endpoints and safe DTO fields reach the browser.
- [ ] `thread_id` remains the Customer Support `session_id`; pending threads expose no approval details.
- [ ] Desktop/mobile states and the two safe tabs work after a reproducible static build.
- [ ] The delivery-size blocker is explicitly resolved before apply.

## Proposal Question Round

Auto mode recorded these assumptions: this first slice remains local-only, simulated-email-only, and approval-read-only. The required unresolved product/delivery decision is whether to grant a documented single-PR `size:exception` for the pre-existing >800-line work; otherwise the delivery strategy must change before apply.
