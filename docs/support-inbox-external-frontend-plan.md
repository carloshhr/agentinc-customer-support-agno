# External Support Inbox Deployment Plan

This plan moves the Support Inbox user interface out of AgentOS while preserving a narrow, authenticated boundary around support data and actions. The target architecture serves the static React application from Cloudflare Pages, runs a dedicated Backend for Frontend (BFF) on Railway, and keeps AgentOS and PostgreSQL on Railway. A separate staging environment is intentionally omitted; production readiness is established through deterministic local/CI checks, explicit preflight gates, read-only-first smoke checks, and a reversible cutover.

The BFF is the only service allowed to call the Support Inbox API. Operators authenticate to the BFF with a username and password. The BFF keeps operator sessions in PostgreSQL, audits operator actions, and calls AgentOS with one scoped service-account Personal Access Token (PAT). AgentOS therefore records BFF-originated operations as the Support Inbox service; operator-level attribution remains in the BFF audit log.

## Decision Summary

| Area | Decision |
| --- | --- |
| Frontend hosting | Cloudflare Pages, deployed independently from AgentOS |
| Browser API | Dedicated Support Inbox BFF on Railway |
| AgentOS hosting | Existing Railway `agent-os` service |
| Database | Dedicated Railway PostgreSQL service, with application-owned operator tables |
| Operator authentication | Username and password verified by the BFF |
| Password storage | Argon2id hashes only; never plaintext or reversible encryption |
| Browser session | Opaque, random session token in a secure HttpOnly cookie |
| BFF to AgentOS authentication | One narrowly scoped AgentOS service-account PAT |
| AgentOS attribution | All calls appear as the Support Inbox service account |
| Operator attribution | Application-owned append-only BFF audit records |
| Browser access to AgentOS | Prohibited; the browser calls only the BFF |
| Cross-origin policy | BFF allows only the exact production and approved preview frontend origins |
| Existing `/api/support/*` routes | Retained initially, then made reachable only by the BFF credential and deployment network policy |
| Existing FastAPI static hosting | Removed only after the external deployment passes production smoke checks |

## Why This Topology

The existing `frontend/support-inbox/src/api.ts` uses relative `/api/support/*` requests and sends no authentication credential. That works only when the compiled SPA and API share an origin in local development. It is not a safe production contract for a frontend hosted by Cloudflare.

AgentOS already enables authorization outside development through `authorization=runtime_env != "dev"` in `app/main.py`. Its authentication middleware protects REST, MCP, and other AgentOS surfaces. Adding an unrelated opaque operator cookie directly to the same process would require custom route exclusions and a second security model inside the AgentOS authentication boundary. That is possible, but it is more difficult to reason about and easier to misconfigure.

A separate BFF keeps the boundaries explicit:

1. The browser proves an operator session only to the BFF.
2. The BFF exposes only inbox-specific DTOs and operations.
3. The AgentOS PAT never reaches JavaScript, Cloudflare Pages, browser storage, logs, or source control.
4. AgentOS retains its existing production authorization behavior.
5. Operator credentials live in application-owned tables, not internal Agno tables.
6. A compromise of the static frontend does not directly expose AgentOS credentials.

The official Agno guidance supports product frontends calling AgentOS through its REST API, service-account tokens for machine callers, JWT authentication for end users, and exact CORS origin allowlists. This plan deliberately uses the machine-caller path because operator identity is required only inside the Support Inbox, not inside AgentOS.

## Target Architecture

```text
Operator browser
    |
    | HTTPS
    | Cookie: support_session=<opaque token>
    v
Cloudflare Pages
    Support Inbox React/Vite SPA
    |
    | HTTPS fetch(..., credentials="include")
    v
Railway: support-inbox-bff
    /auth/login
    /auth/logout
    /auth/session
    /api/support/threads
    /api/support/threads/{session_id}
    /api/support/emails
    |
    | Authorization: Bearer agno_pat_...
    | Railway private network where supported
    v
Railway: agent-os
    Existing safe Support Inbox DTO/API boundary
    Existing Customer Support team
    |
    v
Railway PostgreSQL
    Agno-owned schemas and tables
    Application-owned support_operator_* tables
```

## Trust Boundaries

| Boundary | Trusted input | Required validation |
| --- | --- | --- |
| Browser to Cloudflare Pages | Static requests only | Standard Cloudflare asset delivery controls |
| Browser to BFF | Operator cookie and user input | Session lookup, CSRF, origin check, request validation, rate limits |
| BFF to AgentOS | Server-held PAT and normalized request | PAT scopes, AgentOS validation, support DTO allowlist |
| BFF to PostgreSQL | Parameterized application queries | Schema constraints, transaction boundaries, least-privilege DB user if available |
| AgentOS to PostgreSQL | Existing Agno runtime state | Existing AgentOS persistence controls |

The browser must never call the AgentOS public URL. CORS on AgentOS is not the browser integration mechanism in this design. Only the BFF needs browser CORS configuration.

## Repository Strategy

### Recommended End State

Create a separate private repository for the Support Inbox product surface:

```text
support-inbox/
├── frontend/
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── bff/
│   ├── app/
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
├── README.md
└── railway.json
```

The extraction should happen after the BFF contract is covered by tests. Moving files first would mix a security change, an API change, and a repository migration in one difficult-to-review operation.

### AgentOS Repository After Migration

This repository should retain:

