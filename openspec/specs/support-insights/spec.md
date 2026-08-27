# Support Insights Specification

## Purpose

Provide a separate administrator-facing view of persisted customer-support patterns.

## Requirements

### Requirement: Deterministic Insights Report

The agent MUST produce `InsightsReport` with period bounds, total interactions, ranked issue counts, affected products, refund outcomes, and recommendations. Counts, grouping, and refund totals MUST derive from deterministic SQL over completed interaction records; the model MAY explain only those observed results.

#### Scenario: Aggregated report
- GIVEN completed interactions within a requested period
- WHEN an administrator requests insights
- THEN totals and top issues equal SQL-derived aggregates

#### Scenario: Duplicate source message
- GIVEN retried processing for one `message_id`
- WHEN insights are generated
- THEN that interaction contributes once

### Requirement: Administrator-Only Reporting Boundary

Support insights MUST be separately registered from the customer team and MUST NOT be emitted through customer email replies. Reports MUST be on demand; scheduled reporting is out of scope.

#### Scenario: Customer request
- GIVEN a customer team invocation
- WHEN processing completes
- THEN it returns only `CustomerEmailReply`, not an insights report
