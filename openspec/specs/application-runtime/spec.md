# Application Runtime Specification

## Purpose

Run the API with its dependencies wired together, resolve the database connection, and coordinate startup readiness through Docker Compose.

## Requirements

### Requirement: Resolve the database connection

The API SHALL resolve its connection in this order of precedence: a non-empty explicit URL, `DATABASE_URL`, and the default connection. Migrations SHALL use `DATABASE_URL` and, if it is not set, the default connection. In both cases, the default SHALL be `postgresql+asyncpg://hexagonal:hexagonal@localhost:5432/hexagonal`.

#### Scenario: Configuration through the environment
- **WHEN** `DATABASE_URL` is set and the API receives no explicit URL
- **THEN** both the API and migrations use the configured value

#### Scenario: Explicit URL
- **WHEN** an API instance is constructed with a non-empty explicit URL
- **THEN** that instance uses the supplied URL even if `DATABASE_URL` has a different value

#### Scenario: Default connection
- **WHEN** `DATABASE_URL` is not set and the API receives no non-empty explicit URL
- **THEN** the API and migrations use the default local connection

### Requirement: Manage resources per application instance

Each API instance SHALL wire together and reuse its delivery and return services and connection resources. On exiting its lifecycle, it SHALL dispose of the database engine, including when that exit results from an exception.

#### Scenario: Resource reuse and cleanup
- **WHEN** an instance handles delivery and return operations and then ends its lifecycle, either normally or due to an exception
- **THEN** the operations use the services wired for that instance and its engine is disposed of on exit

### Requirement: Coordinate readiness and persistence with Compose

The Compose configuration SHALL require PostgreSQL to be healthy before migrations run and migrations to succeed before the API starts. It SHALL store PostgreSQL data in the named volume `postgres_data`.

#### Scenario: Startup depends on migrations
- **WHEN** the services are started with Compose
- **THEN** the migration service waits for PostgreSQL to be healthy and the API waits for `alembic upgrade head` to complete successfully

#### Scenario: Retain the volume when stopping services
- **WHEN** `docker compose down` is run without requesting volume removal
- **THEN** the `postgres_data` volume is retained for a subsequent startup
