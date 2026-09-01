# Design: Customer Support Inbox

## Technical Approach

Reconcile uncommitted code against authoritative `docs/customer-support-inbox-plan.md`. Map private AgentOS sessions/runs to explicit DTOs for three allow-listed routes and serve the Vite build at `/support-inbox/`. No schema/topology change.

## Architecture Decisions

| Decision | Options / trade-off | Decision and rationale |
|---|---|---|
| Browser boundary | Raw runs leak internals; a projection adds schema/write complexity. | Validate `CustomerEmail` plus `CustomerEmailReply`, then emit allow-listed DTOs from `customer-support` sessions/runs. |
| Run decoding | `isinstance(TeamRunOutput)` can omit deserialized records; raw fallback leaks data. | Normalize typed runs, skip malformed/legacy records, and prove PostgreSQL reloading. |
| Route order | AgentOS has a root UI catch-all; broad list mutation is brittle. | Put `/api/support/*` routes ahead of that mount. Narrow middleware handles `/support-inbox`, `/support-inbox/`, and `/support-inbox/assets/*`; every other request delegates unchanged. |
| Approval/idempotency | Requirements or resume controls leak privilege; dedupe needs durable state. | Pauses return only `202 {session_id, run_id, status}`. The UI has no retry/continuation control, disables in-flight sends, and generates bounded IDs. Manual duplicate POSTs remain a documented local-only limitation. |
| Packaging | A Node service expands deployment; the image has no Node build stage. | Ship freshly rebuilt `dist/` in the Python image. Require `npm ci && npm run build`; ignore Node installs and TypeScript metadata. |

## Data Flow

```text
SPA -- GET list/detail --> typed mapper --> Postgres customer-support sessions/runs
SPA -- POST email ------> CustomerSupportTeam(session_id=thread_id) --> persisted run
SPA <-- ThreadDetail or safe 202 pending -- API
```

The mapper filters `team_id="customer-support"`, orders by persisted time, emits inbound then completed outbound messages, and derives `completed`, `approval_pending`, or `incomplete`. Summaries omit body/run IDs. Member output, tools/traces, reasoning, requirements, approval details, and exceptions never cross the DTO boundary. `support_interaction` remains analytics-only.

## File Changes

| File | Action | Description |
|---|---|---|
| `app/support_inbox.py` | Modify | Normalize runs; harden DTO, error/status, and asset path handling. |
| `app/main.py` | Modify | Make support API precedence explicit; retain narrow static middleware before AgentOS UI. |
| `tests/test_support_inbox.py` | Modify | Add mapper, persistence, API, pending, static-order, and field-leak RED tests. |
| `frontend/support-inbox/src/{api,App}.tsx`, `styles.css`, `*.test.tsx` | Modify | Typed client; responsive list/detail, compose, pending/loading/error, two safe tabs. |
| `frontend/support-inbox/{package.json,package-lock.json,vite.config.ts,dist/**}` | Modify | Reconcile pinned toolchain, base path, tests, and shipped assets. |
| `.gitignore`, `.dockerignore` | Modify | Include source/lock/dist; exclude Node installs and compiler artifacts; retain `dist` in Docker context. |

## Interfaces / Contracts

| Endpoint | Success | Failure / pending |
|---|---|---|
| `GET /api/support/threads` | `{threads: ThreadSummary[]}`, newest first | Empty list for no safe threads. |
| `GET /api/support/threads/{session_id}` | `ThreadDetail` | `404` for missing, foreign, or unmappable sessions. |
| `POST /api/support/emails` | `ThreadDetail`; `arun(request, session_id=request.thread_id)` | Validation `4xx`, generic `500`, or safe `202 PendingSend`. |

The TypeScript client mirrors these DTOs. React renders strings as text and pretty-prints only `ThreadDetail`; no `innerHTML` or `dangerouslySetInnerHTML`. Load, selection, and send failures preserve safe content and show generic messages.

## Testing Strategy

| Layer | Coverage | Approach |
|---|---|---|
| Pytest | Allow-list, chronology, foreign/malformed input, 404/4xx/500, thread identity, pending, route/static order | `TestClient`, typed fixtures, monkeypatched team. |
| PostgreSQL | Saved/reloaded runs map without raw fallback | Isolated persistence fixture; no model call. |
| Vitest | States, mobile back, validation/pending, two tabs, escaped text | Mock `supportApi`; assert no approval control or executable DOM. |
| Build | Base-path assets and `dist` | `npm ci && npm run build`, `npm test`, static-serving and Docker validation. |

Model-backed smoke tests need an exclusive-writer window; normal feedback is pytest/Vitest.

## Threat Matrix

| Boundary | Applicability | Design response / RED tests |
|---|---|---|
| Documentation-like paths | N/A — assets are served, never classified or executed. | N/A |
| Git repository selection | N/A — no VCS command. | N/A |
| Commit state | N/A — no commit automation. | N/A |
| Push state | N/A — no push automation. | N/A |
| PR commands | N/A — no PR automation. | N/A |

## Migration / Rollout

No migration. Build/test committed assets before image creation. Rollback removes the router/precedence, middleware/assets, and related tests as one work unit; persisted sessions stay intact.

## Implementation Work Units and Delivery Gate

1. Mapper plus deterministic backend RED tests, including persisted decoding and forbidden fields.
2. API/static precedence, packaging, and their tests.
3. Typed SPA states, Vitest coverage, then reproducible assets.

Tests stay with each work unit. Existing work is estimated at least 3,204 changed lines, over the 800-line single-PR budget. **Before apply, record `size:exception` or change delivery strategy; this design authorizes no silent exception.**

## Open Questions

- [ ] Will the owner accept `size:exception` for the configured single PR, or change strategy before apply?
