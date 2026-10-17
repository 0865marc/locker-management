# test-execution Specification

## Purpose

Provide independent service-free unit tests and isolated PostgreSQL integration tests, with explicit execution failures and preserved behavioral coverage.

## Requirements

### Requirement: Run unit tests without database services

The documented unit-test command SHALL discover and execute domain, application, provider-contract, isolated HTTP-adapter and composition tests without TEST_DATABASE_URL, running services or a SQLite driver. Unit execution SHALL not create databases/schemas or service connections. The comparator SHALL be tested directly with in-process simulators and doubles without HTTP or locker persistence.

#### Scenario: Unit suite with no database configuration
- **WHEN** dependencies are installed without aiosqlite and the unit command runs with TEST_DATABASE_URL unset and PostgreSQL unavailable
- **THEN** unit scenarios execute successfully without contacting a database or importing an integration fixture that requires one

#### Scenario: Comparator without infrastructure
- **WHEN** transport data is compared directly using simulators or doubles without services
- **THEN** validation, normalized offers, no coverage and technical failures are verified without HTTP requests or database connections

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

### Requirement: Verify provider extensibility and cancellation

Tests SHALL demonstrate a fourth injected provider and multiple services without modifying common domain/comparison logic. They SHALL distinguish no coverage, technical failure and timeout, preserve other providers' offers, reject invalid collections, bound concurrent calls and verify cancellation cleanup. Concurrency evidence SHALL use observable barriers/events rather than timing assumptions or external provider APIs.

#### Scenario: Fourth provider with two services
- **WHEN** a double with its own code and two service offers is supplied alongside three simulators
- **THEN** direct comparison returns all four providers and the two normalized services without provider-specific branches

#### Scenario: Invalid configuration and cancellation
- **WHEN** tests supply empty/duplicate provider collections or cancel a comparison with active/waiting children
- **THEN** configuration fails clearly before calls and cancellation leaves no active or detached work

### Requirement: Preserve PostgreSQL geography and custody evidence

The PostgreSQL suite SHALL retain isolated schemas, explicit configuration failures, historical migration, metadata, rollback and custody-concurrency scenarios. It SHALL verify populated 0003-to-0004 geographic upgrade, guarded downgrade and compatible locker HTTP contracts. The comparator SHALL require no integration service. Only the new messaging suite SHALL require RabbitMQ; existing PostgreSQL tests SHALL remain executable without it.

#### Scenario: Geographic migration coverage
- **WHEN** historical migration tests run explicitly through 0004 and metadata tests run at current head
- **THEN** explicit 0002-to-0003 and geography evidence remains, current constraints agree with metadata and rejected downgrades preserve data/schema/revision without weakening occupancy constraints

#### Scenario: Compatible locker administration
- **WHEN** integration tests create legacy and address-only lockers and patch or clear geographic values
- **THEN** values persist atomically, historical nulls and alias filtering are preserved, and existing custody/availability contracts still pass

### Requirement: Keep standard Python annotations complete and coherent

Affected existing and new functions SHALL have standard Python annotations for parameters, returns, collections, generics and optional values. Ports and adapters SHALL agree on types, with correct narrowing. Real incompatibilities SHALL be corrected rather than hidden with generalized Any or suppressions. Historical migrations 0001–0003 SHALL remain unchanged. Verification SHALL include the configured Pyright check alongside annotation review and behavioral tests.

#### Scenario: Review affected function contracts
- **WHEN** affected functions, their callers and port implementations are reviewed
- **THEN** annotations describe actual inputs/results, optional values are handled explicitly and existing behavioral tests remain applicable and the configured type checker verifies compatibility

#### Scenario: Editor diagnostics when available
- **WHEN** Pylance diagnostics are available in VSCode during verification
- **THEN** relevant genuine type inconsistencies are corrected; if the editor is unavailable, the report records that limitation without claiming its diagnostics ran

### Requirement: Run a reproducible backend type check

The locked development dependencies SHALL provide Pyright with shared root configuration for CLI and Pylance. Analysis SHALL include backend production and tests, targeting Python 3.11 with backend/.venv. Domain, application, adapters, main and the worker entry point SHALL use strict mode; tests SHALL use standard mode. Only environments/caches and historical migrations 0001–0003 SHALL be excluded. Migrations 0004, 0005 and the migration environment SHALL remain checked.

#### Scenario: Check without services
- **WHEN** `uv run --extra dev pyright --project .. --warnings` runs from backend with the development dependencies installed and no database configuration
- **THEN** it analyzes the configured backend and returns success only with zero errors and zero warnings, without connecting to a database or broker

#### Scenario: Correct the entire analyzed scope
- **WHEN** diagnostics occur in production, tests or migration code included in analysis
- **THEN** their real causes are corrected without hiding them through broad exclusions, disabled rules, generalized Any or untruthful narrowing

### Requirement: Require type evidence before completing a spec

Completing implementation of each spec/change SHALL require the configured Pyright command to pass with zero errors and warnings, alongside relevant runtime tests. Builder and independent reviewer SHALL report the command and result; corrections affecting types SHALL trigger another check. Previous manual/AST inspection or editor screenshots SHALL not substitute for current CLI evidence.

#### Scenario: Type failures block completion
- **WHEN** functional tests pass but the final type command reports errors or warnings
- **THEN** implementation remains incomplete until the causes are corrected, the command passes and affected runtime tests are repeated

#### Scenario: Preserve earlier evidence honestly
- **WHEN** an earlier implementation was verified before the checker was introduced
- **THEN** its prior test/review evidence remains historical and no clean checker result is claimed until the configured command actually runs successfully

### Requirement: Verify simulation and the single execution flow

Unit tests SHALL verify fixed provider profiles, zero-argument construction, outcomes, unchanged tariffs, timeout/no retry, enqueue success/failure and early acknowledgement without services. Tests SHALL control randomness/waiting at execution time without constructor configuration, random seeds or concurrent call-order assumptions. PostgreSQL integration SHALL retain request/result and migration coverage.

#### Scenario: Unit and persistence evidence
- **WHEN** the unit suite runs without services and the PostgreSQL suite runs against an isolated test schema
- **THEN** the new flow and existing comparator pass deterministically, and another instance reads persisted requests and outcomes with migration safeguards intact

#### Scenario: Fixed profiles without random test failures
- **WHEN** unit tests exercise the three providers, their thresholds, price examples and worker composition
- **THEN** locally controlled random/wait operations make outcomes repeatable, constructors receive no configuration and normal production construction remains stochastic

### Requirement: Verify queue consumption with an isolated smoke test

The messaging smoke SHALL use explicit TEST_RABBITMQ_URL and TEST_DATABASE_URL, isolated queues/schemas and resource cleanup. It SHALL verify one publication, consumption before provider execution, result persistence and no requeue after provider failure. Its successful provider double SHALL return a fixed test offer without invoking a stochastic simulator. Missing/unusable configuration SHALL fail clearly instead of skipping tests or exposing credentials.

#### Scenario: Queue to comparison to storage
- **WHEN** the smoke submits a quotation with controlled successful and failing providers
- **THEN** the worker acknowledges before execution, stores the mixed result set and makes no automatic second attempt or requeue, then the test cleans up only its resources
