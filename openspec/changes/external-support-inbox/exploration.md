## Exploration: External Support Inbox

### Current State
`customer-support-inbox` is a completed, separate OpenSpec change and MUST remain an immutable reference; this is a new migration change. The current AgentOS serves a React/Vite SPA from `frontend/support-inbox/dist/` through middleware and exposes three unauthenticated-in-application `/api/support/*` routes from `app/support_inbox.py`. Those routes already provide the important safe DTO boundary: only typed `customer-support` `TeamRunOutput` records are mapped, private member/tool/reasoning/approval/order/product fields are excluded, and paused runs expose only a coarse pending status. The completed change has passing deterministic pytest/Vitest/build/validation evidence, but it intentionally has no operator authentication, BFF, application-owned operator tables, audit log, external hosting contract, or production cutover mechanism.

The authoritative external plan is feasible as a controlled migration, not as a single repository-only edit. The repository has no migration framework and no BFF package; application-owned PostgreSQL tables, a separate FastAPI service, independent frontend deployment, Railway configuration, and operational PAT provisioning will need a new product repository or an explicitly approved temporary location. The current Docker image ships prebuilt frontend assets and excludes `package.json`/`package-lock.json` from its context, so the legacy SPA must remain until the external deployment is proven. A separate staging environment is intentionally omitted; production readiness must therefore be established with local/CI checks, explicit preflight gates, read-only production smoke checks, and a reversible cutover. Agno documentation for the pinned 3.0 line supports service-account PAT verification and custom route-to-scope mappings, but the current `app/main.py` only enables authorization as a boolean; the exact middleware installation/order and service-account scope behavior for these custom routes still require a production-mode integration test.

### Affected Areas
- `docs/support-inbox-external-frontend-plan.md` — authoritative topology, security contract, phased rollout, acceptance criteria, and unresolved operational choices.
- `app/support_inbox.py` — retain and potentially harden the BFF-facing DTO/API boundary; add explicit production authorization without exposing AgentOS internals or turning the routes into a generic proxy.
- `app/main.py` — integrate custom route scope enforcement with the existing AgentOS authorization middleware; preserve route precedence and defer static-hosting removal until cutover.
- `tests/test_support_inbox.py` — retain all completed DTO/privacy tests and add production-mode credential matrix coverage for unauthenticated, invalid, unrelated, under-scoped, and correctly scoped callers.
- `frontend/support-inbox/src/api.ts` — replace relative requests with the configured BFF origin, credentialed cookies, CSRF headers for sends, and stable `401`/`403`/`429`/gateway handling.
- `frontend/support-inbox/src/App.tsx`, `src/App.test.tsx`, `vite.config.ts`, `package*.json`, `dist/**` — add authentication/session UI states and root deployment configuration while preserving safe rendering, pending status, mobile behavior, and the existing two-tab contract.
- `Dockerfile`, `.dockerignore`, `.gitignore`, and AgentOS documentation — keep legacy packaging valid during migration, then remove static-serving assumptions only in the final cleanup slice.
- New private `support-inbox/bff/` service — own settings, operator/session/audit models, migrations, Argon2id handling, opaque cookie sessions, CSRF/origin checks, typed AgentOS client, explicit proxy routes, rate limits, redacted logging, and deterministic cleanup.
- New private `support-inbox/frontend/` repository area — become the authoritative Cloudflare Pages project only after the in-place frontend contract and production-readiness gates are complete.
- Railway/Cloudflare deployment configuration and operator administration procedure — provision the BFF, restricted database access, exact origin allowlists, private AgentOS URL, scoped PAT, test operator, rotation, rollback, and retention policies.

### Approaches
1. **Controlled strangler migration with an AgentOS security-first slice** — first pin the existing DTO contract and prove custom route authorization; then build and test the BFF; then refactor the frontend against the BFF; then waive separate staging in favor of production-readiness gates and a guarded cutover; finally remove legacy static hosting.
   - Pros: Matches the authoritative plan; keeps the known-good privacy boundary; makes each trust boundary independently testable; preserves rollback through the existing SPA; limits the blast radius of the new credential model.
   - Cons: Temporarily maintains two frontend paths; requires coordination across two repositories/services and operational secrets; production integration tests need a realistic authorized AgentOS stack.
   - Effort: High.

