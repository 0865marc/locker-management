# test-execution Spec Delta

## MODIFIED Requirements

### Requirement: Run unit tests without database services

The documented unit-test command SHALL discover and execute domain, application, provider-contract, isolated HTTP-adapter and composition tests without TEST_DATABASE_URL, running services or a SQLite driver. Unit execution SHALL not create databases/schemas or service connections. The comparator SHALL be tested directly with in-process simulators and doubles without HTTP or locker persistence.

#### Scenario: Unit suite with no database configuration
- **WHEN** dependencies are installed without aiosqlite and the unit command runs with TEST_DATABASE_URL unset and PostgreSQL unavailable
- **THEN** unit scenarios execute successfully without contacting a database or importing an integration fixture that requires one

#### Scenario: Comparator without infrastructure
- **WHEN** transport data is compared directly using simulators or doubles without services
- **THEN** validation, normalized offers, no coverage and technical failures are verified without HTTP requests or database connections

## ADDED Requirements

### Requirement: Verify provider extensibility and cancellation

Tests SHALL demonstrate a fourth injected provider and multiple services without modifying common domain/comparison logic. They SHALL distinguish no coverage, technical failure and timeout, preserve other providers' offers, reject invalid collections, bound concurrent calls and verify cancellation cleanup. Concurrency evidence SHALL use observable barriers/events rather than timing assumptions or external provider APIs.

#### Scenario: Fourth provider with two services
- **WHEN** a double with its own code and two service offers is supplied alongside three simulators
- **THEN** direct comparison returns all four providers and the two normalized services without provider-specific branches

#### Scenario: Invalid configuration and cancellation
- **WHEN** tests supply empty/duplicate provider collections or cancel a comparison with active/waiting children
- **THEN** configuration fails clearly before calls and cancellation leaves no active or detached work

### Requirement: Preserve PostgreSQL geography and custody evidence

The PostgreSQL suite SHALL retain isolated schemas, explicit configuration failures, historical migration, metadata, rollback and custody-concurrency scenarios. It SHALL verify populated 0003-to-0004 geographic upgrade, guarded downgrade and compatible locker HTTP contracts. The comparator SHALL require no PostgreSQL integration fixture, and no additional test service SHALL be introduced.

#### Scenario: Geographic migration coverage
- **WHEN** migration and metadata tests run with head 0004
- **THEN** explicit 0002-to-0003 evidence remains, geography constraints agree with metadata and rejected downgrades preserve data/schema/revision without weakening occupancy constraints

#### Scenario: Compatible locker administration
- **WHEN** integration tests create legacy and address-only lockers and patch or clear geographic values
- **THEN** values persist atomically, historical nulls and alias filtering are preserved, and existing custody/availability contracts still pass

### Requirement: Keep standard Python annotations complete and coherent

Affected existing and new functions SHALL have standard Python annotations for parameters, returns, collections, generics and optional values. Ports and adapters SHALL agree on types, with correct narrowing. Real incompatibilities SHALL be corrected rather than hidden with generalized Any or suppressions. Historical migrations 0001–0003 SHALL remain unchanged. Annotation review SHALL require no new checker, configuration or dependency.

#### Scenario: Review affected function contracts
- **WHEN** affected functions, their callers and port implementations are reviewed
- **THEN** annotations describe actual inputs/results, optional values are handled explicitly and existing behavioral tests remain applicable without installing additional typing tools

#### Scenario: Editor diagnostics when available
- **WHEN** Pylance diagnostics are available in VSCode during verification
- **THEN** relevant genuine type inconsistencies are corrected; if the editor is unavailable, the report records that limitation without claiming its diagnostics ran
