# Tasks: Customer Support Team

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1,500–1,900 authored lines |
| 800-line budget risk | High |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |
| Suggested split | One exception PR; four work-unit commits |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: size-exception
400-line budget risk: High

Maintainer `size:exception` is required before apply because the cached `single-pr` strategy exceeds both 400 and 800 lines.

### Suggested Work Units

| Unit / commit boundary | Focused evidence | Runtime harness / rollback |
|---|---|---|
| 1 `test(store): establish deterministic support foundation` | `pytest tests/test_support_models.py tests/test_store.py` → models, 4 products, 7 fixtures, idempotent seed pass | `docker compose exec agentos-api python scripts/seed_store.py` → rerun preserves a mutated order; revert `app/store.py`, models, seed, catalog, fixture/tests |
| 2 `feat(store): enforce refund and product knowledge boundaries` | `pytest tests/test_store.py` → ownership, Decimal 39.99/50.00/50.01, lock/idempotency pass | Seed then query supported catalog path; revert repository/RAG files and tests |
| 3 `feat(support): add private coordinated support flow` | `pytest tests/test_customer_support_integration.py` → PAUSED/approve/reject/recheck and one resumed interaction pass | Run USD 120.00 approval continuation; revert agents/team/hook/insights and tests |
| 4 `feat(agentos): expose approved support surfaces` | `pytest tests/test_customer_support_integration.py && python -m evals --tag smoke` → registrations and smoke scenarios pass | AgentOS discovery lists only team, insights, knowledge; revert registrations/manifest/evals |

## Phase 1: Test Foundation, Schema, and Seed

- [x] 1.1 Add pytest via `pyproject.toml`/uv-generated `requirements.txt`; create `tests/conftest.py` PostgreSQL fixture and record its focused command/result.
- [x] 1.2 **RED** `tests/test_support_models.py` and `tests/test_store.py`: require typed email/enums, table constraints, four catalog IDs, seven boundary orders, and non-destructive seed reruns.
- [x] 1.3 **GREEN/REFACTOR** create `app/support_models.py`, `app/store.py`, `knowledge/store_catalog.md`, and `scripts/seed_store.py`; implement idempotent schema/upserts and keep tests green.

## Phase 2: Deterministic Store, Refunds, and RAG

- [x] 2.1 **RED** extend `tests/test_store.py` for ownership, no amount parameter, USD/eligibility/deadline/already-refunded refusals, 39.99/50.00 success, 50.01/50.00 route rejection, and repeated-call locking.
- [x] 2.2 **GREEN/REFACTOR** implement narrow lookup/refund repository tools in `app/store.py` using persisted `Decimal` and transactional row locks.
- [x] 2.3 **RED → GREEN/REFACTOR** test and create `app/store_knowledge.py`; ingest Markdown with `skip_if_exists=True`, then create `agents/product_support.py` with dedicated retrieval and unsupported-fact refusal.

## Phase 3: Private Team, HITL, Hooks, and Insights

- [x] 3.1 **RED → GREEN/REFACTOR** add private `agents/order_support.py`, `agents/refund_support.py`, and `teams/customer_support.py`; assert JSON-only typed English replies, three distinct private roles, and no `shared_learning`.
- [x] 3.2 **RED → GREEN/REFACTOR** add `tests/test_customer_support_integration.py` and member-required approval: USD 120.00 pauses without mutation; approve/reject continuation rechecks state and records its approval ID.
- [x] 3.3 **RED → GREEN/REFACTOR** add `app/support_hooks.py` and `agents/support_insights.py`; prove malformed/paused output is skipped, retries upsert one interaction, and SQL aggregates equal report counts.

## Phase 4: Registration and Release Evidence

- [x] 4.1 **RED → GREEN/REFACTOR** update `app/main.py` bootstrap-before-schedules and public registration; update `app/config.yaml`; prove only team, insights, and knowledge are discoverable.
- [x] 4.2 Add scoped cases in `evals/cases.py` with safe hooks: routing, English, RAG grounding/isolation, no insights reply, and SQL report fidelity; run smoke only after deterministic/HITL tests pass.
- [x] 4.3 Record strict-TDD safety-net, RED, GREEN, triangulation, and refactor evidence per task; run `./scripts/format.sh` and `./scripts/validate.sh` after focused tests.

Threat matrix: all rows are N/A; no threat-matrix RED task is applicable.
