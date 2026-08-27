# Design: Customer Support Team

## Technical Approach

Implement the `customer-support` and `support-insights` delta specs with an application-owned store layer before Agno components. `store_records` is the sole mock-business authority; private specialists receive narrow Python tools, never SQL. Existing `db_url`, `create_knowledge()`, lifecycle, and AgentOS registration patterns remain unchanged.

## Architecture Decisions

| Decision | Options / trade-off | Choice and rationale |
|---|---|---|
| Store boundary | Generic model SQL is smaller but non-deterministic. | `app/store.py` repository plus decorated narrow tools; it centralizes ownership, eligibility, locks, and SQL aggregates. |
| Schema ownership | Framework migrations do not own application tables. | `ensure_store_schema()` executes idempotent `CREATE TABLE/INDEX IF NOT EXISTS` before `register_schedules()`; `seed_store.py` calls it too. Startup fails when schema bootstrap fails. |
| Record shape | Normalized commerce is out of scope. | One JSONB table: identity columns and database constraints protect keys; Pydantic models validate record-specific payloads before writes. |
| Seed contract | Ad hoc fixtures can miss monetary, fulfillment, and refusal boundaries. | `scripts/seed_store.py` owns a fixed fictional catalog and order matrix, inserts by record key without overwriting existing business state, and is reused by PostgreSQL tests. |
| Refund safety | Prompt checks or floats can drift and race. | Parse persisted decimal strings with `Decimal`; one transaction uses `SELECT ... FOR UPDATE`, revalidates every predicate, then changes an unrefunded record once. |
| Exposure | Registering members bypasses coordination and hooks. | Register only the team, insights agent, and dedicated knowledge. Three specialists remain private; no support component receives `shared_learning`. |

## Data Flow

```
CustomerEmail -> customer-support (coordinate) -> private member tools -> StoreRepository
                       |                                  |              |
                       +-> CustomerEmailReply -> post-hook -> interaction upsert
Admin -> support-insights -> aggregate tool ----------------> StoreRepository
Catalog Markdown -> seed command -> store-product-knowledge -> Product Support only
```

`store_records` has `id BIGINT identity`, `record_type TEXT`, `record_key TEXT`, `payload JSONB`, and UTC timestamps; it enforces `record_type IN ('order','support_interaction')`, object JSON, and unique `(record_type, record_key)`. Order payloads contain `customer_email`, decimal-string `total`, `currency`, items, fulfillment/tracking, return state, and `refund {status, reason, approval_id, refunded_at}`. Interaction payloads contain `message_id`, `team_run_id`, bounded category/issue code, optional order/product IDs, outcome, refund outcome, and timestamp. JSONB path indexes support interaction period/category aggregation; no model-facing query accepts SQL.

The seed command defines exactly four fictional catalog products: `PRD-EMBER-MUG` (Emberwake Mug), `PRD-CLOUD-TOTE` (Cloudweave Tote), `PRD-MOSS-TEE` (Mosslight Tee), and `PRD-SOLSTICE-JOURNAL` (Solstice Journal). It inserts seven immutable-by-key order fixtures; rerunning the command must retain a mutated order rather than reset it. All customer addresses use `@example.test`; all tracking IDs are `TRK-LUMEN-*` and URLs use `tracking.example.test`.

| Order | Total / status | Return and refund state | Test boundary |
|---|---|---|---|
| `ORD-LUMEN-1001` | `39.99` USD, delivered | eligible, unrefunded | automatic refund |
| `ORD-LUMEN-1002` | `50.00` USD, shipped | eligible, unrefunded | inclusive automatic boundary |
| `ORD-LUMEN-1003` | `50.01` USD, delivered | eligible, unrefunded | automatic-route rejection |
| `ORD-LUMEN-1004` | `120.00` USD, delivered | eligible, unrefunded | approval pause/continuation |
| `ORD-LUMEN-1005` | `18.00` USD, canceled | ineligible, unrefunded | canceled refusal |
| `ORD-LUMEN-1006` | `24.00` USD, delivered | ineligible (expired deadline), unrefunded | eligibility refusal |
| `ORD-LUMEN-1007` | `49.00` USD, delivered | eligible, already refunded | duplicate-refund refusal |

