## ADDED Requirements

### Requirement: Focus-Centric Graph View
The system SHALL render a focus view that displays only the current focus node and its first-order related nodes.

#### Scenario: Open focus view for a node
- **WHEN** user opens a knowledge node in graph view
- **THEN** system displays the selected node at center and shows only one-hop neighbors around it

### Requirement: Card-Based Drill-Down Navigation
The system MUST support card-based drill-down where tapping a related node transitions it into the new focus node with animated context preservation.

#### Scenario: Drill down to related concept
- **WHEN** user taps a related node card in focus view
- **THEN** system updates the selected related node as new center and retains previous center in navigation history

### Requirement: Progressive Neighborhood Loading
The system SHALL load graph neighbors progressively to keep interaction responsive on mobile networks and low-end devices.

#### Scenario: Load additional neighbors on demand
- **WHEN** user requests more related nodes from the current focus
- **THEN** system loads additional neighbors asynchronously without blocking current view interactions