- `app/support_inbox.py` or a smaller equivalent that exposes the safe BFF-facing API.
- The allow-listed DTO mapping from AgentOS sessions and runs.
- Customer Support team invocation.
- Tests proving private run, tool, reasoning, requirement, order, and product data cannot cross the API boundary.

This repository should eventually remove:

- `frontend/support-inbox/` after the external repository is authoritative.
- The `/support-inbox` redirect middleware in `app/main.py`.
- Static asset serving functions and `frontend_directory` from `app/support_inbox.py`.
- Docker assumptions related to bundled frontend assets.
- Documentation that directs production users to the FastAPI-served SPA.

Do not remove the current static frontend until the external deployment and rollback path are verified.

## Authentication Model

### Operator Account

An operator is an application identity owned by the Support Inbox, not an Agno user or service account.

Minimum fields:

| Field | Purpose |
| --- | --- |
| `id` | Stable UUID used in sessions and audit records |
| `username` | Normalized unique login name |
| `password_hash` | Argon2id encoded hash |
| `display_name` | Human-readable audit identity |
| `is_active` | Immediate account disable switch |
| `failed_login_count` | Rate-limit and lockout support |
| `locked_until` | Temporary lockout deadline |
| `password_changed_at` | Session revocation boundary |
| `last_login_at` | Operational visibility |
| `created_at` / `updated_at` | Lifecycle timestamps |

Usernames should be normalized consistently before comparison. Prefer lowercase Unicode-normalized values or restrict usernames to a documented ASCII format. Preserve the chosen normalization as a database uniqueness constraint.

### Password Requirements

- Hash passwords with Argon2id using a maintained password-hashing library.
- Store the complete encoded hash string, including salt and parameters.
- Never store plaintext passwords, password hints, reversible ciphertext, or shared default passwords.
- Use a minimum password length of 12 characters for manually managed operator accounts.
- Check submitted passwords in constant-time through the password-hashing library.
- Rehash on successful login when stored parameters are weaker than the current policy.
- Do not reveal whether a username exists.
- Provision the first operator through a one-time administration command, not a public registration route.
- Do not implement password recovery until there is a verified operator identity channel. Initially, use an authenticated administrative reset command.

### Browser Session

Use an opaque session token rather than a browser-readable JWT:

1. Generate at least 256 bits of cryptographically secure random data.
2. Send the raw token only in the login response cookie.
3. Store only a SHA-256 digest of the token in PostgreSQL.
4. Look up sessions by the digest on each authenticated request.
5. Bind the session to the operator ID and an absolute expiry.
6. Rotate the session token after login and any privilege-sensitive change.
7. Revoke the current session on logout.
8. Revoke all sessions created before `password_changed_at` after a password reset.

Production cookie attributes:

```text
HttpOnly
Secure
SameSite=None
Path=/
Domain omitted
```

`SameSite=None` is required when Cloudflare Pages and Railway use different sites. It also requires `Secure`. If production uses subdomains under the same registrable domain, for example `support.example.com` and `support-api.example.com`, evaluate `SameSite=Lax` after testing the exact browser behavior. Do not weaken the CSRF controls based only on SameSite behavior.

The cookie should have a short inactivity window and a bounded absolute lifetime. A reasonable initial policy is 30 minutes idle and 8 hours absolute, with both values configurable.

### PAT Model

Create one AgentOS service account named `support-inbox-bff`. Grant only the scopes required by the final AgentOS paths. Do not accept the default PAT scopes without reviewing them.

The PAT must:

- Exist only as a secret environment variable on the Railway BFF service.
- Never use a `VITE_*` variable.
- Never be stored in PostgreSQL, source control, frontend build output, test fixtures, or logs.
- Be redacted from exception reporting and HTTP client traces.
- Be revocable without rebuilding either application.
- Be rotated through a documented overlap procedure.

Because `/api/support/*` are custom routes, verify how the current Agno authentication middleware maps service-account permissions to them. Authentication and authorization are separate concerns: accepting the PAT is not sufficient if custom routes have no explicit scope policy. The implementation must add and test route-specific scope mappings or an equivalent BFF credential dependency before production.

Suggested logical permissions:

```text
support_inbox:read
support_inbox:send
```

Expected route mapping:

| Method and path | Required permission |
| --- | --- |
| `GET /api/support/threads` | `support_inbox:read` |
| `GET /api/support/threads/{session_id}` | `support_inbox:read` |
| `POST /api/support/emails` | `support_inbox:send` |

If AgentOS custom scope mappings cannot express the parameterized route safely in the pinned Agno version, add an explicit server-side authorization dependency that validates the authenticated service-account principal and denies every other principal. Do not leave the routes protected only by possession of any valid AgentOS credential.

## Database Design

Use application-owned tables with a clear prefix. Do not modify Agno-owned tables or rely on their undocumented shape.

### `support_operators`

```sql
CREATE TABLE support_operators (
    id UUID PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    password_changed_at TIMESTAMPTZ NOT NULL,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
```

The exact migration should use the repository's chosen migration mechanism rather than executing this illustrative SQL blindly.

### `support_operator_sessions`

```sql
CREATE TABLE support_operator_sessions (
    id UUID PRIMARY KEY,
    operator_id UUID NOT NULL REFERENCES support_operators(id) ON DELETE CASCADE,
    token_digest BYTEA NOT NULL UNIQUE,
    csrf_token_digest BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    idle_expires_at TIMESTAMPTZ NOT NULL,
    absolute_expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    user_agent TEXT,
    source_ip_hash BYTEA
);
```

