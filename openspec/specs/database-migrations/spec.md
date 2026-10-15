# Database Migrations Specification

## Purpose

Prepare and evolve the shared delivery and return schema through a migration history separate from API startup.

## Requirements

### Requirement: Manage a shared and reversible history

Migrations SHALL manage deliveries and returns through a single history. Revision `0001` SHALL retain its legacy UUID and required text columns. A subsequent revision SHALL establish the parcel custody schema. Reverting that revision SHALL be allowed only when no parcel records would be lost; an empty history SHALL remain reversible to base.

#### Scenario: Apply the initial revision
- **WHEN** `alembic upgrade 0001` runs against an empty database
- **THEN** `deliveries` contains UUID `id` and non-null `address`, `returns` contains UUID `id` and non-null `reason`, and revision `0001` is recorded

#### Scenario: Apply the current schema
- **WHEN** `alembic upgrade head` runs against an empty database
- **THEN** both tables have the current parcel fields, timezone-aware timestamp columns, and custody state constraints, and the new revision is recorded without retaining `address` or `reason`

#### Scenario: Revert the initial revision
- **WHEN** `alembic downgrade base` runs with both tables empty
- **THEN** the migration history is reversed and both tables are dropped

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

Downgrading from the parcel schema SHALL refuse any populated delivery or return table before changing data or schema. An empty parcel schema SHALL downgrade to the unchanged `0001` structure. A rejected downgrade SHALL preserve the current revision and all parcel data.

#### Scenario: Populated parcel schema blocks downgrade
- **WHEN** downgrade is attempted while either table contains a parcel
- **THEN** it fails with an actionable data-preservation explanation and leaves rows, schema, and revision unchanged

#### Scenario: Empty round trip
- **WHEN** the empty database is upgraded to head, downgraded to `0001`, and upgraded again
- **THEN** each step succeeds with the expected schema and revision and no invented business data
