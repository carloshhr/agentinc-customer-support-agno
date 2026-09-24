# Tasks: External Support Inbox

## Review Workload Forecast

| Field | Value |
| --- | --- |
| Review budget | 800 changed lines |
| Estimate | 1,000–1,500 |
| 400-line risk | High |
| Chained PRs | Yes |
| Suggested split | PR 1 complete → PR 2 BFF → PR 3 frontend → PR 4 production readiness waiver → PR 5 cutover |
| Delivery | ask-on-risk |
| Chain | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal / base | Focused test command | Runtime harness | Rollback boundary |
| --- | --- | --- | --- | --- |
| 1 | AgentOS proof; done | `uv run --extra dev pytest tests/test_support_inbox.py -q` | Production PAT matrix | AgentOS proof files |
| 2 | BFF proxy; PR #1 base = tracker | `uv run --extra dev pytest support-inbox/bff/tests -q` | Fake AgentOS server | `support-inbox/bff/` only |
| 3 | Frontend; PR #2 base = PR #2 | `npm test && npm run build` | Local BFF, no AgentOS | `frontend/support-inbox/**` |
| 4 | Production readiness without staging; PR #3 base = PR #3 | BFF/frontend CI + preflight checklist | Local/CI synthetic E2E | Readiness artifacts only |
| 5 | Cutover; PR #4 base = PR #4 | Full gates | Read-only then controlled send | Legacy routing |

Open decisions: migration/retention execution (separate role vs deploy job; default separate role, runtime DML-only); operator provisioning/reset (admin vs IdP; default manual, no self-service); domains/previews (default one exact origin, previews off); send idempotency key/window/replay (default one attempt, no retry/deduplication); extraction owner/date (default in-repo through production readiness/observation, then extract after rollback proof). Separate staging is intentionally omitted; no external repository now.

## Phase 1: AgentOS Proof (complete)

- [x] 1.1–1.4 Preserve PAT/scope, DTO/privacy proof, route enforcement, PAT docs, and unchanged `customer-support-inbox`.

## Phase 2: BFF Security/Proxy (next unit; `support-inbox/bff/` only)

- [x] 2.1 RED: test Argon2id without pepper, indistinguishable login, 5-failure/15-minute lockout, digest-only secure sessions, 30-minute idle/8-hour absolute expiry, logout, exact Origin/CSRF, and secure cookies.
- [x] 2.2 RED: test explicit routes, bounded schemas, malformed/timeout/5xx failures, safe `202 approval_pending`, audit redaction, PAT secrecy, no send retry, and HTTP/process integration.
- [x] 2.3 GREEN: create `support-inbox/bff/app/` settings, database, models, schemas, security, auth, client, support, audit, and main; use typed proxying and safe errors.
- [x] 2.4 GREEN: add reversible Alembic revisions in `support-inbox/bff/migrations/` for schema `support_inbox`, plus BFF tests, CI, Dockerfile, and retention hook; touch no AgentOS/frontend files.

## Phase 3: Frontend

- [x] 3.1 RED/GREEN: update `frontend/support-inbox/src/App.test.tsx`, `src/api.ts`, `App.tsx`, and `vite.config.ts` for BFF-only calls, session gate, in-memory CSRF, expiry/logout, 401/403/429/gateway states, and safe rendering.

## Phase 4: Staging and Extraction — intentionally waived

- [x] 4.1 **Waived by explicit decision:** do not provision a separate staging BFF/frontend environment or staging credentials.
- [x] 4.2 **Replaced by compensating checks:** complete local/CI security, build, migration, bundle-secret, and synthetic login/read/send/audit/logout/denial checks; complete production preflight before traffic is switched.

## Apply evidence for the bounded feature-branch slice

Repository-local compensating checks have been run and recorded in `docs/support-inbox-production-plan.md` and `docs/support-inbox-external-frontend-plan.md`. BFF, frontend, and AgentOS checks are green; the checked-in Railway shape and `/health` boundary have deterministic tests; PostgreSQL migration validation still needs a PostgreSQL-backed environment. No live deployment, credential change, traffic switch, controlled send, or destructive cleanup was performed.

## Phase 5: Cutover and Cleanup

- [ ] 5.1 Complete production preflight, observe production read-only, rehearse rollback, then controlled send only against an explicitly safe deterministic target; retain legacy hosting until exit criteria pass.
- [ ] 5.2 Remove legacy static serving and `frontend/support-inbox/` only after approval; rerun gates and preserve `customer-support-inbox` unchanged.

### Phase 4 Compensation / Phase 5 Gates

- [ ] Production configuration, migration state, operator provisioning, exact CORS/TLS, PAT principal/scopes, logging/redaction, health checks, and alerting are reviewed before cutover.
- [ ] Read-only production smoke checks pass before any send is attempted.
- [ ] Controlled send has an explicitly safe deterministic target, one-attempt/no-retry behavior, and an auditable request ID.
- [ ] Rollback rehearsal proves external routing can be disabled, the legacy SPA remains deployable, BFF/frontend can be reverted independently, and the PAT can be revoked without weakening AgentOS authorization or dropping operator/audit data.