Do not store raw session or CSRF tokens. Treat source IP and user-agent values as personal data. If they are not needed operationally, omit them. If retained, define a retention period.

### `support_operator_audit_log`

```sql
CREATE TABLE support_operator_audit_log (
    id UUID PRIMARY KEY,
    operator_id UUID REFERENCES support_operators(id),
    event_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    outcome TEXT NOT NULL,
    request_id TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);
```

Audit metadata must not include passwords, session cookies, CSRF tokens, PATs, complete email bodies, private model output, or raw AgentOS responses. For send operations, record identifiers, result status, and a content hash when needed; do not duplicate customer content without a retention requirement.

### Schema Ownership

Prefer one of these ownership models, in order:

1. A dedicated PostgreSQL schema and DB role for the BFF, with read/write access only to the operator tables.
2. Application-prefixed tables in the existing schema with a dedicated DB role.
3. Shared database credentials only for the first deployment, with a follow-up task to reduce privileges.

The BFF should not query Agno session/run tables directly. Support conversation data must continue through the safe DTO boundary in `app/support_inbox.py`.

## BFF API Contract

### Authentication Routes

#### `POST /auth/login`

Request:

```json
{
  "username": "operator-name",
  "password": "operator password"
}
```

Behavior:

- Require `Content-Type: application/json`.
- Validate bounded string lengths before hashing work.
- Apply IP and normalized-username rate limits.
- Return the same error for unknown users, invalid passwords, inactive users, and locked users.
- On success, reset failed-attempt state, create a session, set the cookie, and return the safe operator profile.
- Never return the session token in JSON.
- Set `Cache-Control: no-store`.

Responses:

- `200` with `{ "operator": { "id", "username", "display_name" }, "csrf_token": "..." }`
- `400` for malformed input
- `401` for failed authentication
- `429` for rate limiting

The CSRF token may be returned in JSON because it is not an authentication credential. Store it only in memory on the frontend, not local storage. Refreshing the page can call `/auth/session` for a new CSRF token.

#### `GET /auth/session`

- Validate the session cookie.
- Refresh the idle deadline with write-throttling to avoid one database update per request.
- Return the safe operator profile and a current CSRF token.
- Return `401` for absent, expired, revoked, or invalid sessions.
- Set `Cache-Control: no-store`.

#### `POST /auth/logout`

- Require a valid session and CSRF token.
- Revoke the server-side session.
- Expire the browser cookie using matching attributes.
- Return `204` whether the current session was already revoked or not.

### Support Proxy Routes

The browser-facing BFF can preserve the current route shapes to minimize frontend changes:

| Method | BFF path | AgentOS path | Behavior |
| --- | --- | --- | --- |
| `GET` | `/api/support/threads` | `/api/support/threads` | Forward safe list DTO |
| `GET` | `/api/support/threads/{session_id}` | `/api/support/threads/{session_id}` | Forward safe detail DTO |
| `POST` | `/api/support/emails` | `/api/support/emails` | Validate, audit, forward mutation |

For every proxy route, the BFF must:

- Require a valid operator session.
- Reject requests from unapproved origins when an `Origin` header is present.
- Require CSRF on state-changing methods.
- Build the AgentOS URL from a server-only environment variable.
- Add the PAT on the server.
- Set explicit connect, read, write, and pool timeouts.
- Never follow arbitrary redirects from AgentOS.
- Enforce maximum response sizes.
- Deserialize and validate the expected DTO instead of blindly relaying arbitrary JSON.
- Replace upstream errors with stable browser-safe errors.
- Preserve `202 approval_pending` behavior for support sends.
- Generate and propagate a request ID without forwarding sensitive browser headers.

Do not implement the BFF as a generic path proxy. A generic `/agentos/*` forwarding route would expose the full AgentOS API and defeat the purpose of the BFF.

## CSRF Protection

Cross-origin cookies require explicit CSRF protection.

For `POST`, `PUT`, `PATCH`, and `DELETE`:

1. Require an exact allowed `Origin` value.
2. Require an `X-CSRF-Token` header.
3. Compare its digest against the token associated with the operator session.
4. Reject missing or mismatched tokens with `403`.
5. Do not accept state-changing requests through `GET`.

The custom header forces a CORS preflight, which the BFF must answer only for allowed origins. Origin validation and CSRF tokens are complementary; keep both.

## CORS Policy

Configure CORS on the BFF, not broadly on AgentOS.

Production policy:

```text
Access-Control-Allow-Origin: https://support.example.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-CSRF-Token, X-Request-ID
Vary: Origin
```

Rules:

- Never use `Access-Control-Allow-Origin: *` with credentials.
- Keep the production origin in an environment variable validated at startup.
- Treat Cloudflare preview deployments as separate origins. Do not allow `*.pages.dev` in production.
- Use a small explicit preview allowlist or deploy previews against a non-production BFF and database.
- Do not forward browser `Authorization`, cookie, or Cloudflare-specific headers to AgentOS.

## Frontend Refactor

### Build Configuration

The current Vite configuration uses `base: '/support-inbox/'` because FastAPI serves the SPA beneath that path. For a dedicated Cloudflare Pages project, choose one canonical URL:

- Root deployment: set `base: '/'` and publish at `https://support.example.com/`.
- Subpath deployment: retain `/support-inbox/` only if Cloudflare routing explicitly requires it.

