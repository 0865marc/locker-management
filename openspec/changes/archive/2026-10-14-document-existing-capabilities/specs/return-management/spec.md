# Spec Delta

## Purpose

Allow returns independent of deliveries to be recorded and retrieved, identified by UUID and with a reason validated through the existing HTTP contract.

## ADDED Requirements

### Requirement: Create an independent return

The system SHALL create a return with a generated UUID and a reason with leading and trailing whitespace removed, without requiring an associated delivery. It SHALL save the return before responding to `POST /returns` with HTTP `201`, `id`, and `reason`.

#### Scenario: Creation with a normalized reason
- **WHEN** `POST /returns` is submitted with `{"reason": "  Producto dañado  "}`, without a delivery reference, and the write succeeds
- **THEN** `201` is returned with the UUID of the saved return and `reason` equal to `Producto dañado`

### Requirement: Reject empty reasons

The system SHALL reject a reason that becomes empty after leading and trailing whitespace is removed, before persisting the return. Over HTTP, it SHALL respond with `422` and the validation message in `detail`.

#### Scenario: Empty or whitespace-only reason
- **WHEN** an attempt is made to create a return with `reason` equal to `""` or `" \t\n "`
- **THEN** no return is saved and, over HTTP, `422` is returned with `detail` equal to `El motivo no puede estar vacío`

### Requirement: Validate the HTTP creation body

The HTTP adapter SHALL require the text field `reason` and reject a missing field, a null value, or a list with HTTP `422`, without executing the use case.

#### Scenario: Invalid body
- **WHEN** `POST /returns` is submitted with `{}`, `{"reason": null}`, or `{"reason": []}`
- **THEN** `422` is returned without invoking return creation

### Requirement: List returns

The system SHALL respond to `GET /returns` with HTTP `200` and an array of the retrieved returns, including `id` and `reason` in each item.

#### Scenario: List with records
- **WHEN** `GET /returns` is requested and saved returns exist
- **THEN** `200` is returned with those returns and their UUIDs and reasons

#### Scenario: Empty list
- **WHEN** `GET /returns` is requested and no returns exist
- **THEN** `200` is returned with `[]`
