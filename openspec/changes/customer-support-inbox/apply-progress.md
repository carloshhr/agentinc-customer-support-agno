# Apply Progress: Customer Support Inbox

**Mode:** Strict TDD
**Delivery:** `single-pr` with maintainer-approved `size:exception`
**Native attempt token:** `sha256:82324397911d913c362ed7a3471c9edd3d14ee01433f957dfbcf3ff4932ae191`

## Completed Tasks

All 12 planned tasks are complete and checked in `tasks.md`.

## TDD Cycle Evidence

| Task | Layer | RED | GREEN | REFACTOR |
|---|---|---|---|---|
| 1.1 | Configuration | Structural; baseline 6/6 passed | Config updated; 6/6 passed | Triangulation skipped: one configuration outcome |
| 1.2 | Pytest | 2 failures for foreign runs and inbound metadata | 8/8 passed | Added serialized/unsafe cases; 9/9 passed |
| 1.3 | Pytest | Covered by 1.2 | 8/8 passed | Persisted status normalization added; 12/12 passed |
| 1.4 | Pytest | Approval baseline 9/9 | 9/9 passed | Extracted typed Customer Support run normalization |
| 2.1 | TestClient | 2 failures for generic error and traversal | 11/11 passed | Exact route/static checks retained |
| 2.2 | TestClient | Covered by 2.1 | 11/11 passed | Narrow middleware converts static 404 errors to responses |
| 2.3 | Configuration | Structural ignore checks | Docker check passed | Triangulation skipped: ignore rules have one intended outcome |
| 3.1 | Vitest | Loading-status test failed | 4/4 passed | Added reply identity coverage; 5/5 passed |
| 3.2 | Node/Vitest | Unpinned dependency assertion failed | `npm ci`, 5/5 tests, build passed | Removed generated TypeScript output |
| 3.3 | Vitest/static | Existing text-only rendering exercised | 5/5 passed | No HTML injection API found |
| 4.1 | Build | N/A: package verification | `npm ci && npm test && npm run build` passed | Fresh `dist/**` retained |
| 4.2 | Image harness | N/A: verification task | Validation and image routes passed | Ephemeral image, database, and networks removed |
| 4.3 | Runtime smoke | N/A: no exclusive shared PostgreSQL writer window | Not run | Model-backed smoke deliberately skipped |

## Work Unit Evidence

| Work unit | Focused test command and result | Runtime harness and result | Rollback boundary |
|---|---|---|---|
| Mapper | `uv run --extra dev pytest tests/test_support_inbox.py -q` — 12 passed, 1 warning | Isolated PostgreSQL save/reload mapped `THREAD-PG-1` with 2 messages; no model call | `app/support_inbox.py`, `tests/test_support_inbox.py` |
| API and assets | Same pytest command — 12 passed, 1 warning | TestClient verifies list/detail/send, redirect, asset, and traversal; built image returned `/support-inbox/` and asset `200` | `app/main.py`, `app/support_inbox.py`, ignores, backend tests |
| SPA and package | `npm test` — 5 passed; `npm run build` passed | Ephemeral built image returned inbox and base-path asset `200`; no model call | `frontend/support-inbox/**`, `frontend/support-inbox/dist/**` |

## Validation

- `./scripts/validate.sh`: ruff format/check and mypy passed.
- `docker build --check .`: passed.
- Docker runtime image harness: inbox `200`, asset `200`; temporary PostgreSQL containers, networks, and image were removed.
- Model-backed simulated-thread smoke: N/A. No exclusive shared PostgreSQL writer window was demonstrated.

## Evidence Revision

`9de16a21ec269ee3c4866da373eacccf6f3b7999459dfd010cf46bdb94e2ad2c`