`refund_order_automatically(order_id, customer_email, reason)` and the required-approval equivalent accept no amount. Both reload the row under lock and validate existence, ownership, USD, eligibility, deadline, unrefunded status, and their symmetric threshold. The over-threshold tool is member-level `@approval(type="required")` plus confirmation: it pauses the member and parent team without mutation. On resolved continuation it obtains the approved record by the run ID, rechecks all predicates and locks again; rejection or failed recheck leaves state unchanged. The final run metadata supplies the approval audit ID to the hook.

The team hook ignores paused/incomplete output, requires a valid `CustomerEmailReply` (including string-fallback protection), and upserts on `message_id`. It catches/logs persistence exceptions with run/message identifiers but never body content, so analytics failure cannot suppress a valid reply. Insights tools return SQL-derived typed aggregates or a logged, explicit unavailable result; they never invent counts.

## File Changes

| File | Action | Description |
|---|---|---|
| `app/store.py`, `app/support_models.py`, `app/support_hooks.py`, `app/store_knowledge.py` | Create | Schema/repository, Pydantic enums/contracts, fail-soft hook, and dedicated knowledge factory. |
| `agents/order_support.py`, `agents/product_support.py`, `agents/refund_support.py`, `agents/support_insights.py` | Create | Three private specialists and the public administrator surface. |
| `teams/customer_support.py` | Create | Typed coordinate team, private membership, output contract, and hook. |
| `knowledge/store_catalog.md`, `scripts/seed_store.py` | Create | Fictional catalog and explicit idempotent bootstrap/upsert/Markdown ingestion. |
| `tests/conftest.py`, `tests/test_support_models.py`, `tests/test_store.py`, `tests/test_support_hooks.py`, `tests/test_customer_support_integration.py` | Create | Deterministic PostgreSQL fixture and unit/HITL/registration coverage. |
| `app/main.py`, `app/config.yaml`, `pyproject.toml`, `requirements.txt` | Modify | Bootstrap before schedules; public registrations/manifest; pytest dependency and uv lock generation. |

## Interfaces / Contracts

`CustomerEmail` validates `message_id`, optional `thread_id`, `EmailStr from_email`, subject, and body. `CustomerEmailReply` returns the same ID, English subject/body, bounded `SupportCategory`/`IssueCode`, allowed outcome, and optional order/product IDs. `InsightsReport` returns requested bounds, SQL total, ranked `InsightItem`s, and refund-outcome counts. Product Support alone has `knowledge=store_knowledge, search_knowledge=True`; it must decline unsupported catalog facts. Seed ingestion uses `MarkdownReader` and `Knowledge.insert(..., skip_if_exists=True)`, never request-time embedding.

## Testing Strategy

| Layer | What to test | Approach |
|---|---|---|
| Deterministic PostgreSQL | schemas, ownership, JSON payloads, catalog/order seed matrix, Decimal boundaries, locks, duplicate/refund rejection, upsert, aggregates | Add pytest and fixture first. Assert idempotent seed insertion, the four catalog IDs, all seven fixtures, and every threshold/status boundary before models/store logic. |
| Integration | required approval pause/reject/approve/continue, revalidation, one resumed interaction, registrations | Real PostgreSQL with controlled framework approval records; no live model dependency for monetary rules. |
| Agno evals | routing, English output, RAG grounding/isolation, report fidelity | Add after deterministic and HITL tests; run existing smoke suite only as model-backed coverage. |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary is introduced.

## Migration / Rollout

Deploy application-owned idempotent bootstrap, then run the explicit seed command. Catalog insertion is repeat-safe; no automatic re-embedding. Roll back by unregistering the team, insights, and knowledge and stopping seeds; preserve business/knowledge tables until retention approval explicitly authorizes deletion.

## Open Questions

- [ ] None; approval-ID propagation is verified in the required HITL integration test before release.
