# Proposal: Customer Support Team

## Intent

Process simulated customer emails and provide a separate administrator insights surface. Keep refund, ownership, reporting, and customer-state rules deterministic.

## Proposal Question Round

Auto mode uses the authoritative plan: simulated customers only; no real authentication, partial refunds, or scheduled reports.

## Scope

### In Scope
- Typed `customer-support` team, three private specialists, and English replies.
- `store_records`, idempotent mock seed/catalog ingestion, and dedicated product RAG.
- Transactional refunds from persisted `Decimal` totals: `<= USD 50.00` automatic; `> USD 50.00` member-approved.
- Idempotent interaction recording and separately registered, SQL-backed `support-insights`.
- Deterministic pytest/PostgreSQL support; tests precede each business-logic step.

### Out of Scope
- Real email, commerce, payments, authentication, partial refunds, scheduled reports, or normalized commerce data.
- Registered operational specialists, `shared_learning`, or customer-facing insights.

## Capabilities

### New Capabilities
- `customer-support`: Typed email support, private routing, dedicated RAG, deterministic refunds, and interaction persistence.
- `support-insights`: On-demand reports from deterministic interaction aggregates.

### Modified Capabilities
None; no existing OpenSpec capabilities exist.

## Approach

Use a curated `app/store.py` repository and narrow tools; never expose generic SQL. Resolve bootstrap as application-owned idempotent DDL: `ensure_store_schema()` runs in the existing lifespan before schedules, and the seed command reuses it before upserts. This uses the existing lifespan and SQLAlchemy/PostgreSQL patterns without touching framework migrations. Add pytest and a PostgreSQL fixture first; follow RED-GREEN-REFACTOR through repository/refunds, agents, hooks, HITL integration, then evals.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `app/store.py`, `app/support_*.py` | New | Store, contracts, hooks, bootstrap. |
| `agents/`, `teams/customer_support.py` | New | Specialists, insights, team. |
| `app/main.py`, `app/config.yaml` | Modified | Public registrations only. |
| `knowledge/`, `scripts/`, `tests/` | New | Catalog, seed, tests. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Duplicate refunds | Med | Lock/conditional update; PostgreSQL tests. |
| Resume duplicates analytics | Med | `message_id` key; idempotent hook. |
| Missing table | Low | Lifespan bootstrap; seed reuse. |

## Rollback Plan

Unregister the team, insights agent, and knowledge base; stop seeding. Preserve mock data by default; explicitly remove `store_records` and dedicated knowledge tables only after retention confirmation.

## Dependencies

- `pytest` and a PostgreSQL-capable fixture; dependencies managed only through `uv`.

## Success Criteria

- [ ] Valid `CustomerEmail` JSON yields a structured English reply; specialists remain private and no support component uses shared learning.
- [ ] USD 39.99/50.00 refund automatically; USD 50.01/120.00 pauses, never mutates pre-approval, and cannot double-refund.
- [ ] Repeated/resumed `message_id` yields one interaction; insight counts are SQL-derived.
- [ ] Deterministic tests precede logic and pass before HITL integration, smoke evals, formatting, and validation.
