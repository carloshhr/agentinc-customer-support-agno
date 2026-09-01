# Customer Support Inbox Specification

## Purpose

Provide a local inbox for Customer Support inspection and simulated email sending without execution or approval controls.

## Requirements

### Requirement: Allow-Listed Inbox DTOs

Only persisted `customer-support` sessions and runs MAY supply browser data; `support_interaction` MUST NOT. Data MUST be chronological and expose only:

- `ThreadSummary(session_id, subject, customer_email, preview, last_message_at, status)`
- `ThreadDetail(session_id, status, messages)`
- `InboxMessage(message_id, direction, from_email, subject, body, sent_at, category?, issue_code?, outcome?)`

Timestamps MUST be UTC ISO-8601; optional metadata MUST occur only on outbound messages. Status MUST be exactly `completed`, `approval_pending`, or `incomplete`. DTOs MUST exclude raw session/run data, member output/`member_responses`, `tool_calls`, tools, tool results, traces, reasoning, `requirements`, approval IDs, approval statuses other than `approval_pending`, approval tool arguments, `order_id`, and `product_id`. Malformed/legacy records MUST NOT fall back to raw data; threads with no safe message MUST be unavailable.

#### Scenario: Safe conversation
- GIVEN valid input and completed replies
- WHEN the thread is mapped
- THEN messages are chronological and contain only allow-listed fields

#### Scenario: Unsafe record
- GIVEN a run with internal fields or invalid email/reply data
- WHEN its thread is mapped
- THEN forbidden data is absent and an entirely unsafe thread is unavailable

### Requirement: Exact Support Browser API

Inbox-specific browser routes MUST be only `GET /api/support/threads`, `GET /api/support/threads/{session_id}`, and `POST /api/support/emails`; raw AgentOS proxy and approval/continuation routes MUST NOT exist. List MUST return `200` with `{ "threads": ThreadSummary[] }`, most-recent-first, without bodies or run IDs. Detail MUST return `200` with `ThreadDetail`, or `404` with exactly `{ "detail": "Support thread not found" }` when absent, foreign, or unsafe.

The send route MUST accept valid `CustomerEmail` fields plus a `thread_id` from 1 through 128 characters and MUST dispatch it unchanged as the Customer Support `session_id`. Invalid input MUST return `422` without dispatch. A completed run MUST return `200` with `ThreadDetail`; a paused run MUST return `202` with exactly `{ "session_id": string, "run_id": string | null, "status": "approval_pending" }`. Execution or safe-mapping failure MUST return `500` with exactly `{ "detail": "Support email could not be processed" }`, without exception, trace, or run data.

#### Scenario: Route results
- GIVEN safe, foreign, valid, paused, invalid, and failing requests
- WHEN the three routes are requested
- THEN they return only the exact success and error statuses and payloads specified above
- AND dispatch preserves `thread_id` only for valid sends

### Requirement: SPA Serving and Interaction

The existing application MUST serve `GET /support-inbox/` with `200`, assets below `/support-inbox/assets/`, and redirect `GET /support-inbox` to `/support-inbox/` with `307`. It MUST introduce neither a second service nor browser-authentication changes.

The SPA MUST provide desktop two-column list/detail and mobile list/detail with back control. It MUST show empty, selection-empty, loading, request-failure, and send-in-progress states without replacing safe content. Compose MUST validate required fields locally, generate a bounded unique message ID, retain selected `session_id` as reply `thread_id`, refresh data after send, and show pending state only as a neutral notice.

#### Scenario: Responsive and safe states
- GIVEN a listed thread, no threads, a failed request, or a `202` response
- WHEN the SPA renders, navigates, or sends a reply
- THEN its layout, session-ID preservation, and corresponding safe state are available
- AND no approval control or metadata is rendered

### Requirement: Safe Detail Rendering

Detail MUST expose exactly `Email` and `JSON` tabs. It MUST render model-originated subjects, bodies, and metadata as text and MUST NOT use `innerHTML` or `dangerouslySetInnerHTML`. JSON MUST pretty-print normalized `ThreadDetail` only, never framework, trace, tool, or persistence data.

#### Scenario: Hostile model content
- GIVEN a normalized message containing HTML or script-like text
- WHEN either detail view is rendered
- THEN it remains text, creates no executable markup, and exposes exactly two tabs

## Pre-Apply Gate

Before apply, `single-pr` MUST change or an explicit `size:exception` MUST be accepted: work is estimated at least 3,204 lines against the 800-line budget. This delivery condition is not product scope.