Root deployment is simpler and is recommended.

### Runtime Configuration

Set only the public BFF origin in the frontend build:

```text
VITE_SUPPORT_API_ORIGIN=https://support-api.example.com
```

This is not a secret. Validate it during application startup and fail visibly when missing in production. Never put the PAT, database credentials, password pepper, session secret, or AgentOS private URL in a `VITE_*` variable.

### API Client Changes

Refactor `frontend/support-inbox/src/api.ts` to:

- Prefix requests with the configured BFF origin.
- Set `credentials: 'include'` on every request.
- Add `X-CSRF-Token` only for state-changing calls.
- Handle `401` as an expired or absent operator session.
- Handle `403` separately from generic upstream failure.
- Preserve `202` as a successful pending response.
- Avoid retries for `POST /api/support/emails` unless an idempotency contract exists.
- Parse and validate error envelopes without exposing backend internals.

### Authentication UI

Add these application states:

- Initial session check.
- Signed-out login form.
- Login in progress.
- Invalid credentials without user enumeration.
- Rate limited or temporarily locked.
- Signed-in operator identity.
- Session expired.
- Logout in progress.

Do not render the inbox or issue support API requests until `/auth/session` succeeds.

Keep password values in component state only. Disable browser persistence and clear the field after every completed attempt.

### Existing Safety Properties

Preserve the current frontend protections:

- Render model and customer content as text.
- Do not introduce `dangerouslySetInnerHTML` or `innerHTML`.
- Keep the safe normalized JSON view rather than raw AgentOS responses.
- Preserve mobile back navigation.
- Preserve empty, loading, failure, sending, and approval-pending states.
- Preserve the selected support session ID when replying.

## BFF Implementation

Use a small FastAPI application because the existing team already operates Python/FastAPI and the DTO boundary is Python-based. Keep the BFF independent from Agno internals: it should know only HTTP contracts.

Suggested modules:

```text
bff/app/
├── main.py             # FastAPI construction, CORS, lifespan
├── settings.py         # Validated environment configuration
├── database.py         # Engine/session lifecycle
├── models.py           # Operator, session, audit persistence
├── schemas.py          # Browser and AgentOS DTOs
├── security.py         # Argon2, token digest, cookies, CSRF
├── auth.py             # Login/logout/session routes
├── support.py          # Explicit support proxy routes
├── agentos_client.py   # Narrow typed HTTP client
└── audit.py            # Append-only audit writer
```

Implementation constraints:

- Use one shared HTTP client pool per process.
- Use one managed SQLAlchemy engine per process.
- Validate required settings at startup.
- Fail startup when the PAT, AgentOS URL, database URL, allowed origins, or secure-cookie setting is invalid in production.
- Avoid background audit writes that can disappear on process termination. Write the audit record in the request transaction or use a reliable outbox.
- Keep login and proxy request bodies bounded at the server and reverse-proxy layers.
- Return JSON errors with stable codes and a request ID.

## AgentOS Changes

### Keep the Safe DTO Boundary

The mapping in `app/support_inbox.py` currently excludes:

- Member responses.
- Tool calls and arguments.
- Reasoning content.
- Approval requirement payloads.
- Private order and product identifiers.
- Sessions belonging to other teams.
- Malformed or untyped runs.

These properties are security controls, not presentation details. Preserve their tests throughout the migration.

### Add Explicit BFF Authorization

Verify the pinned Agno version's custom route scope behavior with a production-mode integration test. Then implement one of these, preferring the first supported option:

1. AgentOS custom scope mapping requiring `support_inbox:read` and `support_inbox:send` for the three routes.
2. A route dependency that accepts only the `support-inbox-bff` authenticated service-account principal.

The test matrix must prove:

| Caller | Expected result |
| --- | --- |
| No credential | `401` |
| Invalid credential | `401` |
| Valid unrelated PAT | `403` |
| Support BFF PAT without read scope | `403` on reads |
| Support BFF PAT without send scope | `403` on send |
| Properly scoped Support BFF PAT | Expected DTO/status |

Do not disable AgentOS authorization, set `RUNTIME_ENV=dev` in Railway, or make these paths globally excluded from authentication.

#### Support Inbox PAT Provisioning

The pinned AgentOS 3.0.0 runtime does not pass custom route mappings through
`AgentOS` construction. The Support Inbox therefore uses a server-side
principal-plus-scope dependency for these custom routes, after AgentOS verifies
the PAT. The only accepted principal is `sa:support-inbox-bff`:

| Route | Required scope |
| --- | --- |
| `GET /api/support/threads` | `support_inbox:read` |
| `GET /api/support/threads/{session_id}` | `support_inbox:read` |
| `POST /api/support/emails` | `support_inbox:send` |

Provision the account from an authenticated AgentOS administrator. The token
is printed only once; store it only in the BFF's server-side secret manager:

```bash
agno tokens create support-inbox-bff \
  --scopes support_inbox:read \
  --scopes support_inbox:send \
  --expires 90d
```

Do not use `--privileged`; these support scopes are not administrative scopes.
Never paste the token into this repository, a `VITE_*` variable, a browser,
an audit record, or logs. Confirm the account metadata with `agno tokens list`
without recording token material.

