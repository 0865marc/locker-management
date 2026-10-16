# Spec Delta

## MODIFIED Requirements

### Requirement: Manage resources per application instance

Each API instance SHALL wire together and reuse its delivery, return, locker and quotation services and connection resources. Its quotation publisher SHALL use RABBITMQ_URL and SHALL not run provider comparisons. On lifecycle exit, including exceptions, the API SHALL dispose of its database engine and close any acquired broker resources.

#### Scenario: Resource reuse and cleanup
- **WHEN** an API instance handles operations and then exits normally or due to an exception
- **THEN** it reuses its composed services and closes its database and broker resources

### Requirement: Coordinate readiness and persistence with Compose

Compose SHALL require healthy PostgreSQL before migrations and successful migrations before API or worker startup. API and the single worker SHALL also wait for healthy RabbitMQ. PostgreSQL and RabbitMQ SHALL retain their data in named postgres_data and rabbitmq_data volumes.

#### Scenario: Startup depends on migrations
- **WHEN** the services start with Compose
- **THEN** migrations wait for healthy PostgreSQL, and API/worker wait for successful migrations and healthy RabbitMQ

#### Scenario: Retain the volume when stopping services
- **WHEN** docker compose down runs without requesting volume removal
- **THEN** postgres_data and rabbitmq_data remain available for subsequent startup

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
