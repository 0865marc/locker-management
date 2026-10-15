## Purpose

Configure physical lockers and identifiable compartments, and report current capacity for parcels at a selected location without reserving space.

## ADDED Requirements

### Requirement: Create identifiable lockers and compartments

The system SHALL create lockers with generated UUIDs, trimmed nonblank case-sensitive location_id and active status. POST /lockers SHALL accept location_id, optional active defaulting to true, and a nonempty compartments list of quantity/dimensions/optional enabled batches. It SHALL create distinct compartment UUIDs and return 201 with the full configuration only after atomic persistence.

#### Scenario: Configure quantities and physical dimensions
- **WHEN** a locker is created with two batches containing quantities 2 and 3
- **THEN** its configuration contains five identifiable compartments with their requested dimensions and enabled flags, and compartment_count is 5

#### Scenario: Invalid configuration rolls back
- **WHEN** any batch has nonpositive quantity, dimensions outside 1..2147483647, noninteger JSON numbers, boolean numbers, unknown fields, or location_id is blank
- **THEN** HTTP 422 is returned without creating the locker or any compartments

### Requirement: Bound compartment creation batches

Locker creation and compartment addition SHALL accept positive integer quantities and at most 1000 new compartments in total per request. The system SHALL validate the sum before materializing compartments or writing data and return 422 when it exceeds 1000. This limit SHALL apply to each request, not to total locker capacity accumulated through multiple requests.

#### Scenario: Oversized batch leaves no writes
- **WHEN** a locker creation or compartment addition request contains batches whose quantities sum to 1001 or more
- **THEN** 422 is returned before materializing cells or writing any locker or compartment, and existing configuration remains unchanged

#### Scenario: Capacity can grow through bounded batches
- **WHEN** valid batches of at most 1000 cells are added in successive requests
- **THEN** each request succeeds even when the locker's resulting total exceeds 1000 compartments

### Requirement: Read locker configuration by location

GET /lockers SHALL return configurations ordered by UUID, optionally filtered by exact trimmed location_id. GET /lockers/{id} SHALL return one configuration or 404. Configurations SHALL expose id, location_id, active, compartment_count and non-retired compartments with id, dimensions, enabled and occupied. Counts SHALL be derived from compartments; occupied SHALL reflect an active custody assignment.

#### Scenario: Multiple lockers at one location
- **WHEN** two lockers share a location and a third has another location
- **THEN** filtering by the shared location returns exactly the first two, and an unknown location returns 200 with an empty list

#### Scenario: Disabled versus retired compartments
- **WHEN** a configuration contains enabled, disabled and retired compartments
- **THEN** enabled and disabled compartments appear and count toward compartment_count, while retired compartments do not

### Requirement: Reconfigure free compartments safely

POST /lockers/{id}/compartments SHALL add a nonempty list of quantity/dimensions/enabled batches atomically and return 201 configuration. PATCH /lockers/{id}/compartments/{cell_id} SHALL accept nonempty dimensions and/or enabled changes and return 200 cell. DELETE on that path SHALL retire a free cell with 204. Any modification or retirement of an occupied cell SHALL return 409 without altering it.

#### Scenario: Change capacity without replacing occupied identities
- **WHEN** new cells are added and a free cell is resized, disabled or retired
- **THEN** occupied cell identities, dimensions and assignments remain unchanged, and derived counts reflect the successful changes

#### Scenario: Occupied and retired cell protection
- **WHEN** a request changes or retires an occupied cell, or targets a retired, unknown or foreign-locker cell
- **THEN** the occupied cell returns 409 unchanged; the retired, unknown or foreign cell returns 404

### Requirement: Control locker operation separately from custody

PATCH /lockers/{id} SHALL accept only active as a boolean and return 200 configuration. An inactive locker SHALL reject new custody assignments and offer zero available cells, while allowing existing parcels to leave and release their own cells. Location and compartment ownership SHALL NOT change through this operation.

#### Scenario: Inactivate an occupied locker
- **WHEN** an occupied locker becomes inactive and its parcel is subsequently collected or handed over
- **THEN** the exit succeeds and releases that assignment; availability remains zero until reactivation

### Requirement: Match parcels using usable physical dimensions

Parcel and cell dimensions SHALL be integer millimetres in 1..2147483647 named width_mm, height_mm and depth_mm. Compatibility SHALL allow orthogonal rotations by comparing the sorted dimensions componentwise, including exact equality. Allocation SHALL choose the compatible free enabled non-retired cell with lowest volume, breaking ties by ascending UUID.

#### Scenario: Rotation and smallest fitting cell
- **WHEN** a parcel fits a smaller cell only after rotation and also fits a larger cell
- **THEN** the smaller cell is compatible and is preferred; a parcel exceeding one sorted dimension is incompatible even if its volume is lower

### Requirement: Query coherent availability without reservation

GET /lockers/availability SHALL require location_id and width_mm/height_mm/depth_mm query parameters and return 200 with location_id, parcel_dimensions, checked_at UTC, reason and lockers. Each locker result SHALL include locker_id, active, compatible_count, available_count and reason. The snapshot SHALL be coherent and read-only; reception SHALL recheck current capacity independently.

#### Scenario: Capacity counts
- **WHEN** a locker has compatible free, occupied, disabled and retired cells
- **THEN** compatible_count includes only enabled non-retired compatible cells, and available_count includes only their free cells if active, otherwise zero

#### Scenario: Distinct absence reasons
- **WHEN** availability is queried for no lockers, only inactive lockers, active lockers without compatible cells, or active lockers with all compatible cells occupied
- **THEN** the overall reason is respectively NO_LOCKER, LOCKER_INACTIVE, NO_COMPATIBLE_CELL or FULL, with zero available_count

#### Scenario: Multiple locker outcomes
- **WHEN** matching lockers have mixed outcomes
- **THEN** overall reason is AVAILABLE if any is available, otherwise FULL if an active locker has occupied compatible cells, otherwise NO_COMPATIBLE_CELL if any locker is active, otherwise LOCKER_INACTIVE; each result retains its own reason

#### Scenario: Consultation does not hold space
- **WHEN** two clients observe the same last available cell and then separately request reception
- **THEN** consultation creates no reservation and at most one reception acquires the cell; the other receives a capacity conflict
