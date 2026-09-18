# Apply Progress: External Support Inbox

## Status

Phase 5 cutover-readiness slice remains at the production-operator boundary. The repository readiness objective passes its corrective re-run: local BFF, frontend, AgentOS, static-quality, compile/import, configuration, bundle, and diff checks are green. Production preflight, migration execution, deployment, production read-only observation, controlled send, rollback rehearsal, and legacy removal were not performed.

## Completed in this attempt

- Repaired legacy AgentOS static hosting compatibility for the root-built independent frontend: `/support-inbox/` now rewrites generated root asset references to the legacy asset mount while leaving the external build output unchanged.
- Updated the readiness ledger to record the AgentOS Support Inbox suite as green.
- Preserved task 5.1 and 5.2 unchecked because their production/approval gates are not available in this repository-only attempt.
- Added `support-inbox/bff/railway.json` for the separate Railway service and documented the same-project/private-network topology, secret names, PAT scopes, controlled Alembic release, observability, send gate, rollback, and legacy-retention criteria.
- Re-ran the corrective Phase 5 readiness evidence without changing implementation files; no concrete repository defect was found.

## Files changed in the prior implementation attempt

- `app/support_inbox.py`
- `docs/support-inbox-external-frontend-plan.md`
- `openspec/changes/external-support-inbox/tasks.md`
- `openspec/changes/external-support-inbox/apply-progress.md`

No implementation files were changed in this corrective re-run.

## Verification evidence

- `uv run --extra dev pytest tests/test_support_inbox.py -q` — initially RED (1 static-serving failure), then GREEN: 14 passed, 1 warning.
- `cd support-inbox/bff && uv run pytest tests -q` — GREEN: 30 passed, 1 skipped, 7 warnings.
- `cd frontend/support-inbox && npm test -- --run` — GREEN: 16 passed.
- `cd frontend/support-inbox && npm run build` — GREEN: TypeScript and Vite build passed.
- Bundle secret scan for PAT/JWT/database/OpenAI names — GREEN: no matches.
- `git diff --check` — GREEN.
- `cd support-inbox/bff && uv run pytest tests/test_deployment_config.py -q` — GREEN: 4 passed, 1 warning.
- `cd support-inbox/bff && uv run pytest tests -q` — GREEN: 34 passed, 1 skipped, 7 warnings.
- `cd support-inbox/bff && uv run ruff check app tests retention.py migrations && uv run mypy app retention.py` — GREEN.

## Corrective re-run evidence

- `uv run --extra dev pytest tests/test_support_inbox.py -q` — GREEN: 14 passed, 1 warning.
- `cd support-inbox/bff && uv run pytest tests/test_deployment_config.py -q` — GREEN: 4 passed, 1 warning.
- `cd support-inbox/bff && uv run pytest tests -q` — GREEN: 34 passed, 1 skipped, 7 warnings.
- `uv run ruff check . && uv run mypy . --config-file pyproject.toml` — GREEN: Ruff passed; mypy passed on 46 source files.
- `cd support-inbox/bff && uv run ruff check . && uv run mypy app retention.py` — GREEN: Ruff and mypy passed on 13 source files.
- `uv run python -m compileall -q app tests` and `RUNTIME_ENV=dev uv run python -c 'import app.main; import app.support_inbox'` — GREEN.
- `cd support-inbox/bff && RUNTIME_ENV=test uv run python -m compileall -q app tests` and `RUNTIME_ENV=test uv run python -c 'import app.main; import app.deployment_config'` — GREEN.
- `npm test -- --run && npm run build` — GREEN: 16 frontend tests passed; TypeScript and Vite build passed.
- Bundle secret scan — GREEN: no forbidden PAT/JWT/configuration-name matches.
- JSON/config parse and `git diff --check` — GREEN.

The import checks intentionally use non-production environments because production startup must reject missing secrets/keys; the initial unset production imports correctly failed closed and was not a repository defect.

## TDD Cycle Evidence

| Cycle | Evidence |
| --- | --- |
| RED | Existing static-serving test failed because root-built HTML had no `/support-inbox/assets/` reference. |
| GREEN | `support_inbox_frontend()` rewrites only generated `src`/`href` root asset references; focused AgentOS tests pass. |
| TRIANGULATE | BFF tests, frontend tests/build, and bundle-secret scan pass; external build output remains root-based. |
| REFACTOR | Kept the compatibility rewrite narrow and documented; no unrelated files or hosting removal changed. |
| RED | Deployment-config tests initially failed at collection because `app.deployment_config` did not exist. |
| GREEN | Added checked-in Railway shape validation and `/health`; deployment-config tests pass 4/4. |
| TRIANGULATE | Covered valid config, wrong healthcheck/private URL, empty config, and live health response. |
| REFACTOR | Fixed import ordering with Ruff; full BFF suite and mypy remain green. |

## Cleanup evidence

No deployment, credential mutation, traffic switch, controlled send, destructive migration, database cleanup, or legacy static-host removal was performed. Existing uncommitted SDD work was preserved. The candidate changed relative to failed evidence revision `sha256:dbef3156e54bbbe1d91f503d3688df2bdab4870940fe22c51f3ac6b9fd13483e`.

## Remaining tasks

- Task 5.1 remains unchecked: authorized production preflight, read-only observation, safe controlled-send decision/execution, and rollback rehearsal.
- Task 5.2 remains unchecked and blocked until task 5.1 exit criteria and explicit approval pass.
- PostgreSQL-backed migration validation remains unevidenced locally.

## Workload / PR boundary

Work unit: `phase-5-cutover-readiness`; delivery strategy `ask-on-risk`; chain strategy `feature-branch-chain`; review budget 800 lines. This repository-only slice stayed within the 400-line work-unit budget and did not broaden the approved scope. Parent must settle the held runtime attempt with evidence distinct from the failed revision.

## Work Unit Evidence

| Evidence | Result |
| --- | --- |
| Focused test command and exact result | `cd support-inbox/bff && uv run pytest tests/test_deployment_config.py -q` — 4 passed, 1 warning. |
| Runtime harness command/scenario and exact result | `TestClient(create_app(Settings(...))).get('/health')` — 200 and `{"status":"ok"}`; no external runtime boundary exists in this repository-only slice. |
| Rollback boundary | Revert `support-inbox/bff/railway.json`, `support-inbox/bff/app/deployment_config.py`, the `/health` route, and the readiness documentation; leave AgentOS authorization, frontend, and legacy hosting unchanged. |
