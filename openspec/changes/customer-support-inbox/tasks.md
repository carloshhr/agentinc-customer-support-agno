# Tasks: Customer Support Inbox

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 3,783 current additions; 3,509 authored implementation lines |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Three work-unit commits inside one exception PR |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

The 3,509 authored estimate excludes 23 generated `dist/**` lines and SDD artifacts; generated assets remain in complete snapshot identity. The configured 800-line budget is exceeded.

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: size-exception
400-line budget risk: High

### Suggested Work Units

| Unit | Goal / commit | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | `test/fix(inbox): harden persisted DTO mapper` | PR 1 | `uv run --extra dev pytest tests/test_support_inbox.py -q` | Isolated PostgreSQL reload; no model | `app/support_inbox.py`, mapper tests |
| 2 | `feat(inbox): expose safe API and assets` | PR 1 | same pytest command | `TestClient` list/detail/send/redirect/assets | `app/main.py`, ignores, routes/tests |
| 3 | `feat(inbox): ship safe Vite inbox` | PR 1 | `npm test && npm run build` | Built image serves `/support-inbox/` and an asset | `frontend/support-inbox/**`, `dist/**` |

## Phase 1: Test Foundation and Mapper

- [x] 1.1 Update `openspec/config.yaml` inbox test context; prove `uv run --extra dev pytest tests/test_support_inbox.py -q` is deterministic before logic changes.
- [x] 1.2 RED: extend `tests/test_support_inbox.py` for chronology, foreign/malformed/unsafe records, forbidden fields, and PostgreSQL-reloaded serialized runs with no raw fallback.
- [x] 1.3 GREEN: normalize persisted runs in `app/support_inbox.py`; emit only valid allow-listed DTOs and `completed`/`approval_pending`/`incomplete`.
- [x] 1.4 REFACTOR: isolate mapper parsing/status helpers in `app/support_inbox.py` while preserving the new RED cases.

## Phase 2: Browser API and Static Boundary

- [x] 2.1 RED: add `TestClient` cases for exact list/detail/send payloads, 404/422/500/202, unchanged `thread_id`, 307 redirect, assets, traversal rejection, and route precedence.
- [x] 2.2 GREEN: reconcile `app/support_inbox.py` and `app/main.py` to expose only the three API routes, generic failures, safe pending data, and narrow static middleware.
- [x] 2.3 REFACTOR: update `.gitignore` and `.dockerignore` so source/lock/`dist/**` ship while `node_modules` and compiler output do not.

## Phase 3: Typed SPA

- [x] 3.1 RED: expand `frontend/support-inbox/src/App.test.tsx` for empty/loading/error/send states, reply session preservation, mobile back, exactly two tabs, and hostile text escaping.
- [x] 3.2 GREEN: reconcile `src/api.ts`, `App.tsx`, and `styles.css`; pin `package*.json`/`vite.config.ts` and remove generated TypeScript config outputs.
- [x] 3.3 REFACTOR: keep normalized DTO rendering text-only and preserve safe content on request failures.

## Phase 4: Package and Verify

- [x] 4.1 Run `npm ci && npm test && npm run build`; refresh and retain `frontend/support-inbox/dist/**` as snapshot-identified shipped assets.
- [x] 4.2 Run pytest and `./scripts/validate.sh`; build the Docker image and prove `/support-inbox/` plus a base-path asset respond from it.
- [x] 4.3 Only with an exclusive-writer window, smoke one simulated thread and record cleanup; otherwise record runtime smoke as N/A.
