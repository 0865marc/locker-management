## MODIFIED Requirements

### Requirement: Validate the HTTP creation body

The HTTP adapter SHALL require text `tracking_number` and `carrier_code`, allow nullable text `sender_name`, and reject incorrect types, missing required fields, unknown fields, or system-managed fields with HTTP `422` without executing creation. Domain validation SHALL reject required text that is blank after trimming before persistence. It SHALL additionally accept the optional locker_id and parcel_dimensions pair defined below.

#### Scenario: Invalid body
- **WHEN** a required field is missing, null, or a list, or a non-text sender is supplied
- **THEN** HTTP `422` is returned without invoking return creation

#### Scenario: Empty required text
- **WHEN** tracking or carrier is empty or whitespace-only
- **THEN** HTTP `422` is returned and no return is saved

#### Scenario: Legacy or unapproved input
- **WHEN** a request includes `reason`, `item_sku`, `quantity`, `requested_resolution`, `storage_location`, `sender_phone`, a supplied UUID, state, or timestamp
- **THEN** HTTP `422` is returned without invoking return creation


## ADDED Requirements

### Requirement: Accept optional return locker reception data

POST /returns SHALL accept locker_id and parcel_dimensions together as non-null values, or both absent/null for unassigned reception. Dimensions SHALL follow locker-management. Partial pairs, malformed identifiers, invalid dimensions and supplied compartment_id SHALL return 422 before persistence. A valid unknown locker SHALL return 404. No associated delivery SHALL be required.

#### Scenario: Existing request and historical return
- **WHEN** a valid request omits locker data or an unassigned historical return is listed
- **THEN** current behavior remains available and locker_id, compartment_id and parcel_dimensions appear as null

#### Scenario: Invalid assignment input
- **WHEN** only one assignment input is non-null, dimensions are invalid, or compartment_id is supplied
- **THEN** 422 is returned without saving a return or occupancy

### Requirement: Receive a return into available shared capacity

For locker reception, the system SHALL atomically persist the return and chosen cell assignment before returning 201. It SHALL use locker-management compatibility and selection rules. An inactive locker, no compatible enabled cell, or no free compatible cell SHALL return 409 with detail containing code and message, using LOCKER_INACTIVE, NO_COMPATIBLE_CELL or FULL respectively, without creating the return.

#### Scenario: Delivery and return share capacity
- **WHEN** a delivery already occupies the locker's only compatible cell and a return is received there
- **THEN** 409 FULL is returned without saving the return; after the delivery exits, a new return can receive that cell

### Requirement: Preserve return assignment in representations

All return creation, list and handover representations SHALL include locker_id, compartment_id and parcel_dimensions together or all null. Assigned values SHALL remain reconstructible and unchanged after handover, subsequent cell resizing or retirement. Parcel dimensions SHALL describe the received parcel.

#### Scenario: Retrieve a completed assigned return
- **WHEN** a return is handed over and its cell is later changed or retired
- **THEN** subsequent reads retain its original locker, compartment and parcel dimensions alongside HANDED_OVER and its original handover timestamp

### Requirement: Release the return cell with its winning handover

A successful handover SHALL release exactly that return's active assignment in the same committed operation as the custody change. A conflict or failure SHALL leave state and occupancy unchanged. Existing validation and timestamps SHALL remain applicable; an inactive locker SHALL not prevent handover.

#### Scenario: Reoccupy then repeat the previous handover
- **WHEN** return A is handed over, parcel B occupies its old cell and A's handover is repeated
- **THEN** A returns 409 and B remains the active occupant unchanged
