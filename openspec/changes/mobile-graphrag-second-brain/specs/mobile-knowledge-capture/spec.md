## ADDED Requirements

### Requirement: Multi-Entry Knowledge Capture
The system SHALL support capturing knowledge from system share sheets, on-screen text selection, and voice input, and MUST assign each capture a unique source identifier.

#### Scenario: Capture from system share
- **WHEN** user shares a webpage or article to the app from another mobile application
- **THEN** system creates a new capture record with source type `share` and preserves source metadata (title, url, timestamp)

#### Scenario: Capture from voice note
- **WHEN** user records a voice idea through the mobile assistant entry
- **THEN** system transcribes speech to text and stores the transcript as a pending knowledge capture with source type `voice`

### Requirement: Normalized Ingestion Schema
The system MUST convert all capture inputs into a normalized graph-ingestion draft containing entities, candidate relations, confidence score, and capture timestamp.

#### Scenario: Normalize heterogeneous inputs
- **WHEN** capture records from different entry types are submitted to ingestion
- **THEN** system outputs a unified draft payload with consistent required fields for downstream graph processing

### Requirement: Privacy-Aware Capture Processing
The system SHALL provide a privacy mode for sensitive content where raw source content is not uploaded, and only extracted structured facts are synchronized.

#### Scenario: Sensitive local document capture
- **WHEN** user marks a capture as sensitive before processing
- **THEN** system keeps raw content on device and uploads only structured entities and relations with anonymized source reference
