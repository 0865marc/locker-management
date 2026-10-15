# Return Management Delta

## MODIFIED Requirements

### Requirement: Create an independent return

The system SHALL record one parcel deposited by a customer for carrier collection, with a generated UUID, required `tracking_number` and `carrier_code`, optional `sender_name`, and system-assigned UTC `received_at`. It SHALL require no associated delivery and save the return before responding to `POST /returns` with HTTP `201` and its complete representation.

#### Scenario: Creation with normalized parcel data
- **WHEN** valid tracking and carrier values with surrounding whitespace are submitted without a delivery reference
- **THEN** the saved response contains trimmed tracking and carrier values, a generated UUID and reception timestamp, status `AWAITING_CARRIER`, and null `handed_over_at`

#### Scenario: Creation with a normalized reason
- **WHEN** the legacy request `{"reason": "  Producto dañado  "}` is submitted to `POST /returns`
- **THEN** HTTP `422` is returned and no return is saved because a commercial reason no longer represents parcel reception

#### Scenario: Optional sender
- **WHEN** a sender name has surrounding whitespace, is blank, or is omitted
- **THEN** a nonblank sender name is trimmed; a blank or omitted sender is represented as null

### Requirement: Validate the HTTP creation body

The HTTP adapter SHALL require text `tracking_number` and `carrier_code`, allow nullable text `sender_name`, and reject incorrect types, missing required fields, unknown fields, or system-managed fields with HTTP `422` without executing creation. Domain validation SHALL reject required text that is blank after trimming before persistence.

#### Scenario: Invalid body
- **WHEN** a required field is missing, null, or a list, or a non-text sender is supplied
- **THEN** HTTP `422` is returned without invoking return creation

#### Scenario: Empty required text
- **WHEN** tracking or carrier is empty or whitespace-only
- **THEN** HTTP `422` is returned and no return is saved

#### Scenario: Legacy or unapproved input
- **WHEN** a request includes `reason`, `item_sku`, `quantity`, `requested_resolution`, `storage_location`, `sender_phone`, a supplied UUID, state, or timestamp
- **THEN** HTTP `422` is returned without invoking return creation

### Requirement: List returns

The system SHALL respond to `GET /returns` with HTTP `200` and an array containing each return's UUID, tracking number, carrier, optional sender, status, reception timestamp, and nullable handover timestamp. Commercial return reasons and product or order fields SHALL NOT appear.

#### Scenario: List with records
- **WHEN** pending and handed-over returns have been saved
- **THEN** the list contains their complete persisted representations, including nullable optional fields

#### Scenario: Empty list
- **WHEN** no returns exist
- **THEN** `GET /returns` returns `200` and `[]`

## REMOVED Requirements

### Requirement: Reject empty reasons

**Reason**: A pickup point records custody of a return parcel rather than the commercial reason for returning a product.
**Migration**: Clients must send tracking and carrier data; the new migration refuses unsupported legacy rows without deleting or fabricating their data.

## ADDED Requirements

### Requirement: Hand a return over to its carrier once

The system SHALL allow an `AWAITING_CARRIER` return to become `HANDED_OVER` through an explicit handover operation, assigning a UTC `handed_over_at` at or after `received_at`. A repeated handover SHALL fail without changing the saved parcel or timestamp.

#### Scenario: Successful handover
- **WHEN** `POST /returns/{id}/hand-over` targets a pending return
- **THEN** HTTP `200` returns the complete saved representation with status `HANDED_OVER` and its system-assigned handover timestamp

#### Scenario: Repeated handover or invalid chronology
- **WHEN** a handover targets a completed return or its operation timestamp would precede reception
- **THEN** HTTP `409` is returned without changing the persisted representation

#### Scenario: Unknown identifier or supplied action data
- **WHEN** handover references an unknown UUID, uses a malformed UUID, or includes nonempty action data
- **THEN** an unknown UUID returns `404`; malformed identifiers or supplied action data return `422`
