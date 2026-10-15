## Purpose

Provide independent service-free unit tests and isolated PostgreSQL integration tests, with explicit execution failures and preserved behavioral coverage.

## ADDED Requirements

### Requirement: Run unit tests without database services

The documented unit-test command SHALL discover and execute domain, application, isolated HTTP-adapter and composition tests without TEST_DATABASE_URL, a running database service or a SQLite driver. Unit execution SHALL not create databases, schemas or database connections.

#### Scenario: Unit suite with no database configuration
- **WHEN** dependencies are installed without aiosqlite and the unit command runs with TEST_DATABASE_URL unset and PostgreSQL unavailable
- **THEN** unit scenarios execute successfully without contacting a database or importing an integration fixture that requires one

### Requirement: Require PostgreSQL for integration and full execution

Integration SHALL use only PostgreSQL through an explicit postgresql+asyncpg TEST_DATABASE_URL. Missing or invalid configuration, unavailable PostgreSQL and insufficient setup permissions SHALL fail integration and full-suite execution with nonzero status and a clear diagnostic, without exposing credentials. Database-dependent tests SHALL not be skipped because their environment is missing.

#### Scenario: Missing integration configuration
- **WHEN** integration or the complete suite runs without TEST_DATABASE_URL
- **THEN** setup fails clearly, the process exits nonzero and the result cannot be reported as successful tests skipped

#### Scenario: Wrong backend or unreachable server
- **WHEN** TEST_DATABASE_URL selects another driver or PostgreSQL cannot be reached
- **THEN** execution fails with a configuration or connection diagnostic instead of falling back to another URL or SQLite

#### Scenario: Configured integration
- **WHEN** a dedicated PostgreSQL test database is reachable with the required schema permissions
- **THEN** integration and the complete suite execute their applicable scenarios without database-environment skips

### Requirement: Isolate integration data and clean up resources

Every integration case SHALL use its own generated PostgreSQL schema and SHALL leave public and unrelated schemas unchanged. Preparation SHALL use the migration history, except cases intentionally testing an unprepared schema. Cleanup SHALL close clients, connections and engines and remove the generated schema after success or failure, including partial setup failures.

#### Scenario: Test fails after schema creation
- **WHEN** setup or execution fails after creating the case's schema
- **THEN** registered cleanup removes that schema and closes its resources without deleting another case's data

#### Scenario: Persistence across application instances
- **WHEN** one application writes and closes and another application opens against the same case's schema
- **THEN** the second observes the committed records and both instances remain isolated from public tables

### Requirement: Preserve database behavior coverage on PostgreSQL

The integration suite SHALL retain the existing repository, HTTP, rollback, constraint, migration and concurrency scenarios when removing SQLite. It SHALL verify aware UTC round trips, shared capacity and safe reoccupation, additive and protected historical migrations, and agreement between migrated PostgreSQL schema and current metadata. Equivalent consolidation SHALL preserve identifiable scenario evidence.

#### Scenario: Historical migration coverage survives the port
- **WHEN** the PostgreSQL migration suite executes
- **THEN** it checks 0001 legacy columns, empty history round trips, populated-legacy upgrade rejection, populated-custody downgrade rejection, additive 0002-to-0003 upgrade and rejection of locker-data loss, preserving snapshots on rejection

#### Scenario: No loss of concurrency or schema evidence
- **WHEN** the complete integration suite executes
- **THEN** independent database connections still exercise competing receptions/exits and rollback, and a migrated empty schema matches metadata with its active-occupancy unique index intact

### Requirement: Remove the active SQLite test dependency without rewriting history

Development dependency resolution and active test fixtures SHALL no longer require or invoke aiosqlite or SQLite. Migration files 0001, 0002 and 0003 SHALL remain unchanged, including inert historical dialect options. API behavior, data and runtime database URL precedence SHALL remain unchanged; this change SHALL not require a new schema migration.

#### Scenario: Install and verify with historical migrations retained
- **WHEN** the updated dependencies are installed and PostgreSQL verification runs
- **THEN** aiosqlite is absent from declared/resolved dependencies, current tests use PostgreSQL or doubles, historical migrations are unchanged and existing API contracts still pass