To rotate, create a replacement account with the same reviewed scopes, update
the BFF secret, restart the BFF, verify read and controlled-send checks, then
revoke the old account with `agno tokens revoke <name>` (or the authenticated
`DELETE /service-accounts/{id}` endpoint). To revoke during an incident, revoke
the account immediately and disable the external route; do not weaken AgentOS
authorization or remove the legacy inbox. Revocation is one-way, and cached
verification on other workers may persist only for the configured service
account cache TTL.

### Remove Static Serving Last

After the external frontend is stable:

- Remove `support_inbox_frontend()` and `support_inbox_asset()`.
- Remove `_frontend_asset()` and `frontend_directory`.
- Remove `serve_support_inbox` middleware from `app/main.py`.
- Remove the route-order workaround only after proving `/api/support/*` still resolve correctly.
- Remove `frontend/support-inbox` from this repository after preserving history in the new repository.
- Update tests to remove static asset expectations while retaining API safety and authorization coverage.

## Environment Variables

### Cloudflare Pages

| Variable | Visibility | Purpose |
|---|---|---|
| `VITE_SUPPORT_API_ORIGIN` | Public | HTTPS origin of the BFF |

### Railway BFF

| Variable | Secret | Purpose |
| --- | --- | --- |
| `RUNTIME_ENV` | No | `prd` enables production validation |
| `DATABASE_URL` or DB parts | Yes | PostgreSQL connection for operator state |
| `AGENTOS_BASE_URL` | No, but server-only | Prefer Railway private service URL |
| `AGENTOS_PAT` | Yes | Scoped `support-inbox-bff` credential |
| `SUPPORT_ALLOWED_ORIGINS` | No | Exact comma-separated frontend origins |
| `SUPPORT_COOKIE_NAME` | No | Production cookie name |
| `SUPPORT_COOKIE_SECURE` | No | Must be true in production |
| `SUPPORT_SESSION_IDLE_SECONDS` | No | Idle session limit |
| `SUPPORT_SESSION_ABSOLUTE_SECONDS` | No | Absolute session limit |
| `SUPPORT_LOGIN_RATE_LIMIT` | No | Login attempt policy |
| `SUPPORT_PASSWORD_PEPPER` | Yes, optional | Additional server-side secret if adopted |

If a password pepper is used, document its backup and rotation procedure. Losing it invalidates every password; rotating it requires a staged strategy. Argon2id with unique salts remains mandatory whether or not a pepper is used.

### Railway AgentOS

Retain the existing production variables, including:

- `RUNTIME_ENV=prd`
- `JWT_VERIFICATION_KEY` or `JWT_JWKS_FILE`
- `OPENAI_API_KEY`
- Database variables
- `AGENTOS_URL`

The Support Inbox PAT is not an AgentOS environment variable. It is created and stored by AgentOS but injected only into the BFF service.

## Network Controls

- The production topology is one Railway project containing `agent-os`,
  `support-inbox-bff`, and a dedicated PostgreSQL service (reference name
  `support-inbox-db`). Configure `AGENTOS_BASE_URL` from
  `http://${{agent-os.RAILWAY_PRIVATE_DOMAIN}}:8000`; use the public AgentOS
  domain only if private networking is unavailable and that exception is reviewed.
- Configure `DATABASE_URL` from `${{support-inbox-db.DATABASE_URL}}`. This
  database is not shared with AgentOS and is never reachable from Cloudflare
  Pages or operator browsers.
- Railway service root/build/start configuration is checked in at
  `support-inbox/bff/railway.json`: root `support-inbox/bff`, Dockerfile
  `Dockerfile`, process `uvicorn app.main:app` on port 8000, and health check
  `/health`.
- Keep the public AgentOS domain because AgentOS UI, MCP OAuth, webhooks, or other interfaces may need it.
- Do not rely on private networking as authentication; the PAT remains required.
- Configure trusted host/origin controls where supported.
- Permit only HTTPS public traffic.
- Keep PostgreSQL private and inaccessible from Cloudflare Pages or operator browsers.
- If the BFF and AgentOS cannot communicate through Railway private DNS for a required route, use the public HTTPS origin with the same PAT and strict outbound destination configuration.

## Logging and Observability

Every BFF request should carry a generated request ID.

Log:

- Request ID.
- Route template and method.
- Response status.
- Duration.
- Authenticated operator ID when present.
- AgentOS upstream status and duration.
- Audit event outcome.

Never log:

- Passwords or password hashes.
- Cookies or session tokens.
- CSRF tokens.
- PATs or Authorization headers.
- Full customer email bodies.
- Raw AgentOS run payloads.

Add operational signals for:

- Repeated failed logins.
- Locked operator accounts.
- AgentOS `401` or `403` responses, which may indicate PAT expiry or scope drift.
- AgentOS timeouts and `5xx` responses.
- Session table growth and cleanup failures.
- Audit write failures.
- Unexpected response-schema validation failures.

For the cutover window, alert on BFF health-check failures, upstream 401/403,
timeouts and 5xx responses, failed logins/lockouts, audit-write failures,
cleanup failures, and migration/schema validation failures. Correlate alerts
with the BFF request ID and Railway deploy revision; never attach request
bodies, cookies, PATs, or raw upstream payloads.

## Session and Audit Maintenance

Run periodic deterministic cleanup for:

- Expired sessions.
- Revoked sessions older than the retention window.
- Login-attempt state no longer needed.
- Audit records past the agreed retention period.

