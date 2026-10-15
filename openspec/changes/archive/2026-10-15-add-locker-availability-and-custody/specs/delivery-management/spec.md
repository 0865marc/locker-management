## MODIFIED Requirements

### Requirement: Validate the HTTP creation body

The HTTP adapter SHALL require text `tracking_number`, `carrier_code`, and `recipient_name`, allow nullable text `recipient_phone` and nullable timezone-aware `pickup_deadline_at`, and reject incorrect types, missing required fields, unknown fields, or system-managed fields with HTTP `422` without executing creation. Domain validation SHALL reject required text that is blank after trimming before persistence. It SHALL additionally accept the optional locker_id and parcel_dimensions pair defined below.

#### Scenario: Invalid body
- **WHEN** a required field is missing, null, or a list, or a deadline lacks a timezone
- **THEN** HTTP `422` is returned without invoking delivery creation

#### Scenario: Empty required text
- **WHEN** tracking, carrier, or recipient is empty or whitespace-only
- **THEN** HTTP `422` is returned and no delivery is saved

#### Scenario: Legacy or system-managed input
- **WHEN** a request includes `address`, `delivery_instructions`, `storage_location`, a supplied UUID, status, reception date, or exit date
- **THEN** HTTP `422` is returned without invoking delivery creation


## ADDED Requirements

### Requirement: Accept optional locker reception data

POST /deliveries SHALL accept locker_id and parcel_dimensions together as non-null values, or both absent/null for unassigned reception. Dimensions SHALL follow locker-management. Partial pairs, malformed identifiers, invalid dimensions and supplied compartment_id SHALL return 422 before persistence. A valid unknown locker SHALL return 404.

#### Scenario: Existing client and historical record
- **WHEN** a valid existing request omits locker data or an unassigned historical delivery is listed
- **THEN** current custody behavior remains available and the response includes locker_id, compartment_id and parcel_dimensions as null

#### Scenario: Partial assignment input
- **WHEN** only locker_id or only parcel_dimensions is supplied non-null, or compartment_id is supplied
- **THEN** the request returns 422 and creates neither delivery nor occupancy

### Requirement: Receive a delivery into available shared capacity

For a valid locker reception, the system SHALL atomically persist the delivery and its chosen cell assignment before returning 201. It SHALL use locker-management compatibility and selection rules. An inactive locker, no compatible enabled cell, or no free compatible cell SHALL return 409 with detail containing code and message, using LOCKER_INACTIVE, NO_COMPATIBLE_CELL or FULL respectively, without creating the delivery.

#### Scenario: Assigned reception
- **WHEN** a valid delivery is received into an active locker with capacity
- **THEN** 201 includes locker_id, selected compartment_id and parcel_dimensions, and that cell becomes unavailable to both delivery and return receptions

#### Scenario: Capacity failure
- **WHEN** reception fails because the locker is inactive, incompatible or full
- **THEN** 409 exposes the corresponding reason and neither a delivery nor assignment is created

### Requirement: Preserve delivery assignment in representations

All delivery creation, list and exit representations SHALL include locker_id, compartment_id and parcel_dimensions together or all null. Assigned values SHALL remain reconstructible and unchanged after exit, subsequent cell resizing or retirement. Parcel dimensions SHALL represent the received parcel, not the cell dimensions.

#### Scenario: Retrieve a completed assigned delivery
- **WHEN** a delivery exits, its free cell is resized or retired and the delivery is read again
- **THEN** the response retains the original locker and compartment identity and parcel dimensions alongside its terminal custody state

### Requirement: Release the delivery cell with its winning exit

Successful collect and return-to-carrier operations SHALL release exactly the delivery's own active assignment in the same committed operation as the state change. A conflict or failure SHALL leave both custody and occupancy unchanged. Existing exit validation and timestamps SHALL remain applicable; an inactive locker SHALL not prevent exit.

#### Scenario: Exit and reuse
- **WHEN** an assigned delivery is collected or returned to its carrier
- **THEN** that cell becomes available after the successful commit and can receive a delivery or return

#### Scenario: Repeated old exit cannot release a new occupant
- **WHEN** delivery A exits, parcel B takes the same cell, and an exit of A is repeated
- **THEN** A returns 409 and B remains the active occupant with unchanged data
