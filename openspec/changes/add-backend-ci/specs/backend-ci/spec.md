# Spec Delta

## Purpose

Provide repeatable backend quality and runtime evidence on pull requests and the main branch, with five independent checks that expose failures without changing application behavior.

## ADDED Requirements

### Requirement: Report five independent CI checks

GitHub Actions SHALL run five independently reported checks for pull requests targeting main and pushes to main: Ruff, Pyright, unit tests, PostgreSQL integration with migrations, and Docker build with API smoke. Failures SHALL fail their check. Each run SHALL have bounded execution, read-only repository permissions and no deployment credentials. A newer update to a PR SHALL cancel its superseded run without cancelling another PR.

#### Scenario: Verify a pull request and its merge
- **WHEN** a pull request to main is opened or updated, or a commit is pushed to main
- **THEN** all five checks run with stable names, including for changes outside backend, and each reports its own outcome without suppressing command failures

#### Scenario: Replace obsolete pull request work
- **WHEN** a PR receives another commit while its checks are running
- **THEN** its older run is cancelled, the newer revision is verified and runs for other PRs remain unaffected

### Requirement: Use the committed dependency resolution

CI environments and the application image SHALL install the committed dependency resolution and fail when it is inconsistent with the declared dependencies. Verification SHALL not update the lockfile or source files. Local documentation SHALL provide equivalent commands and identify the selected CI suites separately from the complete local suite.

#### Scenario: Reproduce checks from a clean checkout
- **WHEN** the committed dependency declarations and lockfile agree
- **THEN** a clean CI environment and Docker build install the locked dependency versions, and a developer can reproduce the documented checks without modifying tracked files

#### Scenario: Reject dependency drift
- **WHEN** dependency declarations change without the required lockfile update
- **THEN** installation fails before affected verification instead of silently resolving a different dependency set

### Requirement: Enforce a shared Ruff lint and format policy

The Ruff check SHALL verify lint, import ordering and formatting against one committed configuration without modifying files. Backend production and test Python SHALL be covered except the explicitly listed historical migration files 0001 through 0005. Future migrations and the migration environment SHALL remain covered. Initial normalization SHALL preserve application behavior and historical migration contents.

#### Scenario: Reject inconsistent code
- **WHEN** an analyzed file violates a selected lint rule, import order or the formatter output
- **THEN** the Ruff check fails with the affected file and diagnostic, and local checks apply the same policy

#### Scenario: Preserve migration history without excluding future work
- **WHEN** initial normalization and subsequent Ruff verification run
- **THEN** migrations 0001 through 0005 remain byte-for-byte unchanged, while the migration environment and future revisions are analyzed

### Requirement: Require a clean configured type check

The Pyright check SHALL run the repository's configured backend analysis and succeed only with zero errors and zero warnings. It SHALL preserve the shared scope, strictness and exclusions, including analysis of the worker, tests, migration environment and migrations 0004 and 0005. It SHALL not require running services.

#### Scenario: Type diagnostics block success
- **WHEN** runtime tests pass but configured type analysis reports an error or warning
- **THEN** the Pyright check fails and neither broader exclusions nor weaker rules are used to make it pass

#### Scenario: Analyze without infrastructure
- **WHEN** PostgreSQL and RabbitMQ are unavailable and their test URLs are unset
- **THEN** configured type analysis runs without opening service connections

### Requirement: Execute unit tests without services

The unit check SHALL discover and execute the existing unit suite without PostgreSQL, RabbitMQ or their test URLs. Failed tests or discovery errors SHALL fail the check. Its result SHALL be identified as unit evidence rather than as execution of the complete suite.

#### Scenario: Run the service-free suite
- **WHEN** the unit check runs on a runner without database or broker services
- **THEN** domain, application, isolated adapter and composition unit tests execute and their failures propagate to the check

### Requirement: Execute PostgreSQL integration and migration scenarios

The integration check SHALL execute the existing PostgreSQL integration suite, including migration history, schema agreement, rollback and concurrency scenarios, against an ephemeral dedicated database. It SHALL preserve per-case schema isolation and require explicit valid test configuration. Missing services, configuration or permissions SHALL fail rather than skip database-dependent checks. RabbitMQ SHALL not be required by this check.

#### Scenario: Verify real database behavior
- **WHEN** the dedicated PostgreSQL service is healthy and test configuration is valid
- **THEN** the integration suite executes with isolated schemas, including upgrade/downgrade guards and migrated-schema comparison, and its failures fail the check

#### Scenario: Reject incomplete database verification
- **WHEN** the URL is missing or invalid, PostgreSQL is unreachable, or schema creation is denied
- **THEN** integration fails with a clear diagnostic and is not reported as passing with database tests skipped

### Requirement: Verify the built API against disposable dependencies

The Docker check SHALL build the application image and start the API with its existing PostgreSQL, migration and RabbitMQ dependencies in an isolated disposable stack. Success SHALL require successful migrations and an HTTP response from an existing database-backed route within a fixed deadline. Build, migration, startup or response failures SHALL fail the check with useful logs. Cleanup SHALL affect only resources created for that run.

#### Scenario: Build and start the application
- **WHEN** the image builds and the isolated stack starts against a fresh database
- **THEN** migrations succeed and GET /lockers returns HTTP 200 with an empty JSON array within the deadline, without starting the worker or adding an API endpoint

#### Scenario: Fail and clean up a broken stack
- **WHEN** building, migration, service startup or the expected HTTP response fails
- **THEN** the check exits nonzero, exposes diagnostic logs and cleans up its own stack without removing development data or reporting a successful smoke
