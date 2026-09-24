# Support Insights Specification

## Purpose

Provide a separate operator-facing view of persisted customer-support patterns.

## Requirements

### Requirement: Deterministic Insights Report

The agent MUST produce `InsightsReport` with period bounds, total interactions, ranked issue counts, affected products, refund outcomes, and recommendations. Counts, grouping, and refund totals MUST derive from deterministic SQL over completed interaction records; the model MAY explain only those observed results.

#### Scenario: Aggregated report
- GIVEN completed interactions within a requested period
- WHEN a trusted operator requests insights
- THEN totals and top issues equal SQL-derived aggregates

#### Scenario: Duplicate source message
- GIVEN retried processing for one `message_id`
- WHEN insights are generated
- THEN that interaction contributes once

### Requirement: Operator-Facing Reporting Boundary

Support Insights MUST be separately registered as an operator-facing reporting agent and MUST NOT be emitted through customer email replies. Its access follows deployment-wide AgentOS agent-run authorization, not a component-specific administrator role. Reports MUST be on demand; scheduled reporting is out of scope.

#### Scenario: Customer request
- GIVEN a customer team invocation
- WHEN processing completes
- THEN it returns only `CustomerEmailReply`, not an insights report
