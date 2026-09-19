# Recruiter Frontend UX Tasks

## Goal

Make the local Customer Support demo immediately understandable to recruiters by explaining the specialist routing, clarifying compose and reply behavior, making refresh failures recoverable, and presenting approval-pending threads as read-only administrative review states.

## Scope

- Add a compact recruiter-facing explanation of the three Customer Support specialists.
- Clarify that compose creates a simulated customer thread and reply continues the selected thread.
- Add manual inbox refresh and retry affordances for inbox and detail failures.
- Present `approval_pending` as “Awaiting administrative review” without approval controls.
- Rewrite the README entry path around the recruiter demo and distinguish Support Inbox from Support Insights.
- Regenerate the tracked frontend production build.

## Non-goals

- No polling or background refresh.
- No approve, reject, resume, or other administrative controls in Support Inbox.
- No API, BFF, authentication, or persistence changes.
- No changes to the administrator-only Support Insights agent.
- No staging of `.codegraph/` or unrelated working-tree changes.

## Delivery

- Forecast: approximately 220 authored changed lines, excluding generated build output.
- Strategy: `ask-on-risk`; no chain expected below the 400-line review guideline.
- Branch: `feat/support-inbox-production-readiness`.
- TDD mode: not enabled by repository or session configuration; use behavior-first tests and ordinary focused checks.

## Tasks

- [x] Add recruiter-facing guidance, manual refresh/retry behavior, approval-status copy, focused tests, and regenerated frontend assets.
  - Route: delegated to `gentle-ai-worker` because the implementation spans multiple non-trivial frontend files.
  - Checks: `cd frontend/support-inbox && npm test` (20 passed, including parent spot check); `cd frontend/support-inbox && VITE_SUPPORT_API_ORIGIN=http://localhost:8001 npm run build` (passed); `git diff --check -- frontend/support-inbox odd/tasks/recruiter-frontend-ux.md` (passed).
  - Independent verification confirmed the behavior and identified the regenerated hashed assets that must be included with `dist/index.html`; the complete asset set is part of this work unit.
  - Commit evidence: recorded in work-unit commit `feat: improve recruiter support inbox UX`.
- [ ] Rewrite the README entry path for recruiters and distinguish Support Inbox from Support Insights.
  - Route: inline after the frontend behavior and wording are verified; this is one bounded documentation file.
  - Checks: README structural readback and `git diff --check`.
  - Commit evidence: pending.

## Evidence

- Read `odd/tasks/public-portfolio-phase-1.md`, `odd/tasks/recruiter-demo-data.md`, `docs/recruiter-demo.md`, and the prior Engram session summary before implementation.
- Read-only mapping confirmed that compose creates a new session, reply reuses the selected session, paused runs map to `approval_pending`, the UI lacked refresh/retry controls, and Support Insights is a separate administrator-only agent.
- The transient root `.vitest/` report created during delegated verification was diagnosed as disposable test output and removed without staging or changing ignore rules.
