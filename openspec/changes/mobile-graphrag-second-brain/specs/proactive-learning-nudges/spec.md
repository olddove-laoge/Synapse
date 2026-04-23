## ADDED Requirements

### Requirement: Unexplored Branch Reminder
The system SHALL identify unexplored branch nodes and surface at least one daily reminder through widget or notification channel.

#### Scenario: Daily branch reminder push
- **WHEN** user has unresolved branch nodes and reminder window is reached
- **THEN** system sends a reminder containing one branch topic and a direct deep-link to focus view

### Requirement: Cross-Time Knowledge Association Notification
The system MUST detect high-relevance relations between newly captured knowledge and historical nodes and notify user with explainable linkage.

#### Scenario: Notify new-old node relation
- **WHEN** a newly added node has relevance score above configured threshold with an older node
- **THEN** system sends a notification describing why the two nodes are related and provides one-tap view action

### Requirement: User-Controlled Nudge Intensity
The system SHALL allow users to configure reminder frequency and mute categories.

#### Scenario: Reduce notification frequency
- **WHEN** user sets reminder intensity to low
- **THEN** system limits proactive nudges to configured maximum frequency and suppresses non-priority reminders
