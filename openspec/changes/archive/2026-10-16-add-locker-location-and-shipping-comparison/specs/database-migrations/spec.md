# database-migrations Spec Delta

## MODIFIED Requirements

### Requirement: Manage a shared and reversible history

Migrations SHALL manage parcels and lockers through one history. Revision 0001 SHALL retain its legacy UUID and required text columns; 0002 SHALL establish custody; 0003 SHALL add lockers/cells/assignments; 0004 SHALL add locker geography and permit null aliases without adding quote storage. Revisions 0001–0003 SHALL remain unchanged. Downgrades SHALL preserve business data through their guards, and an empty history SHALL remain reversible to base.

#### Scenario: Apply the initial revision
- **WHEN** `alembic upgrade 0001` runs against an empty database
- **THEN** `deliveries` contains UUID `id` and non-null `address`, `returns` contains UUID `id` and non-null `reason`, and revision `0001` is recorded

#### Scenario: Apply the current schema
- **WHEN** `alembic upgrade head` runs against an empty database
- **THEN** parcel fields and custody constraints, locker storage and geographic constraints exist, revision 0004 is recorded and no quote tables or legacy parcel address/reason columns are introduced

#### Scenario: Revert the initial revision
- **WHEN** `alembic downgrade base` runs with all business tables empty
- **THEN** the migration history is reversed and all business tables are dropped

## ADDED Requirements

### Requirement: Add geography to a populated locker database

Upgrade 0003 to 0004 SHALL preserve all parcel, locker, compartment and assignment identities/values. It SHALL add only nullable address/coordinate columns, their constraints and nullable location_id, without backfill. Address fields SHALL be all present or all null; coordinates SHALL be a complete finite bounded pair or both null. Format checks SHALL enforce geographic storage integrity without requiring a postal-search index.

#### Scenario: Populated custody survives additive upgrade
- **WHEN** 0003 contains pending/completed parcels, active/inactive lockers, occupied/retired cells and released assignments and is upgraded to 0004
- **THEN** their original values and non-null aliases remain unchanged, all geographic fields are null and revision 0004 is recorded

#### Scenario: Migrated metadata agrees
- **WHEN** a fresh PostgreSQL database is migrated to head and compared with current persistence metadata
- **THEN** geographic columns, alias nullability and checks agree, the active-occupancy unique constraint remains intact and no quote persistence exists

#### Scenario: Reject partial geography at the database boundary
- **WHEN** a direct write supplies a partial address, unsupported country, invalid postal/text value, partial coordinates or coordinates outside finite valid ranges
- **THEN** constraints reject the write without altering existing data

### Requirement: Reject destructive geography downgrade before alteration

Downgrade 0004 to 0003 SHALL reject any non-null geographic field or locker with null location_id before altering data, schema or revision. A permitted downgrade SHALL remove only new geographic columns/checks and restore location_id NOT NULL, preserving all earlier business data. Rejection SHALL explain data preservation without discarding records or inventing aliases/addresses.

#### Scenario: Geographic data blocks downgrade
- **WHEN** a locker has an address or coordinates and downgrade to 0003 is requested
- **THEN** it fails and the schema, rows and revision 0004 remain unchanged

#### Scenario: Missing alias blocks restoring the old constraint
- **WHEN** all geographic fields are null but a locker has null location_id and downgrade to 0003 is requested
- **THEN** it fails before DDL, preserving the locker and revision without fabricating an alias

#### Scenario: Existing custody permits a safe round trip
- **WHEN** geographic fields are null and all lockers retain non-null aliases while older custody data exists, and downgrade to 0003 then upgrade to 0004 run
- **THEN** both operations succeed, downgrade restores alias NOT NULL and the older data survives without invented geography
