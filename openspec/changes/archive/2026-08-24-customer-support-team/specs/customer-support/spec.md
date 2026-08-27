# Customer Support Specification

## Purpose

Process simulated customer emails through one private specialist team with deterministic store and refund behavior.

## Requirements

### Requirement: Typed Customer Exchange

The team MUST accept only valid `CustomerEmail` JSON and return `CustomerEmailReply` metadata. Replies MUST be concise, professional, empathetic English; MUST NOT expose internal reasoning, taxonomy, or another customer's data. Plain text or malformed input MUST be rejected.

#### Scenario: Valid email
- GIVEN a valid email JSON
- WHEN the team completes processing
- THEN it returns a structured English reply with bounded category and issue code

#### Scenario: Invalid input
- GIVEN plain text or invalid email JSON
- WHEN the team is invoked
- THEN it rejects the request without heuristic parsing

### Requirement: Private State and Knowledge Boundaries

The system MUST derive customer facts only from validated input and application-owned `store_records`; ownership MUST match `from_email`. It MUST NOT use `shared_learning` or expose generic SQL. Product and sizing answers MUST use dedicated product knowledge and MUST NOT invent unsupported facts; order facts MUST NOT come from RAG. Bootstrap and mock catalog/order ingestion MUST be idempotent, and the single mock business table MUST uniquely identify each record type/key.

#### Scenario: Foreign order
- GIVEN an order owned by a different email
- WHEN a customer requests it
- THEN the team refuses access without revealing its data

#### Scenario: Missing catalog support
- GIVEN retrieval has no supporting product information
- WHEN a product question is answered
- THEN the reply does not invent dimensions, availability, materials, or policy

### Requirement: Deterministic Refunds

Refund tools MUST reload the persisted USD `Decimal` total, accept no model-supplied amount, validate existence, ownership, eligibility, deadline, and unrefunded status, and perform one transactional refund at most. Totals `<= USD 50.00` MUST use automatic refund; totals `> USD 50.00` MUST use the approval route; either route MUST reject the other threshold. Partial refunds are prohibited.

#### Scenario: Boundary refund
- GIVEN an eligible USD 50.00 order
- WHEN automatic refund is requested
- THEN exactly one refund is recorded

#### Scenario: Repeated or mismatched request
- GIVEN a USD 50.01 order or an already-refunded order
- WHEN automatic or repeated refund is requested
- THEN no additional refund is recorded

### Requirement: Approval Continuation

An over-threshold refund MUST pause for required administrator approval and MUST NOT mutate the order before continuation. On approval or rejection, continuation MUST reload and revalidate the order; approval MAY refund it, while rejection or failed revalidation MUST leave it unchanged. No final refund email SHALL precede resolution.

#### Scenario: Approved continuation
- GIVEN an eligible USD 120.00 order and persisted pending approval
- WHEN an administrator approves and continues the run
- THEN the order is refunded and the final English reply is emitted

#### Scenario: Rejected continuation
- GIVEN a paused refund request
- WHEN its approval is rejected and the run continues
- THEN the order remains unchanged

### Requirement: Idempotent Interaction Record

Completed valid replies MUST create at most one `support_interaction` per `message_id`, retaining run ID and bounded category, issue code, links, and outcome. Paused or malformed output MUST NOT be guessed or recorded; persistence errors MUST NOT suppress a valid reply.

#### Scenario: Resumed run
- GIVEN a post-hook retry after a completed continuation
- WHEN it records the same `message_id`
- THEN one interaction remains available for reporting

### Requirement: Public Surface and Verification

The `customer-support` team MUST coordinate exactly three specialists with distinct roles. Only `customer-support`, `support-insights`, and dedicated store knowledge MUST be registered; operational specialists MUST remain private. Deterministic PostgreSQL tests MUST precede business logic and prove typed input, ownership, thresholds, idempotency, approval lifecycle, bounded taxonomy, aggregation, and registrations; smoke evals MUST additionally prove routing, English, retrieval grounding, isolation, and report fidelity.

#### Scenario: Runtime discovery
- GIVEN AgentOS registrations
- WHEN public components are listed
- THEN the team, insights agent, and store knowledge appear, but specialists do not
