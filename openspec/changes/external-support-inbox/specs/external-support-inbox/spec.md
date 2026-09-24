# Delta for External Support Inbox

## ADDED Requirements

### Requirement: Production Readiness Without Separate Staging

The change MUST waive a separate staging BFF/frontend environment and MUST replace it with compensating local, CI, security, synthetic, and production-preflight checks before production traffic is switched.

#### Scenario: Compensating checks complete

- GIVEN no separate staging environment or staging credentials are provisioned
- WHEN local and CI security, build, migration, bundle-secret, and synthetic login/read/send/audit/logout/denial checks complete
- THEN the release MAY proceed to production preflight

#### Scenario: Production preflight blocks cutover

- GIVEN production configuration, migration state, operator provisioning, exact CORS/TLS, PAT principal and scopes, logging/redaction, health checks, alerting, or rollback readiness is unverified
- WHEN cutover is requested
- THEN external traffic MUST remain on the legacy hosting path

### Requirement: Customer Support Behavior Preservation

The change MUST preserve the existing `customer-support-inbox` behavior and MUST NOT modify its artifacts or weaken its deployability while the external inbox is introduced or rolled back.

#### Scenario: Existing inbox remains available

- GIVEN the external BFF/frontend is unavailable or its cutover criteria are incomplete
- WHEN an operator accesses the support workflow
- THEN the unchanged `customer-support-inbox` deployment remains available as the fallback

## MODIFIED Requirements

### Requirement: BFF-Only AgentOS Authorization

In production, AgentOS MUST authenticate every support route and authorize only the designated BFF service credential with route-appropriate read or send permission. Any other authenticated principal MUST be denied. Local and CI checks, plus production preflight and smoke checks, MUST prove this credential and scope matrix before external traffic is enabled.
(Previously: Production AgentOS support routes authorized only the designated BFF service credential, with denial for other principals.)

#### Scenario: Credential denial matrix

- GIVEN no, invalid, unrelated, or under-scoped credentials
- WHEN each calls a support route in production or in the authorization test harness
- THEN no or invalid credentials receive 401 and all others receive 403

#### Scenario: Authorization proof gates traffic

- GIVEN the designated BFF principal, route scopes, and safe DTO privacy checks have not been proven
- WHEN production cutover is requested
- THEN the external route MUST remain disabled

### Requirement: Independent Deployment Boundary

The frontend and BFF MUST deploy independently from AgentOS; browsers MUST call only the configured BFF origin; and the BFF PAT MUST exist only in BFF server configuration. Production origins MUST be explicitly allowlisted, and any enabled preview MUST use isolated data, origin, PAT, and database settings. A separate staging deployment MUST NOT be a prerequisite when the compensating readiness checks are complete.
(Previously: The frontend and BFF deployed independently, with a staging deployment scenario requiring frontend-to-BFF-to-AgentOS checks.)

#### Scenario: Browser-to-BFF-only traffic

- GIVEN the frontend is configured for an approved BFF origin
- WHEN an operator logs in, reads inbox data, sends a permitted message, or logs out
- THEN every browser request goes to the BFF and AgentOS sees only the BFF identity

#### Scenario: Preview isolation

- GIVEN previews are enabled
- WHEN a preview deployment is used
- THEN it MUST use settings isolated from production data, origin, PAT, and database resources

### Requirement: Staged Cutover, Rollback, and Reference Preservation

The first implementation slice MUST retain the AgentOS DTO/privacy contract and production authorization proof. `customer-support-inbox` artifacts MUST remain immutable. Legacy hosting MUST remain deployable until production read-only smoke checks, observation, controlled-send safety, and rollback readiness are verified. Rollback MUST disable external routing and, when needed, revoke the BFF PAT or revert the BFF/frontend independently before weakening AgentOS authorization or deleting operator or audit data.
(Previously: Legacy hosting remained deployable until external production observation and rollback readiness were verified, with rollback preserving AgentOS authorization and data.)

#### Scenario: Read-only-first cutover

- GIVEN production preflight has passed and legacy hosting remains deployable
- WHEN cutover begins
- THEN the external inbox MUST be observed with read-only smoke checks before any send is attempted

#### Scenario: Controlled send gate

- GIVEN read-only smoke checks have passed
- WHEN a production send is tested
- THEN it MUST target an explicitly safe deterministic target, use one upstream attempt with an auditable request ID, and avoid automatic retry or deduplication until an idempotency contract is approved

#### Scenario: Pre-cutover failure

- GIVEN external production checks or rollback rehearsal fail before legacy removal
- WHEN rollback is invoked
- THEN operators MUST be returned to the unchanged legacy inbox while AgentOS authorization and operator/audit data remain intact

#### Scenario: Legacy removal exit criteria

- GIVEN production observation and rollback readiness have not been verified
- WHEN legacy static serving removal is requested
- THEN the legacy hosting path MUST NOT be removed
