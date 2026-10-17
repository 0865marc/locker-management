# Spec Delta

## MODIFIED Requirements

### Requirement: Manage a shared and reversible history

Migrations SHALL manage parcels, lockers and quotations through one history. Revision 0001 SHALL retain its legacy UUID and required text columns; 0002 SHALL establish custody; 0003 SHALL add lockers/cells/assignments; 0004 SHALL add locker geography and permit null aliases without quote storage; 0005 SHALL add quotation requests, provider results and offers. Revisions 0001–0004 SHALL remain unchanged. Downgrades SHALL preserve business data through their guards, and an empty history SHALL remain reversible to base.

#### Scenario: Apply the initial revision
- **WHEN** `alembic upgrade 0001` runs against an empty database
- **THEN** deliveries contains UUID id and non-null address, returns contains UUID id and non-null reason, and revision 0001 is recorded

#### Scenario: Apply the current schema
- **WHEN** `alembic upgrade head` runs against an empty database
- **THEN** parcel custody, locker/geographic constraints and quotation/result/offer storage exist, revision 0005 is recorded and legacy parcel address/reason columns are absent

#### Scenario: Revert the initial revision
- **WHEN** `alembic downgrade base` runs with all business tables empty
- **THEN** the migration history is reversed and all business tables are dropped

### Requirement: Add geography to a populated locker database

Upgrade 0003 to 0004 SHALL preserve all parcel, locker, compartment and assignment identities/values. It SHALL add only nullable address/coordinate columns, their constraints and nullable location_id, without backfill. Address fields SHALL be all present or all null; coordinates SHALL be a complete finite bounded pair or both null. Format checks SHALL enforce geographic storage integrity without requiring a postal-search index.

#### Scenario: Populated custody survives additive upgrade
- **WHEN** 0003 contains pending/completed parcels, active/inactive lockers, occupied/retired cells and released assignments and is upgraded to 0004
- **THEN** their original values and non-null aliases remain unchanged, all geographic fields are null and revision 0004 is recorded

#### Scenario: Migrated metadata agrees
- **WHEN** a fresh PostgreSQL database is migrated specifically to 0004 and inspected
- **THEN** geographic columns, alias nullability and checks match the 0004 contract, the active-occupancy unique constraint remains intact and no quote persistence exists at that revision

#### Scenario: Reject partial geography at the database boundary
- **WHEN** a direct write supplies a partial address, unsupported country, invalid postal/text value, partial coordinates or coordinates outside finite valid ranges
- **THEN** constraints reject the write without altering existing data

## ADDED Requirements

### Requirement: Add quotations without altering existing business data

Upgrade 0004 to 0005 SHALL add empty quotation request, provider result and offer storage with their integrity constraints. It SHALL preserve all existing parcel, locker, cell, assignment and geographic values without backfill. A fresh schema migrated to head SHALL agree with current persistence metadata and retain previous custody/geography constraints.

#### Scenario: Populated current database upgrades
- **WHEN** 0004 contains pending/completed parcels, locker geography, occupied/retired cells and assignment history and is upgraded to 0005
- **THEN** every existing identity/value is unchanged, the new storage is empty and revision 0005 is recorded

#### Scenario: New metadata agrees and enforces integrity
- **WHEN** the current schema is migrated on PostgreSQL and compared with metadata, then invalid references or duplicate quotation/provider/service identities are inserted
- **THEN** the schemas agree, existing occupancy/geography protections remain and invalid quote writes are rejected

### Requirement: Reject quotation data loss before downgrade

Downgrade 0005 to 0004 SHALL reject any stored quotation, provider result or offer before changing schema, data or revision. If all new storage is empty, it SHALL remove only that storage and preserve all earlier business data, even when populated.

#### Scenario: Stored quotations block downgrade
- **WHEN** a quotation in any state exists and downgrade to 0004 is requested
- **THEN** it fails with a data-preservation explanation and leaves all rows, constraints, schemas and revision 0005 unchanged

#### Scenario: Older populated business data survives round trip
- **WHEN** parcel and locker data exist but quotation/result/offer storage is empty, and downgrade to 0004 then upgrade to 0005 run
- **THEN** both steps preserve the older data and return to empty quotation storage without fabricated records
