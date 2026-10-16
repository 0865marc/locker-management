# locker-management Specification

## Purpose

Configure physical lockers and identifiable compartments, and report current capacity for parcels at a selected location without reserving space.

## Requirements

### Requirement: Create identifiable lockers and compartments

POST /lockers SHALL create generated locker/compartment UUIDs atomically from a nonempty compartments list of quantity/dimensions/optional enabled batches and optional active defaulting to true. It SHALL accept nullable address, coordinates and location_id, requiring a complete address or non-null location_id at creation. A supplied alias SHALL be trimmed, nonblank and case-sensitive. Success SHALL return 201 full configuration after persistence.

#### Scenario: Configure quantities and physical dimensions
- **WHEN** a locker is created with two batches containing quantities 2 and 3
- **THEN** its configuration contains five identifiable compartments with their requested dimensions and enabled flags, and compartment_count is 5

#### Scenario: Invalid configuration rolls back
- **WHEN** any batch has nonpositive quantity, dimensions outside 1..2147483647, noninteger JSON numbers, boolean numbers, unknown fields, or location_id is blank
- **THEN** HTTP 422 is returned without creating the locker or any compartments

#### Scenario: Legacy creation remains accepted
- **WHEN** a valid creation supplies location_id and omits address/coordinates or supplies them as null
- **THEN** creation succeeds with the original alias and null geographic values without inferring an address or postal code

#### Scenario: New creation needs no arbitrary alias
- **WHEN** a valid creation supplies a complete address and omits location_id or sets it to null
- **THEN** it succeeds with location_id null and that address, whether coordinates are supplied or omitted

#### Scenario: Missing creation locator
- **WHEN** creation has neither a complete address nor a non-null location_id, even if coordinates are supplied
- **THEN** it returns 422 without creating a locker or compartments

### Requirement: Bound compartment creation batches

Locker creation and compartment addition SHALL accept positive integer quantities and at most 1000 new compartments in total per request. The system SHALL validate the sum before materializing compartments or writing data and return 422 when it exceeds 1000. This limit SHALL apply to each request, not to total locker capacity accumulated through multiple requests.

#### Scenario: Oversized batch leaves no writes
- **WHEN** a locker creation or compartment addition request contains batches whose quantities sum to 1001 or more
- **THEN** 422 is returned before materializing cells or writing any locker or compartment, and existing configuration remains unchanged

#### Scenario: Capacity can grow through bounded batches
- **WHEN** valid batches of at most 1000 cells are added in successive requests
- **THEN** each request succeeds even when the locker's resulting total exceeds 1000 compartments

### Requirement: Read locker configuration by location

GET /lockers SHALL return configurations ordered by UUID, optionally filtered by exact trimmed location_id. GET /lockers/{id} SHALL return one configuration or 404. Configurations SHALL expose id, nullable location_id/address/coordinates, active, compartment_count and non-retired compartments with id, dimensions, enabled and occupied. Counts SHALL derive from compartments; occupied SHALL reflect an active custody assignment.

#### Scenario: Multiple lockers at one location
- **WHEN** two lockers share a location and a third has another location
- **THEN** filtering by the shared location returns exactly the first two, and an unknown location returns 200 with an empty list

#### Scenario: Disabled versus retired compartments
- **WHEN** a configuration contains enabled, disabled and retired compartments
- **THEN** enabled and disabled compartments appear and count toward compartment_count, while retired compartments do not

#### Scenario: Historical lockers expose no invented geography
- **WHEN** an existing locker created before geographic values were supported is retrieved
- **THEN** address and coordinates are present as null and its original alias, cells and custody remain unchanged

#### Scenario: Locker without alias remains manageable
- **WHEN** a locker is created with an address and null location_id
- **THEN** it is retrievable by UUID and the unfiltered list, but does not match any location_id filter; availability retains its existing alias-only contract without postal selection or invented aliases

### Requirement: Reconfigure free compartments safely

