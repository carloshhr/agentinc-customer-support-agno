# Portfolio Identity Phase 4 Tasks

## Goal

Present the repository as **Customer Support AgentOS**, a recruiter-ready multi-agent Customer Support project, while accurately crediting AgentOS and Agno as its platform foundation.

## Product Decision

- Canonical public title: **Customer Support AgentOS**.
- Customer Support and its deterministic recruiter demo lead the public narrative.
- AgentOS platform capabilities remain documented as supporting architecture.
- Support Insights remains a separate administrator-only validation surface.

## Scope

- Rewrite and reorder the README so the project outcome, architecture, recruiter demo, and quick local path appear before generic platform capabilities.
- Preserve accurate setup, security, MCP, AgentOS, Studio, coding-agent, and Railway documentation through progressive disclosure.
- Align `docs/recruiter-demo.md` terminology and add honest guidance for capturing real deterministic screenshots or a GIF.
- Refine `app/config.yaml` descriptions and quick prompts so the Customer Support showcase is immediately visible while platform components remain available.

## Non-goals

- No changes to Customer Support routing, tools, approval policy, persistence, schemas, or demo seeding.
- No changes to Support Insights implementation, SQL aggregation, registration, or administrator-only intent.
- No stable component-ID, route, or session-ID renames.
- No fabricated screenshots, GIFs, benchmarks, or product claims.
- No package authorship changes without an explicit personal attribution decision.
- No runtime `AgentOS(name=...)` change in this phase; the selected title governs public portfolio framing, not stable runtime identity.
- No staging of `.codegraph/` or unrelated working-tree changes.

## Delivery

- Forecast: approximately 280 authored changed lines.
- Strategy: `ask-on-risk`; no chain expected below the 400-line review guideline.
- Branch: `feat/support-inbox-production-readiness`.
- TDD mode: not enabled by repository or session configuration; use structural documentation/config checks and existing integration tests.

## Tasks

- [x] Make README and recruiter demo documentation project-first.
  - Route: delegated to `gentle-ai-worker` because the documentation work spans multiple non-trivial files.
  - Skills: `cognitive-doc-design`.
  - Checks: `git diff --check` (including parent spot check), portfolio terminology/local-link validation, and project-first README ordering all passed.
  - Evidence: README now leads with Customer Support AgentOS, the deterministic Support Inbox demo, private specialists, and the read-only approval boundary; recruiter-demo terminology and seeded-state capture guidance align. Independent verification confirmed that essential setup, security, MCP, Studio, and Railway guidance remain present.
  - Commit evidence: recorded in work-unit commit `docs: make customer support the portfolio focus`.
- [ ] Refine the visible runtime catalog for the Customer Support showcase.
  - Route: inline if the final YAML change is bounded to descriptions, ordering, and quick prompts in `app/config.yaml`; delegate if broader changes become necessary.
  - Checks: YAML parse, `./scripts/validate.sh`, and `pytest -q tests/test_customer_support_integration.py tests/test_support_demo.py`.
  - Commit evidence: pending.

## Evidence

- Read-only mapping found that the implementation is already project-centric, but the README hero, onboarding order, generic image, and template clone path still make the repository appear template-first.
- `customer-support` is a public team with three private specialists; `support-insights` is a separate administrator-only agent.
- The existing deterministic demo supports honest screenshots without model calls.
- Engram persistence was unavailable at phase start because the local memory provider reported an ownership mismatch; this repository task file is the recovery source until memory service ownership is corrected.
