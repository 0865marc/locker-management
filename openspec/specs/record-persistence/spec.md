# Record Persistence Specification

## Purpose

Keep deliveries and returns in persistent storage separated by type, preserving their identity and allowing operations to continue after a failed write.

## Requirements

### Requirement: Preserve identity and content by record type

Persistence SHALL preserve the UUID and text of valid saved entities, keep deliveries separate from returns, and allow them to be retrieved from new instances connected to the same prepared database.

#### Scenario: Retrieve records from another instance
- **WHEN** a delivery and a return are saved and retrieved from new instances connected to the same database
- **THEN** each list contains its record with the saved UUID and text, without mixing deliveries and returns

### Requirement: Isolate a failed write

Each write SHALL be committed when completed successfully or rolled back if it fails. An insertion with a duplicate UUID SHALL fail without replacing the existing record or preventing a subsequent valid write.

#### Scenario: Duplicate UUID followed by a valid write
- **WHEN** an attempt is made to save an entity with the UUID of another already saved in its collection, followed by saving an entity with a new UUID
- **THEN** the duplicate insertion fails, the original record remains, and the subsequent write can complete and be retrieved
