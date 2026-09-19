# Demo Eval Tag Tasks

## Goal

Add a dedicated `demo` eval selection for the model-backed **Customer Support AgentOS** portfolio cases without deleting or weakening the existing platform, smoke, or release coverage.

## Scope

- Add the `demo` tag to the three Customer Support cases and the separate Support Insights case.
- Preserve every existing `smoke` and `release` tag and all cleanup hooks.
- Document `python -m evals --tag demo` as model-backed portfolio verification.
- Keep the deterministic Support Inbox walkthrough distinct from model-backed eval execution.

## Non-goals

- No eval case deletion or rubric/tool/hook changes.
- No change to `EVALS_TAG=smoke`, the run-evals workflow, or schedules.
- No model execution until the tag selection is statically verified and the user authorizes the focused run.
- No MCP smoke, release eval rerun, runtime restart, push, release, or deployment.
- No `.codegraph/` inspection, staging, ignore-rule change, or deletion.

## Delivery

- Forecast: approximately 70 authored changed lines.
- Strategy: `ask-on-risk`; no chain expected.
- Branch: `feat/support-inbox-production-readiness`.
- TDD mode: not enabled; use static case-selection checks and deterministic tests before the authorized model-backed run.

## Tasks

- [x] Add and statically verify the focused demo eval selection.
  - Route: delegated to `gentle-ai-worker` because the change spans eval definitions, CLI guidance, and public docs.
  - Skills: `create-evals`, `cognitive-doc-design`.
  - Evidence: exactly four existing cases gained `demo`; all retain `release`, tracking retains `smoke`, and hooks, rubrics, inputs, timeouts, expected tools, workflow defaults, and schedules are unchanged.
  - Checks: exact case/tag inventory and `--list` passed, including parent spot check; deterministic support/eval-hook tests passed (44 tests); Ruff and mypy passed; documentation distinction passed; independent hunk inspection confirmed tag-only case changes.
  - Commit evidence: recorded in work-unit commit `eval: add Customer Support demo tag`.
- [x] Correct unsupported Product Support elaboration found by the demo gate.
  - Route: inline because diagnosis identified one instruction-only change in `agents/product_support.py`; the eval rubric and catalog fixture remain unchanged.
  - Failure evidence: the price response retrieved and stated the correct `$24.00 USD` price but invented unsupported availability/variant/regional-pricing/promotion details.
  - Fix: Product Support now reports only needed facts explicitly supported by the retrieved passage and does not infer availability, variants, regional pricing, promotions, or discounts.
  - Checks: Ruff format/lint, mypy, static case selection, and 41 focused tests passed; independent semantic diff verification passed; the explicitly authorized single-case run passed judge and reliability in 54.904s with the expected knowledge tool and no unsupported facts.
  - Cleanup: `customer-support:EMAIL-EVAL-PRICE` was absent before and after the single-case run, proving its interaction was cleaned up.
  - Commit evidence: recorded in work-unit commit `fix: keep product answers catalog-grounded`.
- [ ] Run the model-backed demo eval gate when explicitly authorized.
  - Route: delegated to `gentle-ai-verify` with the exact `python -m evals --tag demo` command.
  - First-run evidence: tracking, product facts, and Support Insights passed; product price failed while reliability passed. Cleanup output was not emitted, so hook cleanup remains unknown.
  - Safety: run only when no other writer is adding support interactions because case hooks snapshot and sweep newly created rows.
  - Commit evidence: not applicable unless the run reveals a required source fix.

## Evidence

- The focused selection contains exactly four existing cases: `customer_support_routes_tracking_email`, `customer_support_grounds_product_facts_in_dedicated_catalog`, `customer_support_grounds_product_price_in_dedicated_catalog`, and `support_insights_reports_sql_derived_empty_period`.
- The three Customer Support cases retain `SUPPORT_INTERACTION_HOOKS`; Support Insights remains a separate operator-facing report case with no interaction cleanup hook.
- The cancelled release-eval attempt did not return a completion/cleanup report, so the eventual focused run must report hook cleanup status explicitly.
- Engram remains unavailable because the local memory provider reports an ownership mismatch; this task file is the recovery source.