2. **Build the external BFF/frontend first and defer AgentOS route authorization** — proxy the existing routes with the PAT, then harden AgentOS later.
   - Pros: Produces an early external deployment and exercises the frontend/BFF contract quickly.
   - Cons: Leaves custom AgentOS routes protected only by generic credential possession during the riskiest transition; conflicts with the plan's explicit denial matrix and makes a temporary security gap easy to ship.
   - Effort: High.

3. **Keep the SPA in AgentOS and add a second browser authentication model** — implement operator cookies directly in the current process instead of introducing a BFF.
   - Pros: Avoids a new service and repository initially.
   - Cons: Contradicts the approved topology; mixes opaque operator sessions with AgentOS auth middleware; increases route-exclusion, CORS, secret-handling, and deployment coupling; does not achieve independent Cloudflare Pages hosting.
   - Effort: High.

### Recommendation
Use the controlled strangler migration. The safe first slice is **AgentOS contract pinning and authorization proof only**: document the three exact DTO contracts and forbidden fields, add a production-mode integration harness for custom route scope mappings/service-account verification, and prove the full caller matrix before writing BFF code. The BFF should remain an explicit typed client, never a generic proxy, and should use application-owned operator tables rather than querying Agno persistence. Keep the completed `customer-support-inbox` artifacts unchanged and keep the legacy SPA deployable until production-readiness and rollback checks pass.

Dependency order:
1. Resolve the AgentOS authorization mechanism and PAT scope names against the pinned runtime; establish the route denial matrix.
2. Decide the BFF repository/service ownership, database migration mechanism, operator provisioning command, audit/session retention, and preview-environment policy.
3. Build the BFF with unit/integration tests and a fake AgentOS server; verify PAT secrecy, typed DTO validation, CSRF, CORS, rate limits, audit redaction, and `202 approval_pending` preservation.
4. Refactor the existing SPA to the BFF contract and authentication state machine; run frontend tests/build and scan output for forbidden secrets.
5. Extract into the private repository and complete local/CI security, build, migration, and synthetic end-to-end checks; no separate staging environment is provisioned.
6. Cut over production with read-only smoke checks first, retain the legacy path during observation, and remove static hosting only after rollback readiness is demonstrated.

### Risks
- The current repository does not contain a BFF or migration framework, so implementing the full plan here would silently invent repository ownership and deployment boundaries.
- Custom scope mappings are documented by Agno, but the current AgentOS construction does not configure them; middleware ordering and service-account scope enforcement must be proven rather than assumed.
- The plan's suggested `support_inbox:read` and `support_inbox:send` scopes are a policy choice, not yet provisioned credentials; exact scope grants, route patterns, and whether a principal-only fallback is needed remain unresolved until the integration test.
- Shared PostgreSQL ownership, DB roles, schema/table naming, migration execution, retention, and cleanup scheduling are unresolved and security-relevant.
- Cross-site cookies require `SameSite=None` plus `Secure`, exact CORS origins, and CSRF; preview origins must not gain wildcard access to production.
- `POST /api/support/emails` has no idempotency contract. The BFF must not retry it, and duplicate operator submissions remain a product decision.
- Operator authentication choices remain under-specified for lockout/rate-limit algorithms, password reset administration, pepper adoption, cookie idle/absolute limits, and audit retention.
- The external deployment introduces two repositories and independent rollbacks; without staging, PAT rotation, private networking fallback, observability, Cloudflare/Railway ownership, production preflight, and rollback runbooks need to be complete before cutover.
- The configured repository OpenSpec metadata still contains stale prior-plan wording and records `single-pr` delivery, while this session's approved preflight is `ask-on-risk` with an 800-line budget. The new change must treat the approved session values as authoritative and forecast chained slices; likely BFF plus frontend work exceeds the review budget.

### Ready for Proposal
Yes, with a proposal explicitly scoped as a new external migration change and with the first implementation slice limited to AgentOS authorization/contract proof. Before design or apply, the owner must resolve repository ownership, migration/DB-role strategy, exact PAT scope enforcement, operator provisioning/retention policy, preview isolation, and the delivery split required by the 800-line review budget. Do not extend or modify `customer-support-inbox` artifacts.
