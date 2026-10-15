## MODIFIED Requirements

### Requirement: Manage a shared and reversible history

Migrations SHALL manage deliveries and returns through a single history. Revision `0001` SHALL retain its legacy UUID and required text columns. Revision 0002 SHALL establish the parcel custody schema and revision 0003 SHALL add lockers, cells and assignments without changing populated parcel tables. Reverting that revision SHALL be allowed only when no parcel records would be lost; an empty history SHALL remain reversible to base.

#### Scenario: Apply the initial revision
- **WHEN** `alembic upgrade 0001` runs against an empty database
- **THEN** `deliveries` contains UUID `id` and non-null `address`, `returns` contains UUID `id` and non-null `reason`, and revision `0001` is recorded

#### Scenario: Apply the current schema
- **WHEN** `alembic upgrade head` runs against an empty database
- **THEN** both tables have the current parcel fields, timezone-aware timestamp columns, and custody state constraints, the locker tables and constraints exist, and revision 0003 is recorded without retaining `address` or `reason`

#### Scenario: Revert the initial revision
- **WHEN** `alembic downgrade base` runs with all business tables empty
- **THEN** the migration history is reversed and all business tables are dropped


### Requirement: Protect parcel data during downgrade

Downgrading from revision 0002 toward 0001 SHALL refuse any populated delivery or return table before changing data or schema. An empty parcel schema SHALL downgrade to the unchanged `0001` structure. A rejected downgrade SHALL preserve the current revision and all parcel data.

#### Scenario: Populated parcel schema blocks downgrade
- **WHEN** downgrade from 0002 toward 0001 is attempted while either parcel table contains a parcel
- **THEN** it fails with an actionable data-preservation explanation and leaves rows, schema, and revision unchanged

#### Scenario: Empty round trip
- **WHEN** the empty database is upgraded to head, downgraded to `0001`, and upgraded again
- **THEN** each step succeeds with the expected schema and revision and no invented business data


## ADDED Requirements

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
