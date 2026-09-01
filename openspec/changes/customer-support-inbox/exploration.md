## Exploration: Customer Support Inbox

### Current State
The accepted plan in `docs/customer-support-inbox-plan.md` defines a local React/Vite inbox served by the existing FastAPI process, with three allow-listed API endpoints and no approval controls. The workspace already contains uncommitted implementation work: `app/support_inbox.py` reads `customer-support` team sessions with runs, validates only `CustomerEmail` inputs and `CustomerEmailReply` outputs, and produces explicit DTOs; `app/main.py` routes the API ahead of AgentOS's UI mount and serves `/support-inbox/` assets. The SPA has list/detail, compose/reply, pending status, and exactly Email and JSON tabs.

`support_interaction` remains analytics-only in `app/store.py`; it lacks the inbound/outbound messages and paused-run state needed by the inbox. The existing Customer Support team is already typed with `CustomerEmail` input and `CustomerEmailReply` output, so the send route can reuse that contract with `session_id=request.thread_id`.

### Affected Areas
- `app/support_inbox.py` — DTO allow-list, persisted-session/run mapper, API contracts, safe errors, and static asset handlers.
- `app/main.py` — API route ordering must stay ahead of AgentOS's catch-all UI mount; the static inbox is served by middleware.
- `teams/customer_support.py` and `app/support_models.py` — existing typed run boundary that the inbox reads and invokes; they should not expose member or approval internals.
- `tests/test_support_inbox.py` — deterministic mapper, route, pending-response, and static-serving regression coverage.
- `frontend/support-inbox/src/*` — typed API client, responsive list/detail behavior, compose flow, and escaped Email/JSON rendering.
- `frontend/support-inbox/package.json`, `package-lock.json`, `dist/`, `Dockerfile`, and `.dockerignore` — build artifact reproducibility. The Python image has no Node build stage, so the shipped `dist/` output must be rebuilt before the image is created.
- `openspec/config.yaml` — its source-plan and test-runner context still describe the archived `customer-support-team` change and must not override this accepted inbox plan.

### Approaches
1. **Complete and harden the current allow-listed DTO implementation** — reconcile the uncommitted backend and SPA with the accepted plan, add missing boundary tests, and preserve framework sessions/runs as private persistence.
   - Pros: Matches the accepted data, security, topology, and HITL boundaries; reuses the existing typed team; no migration or second service.
   - Cons: Depends on AgentOS persisted-session shapes; requires a real persistence integration test to prove deserialized runs are `TeamRunOutput` instances; static artifacts can become stale without a build gate.
   - Effort: Medium.

2. **Create an application-owned inbox projection** — persist normalized message records alongside each support run and serve the projection instead of reconstructing framework runs.
   - Pros: Stable browser query shape, simpler list ordering, and less coupling to AgentOS session serialization.
   - Cons: Adds schema, write-path, idempotency, migration, and privacy-retention responsibilities; duplicates data and departs from the accepted persisted-session/run source for the first slice.
   - Effort: High.

### Recommendation
Use the current allow-listed DTO approach. It is the accepted scope and preserves the framework data boundary, but proposal/design work must require a persistence-backed mapper test, forbidden-field regression tests, and a reproducible `npm ci && npm run build` gate before packaging static assets. Keep `support_interaction` out of the inbox read path and keep the UI strictly unable to continue approvals.

### Risks
- The mapper currently filters runs with `isinstance(run, TeamRunOutput)`; deterministic fixture tests pass, but an integration test against actual PostgreSQL-deserialized Customer Support sessions is required to prove real records are not silently omitted.
- `support_inbox_frontend()` assumes `frontend/support-inbox/dist/index.html` exists. `Dockerfile` has no Node build stage and `.dockerignore` excludes frontend package manifests, so image/deploy validation must prove fresh built assets are present rather than stale or missing.
- The current core implementation paths already account for at least 3,204 changed lines before remaining scaffold files and the plan, far above the configured 800-line review budget. The single-PR strategy needs an explicit size exception or a delivery decision before apply.
- `openspec/config.yaml` has stale customer-support-team source-plan/testing text; the inbox plan is the accepted scope, and later SDD artifacts must state that precedence explicitly.
- Model-backed Customer Support smoke tests write shared PostgreSQL state and cleanup is unsafe with concurrent writers. Normal feedback must remain deterministic pytest and Vitest coverage; run the live smoke only in an exclusive-writer window.

### Ready for Proposal
Yes — propose the allow-listed DTO route, record the static-build and real-persistence verification gates, and obtain an explicit decision for the over-budget single-PR delivery before implementation is admitted.
