## ADDED Requirements

### Requirement: Cross-Language API Contract
The system MUST define a versioned contract for Go-to-Python requests and responses, including schema version, idempotency key, trace ID, and error code.

#### Scenario: Validate contract version compatibility
- **WHEN** Go invokes Python with an unsupported contract version
- **THEN** Python rejects the request with a version-compatibility error code and upgrade guidance

### Requirement: Standardized Error Taxonomy
The system SHALL use a shared error taxonomy for retryable, non-retryable, validation, and degraded-mode errors.

#### Scenario: Classify retryable error
- **WHEN** Python returns a transient dependency timeout
- **THEN** Go classifies it as retryable and executes configured retry policy

### Requirement: Cross-Language Timeout and Circuit Control
The system MUST enforce timeout, circuit-breaker, and fallback rules for Go-Python calls.

#### Scenario: Open circuit after repeated failures
- **WHEN** failure rate exceeds configured threshold within observation window
- **THEN** Go opens the circuit and routes subsequent requests to degraded path until recovery conditions are met
