# Spec Delta

## MODIFIED Requirements

### Requirement: Manage resources per application instance

Each API instance SHALL wire together and reuse its delivery, return, locker and quotation services and connection resources. Its quotation publisher SHALL use RABBITMQ_URL and SHALL not run provider comparisons. On lifecycle exit, including exceptions, the API SHALL dispose of its database engine and close any acquired broker resources.

#### Scenario: Resource reuse and cleanup
- **WHEN** an API instance handles operations and then exits normally or due to an exception
- **THEN** it reuses its composed services and closes its database and broker resources

### Requirement: Coordinate readiness and persistence with Compose

Compose SHALL default to project `locker-management-demo`, with explicit overrides supported. It SHALL wait for healthy PostgreSQL before migrations and for successful migrations and healthy RabbitMQ before API and single-worker startup. Data SHALL use named `postgres_data` and `rabbitmq_data` volumes. PostgreSQL database/user/password and RabbitMQ user/password SHALL default to `locker_management_demo`, with explicit existing settings supported.

#### Scenario: Startup depends on migrations
- **WHEN** the services start with Compose
- **THEN** migrations wait for healthy PostgreSQL, and API/worker wait for successful migrations and healthy RabbitMQ

#### Scenario: Retain the volume when stopping services
- **WHEN** docker compose down runs without requesting volume removal
- **THEN** postgres_data and rabbitmq_data remain available for subsequent startup

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
- **THEN** the API and worker retain the current quotation behavior and queue semantics, using each simulator's fixed internal profile without worker simulation settings
- **AND** the conventional local RabbitMQ fallback remains `amqp://guest:guest@localhost/` when `RABBITMQ_URL` is absent outside Compose

## ADDED Requirements

### Requirement: Run one worker with simple runtime configuration

One worker SHALL process messages sequentially using the existing database URL policy and RABBITMQ_URL. It SHALL construct the three self-contained simulators without arguments, avoid migrations at startup and close resources and cancel/await provider calls on shutdown. It SHALL not automatically retry or recover consumed quotations.

#### Scenario: Start and stop the worker
- **WHEN** the worker starts with valid settings and later stops
- **THEN** it consumes sequentially without schema changes and cleans up its resources and active calls without replaying unfinished work

### Requirement: Keep provider behavior out of worker configuration

The worker SHALL use each provider's fixed internal profile without configuring or persisting it. Worker and Compose SHALL not expose simulation delay/probability environment settings. Previously used SHIPPING_DELAY_MIN_SECONDS, SHIPPING_DELAY_MAX_SECONDS, SHIPPING_NO_RESPONSE_PROBABILITY and SHIPPING_ERROR_PROBABILITY SHALL have no effect on provider behavior.

#### Scenario: Worker uses the same autonomous providers as direct callers
- **WHEN** the worker constructs its provider collection, with or without old simulation variables present in its environment
- **THEN** it supplies no constructor arguments and each provider retains its own fixed profile and unchanged tariff rules
