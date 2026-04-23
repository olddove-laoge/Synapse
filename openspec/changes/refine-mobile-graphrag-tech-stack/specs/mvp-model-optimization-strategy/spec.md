## ADDED Requirements

### Requirement: Optimization-First MVP Strategy
The system MUST prioritize extraction quality, retrieval quality, reranking quality, and context construction quality before introducing model fine-tuning.

#### Scenario: Plan MVP milestones
- **WHEN** the team defines MVP milestone scope
- **THEN** the plan includes quality optimization tasks for extraction and retrieval, and excludes mandatory fine-tuning tasks

### Requirement: Fine-Tuning Gating Policy
The system SHALL allow fine-tuning only after baseline quality metrics and stability metrics reach predefined thresholds.

#### Scenario: Evaluate fine-tuning eligibility
- **WHEN** baseline metrics are reviewed at milestone checkpoint
- **THEN** fine-tuning is approved only if gating thresholds for quality and reliability are satisfied

### Requirement: Evaluation-Driven Iteration Loop
The system MUST maintain an evaluation loop with repeatable benchmark set and report quality changes per optimization iteration.

#### Scenario: Compare optimization iterations
- **WHEN** a new optimization iteration is completed
- **THEN** the system publishes metric deltas against previous iteration for retrieval relevance and answer faithfulness
