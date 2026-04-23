## ADDED Requirements

### Requirement: Go Control Plane Responsibilities
The system MUST implement the control-plane services in Go, including API gateway routing, authentication, request throttling, task orchestration, and notification scheduling.

#### Scenario: Route request through Go control plane
- **WHEN** a client submits a capture or query request
- **THEN** the Go service authenticates the request, applies quota checks, and dispatches processing tasks to downstream services

### Requirement: Reliable Task Orchestration
The system SHALL provide idempotent task orchestration in Go with retry policy and dead-letter handling.

#### Scenario: Retry transient downstream failure
- **WHEN** a downstream call fails due to transient network or timeout errors
- **THEN** the Go orchestrator retries the task according to backoff policy and records failure context for observability

### Requirement: Unified Control-Plane Observability
The system MUST emit trace ID, latency, and failure metrics for each control-plane request.

#### Scenario: Trace an end-to-end request
- **WHEN** an operator inspects a failed request
- **THEN** the system provides a traceable request path across ingress, orchestration, and downstream invocation
