# Recruiter Demo Data Tasks

## Goal

Make the local Customer Support demo immediately inspectable after setup by providing deterministic demo data without requiring a model call or exposing internal execution details.

## Scope

- Seed mock store order fixtures idempotently.
- Seed safe, persisted Customer Support conversations representing key flows.
- Make the demo setup path discoverable and document it in English.
- Verify that a fresh local stack exposes visible inbox threads without model usage.

## Non-goals

- No frontend redesign.
- No changes to refund authorization policy.
- No automatic model calls during setup.
- No product-knowledge embedding seed during setup; it would require the configured embedding provider.
- No production deployment changes.

## Tasks

- [x] Map the safe persisted-run format and define deterministic demo conversations.
- [x] Implement idempotent demo seeding and wire it into the local setup path.
- [x] Document and verify the recruiter demo flow.

## Evidence

- `app/support_demo.py` builds three typed `TeamRunOutput` fixtures and persists them through the Customer Support session/run APIs.
- The startup lifespan seeds fixed sessions after store schema creation and before schedule registration.
- `tests/test_support_demo.py` verifies safe public mapping and idempotent persistence without models or knowledge.
- `source .venv/bin/activate && pytest -q tests/test_support_demo.py` passed: 2 tests.
- The live local API returned three seeded threads: tracking and sizing as `completed`, refund review as `approval_pending`.
- `docs/recruiter-demo.md` documents the model-free local demo path in English.
- Recorded in the feature work-unit commit `feat: seed deterministic support demo data`.