POST /lockers/{id}/compartments SHALL add a nonempty list of quantity/dimensions/enabled batches atomically and return 201 configuration. PATCH /lockers/{id}/compartments/{cell_id} SHALL accept nonempty dimensions and/or enabled changes and return 200 cell. DELETE on that path SHALL retire a free cell with 204. Any modification or retirement of an occupied cell SHALL return 409 without altering it.

#### Scenario: Change capacity without replacing occupied identities
- **WHEN** new cells are added and a free cell is resized, disabled or retired
- **THEN** occupied cell identities, dimensions and assignments remain unchanged, and derived counts reflect the successful changes

#### Scenario: Occupied and retired cell protection
- **WHEN** a request changes or retires an occupied cell, or targets a retired, unknown or foreign-locker cell
- **THEN** the occupied cell returns 409 unchanged; the retired, unknown or foreign cell returns 404

### Requirement: Control locker operation separately from custody

PATCH /lockers/{id} SHALL atomically accept a nonempty subset of active boolean and address/coordinates, returning 200 configuration. Supplied objects SHALL replace complete values; omission SHALL preserve values and null SHALL clear geographic values, but not active. Inactive lockers SHALL reject new assignments and offer zero capacity while permitting existing parcels to leave. Legacy grouping and compartment ownership SHALL NOT change.

#### Scenario: Inactivate an occupied locker
- **WHEN** an occupied locker becomes inactive and its parcel is subsequently collected or handed over
- **THEN** the exit succeeds and releases that assignment; availability remains zero until reactivation

#### Scenario: Replace geographic metadata safely
- **WHEN** an occupied locker receives complete valid address and coordinate replacements with active omitted
- **THEN** both values change atomically while its active flag, alias, compartments and assignments remain unchanged

#### Scenario: Administrative clearing after creation
- **WHEN** PATCH supplies address null or coordinates null, including for a locker created without an alias
- **THEN** only the supplied values are cleared; the locker remains retrievable by UUID and in the unfiltered list, without fabricating an alias

#### Scenario: Preserve metadata on active-only patch
- **WHEN** a valid active-only patch is applied
- **THEN** existing address and coordinates are preserved, maintaining compatibility with current requests

#### Scenario: Reject invalid metadata patches
- **WHEN** PATCH is empty, includes unknown fields, supplies null active or an invalid/partial address or coordinates object
- **THEN** it returns 422 and leaves the entire configuration unchanged

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

### Requirement: Configure complete Spanish addresses

A non-null address SHALL contain exactly country_code, postal_code, province, city, street and street_number as non-null strings. Country SHALL equal ES and postal code SHALL contain exactly five ASCII digits without spaces. Province, city, street and number SHALL be trimmed and nonblank. The number SHALL remain text. Incomplete or invalid addresses SHALL return 422 without writes; no geographic existence check or inference SHALL be performed.

#### Scenario: Preserve meaningful postal text
- **WHEN** an address uses country ES, postal code "01001", nonblank locality fields and street_number "12B" or "s/n"
- **THEN** it is accepted with leading postal zeroes and textual street number preserved

#### Scenario: Reject unsupported countries and malformed addresses
- **WHEN** an address has a missing/null field, extra field, blank locality text, country other than ES, numeric postal code or non-ASCII/incorrect-length postal digits
- **THEN** the operation returns 422 and neither that address nor any accompanying changes persist

### Requirement: Store optional WGS84 coordinate pairs

Coordinates SHALL be null or an object containing exactly latitude and longitude as finite JSON numbers within [-90,90] and [-180,180]. Booleans, numeric strings, partial pairs, NaN and infinity SHALL be rejected with 422. Coordinates SHALL be optional independently of address and SHALL not affect capacity matching. The system SHALL not infer coordinates or perform radius searches.

#### Scenario: Valid boundaries and absence
- **WHEN** valid boundary coordinates or null are supplied
- **THEN** the pair or absence is preserved, independently of whether an address is present

#### Scenario: Invalid coordinate leaves configuration intact
- **WHEN** a patch combines a valid active/address change with an invalid or partial coordinate pair
- **THEN** it returns 422 without persisting any of the requested changes
