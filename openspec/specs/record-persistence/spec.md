# Record Persistence Specification

## Purpose

Keep deliveries and returns in persistent storage separated by type, preserving their identity and allowing operations to continue after a failed write.

## Requirements

### Requirement: Preserve identity and content by record type

Persistence SHALL preserve each valid parcel's UUID, tracking data, contact data, optional deadline, custody state, and reception and exit timestamps, retaining null optional values and timezone-aware instants. It SHALL keep deliveries separate from returns and support retrieval from new instances connected to the same prepared database.

#### Scenario: Retrieve records from another instance
- **WHEN** a delivery and an independent return are saved and retrieved through new instances connected to the same database
- **THEN** each list contains its complete saved representation without mixing record types or losing optional values or timestamp precision

#### Scenario: Retrieve a completed parcel
- **WHEN** a successful custody exit is retrieved through another instance
- **THEN** the final state and its single corresponding exit timestamp are preserved with the original identity and reception data

### Requirement: Isolate a failed write

Each write SHALL be committed when completed successfully or rolled back if it fails. An insertion with a duplicate UUID SHALL fail without replacing the existing record or preventing a subsequent valid write.

#### Scenario: Duplicate UUID followed by a valid write
- **WHEN** an attempt is made to save an entity with the UUID of another already saved in its collection, followed by saving an entity with a new UUID
- **THEN** the duplicate insertion fails, the original record remains, and the subsequent write can complete and be retrieved

### Requirement: Commit at most one exit per parcel

Persistence SHALL atomically accept an exit only while its parcel is in the corresponding pending state. Concurrent repeated or incompatible exit requests MUST commit at most one transition; a rejected contender SHALL observe a conflict without changing the winning state or timestamp. A successful HTTP response SHALL follow the successful commit.

#### Scenario: Competing delivery exits
- **WHEN** independent requests attempt collection and carrier return for the same pending delivery concurrently
- **THEN** exactly one returns `200`, the other returns `409`, and subsequent reads contain only the winning state and its exit timestamp

#### Scenario: Competing repeated handovers
- **WHEN** independent requests attempt to hand over the same pending return concurrently
- **THEN** exactly one returns `200`, the other returns `409`, and the winning handover timestamp remains unchanged

#### Scenario: Failed exit persistence
- **WHEN** persisting a custody transition fails before commit
- **THEN** the pending parcel remains unchanged and a later valid transition can still succeed