Define retention before production. A reasonable starting point is 30 days for session rows and 90 days for security audit events, subject to business and regulatory requirements.

Cleanup must not run through an LLM or AgentOS agent. Use a deterministic scheduled job or database maintenance task.

## Testing Strategy

### BFF Unit Tests

- Username normalization and uniqueness.
- Argon2 hash and verification behavior.
- Rehash-on-login behavior.
- Session token generation and digest storage.
- Idle and absolute expiry.
- Revocation and logout idempotency.
- CSRF token verification.
- Cookie attributes in production.
- Origin allowlist matching with no suffix or wildcard bypass.
- Login response indistinguishability.
- Lockout and rate-limit boundaries.
- Audit redaction.
- AgentOS error translation.

### BFF Integration Tests

- Login creates a persisted session and secure cookie.
- Invalid login creates no session.
- `/auth/session` rejects expired and revoked sessions.
- Support routes reject requests without a session.
- State-changing routes reject missing or invalid CSRF tokens.
- BFF adds the PAT upstream but never returns it downstream.
- Unexpected AgentOS schemas fail closed.
- AgentOS timeouts return a stable gateway error.
- `202 approval_pending` remains intact.
- Audit rows identify the operator and request outcome.

Use a fake AgentOS HTTP server in most BFF tests. Keep real AgentOS integration tests focused and deterministic.

### AgentOS Tests

Retain current DTO tests and add production authorization tests for the Support Inbox PAT boundary. Tests must inspect responses for forbidden private fields and verify unrelated valid AgentOS credentials cannot use Support Inbox routes.

### Frontend Tests

- Login, logout, and session restoration.
- No support request before authentication succeeds.
- `credentials: 'include'` on every API request.
- CSRF header on sends, not on reads.
- `401` returns the UI to signed-out state.
- `403`, `429`, and upstream failures have distinct safe messages.
- Password is not persisted.
- Existing hostile-content escaping remains intact.
- Existing thread, compose, pending, and mobile behavior remains intact.

### End-to-End Tests

Use local/CI services and synthetic data; do not provision a separate staging stack:

1. Open the locally built frontend with its local BFF.
2. Confirm inbox data is unavailable before login.
3. Log in as a seeded test operator.
4. List and open a known support thread.
5. Send a deterministic test email through a controlled test component.
6. Confirm the BFF audit row names the operator.
7. Confirm AgentOS attributes the call to `sa:support-inbox-bff`.
8. Log out and confirm subsequent API calls return `401`.

Do not run model-backed send smoke tests against production customer data. Use a deterministic test target or an explicitly gated fixture.

## Deployment Plan

### Railway production release boundary

The BFF is a separate Railway service in the same project as AgentOS. The
repository defines the shape only; an authorized operator must create or
select services and enter values in Railway. Required configuration names are
`RUNTIME_ENV`, `DATABASE_URL`, `AGENTOS_BASE_URL`,
`SUPPORT_ALLOWED_ORIGINS`, `SUPPORT_COOKIE_SECURE`, `SUPPORT_COOKIE_NAME`,
`SUPPORT_SESSION_IDLE_SECONDS`, `SUPPORT_SESSION_ABSOLUTE_SECONDS`, and
`SUPPORT_LOGIN_RATE_LIMIT`. The required secret is `AGENTOS_PAT`; it belongs
only in the BFF secret store. Do not add a password pepper: Argon2id is used
without one. The PAT must be limited to `sa:support-inbox-bff` with only
`support_inbox:read` and `support_inbox:send`, and never copied to AgentOS
variables or `VITE_*` variables.

Run migrations as a controlled release step, not from BFF startup:

```text
1. Confirm the dedicated database reference resolves to support-inbox-db.
2. Confirm the provider recovery point before schema changes.
3. Run `alembic upgrade head` from `support-inbox/bff` with the migration role.
4. Verify the `support_inbox` schema and Alembic head; do not alter Agno schemas.
5. Start/restart the BFF with the runtime DML-only role and verify `/health`.
```

The migration role owns upgrades, downgrade rehearsal, and retention cleanup;
the runtime role does not. Never run `downgrade` as an incident shortcut:
retain operator/audit data and roll back service routing first.

The canonical frontend origin is Cloudflare Pages and the browser API origin is
the BFF only. Set `VITE_SUPPORT_API_ORIGIN` to the approved public BFF HTTPS
origin; never set it to AgentOS, a Railway private hostname, or a wildcard.
Preview deployments are off. If enabled later, they require isolated origin,
PAT, database, and BFF configuration.

### Phase 1: Pin the Existing Contract

- [ ] Record the current three Support Inbox request and response schemas.
- [ ] Preserve all existing DTO leakage tests.
- [ ] Add explicit production-mode authorization tests.
- [ ] Decide and implement custom route scope enforcement.
- [ ] Create the scoped `support-inbox-bff` service account.
- [ ] Document PAT creation, rotation, and revocation commands without recording the token.

Exit condition: only the intended BFF service account can call `/api/support/*` in production.

### Phase 2: Build the BFF

- [ ] Scaffold the independent FastAPI service.
- [ ] Add validated settings and startup failure checks.
- [ ] Add migrations for operator, session, and audit tables.
- [ ] Implement Argon2id password handling.
- [ ] Implement login, current-session, and logout routes.
- [ ] Implement session expiry and cleanup.
- [ ] Implement exact-origin CORS and CSRF protection.
- [ ] Implement the narrow typed AgentOS client.
- [ ] Implement the three explicit support proxy routes.
- [ ] Add audit records and redacted structured logging.
- [ ] Add unit and integration coverage.

