## Exploration: Customer Support Team

### Current State
AgentOS currently registers three public reference agents, the `agno` team, and one shared PgVector knowledge base in `app/main.py`; no customer-support components, store table, catalog, or conventional tests exist. `db/session.py` already provides the required reusable PgVector factory (hybrid search, `text-embedding-3-small`, and a distinct contents table), while `workflows/deployment_check.py` is the established local pattern for SQLAlchemy access to the existing PostgreSQL URL.

Agno supports the planned contracts: team `input_schema` rejects non-JSON string input, coordinate teams support a Pydantic `output_schema`, and a member-level `@approval(type="required")` tool pauses its parent team and persists the approval. After an administrator resolves the approval, continuation reloads the tool execution; the protected tool must therefore re-read and lock the order before mutating it.

### Affected Areas
- `app/main.py` — import and register only `customer_support_team`, `support_insights`, and `store_knowledge`.
- `db/session.py` and `app/knowledge.py` — reuse the existing knowledge factory for a separate `store-product-knowledge` instance; do not reuse `shared_knowledge`.
- `app/store.py` (new) — create the `store_records` schema, parameterized JSONB queries, transactional refund mutation, and idempotent seed helpers using the existing PostgreSQL URL.
- `app/support_models.py`, `app/support_hooks.py` (new) — hold Pydantic/enum contracts and the fail-soft, idempotent team post-hook.
- `agents/order_support.py`, `agents/product_support.py`, `agents/refund_support.py`, `agents/support_insights.py` (new) — add specialists and the separately registered insights surface.
- `teams/customer_support.py` (new) — coordinate private specialists, typed email input/output, and the interaction hook without `shared_learning`.
- `knowledge/store_catalog.md` and `scripts/seed_store.py` (new) — provide idempotent catalog ingestion and fictional business data.
- `app/config.yaml` — add customer team and insights manifest entries only.
- `pyproject.toml`, `requirements.txt`, and new deterministic tests — add explicit test/dependency support before business rules; the current dev extra has only `mypy` and `ruff`, and no `tests/` tree exists.

### Approaches
1. **Curated repository and custom tools** — keep all order lookup, eligibility checks, reporting aggregates, and refunds in an `app/store.py` repository; expose only narrow, decorated tool functions to the specialists.
   - Pros: Keeps the USD 50 boundary, ownership validation, JSONB access, locking, and idempotency deterministic and independently testable; prevents a model from issuing arbitrary SQL.
   - Cons: Requires explicit schema bootstrap/migration and a PostgreSQL-capable test fixture.
   - Effort: Medium

2. **Model-facing generic database access** — give agents a broad SQL/database capability and enforce behavior in prompts.
   - Pros: Less initial application code.
   - Cons: Violates the source plan's deterministic authorization and refund boundary; makes query safety, transaction semantics, and aggregate correctness model-dependent.
   - Effort: Low initially, High operational risk

### Recommendation
Use curated repository and custom tools. It matches the plan and existing SQLAlchemy/PostgreSQL pattern: each refund route reloads the persisted order, validates all eligibility conditions, and performs a conditional locked update in one transaction. Keep `store_records` separate from Agno-managed tables, configure `store_knowledge` through `create_knowledge`, and mount only the Product Support Agent with `search_knowledge=True`. Add `pytest` and a deterministic test fixture before implementing the repository; smoke evals remain a later model-backed integration layer, not proof of the monetary business rules.

### Risks
- There is no existing deterministic unit-test runner or test tree. Strict TDD cannot rely on `python -m evals --tag smoke`; the proposal must introduce deterministic tests before implementing store/refund behavior.
- `store_records` needs an explicit idempotent DDL/migration ownership and startup/seed ordering; AgentOS migrations cover framework tables, not this application table.
- A member approval correctly pauses the team, but the resumed-run post-hook and exactly-once interaction record must be demonstrated with integration coverage; malformed typed output and hook failures must not hide a valid reply.
- Concurrent refund requests require real PostgreSQL transaction/locking tests; a repeated or resumed call must not double-refund.
- Email matching is deliberately mock ownership, not customer authentication, and must remain confined to simulated input.

### Ready for Proposal
Yes — propose the authoritative source-plan scope with an explicit schema-bootstrap decision and a first task that installs/configures deterministic test support before any refund or repository implementation.
