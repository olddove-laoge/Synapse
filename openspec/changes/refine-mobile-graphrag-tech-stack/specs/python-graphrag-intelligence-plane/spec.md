## ADDED Requirements

### Requirement: Python Intelligence Plane Responsibilities
The system MUST implement GraphRAG intelligence services in Python, including entity-relation extraction, retrieval reranking, graph-aware context assembly, and answer summarization.

#### Scenario: Execute GraphRAG processing
- **WHEN** the control plane submits a reasoning task
- **THEN** the Python service performs extraction, retrieval, and answer generation and returns structured results

### Requirement: Structured Intelligence Output
The system SHALL return Python intelligence results in a structured schema containing answer text, supporting evidence, confidence, and graph update candidates.

#### Scenario: Return explainable answer package
- **WHEN** the intelligence plane completes a query task
- **THEN** the response includes answer content and machine-readable evidence references for explainability

### Requirement: Degradable Intelligence Mode
The system MUST support fallback to lightweight retrieval-only response mode when advanced reasoning components are unavailable.

#### Scenario: Fallback during model pipeline outage
- **WHEN** advanced graph reasoning module is unavailable
- **THEN** the service returns retrieval-only responses and marks the result mode as degraded
