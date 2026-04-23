## ADDED Requirements

### Requirement: Chat-Derived Graph Expansion
The system MUST extract candidate entities and relations from each completed Q&A turn and map them to graph expansion suggestions.

#### Scenario: Generate graph suggestions after answer
- **WHEN** assistant completes a response in a learning conversation
- **THEN** system generates candidate nodes and relations linked to current focus node

### Requirement: Human-in-the-Loop Confirmation
The system SHALL require user confirmation before persisting low-confidence graph suggestions.

#### Scenario: Confirm low-confidence suggestion
- **WHEN** a candidate node or relation confidence is below configured threshold
- **THEN** system places it into a confirmation queue and persists only after explicit user approval

### Requirement: Recursive Learning Prompting
The system SHALL generate follow-up exploration questions from newly added nodes to support recursive learning progression.

#### Scenario: Suggest next-step questions
- **WHEN** a new node is added to graph from conversation
- **THEN** system proposes at least three context-relevant follow-up questions for deeper exploration
