# Spec Delta

## ADDED Requirements

### Requirement: Present the application identity

The API SHALL identify itself as `Locker Management Demo` in its OpenAPI title and interactive documentation.

#### Scenario: Read the API documentation
- **WHEN** a client reads `/openapi.json` or opens `/docs`
- **THEN** the API title is `Locker Management Demo`
- **AND** the existing endpoint paths, operations and business schemas are preserved

## MODIFIED Requirements

### Requirement: Resolve the database connection

The API SHALL resolve its connection in this order of precedence: a non-empty explicit URL, `DATABASE_URL`, and the default connection. Migrations SHALL use `DATABASE_URL` and, if it is not set, the default connection. In both cases, the default SHALL be `postgresql+asyncpg://locker_management_demo:locker_management_demo@localhost:5432/locker_management_demo`.

#### Scenario: Configuration through the environment
- **WHEN** `DATABASE_URL` is set and the API receives no explicit URL
- **THEN** both the API and migrations use the configured value
- **AND** previously configured database names and credentials remain valid

#### Scenario: Explicit URL
- **WHEN** an API instance is constructed with a non-empty explicit URL
- **THEN** that instance uses the supplied URL even if `DATABASE_URL` has a different value

#### Scenario: Default connection
- **WHEN** `DATABASE_URL` is not set and the API receives no non-empty explicit URL
- **THEN** the API and migrations use the default local connection

### Requirement: Coordinate readiness and persistence with Compose

Compose SHALL default to project `locker-management-demo`, with explicit overrides supported. It SHALL wait for healthy PostgreSQL before migrations and for successful migrations and healthy RabbitMQ before API and single-worker startup. Data SHALL use named `postgres_data` and `rabbitmq_data` volumes. PostgreSQL database/user/password and RabbitMQ user/password SHALL default to `locker_management_demo`, with explicit existing settings supported.

#### Scenario: Startup depends on migrations
- **WHEN** the services are started with Compose
- **THEN** the migration service waits for PostgreSQL to be healthy and the API and single worker wait for `alembic upgrade head` to complete successfully and RabbitMQ to be healthy

#### Scenario: Retain the volume when stopping services
- **WHEN** `docker compose down` is run without requesting volume removal
- **THEN** the `postgres_data` and `rabbitmq_data` volumes are retained for a subsequent startup

#### Scenario: Fresh installation with default settings
- **WHEN** Compose starts with no project or service-credential overrides and no existing volumes for that project
- **THEN** it uses project `locker-management-demo`, PostgreSQL database/user/password `locker_management_demo`, and RabbitMQ user/password `locker_management_demo`
- **AND** API, migration service and worker share the PostgreSQL settings through host `db`, while API and worker share the broker settings through host `rabbitmq`

#### Scenario: Continue using an existing installation
- **WHEN** an operator follows the documented transition for a running installation at the current schema revision, selects its previous Compose project and PostgreSQL/RabbitMQ credentials explicitly, and stops only API and worker
- **THEN** Compose selects the previous physical `postgres_data` and `rabbitmq_data` volumes and configures clients consistently with those credentials
- **AND** database records and the Alembic revision are preserved without renaming roles, databases or volumes
- **AND** the existing RabbitMQ container and node remain unchanged through the identity-only transition

#### Scenario: Preserve the current quotation runtime
- **WHEN** the renamed installation starts with a healthy database and broker and receives a quotation request
- **THEN** the API and worker retain the current quotation behavior, queue semantics and simulation settings
- **AND** the conventional local RabbitMQ fallback remains `amqp://guest:guest@localhost/` when `RABBITMQ_URL` is absent outside Compose
