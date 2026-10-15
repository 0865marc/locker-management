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

### Requirement: Persist shared physical capacity with referential integrity

Persistence SHALL preserve lockers, identifiable cells and parcel assignments, including assignment history after release. Every assignment SHALL reference exactly one existing delivery or return and one existing cell. Each parcel SHALL have at most one assignment, and each cell SHALL have at most one active assignment across both parcel types. Missing references, invalid dimensions and release before assignment SHALL be rejected.

#### Scenario: Invalid shared occupancy
- **WHEN** a write attempts two active assignments for one cell, references a missing parcel/cell, references both parcel types or neither, or assigns the same parcel twice
- **THEN** persistence rejects it without altering existing records

#### Scenario: Retrieve assignment after release
- **WHEN** a completed parcel is retrieved using new repository instances after its cell is resized or retired
- **THEN** its original assignment identity, parcel dimensions and reception/exit timestamps remain available

### Requirement: Commit reception and occupancy together

A locker reception SHALL commit the new parcel and its assignment together, or neither. Competing delivery and return receptions SHALL share the same physical capacity. When only one compatible cell remains, exactly one competing valid reception SHALL succeed and the other SHALL observe a capacity conflict after the winner commits, without leaving an unassigned parcel.

#### Scenario: Last cell across both flows
- **WHEN** independent PostgreSQL requests concurrently receive one delivery and one return into the last compatible cell
- **THEN** one returns 201 and the other 409 FULL, with exactly one new parcel and one active assignment

#### Scenario: Failed reception before commit
- **WHEN** a failure is injected after parcel/assignment writes but before commit
- **THEN** neither record persists, capacity remains available and a later reception succeeds

### Requirement: Commit exit and specific assignment release together

An assigned parcel's successful custody exit SHALL commit its state/timestamp and release of its own active assignment atomically. Failed or losing exits SHALL not release capacity. A later occupant of the same cell SHALL never be affected by an operation on a previously completed parcel. Successful responses SHALL follow commit.

#### Scenario: Failure between custody update and commit
- **WHEN** an assigned parcel's exit fails after its state update and before commit
- **THEN** the parcel remains pending and its assignment remains active; a later valid exit can succeed

#### Scenario: Concurrent exits and reoccupation
- **WHEN** two exits compete for parcel A, the winner releases it, parcel B occupies the cell and the old loser is retried
- **THEN** only one A exit succeeds, A's timestamp remains unchanged and B's active assignment is preserved

### Requirement: Serialize capacity changes with reception and release

Configuration, reception and release affecting the same locker SHALL resolve against committed state without invalidating occupied cells. A reception SHALL re-evaluate configuration and capacity after waiting for a competing operation. Temporary contention SHALL not itself be reported as full capacity; infrastructure failures SHALL remain distinguishable from business conflicts.

#### Scenario: Reception competes with configuration
- **WHEN** reception and resizing, disabling or retiring its candidate cell run concurrently
- **THEN** either reception wins and the configuration change returns 409, or configuration wins and reception uses the new valid configuration or returns a capacity conflict without saving a parcel

#### Scenario: Competing reception rolls back
- **WHEN** the first of two contenders for the last cell rolls back before commit
- **THEN** the waiting contender can acquire that cell and does not report FULL solely because the first transaction held a lock
