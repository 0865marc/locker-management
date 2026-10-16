# Spec Delta

## MODIFIED Requirements

### Requirement: Preserve PostgreSQL geography and custody evidence

The PostgreSQL suite SHALL retain isolated schemas, explicit configuration failures, historical migration, metadata, rollback and custody-concurrency scenarios. It SHALL verify populated 0003-to-0004 geographic upgrade, guarded downgrade and compatible locker HTTP contracts. The comparator SHALL require no integration service. Only the new messaging suite SHALL require RabbitMQ; existing PostgreSQL tests SHALL remain executable without it.

#### Scenario: Geographic migration coverage
- **WHEN** historical migration tests run explicitly through 0004 and metadata tests run at current head
- **THEN** explicit 0002-to-0003 and geography evidence remains, current constraints agree with metadata and rejected downgrades preserve data/schema/revision without weakening occupancy constraints

#### Scenario: Compatible locker administration
- **WHEN** integration tests create legacy and address-only lockers and patch or clear geographic values
- **THEN** values persist atomically, historical nulls and alias filtering are preserved, and existing custody/availability contracts still pass

### Requirement: Run a reproducible backend type check

The locked development dependencies SHALL provide Pyright with shared root configuration for CLI and Pylance. Analysis SHALL include backend production and tests, targeting Python 3.11 with backend/.venv. Domain, application, adapters, main and the worker entry point SHALL use strict mode; tests SHALL use standard mode. Only environments/caches and historical migrations 0001–0003 SHALL be excluded. Migrations 0004, 0005 and the migration environment SHALL remain checked.

#### Scenario: Check without services
- **WHEN** `uv run --extra dev pyright --project .. --warnings` runs from backend with the development dependencies installed and no database configuration
- **THEN** it analyzes the configured backend and returns success only with zero errors and zero warnings, without connecting to a database or broker

#### Scenario: Correct the entire analyzed scope
- **WHEN** diagnostics occur in production, tests or migration code included in analysis
- **THEN** their real causes are corrected without hiding them through broad exclusions, disabled rules, generalized Any or untruthful narrowing

## ADDED Requirements

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
