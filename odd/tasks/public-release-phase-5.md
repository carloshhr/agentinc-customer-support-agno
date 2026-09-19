# Public Release Phase 5 Tasks

## Goal

Bring **Customer Support AgentOS** to a public-ready repository state by correcting proven documentation/configuration drift, updating the contributor architecture source of truth, and restoring clean static validation without changing product behavior or legal identity.

## Authorized Scope

The user selected **Public-ready complete**:

- Fix the known mypy error in the Support demo test.
- Document the separate Support Inbox/BFF environment inventory with value-free examples.
- Correct stale factual wording in the eval-authoring skill.
- Update `AGENTS.md` so its architecture and key-file guidance match the current Customer Support portfolio implementation.
- Run no-cost repository, link, registration, live listing, and validation checks.

## Non-goals

- No package authorship, copyright, license, Railway naming, or upstream attribution changes.
- No `.codegraph/` inspection, ignore-rule change, staging, or deletion.
- No changes to Customer Support, Support Insights, Support Inbox, BFF, or platform runtime behavior beyond the test typing correction.
- No model-backed agent/team smoke runs, MCP smoke, release evals, or other API-cost/shared-state checks without separate explicit authorization.
- No push, release, deployment, remote mutation, or destructive cleanup.
- No translation or broad cleanup of historical Spanish onboarding/planning documents.

## Delivery

- Forecast: approximately 360 authored changed lines.
- Strategy: `ask-on-risk`; no chain expected below the 400-line review guideline.
- Branch: `feat/support-inbox-production-readiness`.
- TDD mode: not enabled by repository or session configuration; use focused regression checks and repository validation.

## Tasks

- [x] Restore clean typing for the deterministic Support demo test.
  - Route: inline because the correction was a one-file type narrowing with no behavioral change.
  - Evidence: the test now asserts each optional `session_id` is present before constructing the same `TeamSession` inputs.
  - Checks: focused Support demo tests passed (2 tests); affected-file mypy passed, including parent spot check; full Ruff and mypy validation passed for 47 files; independent verification found no production-path changes.
  - Commit evidence: recorded in work-unit commit `test: narrow support demo session ids`.
- [x] Correct public environment and eval-skill inventory drift.
  - Route: delegated to `gentle-ai-worker` because the work spans `example.env`, public docs, and a coding-agent skill.
  - Skills: `review-and-improve`, `cognitive-doc-design`.
  - Evidence: `example.env`, `README.md`, and `AGENTS.md` now inventory all 12 separate Support Inbox BFF/operator/database variables without values; the eval skill names Customer Support and Support Insights alongside reference coverage.
  - Checks: `git diff --check` passed; env-variable coverage (including parent spot check), runtime-source name matching, eval-skill wording, and Markdown/local-link validation passed; independent verification confirmed all entries are unique, commented, and value-free.
  - Commit evidence: recorded in work-unit commit `docs: document support inbox deployment settings`.
- [ ] Update the contributor architecture source of truth.
  - Route: delegated to `gentle-ai-worker` because `AGENTS.md` is a large, cross-cutting public architecture document.
  - Skills: `review-and-improve`, `cognitive-doc-design`.
  - Checks: registered component/manifest consistency, key-file path validation, architecture terminology, and diff check.
  - Commit evidence: pending.
- [ ] Run the no-cost public-release gate and report checks still requiring authorization.
  - Route: delegated to `gentle-ai-verify` for repository-wide read-only checks.
  - Checks: Git hygiene, tracked local artifacts, local links/symlinks, component listings, formatting, validation, focused tests, and frontend/BFF checks that do not call models.
  - Commit evidence: pending if the gate requires no further fixes.

## Evidence

- Read-only mapping confirmed that all registered code agents, teams, and workflows have source modules and manifest entries.
- `AGENTS.md` still omits Customer Support, its private specialists, Support Insights, Support Inbox, and support persistence from its architecture/key-file model.
- `example.env` omits the separate Support Inbox/BFF environment inventory.
- `.agents/skills/create-evals/SKILL.md` incorrectly says the committed eval suite covers only reference components.
- The sole current validation failure is the unchanged `tests/test_support_demo.py:61` optional `session_id` mypy diagnostic; Ruff and 24 focused Customer Support tests pass.
- Engram remains unavailable because the local memory provider reports an ownership mismatch; this task file is the recovery source.
