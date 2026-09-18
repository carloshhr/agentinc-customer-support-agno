# Proposal: External Support Inbox

## Intent

Externalize the operator Support Inbox without widening access to AgentOS data. Deliver in-repository BFF and frontend services with explicit boundaries; intentionally omit a separate staging environment, retain legacy same-origin hosting, and use production-readiness gates before a guarded cutover.

## Scope

### In Scope
- Retain the three `/api/support/*` safe DTO contracts and BFF-only production authorization.
- Add a narrow in-repository BFF and frontend boundary; browsers call only the BFF and it alone holds the scoped PAT.
- Use Alembic with versioned, reversible migrations in a dedicated PostgreSQL schema for operator, session, and audit data.
- Enforce Argon2id passwords without a pepper; 30-minute idle / 8-hour absolute sessions; five-failure lockout for 15 minutes; and 90-day audit retention.
- Complete local/CI security and synthetic end-to-end checks, then perform production read-only smoke checks, observation, and legacy-hosting removal behind explicit exit criteria.

### Out of Scope
- Changes to `openspec/changes/customer-support-inbox` or Customer Support team behavior.
- Browser access to AgentOS, generic proxying, public registration, password recovery, and per-operator AgentOS identity.
- Moving the temporary BFF/frontend services to another repository before production readiness and rollback criteria are proven.

## Capabilities

### New Capabilities
- `external-support-inbox`: Secure external operator inbox boundary, BFF/browser contract, production-readiness gates, and cutover safeguards.

### Modified Capabilities
None. Existing `customer-support` behavior remains unchanged; the new API security contract is separate.

## Approach

Use a strangler migration. Preserve the AgentOS proof boundary, then add typed in-repository BFF and frontend services with separate configuration, CI, deployables, and data ownership. Alembic migrations operate only in the dedicated schema and must be reversible. Waive a separate staging environment and compensate with deterministic local/CI checks, production preflight, read-only-first cutover, observation, and rollback proof before removing static serving.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `app/support_inbox.py` | Modified | Preserve safe DTOs; enforce proven BFF-only authorization. |
| `app/main.py` | Modified | Integrate verified custom-route authorization without changing route precedence. |
| `tests/test_support_inbox.py` | Modified | Add production credential and privacy matrix. |
| `support-inbox/bff/` | New | Temporary BFF service, Alembic migrations, and dedicated-schema operator state. |
| `frontend/support-inbox/` | Modified | Temporary frontend service boundary; BFF-only browser contract. |
| `Dockerfile`, frontend, docs | Modified later | Preserve legacy hosting until cutover. |

## Open Decisions

- Dedicated-schema database role and migration/retention cleanup execution model.
- Operator provisioning/reset workflow; production and preview domains/origin isolation; send idempotency contract.
- Future extraction ownership/timing after the temporary in-repository implementation and initial production observation.
- Review chain resolution: use `ask-on-risk` and do not start an oversized slice without a resolved chain.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| BFF-only authorization regresses | Low | Retain the proven production credential matrix in local/CI checks and production preflight/smoke checks. |
| Cross-origin session exposure | Med | Exact origins, CSRF, server-held PAT, local/CI tests, and production smoke checks. |
| Cutover outage | Med | No separate staging; require production preflight, read-only-first smoke checks, observation, and independently reversible BFF/frontend/legacy routing. |

## Rollback Plan

Before legacy removal, disable the external route, revoke a suspected BFF PAT, and return operators to the deployable legacy SPA. Do not weaken AgentOS authorization or drop operator/audit data; roll back independent services first.

## Dependencies

- Scoped service-account provisioning and the proven AgentOS authorization boundary.
- Resolution of the remaining operator, cleanup, origin, idempotency, and review-chain decisions before production cutover.

## Success Criteria

- [ ] Only the intended BFF credential accesses support routes in production mode; DTO privacy tests pass.
- [ ] Browser calls only the BFF; local/CI checks prove login, 30-minute idle and 8-hour absolute expiry, 5/15 lockout, read, controlled send, audit, logout, and denial paths.
- [ ] Production preflight proves configuration, migrations, PAT scope/principal, exact CORS, TLS, observability, and rollback readiness before traffic is switched.
- [ ] Production smoke checks are read-only first; controlled send is performed only against an explicitly safe deterministic target.
- [ ] Legacy static hosting is removed only after verified cutover and rollback readiness.
