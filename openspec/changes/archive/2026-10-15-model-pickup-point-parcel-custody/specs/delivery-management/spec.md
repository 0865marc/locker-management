# Delivery Management Delta

## MODIFIED Requirements

### Requirement: Create a delivery

The system SHALL record one parcel received from a carrier for recipient collection, with a generated UUID, required `tracking_number`, `carrier_code`, and `recipient_name`, optional `recipient_phone` and `pickup_deadline_at`, and system-assigned UTC `received_at`. It SHALL save the delivery before returning its complete representation with HTTP `201` from `POST /deliveries`.

#### Scenario: Creation with normalized parcel data
- **WHEN** a valid request includes `tracking_number` equal to `"  PKG-42  "`, `carrier_code` equal to `"  carrier-a  "`, and `recipient_name` equal to `"  Ana García  "`
- **THEN** the saved response contains the trimmed values, a generated UUID and reception timestamp, status `AWAITING_PICKUP`, and null `collected_at` and `returned_to_carrier_at`

#### Scenario: Creation with a normalized address
- **WHEN** the legacy request `{"address": "  Calle Mayor 1  "}` is submitted to `POST /deliveries`
- **THEN** HTTP `422` is returned and no delivery is saved because an address no longer represents parcel reception

#### Scenario: Optional contact and deadline
- **WHEN** a valid delivery includes a phone with surrounding whitespace and a timezone-aware deadline, including one earlier than reception
- **THEN** the phone is trimmed and the deadline is preserved as its equivalent UTC instant; omitted optional fields and a blank phone are represented as null

### Requirement: Validate the HTTP creation body

The HTTP adapter SHALL require text `tracking_number`, `carrier_code`, and `recipient_name`, allow nullable text `recipient_phone` and nullable timezone-aware `pickup_deadline_at`, and reject incorrect types, missing required fields, unknown fields, or system-managed fields with HTTP `422` without executing creation. Domain validation SHALL reject required text that is blank after trimming before persistence.

#### Scenario: Invalid body
- **WHEN** a required field is missing, null, or a list, or a deadline lacks a timezone
- **THEN** HTTP `422` is returned without invoking delivery creation

#### Scenario: Empty required text
- **WHEN** tracking, carrier, or recipient is empty or whitespace-only
- **THEN** HTTP `422` is returned and no delivery is saved

#### Scenario: Legacy or system-managed input
- **WHEN** a request includes `address`, `delivery_instructions`, `storage_location`, a supplied UUID, status, reception date, or exit date
- **THEN** HTTP `422` is returned without invoking delivery creation

### Requirement: List deliveries

The system SHALL respond to `GET /deliveries` with HTTP `200` and each delivery's UUID, tracking number, carrier, recipient, optional phone and deadline, status, reception timestamp, and nullable collection and carrier-return timestamps. Removed commercial or address fields SHALL NOT appear.

#### Scenario: List with records
- **WHEN** deliveries in different custody states have been saved
- **THEN** the list contains their complete persisted representations, including nullable optional fields

#### Scenario: Empty list
- **WHEN** no deliveries exist
- **THEN** `GET /deliveries` returns `200` and `[]`

## REMOVED Requirements

### Requirement: Reject empty addresses

**Reason**: Deliveries represent parcels at a pickup point and have no destination address in this model.
**Migration**: Clients must send parcel identification and recipient fields; the new migration must refuse unsupported legacy rows without deleting or fabricating their data.

## ADDED Requirements

### Requirement: Record mutually exclusive delivery exits

The system SHALL permit an `AWAITING_PICKUP` delivery to become `COLLECTED` or `RETURNED_TO_CARRIER` through explicit collection or carrier-return operations. It SHALL assign only the corresponding UTC exit timestamp, which MUST be at or after `received_at`. Any repeated or incompatible exit SHALL be rejected without changing the parcel or its timestamps.

#### Scenario: Recipient collects a parcel
- **WHEN** `POST /deliveries/{id}/collect` targets a pending delivery
- **THEN** HTTP `200` returns its complete representation with status `COLLECTED`, system-assigned `collected_at`, and null `returned_to_carrier_at`

#### Scenario: Parcel is handed back to the carrier
- **WHEN** `POST /deliveries/{id}/return-to-carrier` targets a pending delivery
- **THEN** HTTP `200` returns status `RETURNED_TO_CARRIER`, system-assigned `returned_to_carrier_at`, and null `collected_at`

#### Scenario: Invalid or repeated exit
- **WHEN** an exit targets a terminal delivery or the operation's timestamp would precede reception
- **THEN** HTTP `409` is returned and the stored representation remains unchanged

#### Scenario: Unknown identifier or supplied action data
- **WHEN** an exit references an unknown UUID, uses a malformed UUID, or includes nonempty action data
- **THEN** an unknown UUID returns `404`; malformed identifiers or supplied action data return `422`

### Requirement: Treat pickup deadlines as informational

The system SHALL preserve a supplied pickup deadline without automatically changing custody state or blocking collection when that deadline has passed.

#### Scenario: Collection after the deadline
- **WHEN** a pending delivery is collected after its recorded deadline
- **THEN** the normal collection succeeds and records its actual system-assigned exit timestamp