Exit condition: the BFF test suite proves authentication, authorization, CSRF, DTO validation, and PAT secrecy.

### Phase 3: Refactor the Frontend In Place

- [ ] Add public BFF origin configuration.
- [ ] Add login/session/logout UI states.
- [ ] Add credentialed fetch and in-memory CSRF handling.
- [ ] Add explicit `401`, `403`, `429`, and gateway error handling.
- [ ] Update tests without weakening existing safety coverage.
- [ ] Change Vite base path to `/` for the target Cloudflare domain.
- [ ] Verify the production build contains no secret or AgentOS PAT.

Exit condition: the frontend works against a local BFF and never calls AgentOS directly; production validation follows the waived-staging gates below.

### Phase 4: Extract the Frontend and BFF

- [ ] Create the private Support Inbox repository.
- [ ] Move the frontend source with history where practical.
- [ ] Move the BFF and its tests.
- [ ] Establish independent CI for frontend and BFF.
- [ ] Keep the AgentOS DTO API in this repository.
- [ ] Update ownership and deployment documentation.

Exit condition: the new repository builds both deployables without reading files from this repository.

### Phase 5: Deploy Staging — intentionally waived

- [x] Waive a separate staging environment by explicit decision; do not provision staging services, credentials, or data.
- [x] Replace staging validation with local/CI BFF, frontend, AgentOS authorization, migration, bundle-secret, and synthetic end-to-end checks.
- [ ] Complete the production preflight below before switching any external traffic.

Exit condition: deterministic checks pass and production preflight confirms the deployment is safe to enter through read-only smoke checks; this is not a deployment claim.

### Phase 6: Production Cutover

- [ ] Complete a written preflight: production configuration and migrations, operator provisioning, exact CORS/TLS, PAT principal/scopes, logging/redaction, health checks, alerting, and rollback contacts/procedure.
- [ ] Confirm local/CI synthetic checks cover login, session expiry, lockout, reads, controlled send, audit, logout, denial paths, and browser-direct-call rejection.
- [ ] Deploy the production BFF with production cookie and timeout settings.
- [ ] Create the production operator through the administration command.
- [ ] Deploy the production Cloudflare Pages site.
- [ ] Configure the custom frontend and BFF domains.
- [ ] Verify TLS and exact CORS headers.
- [ ] Run read-only production smoke checks first.
- [ ] Run one controlled send check only if an explicitly safe deterministic target exists; otherwise leave send unverified and do not claim cutover completeness.
- [ ] Monitor BFF authorization and upstream errors.
- [ ] Keep the old FastAPI-served SPA available during the observation window.
- [ ] Rehearse rollback: disable external routing, independently revert BFF/frontend, revoke the PAT if compromise is suspected, and restore the legacy SPA without weakening AgentOS authorization or dropping operator/audit data.

Exit condition: read-only production smoke checks pass, any controlled send is safe and auditable, rollback is rehearsed, operators use the external frontend successfully, and no browser request goes directly to AgentOS.

### Phase 7: Remove Legacy Static Hosting

- [ ] Announce and complete the cutover window.
- [ ] Remove static frontend serving from AgentOS.
- [ ] Remove `frontend/support-inbox` from this repository.
- [ ] Remove obsolete Docker and documentation behavior.
- [ ] Keep or redirect `/support-inbox` only if a documented compatibility need exists.
- [ ] Re-run AgentOS validation, Support Inbox API tests, BFF tests, and frontend tests.

Exit condition: each service has one clear responsibility and no stale frontend build ships inside AgentOS.

## CI/CD Gates

### AgentOS

```bash
./scripts/validate.sh
pytest tests/test_support_inbox.py
```

Add the production authorization integration test to this gate.

### Frontend

```bash
npm ci
npm test
npm run build
```

Also scan the generated bundle for forbidden secret prefixes such as `agno_pat_` and known environment variable names. This scan supplements correct secret handling; it does not replace it.

### BFF

The new repository should provide equivalent deterministic commands for:

- Formatting and linting.
- Static type checking.
- Unit and integration tests.
- Migration validation.
- Container build.
- Dependency vulnerability review.

Do not deploy when any security-boundary test fails.

## PAT Rotation Procedure

1. Create a replacement service-account PAT with identical reviewed scopes.
2. Update the BFF Railway secret.
3. Redeploy or restart the BFF.
4. Verify authenticated read and controlled send behavior.
5. Confirm logs show no `401` or `403` from AgentOS.
6. Revoke the old PAT.
7. Record the rotation event without recording either token.

If AgentOS supports multiple active tokens for the same service account, use that overlap. Otherwise create a temporary second service account with the same narrow policy and remove it after rotation.

## Rollback Plan

### Before Legacy Removal

- Keep the current FastAPI-served SPA deployable.
- Keep AgentOS DTO routes unchanged.
- If the external deployment fails, disable the Cloudflare route and direct operators to the prior same-origin URL.
- Revoke the BFF PAT if the BFF is suspected of compromise.
- Do not disable AgentOS authorization to restore availability.

### After Legacy Removal

- Roll back the AgentOS commit that removed static hosting only if the old build artifact is known and verified.
- Prefer rolling back the frontend or BFF independently because their deploys are separate.
- Preserve database migrations unless rollback safety has been explicitly tested; disabling the new service is safer than dropping operator or audit tables.

