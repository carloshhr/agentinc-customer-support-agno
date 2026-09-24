# External Support Inbox Specification

## Purpose

Define the externally hosted operator inbox boundary without widening AgentOS access or retiring the proven legacy inbox prematurely.

## Requirements

### Requirement: Safe AgentOS Support DTO Boundary

AgentOS MUST expose only allow-listed, typed support-thread, detail, and send-result DTOs for the Customer Support team. It MUST NOT disclose member responses, tool data, reasoning, approval payloads, private order/product data, or raw runs.

#### Scenario: Safe typed response
- GIVEN a typed Customer Support run
- WHEN an authorized BFF reads its support thread
- THEN AgentOS returns only the documented safe DTO fields

### Requirement: BFF-Only AgentOS Authorization

In production, AgentOS MUST authenticate every support route and authorize only the designated BFF service credential with route-appropriate read or send permission. Any other authenticated principal MUST be denied.

#### Scenario: Credential denial matrix
- GIVEN no, invalid, unrelated, or under-scoped credentials
- WHEN each calls a support route in production
- THEN no or invalid credentials receive 401 and all others receive 403

### Requirement: Operator Session, CSRF, and CORS Boundary

The BFF MUST authenticate operators with application-owned credentials, issue opaque secure HttpOnly sessions, and require exact allowed origins plus CSRF validation for mutations. It MUST NOT enumerate accounts or allow credentialed wildcard CORS.

#### Scenario: Forged or invalid access
- GIVEN a missing session, disallowed origin, or invalid CSRF token
- WHEN a protected request is made
- THEN the BFF denies it without disclosing account or session details

### Requirement: Typed Narrow BFF Proxy

The BFF MUST expose only explicit inbox routes, validate bounded browser input and expected AgentOS DTOs, and fail closed on schema deviation. It MUST NOT provide a generic AgentOS proxy, forward sensitive browser headers, expose its PAT, or retry sends without an idempotency contract.

#### Scenario: Unexpected upstream response
- GIVEN AgentOS returns malformed data, timeout, or server failure
- WHEN the BFF handles the response
- THEN it returns a stable gateway-safe error and redacted telemetry

### Requirement: Frontend Authentication Contract

The frontend MUST call only the configured BFF origin with credentialed requests, retain CSRF data only in memory, and withhold inbox requests and views until session validation succeeds. It MUST distinguish 401, 403, 429, and gateway failures without rendering unsafe content.

#### Scenario: Restored session
- GIVEN session validation succeeds
- WHEN the frontend loads
- THEN it displays the operator context and may request inbox data

#### Scenario: Expired session
- GIVEN a BFF request returns 401
- WHEN the frontend receives it
- THEN it clears authenticated state and shows the signed-out flow

### Requirement: Application Data Ownership and Migration

The BFF MUST own operator, session, and audit data through versioned, reversible migration controls. It MUST NOT query or alter undocumented Agno persistence; raw passwords, PATs, session tokens, CSRF values, email bodies, and raw AgentOS payloads MUST NOT be stored in audit data.

#### Scenario: Applied operator migration
- GIVEN an approved migration executes
- WHEN it completes
- THEN only application-owned state is created or changed and its version is recorded

#### Scenario: Audit redaction
- GIVEN an operator action is audited
- WHEN the audit record is persisted
- THEN it contains attribution and outcome but no forbidden secret or content

### Requirement: Independent Deployment Boundary

The frontend and BFF MUST deploy independently from AgentOS; browsers MUST NOT call AgentOS directly, and the BFF PAT MUST exist only in BFF server configuration. Production and preview origins MUST be explicitly isolated.

#### Scenario: Staging deployment
- GIVEN approved staging origins and BFF configuration
- WHEN a test operator completes login, read, send, and logout checks
- THEN requests traverse only frontend-to-BFF-to-AgentOS with the BFF identity upstream

### Requirement: Staged Cutover, Rollback, and Reference Preservation

The first implementation slice MUST be AgentOS DTO/privacy contract pinning and production authorization proof only. `customer-support-inbox` artifacts MUST remain immutable. Legacy hosting MUST remain deployable until external production observation and rollback readiness are verified; rollback MUST disable or revoke external components before weakening AgentOS authorization or deleting data.

#### Scenario: Pre-cutover failure
- GIVEN external staging or production checks fail before legacy removal
- WHEN rollback is invoked
- THEN operators can return to the legacy inbox while AgentOS authorization and data remain intact
