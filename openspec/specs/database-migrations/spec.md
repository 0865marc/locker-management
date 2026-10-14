# Database Migrations Specification

## Purpose

Prepare and evolve the shared delivery and return schema through a migration history separate from API startup.

## Requirements

### Requirement: Manage a shared and reversible history

Migrations SHALL manage both tables through a single history. The initial revision `0001` SHALL create `deliveries` and `returns`, each with a UUID primary key and its required text field, and allow both tables to be removed when the revision is reverted.

#### Scenario: Apply the initial revision
- **WHEN** `alembic upgrade head` is run against an empty database with the current history
- **THEN** `deliveries` is created with `id` and `address`, and `returns` with `id` and `reason`, with UUID primary keys and non-null columns, and revision `0001` is recorded

#### Scenario: Revert the initial revision
- **WHEN** `alembic downgrade base` is run against a database at `0001`
- **THEN** the `deliveries` and `returns` tables are dropped

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
