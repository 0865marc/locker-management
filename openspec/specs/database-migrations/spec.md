# Database Migrations Specification

## Purpose

Prepare and evolve the shared delivery and return schema through a migration history separate from API startup.

## Requirements

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

### Requirement: Prepare the schema outside API startup

The API SHALL start its lifecycle without creating tables or running migrations. Schema preparation SHALL take place through the migration process before data operations are used.

#### Scenario: Startup without schema changes
- **WHEN** an API instance is constructed and started
- **THEN** its lifecycle performs neither table creation nor migrations

### Requirement: Manually adopt legacy tables

The procedure for adopting existing tables without a migration history SHALL require a backup and verification that they match `0001` before recording that revision. Recording a revision SHALL leave existing business tables unchanged.

#### Scenario: Record a compatible schema
- **WHEN** the data has been backed up and the types, nullability, and primary keys of the legacy tables have been checked, and `alembic stamp 0001` is run
- **THEN** the revision is recorded without recreating or correcting the business tables, after which `alembic upgrade head` can be run

### Requirement: Refuse unsupported legacy data without alteration

Before replacing the legacy schema, migration SHALL detect rows in either legacy table and refuse the upgrade with an actionable explanation that required parcel data is unavailable and an explicit data migration is needed. Rejection SHALL preserve all rows, column definitions, and the recorded revision. It MUST NOT fabricate missing values or delete records.

#### Scenario: Legacy delivery or return blocks upgrade
- **WHEN** upgrade to the parcel schema is attempted with a legacy delivery, a legacy return, or both
- **THEN** migration fails before schema conversion, identifies the populated tables and missing-information problem, and leaves their data, schema, and revision `0001` unchanged

#### Scenario: No automatic reset or backfill
- **WHEN** the migration finds a populated legacy table
- **THEN** the error directs the operator to preserve the database and arrange an explicit migration of real parcel data; it neither resets tables nor supplies fake tracking, recipients, or reception timestamps

### Requirement: Protect parcel data during downgrade

Downgrading from revision 0002 toward 0001 SHALL refuse any populated delivery or return table before changing data or schema. An empty parcel schema SHALL downgrade to the unchanged `0001` structure. A rejected downgrade SHALL preserve the current revision and all parcel data.

#### Scenario: Populated parcel schema blocks downgrade
- **WHEN** downgrade from 0002 toward 0001 is attempted while either parcel table contains a parcel
- **THEN** it fails with an actionable data-preservation explanation and leaves rows, schema, and revision unchanged

#### Scenario: Empty round trip
- **WHEN** the empty database is upgraded to head, downgraded to `0001`, and upgraded again
- **THEN** each step succeeds with the expected schema and revision and no invented business data

### Requirement: Add lockers to a populated current database

Upgrade from 0002 to 0003 SHALL preserve every existing delivery and return, their schema and values, while adding empty locker, compartment and assignment storage. Existing parcels SHALL remain unassigned. The migration SHALL not invent locations, dimensions or assignments, and SHALL not rewrite revisions 0001 or 0002.

#### Scenario: Populated current schema upgrades
- **WHEN** 0002 contains pending and completed deliveries and returns and is upgraded to 0003
- **THEN** all original values remain unchanged, locker storage is empty, constraints and indexes exist and revision 0003 is recorded

#### Scenario: Older populated legacy schema stays protected
- **WHEN** 0001 contains legacy address or reason data and upgrade head is requested
- **THEN** the existing 0002 guard rejects the upgrade, preserving legacy rows, schema and revision 0001

### Requirement: Reject destructive locker downgrade before alteration

Downgrade from 0003 to 0002 SHALL reject any nonempty locker, compartment or assignment table before changing schema, data or revision, including retired cells and released assignments. When all new tables are empty, downgrade SHALL remove only the new storage and preserve existing deliveries and returns, even when populated.

#### Scenario: Populated locker storage blocks downgrade
- **WHEN** any locker data exists and downgrade to 0002 is attempted
- **THEN** migration fails with a data-preservation explanation and all rows, constraints, schemas and revision 0003 remain unchanged

#### Scenario: Unassigned parcels survive round trip
- **WHEN** deliveries and returns exist but all locker tables are empty, and the database is downgraded to 0002 then upgraded to 0003
- **THEN** both steps succeed without modifying those parcels or fabricating assignments

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
