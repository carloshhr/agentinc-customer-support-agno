# Design: External Support Inbox

## Technical Approach

Use a strangler migration. Phase 1 AgentOS authorization and DTO privacy proof is **complete**; preserve it as the gate for a typed BFF. Build the BFF and frontend temporarily in this repository as separate deployables. A separate staging environment is intentionally waived; use deterministic local/CI checks and production preflight, read-only smoke checks, observation, and rollback criteria before extraction or legacy removal. `customer-support-inbox` remains unchanged and deployable throughout.

## Architecture Decisions

| Decision | Choice | Tradeoff / rationale |
|---|---|---|
| Service boundary | `support-inbox/bff/` is a FastAPI service; `frontend/support-inbox/` is a separate SPA boundary. Browser traffic goes only to the BFF. | Temporary monorepo avoids blocking delivery; independent build/config/deploy boundaries preserve later extraction. |
| AgentOS gate | Retain completed Phase 1 proof: designated `sa:support-inbox-bff` plus route scopes (`support_inbox:read`/`send`), with typed allow-listed DTOs. | Do not widen PAT access, weaken authorization, or rework `customer-support-inbox`. |
| BFF state | BFF owns operator, session, and audit tables in PostgreSQL schema `support_inbox`; never query or migrate Agno tables. | Alembic revisions are versioned and reversible; state ownership stays explicit. |
| Credentials | Argon2id password hashes, **no password pepper**; opaque digest-only secure HttpOnly sessions. | No secret must be shared between deployment systems. |
| Session policy | 30-minute idle timeout; 8-hour absolute timeout; five failed attempts trigger a 15-minute lockout. | Fixed defaults are testable and conservative for the first release. |
| Audit policy | Store actor, action, outcome, request ID, and timestamps; retain 90 days; never store passwords, tokens, CSRF values, bodies, or raw upstream payloads. | Supports incident review without creating a content archive. |

## Data Flow

`Browser SPA → BFF session/CSRF/origin checks → typed AgentOS client + server PAT → safe AgentOS DTOs`

Login returns safe operator data and an in-memory CSRF token. Reads require a session; mutations require exact `Origin` and CSRF. The BFF validates bounded input/upstream schemas, preserves `202 approval_pending`, and emits redacted request-ID errors.

## File Changes

| Path | Action | Description |
|---|---|---|
| `app/support_inbox.py`, `app/main.py`, `tests/test_support_inbox.py` | Preserve/modify only as required | Keep Phase 1 proof, DTOs, route precedence, and legacy serving. |
| `support-inbox/bff/{app,migrations,tests,Dockerfile}` | Create | BFF, Alembic `upgrade/downgrade`, security, tests, and deploy boundary. |
| `frontend/support-inbox/src/*`, `vite.config.ts` | Modify | BFF origin, session/CSRF states, and safe existing UI behavior. |
| `customer-support-inbox/**` | Do not modify | Completed reference remains immutable. |

## Interfaces / Contracts

AgentOS keeps the three existing typed support routes. BFF exposes `POST /auth/login`, `GET /auth/session`, `POST /auth/logout`, plus explicit read/detail/send paths. Failures use safe `401/403/429/502/504` codes. Default send behavior is one upstream attempt, no automatic retry, and no deduplication until idempotency is decided.

## Testing Strategy

Unit/integration tests cover Argon2id/no pepper, expiry, lockout, CSRF/CORS, redaction, reversible migrations, schema failures, timeout, PAT secrecy, and safe `202`. Frontend Vitest covers session gating and direct-AgentOS absence. Local/CI synthetic E2E covers login/read/send/audit/logout/denial; production uses read-only smoke checks first and permits a controlled send only against an explicitly safe deterministic target.

## Threat Matrix

HTTP routing and service/process integration are applicable and covered by the BFF boundary, exact paths, origin checks, local/CI tests, and production smoke checks. Supplied rows: documentation-like paths — N/A (no execution); Git repository selection — N/A (no repository automation); commit state — N/A; push state — N/A; PR commands — N/A. No RED tests apply to N/A rows.

## Migration / Rollout

Default: a separate migration execution role owns Alembic and retention cleanup; the BFF runtime role has DML only. Default operator path is explicitly provisioned accounts, no public registration/recovery. Production uses an exact allowlisted frontend origin; previews are disabled by default and, if enabled, use isolated data, origin, PAT, and database settings. Separate staging is intentionally waived. Complete production preflight, cut over read-only, observe, then perform one controlled send only against an explicitly safe deterministic target; rollback disables external routing, revokes the PAT if needed, and restores the unchanged legacy SPA.

## Open Questions

- [ ] **DB role execution:** approve separate migration/cleanup role versus a controlled deploy job; default is separate role, runtime DML-only.
- [ ] **Operator provisioning/reset:** choose owner-approved CLI/admin workflow versus an identity provider; default is manually provisioned accounts with audited reset, no self-service.
- [ ] **Domains/previews:** approve production domains and whether previews exist; default is one exact production origin and previews off.
- [ ] **Send idempotency:** choose `Idempotency-Key` storage/window/replay semantics; default is no automatic retry or deduplication and one upstream attempt.
- [ ] **Extraction timing:** choose repository owner/date; default is remain in-repo through production readiness and initial observation, then extract after rollback proof.
