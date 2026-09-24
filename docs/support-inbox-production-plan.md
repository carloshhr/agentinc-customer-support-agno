# Support Inbox Production Readiness Runbook

This runbook is the release gate for the external Support Inbox. It deliberately does **not** perform deployment, credential mutation, traffic switching, or live sends. Until every production gate is evidenced by an authorized operator, the unchanged AgentOS-hosted inbox remains the fallback.

## Release decision

**Current decision: do not cut over.** Repository-local compensating checks are available, but production configuration, live authorization, observation, controlled-send safety, and rollback rehearsal require production credentials and operator approval.

## Quick path

1. Run the deterministic local/CI checks in this document.
2. Complete the production preflight evidence table with redacted values and links to the deployment system.
3. Observe the external deployment with read-only requests first.
4. Perform at most one controlled send, only to the approved deterministic target and with a unique request ID.
5. Keep legacy hosting available through the observation window; remove it only after the exit criteria pass.

## Compensating checks for waived staging

A separate staging BFF/frontend environment and staging credentials are intentionally omitted. The following checks replace that environment:

| Check | Command | Required result |
| --- | --- | --- |
| AgentOS DTO/privacy and route contract | `uv run --extra dev pytest tests/test_support_inbox.py -q` | All tests pass |
| BFF security/proxy/integration suite | `cd support-inbox/bff && uv run pytest tests -q` | Tests pass; a PostgreSQL-only migration test may be skipped when no PostgreSQL is available |
| Frontend behavior | `cd frontend/support-inbox && npm test -- --run` | All tests pass |
| Reproducible frontend build | `cd frontend/support-inbox && npm run build` | Typecheck and Vite build pass |
| Bundle secret scan | `grep -R -nE 'agno_pat_ | AGENTOS_PAT | JWT_VERIFICATION_KEY | JWT_JWKS_FILE' frontend/support-inbox/dist --exclude='*.map'` | No matches |
| Static checks | `cd support-inbox/bff && uv run ruff check app tests retention.py migrations && uv run mypy app retention.py` | Both pass |

A failed deterministic check blocks production preflight. Do not bypass a failing test by changing the legacy AgentOS app or its tests in this slice.

## Production preflight — operator-owned evidence

Record only status, timestamps, request IDs, and redacted references. Never record PATs, passwords, cookies, CSRF tokens, customer bodies, or raw upstream payloads.

- [ ] BFF configuration is complete: production runtime, database URL, AgentOS URL, exact frontend origin, secure cookie, session limits, and logging settings.
- [ ] Alembic head is applied to the dedicated `support_inbox` schema; migration and retention roles are separate from the runtime DML role.
- [ ] Approved operator account is provisioned through the administrative workflow; no public registration or recovery is enabled.
- [ ] AgentOS principal is exactly `sa:support-inbox-bff`; read/send scopes are independently verified; unrelated and under-scoped credentials are denied.
- [ ] TLS is valid for both public origins; CORS allows only the exact frontend origin with credentials.
- [ ] Health checks and alerts cover BFF availability, upstream 401/403, timeout/5xx, failed logins/lockouts, audit failures, cleanup failures, and schema-validation failures.
- [ ] Logs and audit records are confirmed redacted; no secret or customer body is retained.
- [ ] Legacy hosting is deployable from a known revision and operators know its fallback URL.
- [ ] Rollback owner, contacts, steps, and verification requests are documented for the cutover window.

### Railway topology and release references

Use one Railway project with separate `agent-os`, `support-inbox-bff`, and
`support-inbox-db` services. The BFF service root is `support-inbox/bff`; use
its checked-in `railway.json`, Dockerfile, `uvicorn app.main:app` start command,
and `/health` check. Reference the private AgentOS hostname with
`AGENTOS_BASE_URL=http://${{agent-os.RAILWAY_PRIVATE_DOMAIN}}:8000` and the
dedicated database with `DATABASE_URL=${{support-inbox-db.DATABASE_URL}}`.
These are deployment references, not values to paste into source control.

Required BFF secret name: `AGENTOS_PAT`. It must be the non-privileged
`sa:support-inbox-bff` credential with exactly `support_inbox:read` and
`support_inbox:send`. Required configuration names include `RUNTIME_ENV`,
`SUPPORT_ALLOWED_ORIGINS`, `SUPPORT_COOKIE_SECURE`, `SUPPORT_COOKIE_NAME`,
`SUPPORT_SESSION_IDLE_SECONDS`, `SUPPORT_SESSION_ABSOLUTE_SECONDS`, and
`SUPPORT_LOGIN_RATE_LIMIT`. Never record secret values, operator passwords,
cookies, CSRF values, or PATs.

The release operator runs `alembic upgrade head` from `support-inbox/bff` as a
controlled migration job using the migration role, confirms the `support_inbox`
head, and only then starts the BFF runtime role. The BFF must not migrate on
startup. Read-only smoke checks and rollback readiness precede any send.

**Preflight gate:** any unchecked item keeps external traffic disabled and legacy hosting active.

## Read-only-first observation

Run these checks against the deployed external frontend and BFF before any mutation:

- [ ] Frontend HTML and a generated asset return successful responses over HTTPS.
- [ ] Browser network trace contains requests only to the configured BFF origin, never the AgentOS origin.
- [ ] Unauthenticated session/read requests return the expected `401` without leaking data.
- [ ] The approved operator can log in and read a known synthetic or approved-safe thread DTO.
- [ ] Unrelated credentials and missing read scope are denied; responses contain no private execution fields.
- [ ] Request IDs, latency, upstream status, and audit outcomes are observable without secrets.
- [ ] Observation window remains healthy while the legacy inbox stays available.

Do not test a mutation while any read-only item is unchecked. The observation
record includes timestamp, deploy revision, endpoint, status, latency, and
request ID only.

## Controlled-send gate

A live send is **not** part of this repository apply phase. An authorized operator may run it only after read-only observation passes:

- [ ] Target is explicitly approved, deterministic, non-customer, and recorded by name (for example, a controlled test sink).
- [ ] Exactly one upstream attempt is used; automatic retry and deduplication remain disabled until idempotency is approved.
- [ ] A unique auditable request ID is captured before the request.
- [ ] Result and BFF audit record are confirmed without recording message content or credentials.

The send gate is a single explicit approval, not an automated health check. It
must be disabled when the deterministic sink, request ID, one-attempt behavior,
or audit confirmation cannot be proved. No retry, queue replay, or implicit
deduplication is permitted before an idempotency contract is approved.

If any condition is unavailable, leave the send unchecked and do not claim cutover readiness.

## Rollback rehearsal and exit criteria

Before legacy removal, rehearse without deleting data:

1. Disable external routing.
2. Confirm the legacy SPA serves the support workflow.
3. Independently identify BFF/frontend revert points.
4. Confirm the PAT can be revoked without weakening AgentOS authorization.
5. Confirm operator and audit data remain intact.
6. Re-enable only after health and read-only checks pass.

Keep the legacy SPA until the complete preflight, read-only observation window,
controlled-send decision, operator success, BFF-only browser trace, and
rollback rehearsal are recorded. On any failure, disable external routing
first, revert BFF or Pages independently, revoke the PAT if exposure is
suspected, and preserve operator/audit data. Legacy removal is a separate
approved change and is not a consequence of green repository tests.

Legacy static hosting may be removed only when preflight, read-only observation, controlled-send safety (or an explicitly approved reason it is not yet required), rollback rehearsal, operator success, and browser BFF-only traffic are all evidenced. Task 5.2 remains out of scope until then.
