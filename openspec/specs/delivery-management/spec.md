# Delivery Management Specification

## Purpose

Allow deliveries identified by UUID to be recorded and retrieved, applying address validation and exposing the existing HTTP contract.

## Requirements

### Requirement: Create a delivery

The system SHALL create a delivery with a generated UUID and an address with leading and trailing whitespace removed, save it before returning it, and respond to `POST /deliveries` with HTTP `201`, `id`, and `address`.

#### Scenario: Creation with a normalized address
- **WHEN** `POST /deliveries` is submitted with `{"address": "  Calle Mayor 1  "}` and the write succeeds
- **THEN** `201` is returned with the UUID of the saved delivery and `address` equal to `Calle Mayor 1`

### Requirement: Reject empty addresses

The system SHALL reject an address that becomes empty after leading and trailing whitespace is removed, before persisting the delivery. Over HTTP, it SHALL respond with `422` and the validation message in `detail`.

#### Scenario: Empty or whitespace-only address
- **WHEN** an attempt is made to create a delivery with `address` equal to `""` or `" \t\n "`
- **THEN** no delivery is saved and, over HTTP, `422` is returned with `detail` equal to `La dirección no puede estar vacía`

### Requirement: Validate the HTTP creation body

The HTTP adapter SHALL require the text field `address` and reject a missing field, a null value, or a list with HTTP `422`, without executing the use case.

#### Scenario: Invalid body
- **WHEN** `POST /deliveries` is submitted with `{}`, `{"address": null}`, or `{"address": []}`
- **THEN** `422` is returned without invoking delivery creation

### Requirement: List deliveries

The system SHALL respond to `GET /deliveries` with HTTP `200` and an array of the retrieved deliveries, including `id` and `address` in each item.

#### Scenario: List with records
- **WHEN** `GET /deliveries` is requested and saved deliveries exist
- **THEN** `200` is returned with those deliveries and their UUIDs and addresses

#### Scenario: Empty list
- **WHEN** `GET /deliveries` is requested and no deliveries exist
- **THEN** `200` is returned with `[]`
