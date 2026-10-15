## ADDED Requirements

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
