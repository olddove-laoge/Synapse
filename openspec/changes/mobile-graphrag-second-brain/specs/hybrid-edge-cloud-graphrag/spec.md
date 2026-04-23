## ADDED Requirements

### Requirement: Edge-Cloud Responsibility Routing
The system MUST route OCR, ASR, and lightweight entity extraction to edge execution, and route community detection, cross-document inference, and global summarization to cloud execution.

#### Scenario: Route heavy inference to cloud
- **WHEN** graph processing request includes cross-document relation inference
- **THEN** system dispatches the task to cloud pipeline and marks task type as `cloud-required`

### Requirement: Resilient Synchronization Pipeline
The system SHALL maintain a reliable synchronization queue between edge and cloud with retry and idempotency guarantees.

#### Scenario: Retry failed sync task
- **WHEN** network interruption causes sync failure
- **THEN** system retries task according to backoff policy without creating duplicate graph updates

### Requirement: Graceful Degradation
The system MUST provide degraded local capabilities when cloud inference is unavailable.

#### Scenario: Cloud unavailable fallback
- **WHEN** cloud reasoning service is unreachable
- **THEN** system continues local capture and focus-view exploration using edge-extracted facts only