## Security Review Checklist

- [ ] Browser network traces contain no PAT or AgentOS credential.
- [ ] Frontend build output contains no secret values.
- [ ] Passwords are Argon2id hashes with reviewed parameters.
- [ ] Login errors do not enumerate users.
- [ ] Login is rate limited by source and account key.
- [ ] Session cookies are HttpOnly and Secure.
- [ ] Cross-site cookie behavior is verified in target browsers.
- [ ] CSRF is enforced on every mutation.
- [ ] CORS uses exact origins and credentials.
- [ ] Preview deployments cannot call production by wildcard.
- [ ] Support routes reject unrelated AgentOS credentials.
- [ ] PAT scopes are minimal and tested.
- [ ] The BFF is not a generic reverse proxy.
- [ ] DTO validation fails closed on unexpected AgentOS responses.
- [ ] Logs and audits exclude secrets and customer bodies.
- [ ] Operator disable and session revocation take effect immediately.
- [ ] PAT and password reset procedures are documented and tested.
- [ ] PostgreSQL is not publicly reachable from the browser.
- [ ] AgentOS remains authenticated in production.

## Acceptance Criteria

The migration is complete only when all of the following are true:

- The Support Inbox frontend is deployed independently on Cloudflare Pages.
- Operators must authenticate with application-managed username and password credentials.
- Passwords are stored only as Argon2id hashes in application-owned PostgreSQL tables.
- The browser receives only an opaque secure session cookie and a non-secret CSRF token.
- The browser communicates only with the BFF.
- The BFF communicates with AgentOS using one scoped service-account PAT.
- The PAT is absent from JavaScript, browser storage, browser traffic, logs, and database rows.
- AgentOS rejects unauthenticated, invalid, and unrelated credentials on Support Inbox routes.
- The BFF validates AgentOS responses against the safe DTO contract.
- Support sends are protected by session validation, exact origin checks, CSRF, validation, rate limits, and auditing.
- Operator actions are attributable in the BFF audit log.
- AgentOS actions are attributable to the Support Inbox service account.
- Existing private AgentOS execution data remains excluded from browser responses.
- Frontend, BFF, AgentOS, and end-to-end test suites pass.
- The deployment has a tested PAT rotation and rollback procedure.
- Legacy FastAPI static serving is removed only after successful production observation.

## Out of Scope

- Per-operator AgentOS identity or scopes.
- External identity providers such as WorkOS, Auth0, Clerk, or Cloudflare Access.
- Public operator registration.
- Self-service password recovery.
- Customer-facing Support Inbox access.
- Approval or rejection controls in the Support Inbox.
- A generic browser client for all AgentOS endpoints.
- Disabling AgentOS production authorization.
- Storing a PAT or JWT in browser local storage.
- Querying Agno persistence tables directly from the BFF.

## Phase 4/5 Evidence Ledger

This ledger is repository-local evidence only. It does not authorize deployment, credential changes, live traffic switching, live sends, or legacy cleanup.

### Verified compensating checks

- [x] BFF security, proxy, audit, and application integration tests pass locally (`30 passed, 1 skipped`).
- [x] Frontend tests pass locally (`16 passed`) and the TypeScript/Vite production build succeeds.
- [x] Generated frontend output contains none of the forbidden PAT/JWT prefixes or variable names.
- [x] AgentOS support-inbox test suite is fully green; legacy hosting rewrites root-built asset references to the `/support-inbox/` mount without changing the external build output.
- [ ] PostgreSQL-backed migration validation is evidenced in an environment with PostgreSQL available.

### Production-only gates still requiring an authorized operator

- [ ] Production configuration, migration head, operator provisioning, exact CORS/TLS, PAT principal/scopes, logging/redaction, health checks, and alerting are reviewed.
- [ ] Read-only production smoke checks pass before any send is attempted.
- [ ] Controlled send uses an explicitly safe deterministic target, one upstream attempt, no retry/deduplication, and an auditable request ID.
- [ ] Rollback rehearsal proves external routing can be disabled, legacy hosting remains deployable, BFF/frontend can be reverted independently, and PAT revocation does not weaken AgentOS authorization or remove operator/audit data.

**Current boundary:** repository-local readiness evidence is green except PostgreSQL-backed migration validation. Task 5.1 remains incomplete because production preflight, read-only smoke checks, controlled-send safety, and rollback rehearsal require authorized production operators. Task 5.2 must not start. Legacy hosting remains deployable.

## References

- Agno: [Serve as an API](https://docs.agno.com/use-cases/product-agents/serve-as-an-api)
- Agno: [Using the API](https://docs.agno.com/agent-os/using-the-api)
- Agno: [Security and authentication](https://docs.agno.com/agent-os/security/overview)
- Agno: [Authorization](https://docs.agno.com/agent-os/security/authorization/overview)
- Agno: [Service accounts](https://docs.agno.com/agent-os/security/authorization/service-accounts)
- Agno: [Authentication middleware](https://docs.agno.com/agent-os/middleware/jwt)
- Current safe DTO boundary: `app/support_inbox.py`
- Current AgentOS construction: `app/main.py`
- Current frontend API client: `frontend/support-inbox/src/api.ts`
- Current frontend tests: `frontend/support-inbox/src/App.test.tsx`
- Current backend tests: `tests/test_support_inbox.py`
