# Application Runtime Specification

## Purpose

Run the API with its dependencies wired together, resolve the database connection, and coordinate startup readiness through Docker Compose.

## Requirements

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

### Requirement: Present the application identity

The API SHALL identify itself as `Locker Management Demo` in its OpenAPI title and interactive documentation.

#### Scenario: Read the API documentation
- **WHEN** a client reads `/openapi.json` or opens `/docs`
- **THEN** the API title is `Locker Management Demo`
- **AND** the existing endpoint paths, operations and business schemas are preserved

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

### Requirement: Generate synthetic lockers manually through the API

The manual generator SHALL create 250 demonstration lockers by default through POST /lockers, supporting positive --count, API base URL, reproducible --seed and --dry-run without HTTP. Each SHALL have a DEMO alias, active state, enabled free compartments and a complete address/coordinate pair from the bundled real-location catalogue. Runtime SHALL NOT download or geocode locations. Startup/builds SHALL NOT invoke the generator.

#### Scenario: Create the requested demonstration collection
- **WHEN** the script runs against a dedicated API with default count and successful responses
- **THEN** exactly 250 new lockers have street, explicit street number, postal code, city, province, country ES and coordinates from their respective source records
- **AND** no source postcode is attached to another random or perturbed position

#### Scenario: Override quantity and exhaust the catalogue
- **WHEN** --count requests 12 lockers or more lockers than the catalogue contains
- **THEN** that exact number is generated, with repetition allowed after exhausting catalogue records
- **AND** existing lockers are neither removed nor updated, including those without addresses

#### Scenario: Reproduce generation without external services
- **WHEN** two dry runs use the same seed, count and catalogue version without network access
- **THEN** they produce identical ordered complete payloads without HTTP, geocoding or fabricated address fields
- **AND** reproducibility covers payloads, not server-generated UUIDs

### Requirement: Preserve traceable real address and coordinate records

The bundled catalogue SHALL retain complete addresses and coordinates together from a fixed documented source. Provenance SHALL identify the source snapshot/date, record identifiers, normalization, hashes and reuse conditions. Ambiguous or incomplete addresses SHALL be excluded rather than invented. Documentation SHALL distinguish source-backed locations from synthetic lockers and physical verification, including possible repeated locations.

#### Scenario: Verify provenance and unambiguous normalization
- **WHEN** a catalogue record is checked against its identified source record
- **THEN** street/number, postcode, municipality/province and coordinates correspond without location jitter or inferred postal data
- **AND** ambiguous road/kilometre text is not converted into a fabricated street number; source attribution/date is retained without implying endorsement

#### Scenario: Invalid catalogue before creation
- **WHEN** the catalogue is unreadable or contains invalid required fields or coordinates
- **THEN** the generator reports the problem before issuing any creation request

### Requirement: Report partial demonstration creation without destructive recovery

The generator SHALL validate its options before sending data, issue bounded sequential creation requests and stop on the first failed or uncertain response. It SHALL report confirmed creations and the failure, return a nonzero exit code, and preserve all existing data. It SHALL NOT retry writes blindly, delete lockers or claim a batch rollback. Documentation SHALL identify synthetic data and explain that another execution adds new records.

#### Scenario: Partial or uncertain failure
- **WHEN** a creation request fails or times out after earlier requests succeeded
- **THEN** the script reports the confirmed count and affected item, stops further creation and makes no retry or deletion
- **AND** an uncertain final request is not reported as a confirmed creation

### Requirement: Build and serve a fully static frontend

The repository SHALL provide locked frontend dependencies and documented development, build and static-preview commands. A build SHALL generate only static HTML, CSS and browser assets in `frontend/dist`, without reading locker data. The output SHALL run on a generic static HTTP host without an application server or server-side functions. Existing backend Compose services and persistence SHALL remain independent of the frontend.

#### Scenario: Build while the backend is offline
- **WHEN** dependencies are installed and the frontend is built while the configured API is unavailable
- **THEN** the static build succeeds without requesting lockers or embedding a locker snapshot
- **AND** serving `dist` from a generic static HTTP server delivers the page, whose browser code handles API availability at visit time

#### Scenario: Preserve backend startup
- **WHEN** an operator starts only the existing backend services with Compose or runs its smoke script
- **THEN** migrations, API, broker, worker and named volumes retain their existing behavior without requiring a frontend container

### Requirement: Serve the static frontend through Compose

Default Compose startup SHALL include a frontend serving only the generated static files at `http://127.0.0.1:4321`. Its image SHALL build without the API and run without Node or an API proxy. Compose SHALL pass `PUBLIC_API_BASE_URL` at build time, defaulting to `http://127.0.0.1:8000` when unset. Browser API reads SHALL remain direct. The CI Compose override SHALL publish no frontend host port.

#### Scenario: Start the complete application locally
- **WHEN** an operator runs `docker compose up --build` with default local settings
- **THEN** the static page is available on port 4321 and, once the API is ready, the browser reads lockers directly from port 8000 using the existing CORS policy
- **AND** no separate npm process is required to serve the page

#### Scenario: Build and serve without API availability
- **WHEN** the frontend image is built and started while the API is unavailable
- **THEN** image creation and static page delivery succeed independently, and API failures are handled by the existing browser error state

#### Scenario: Configure another browser-visible API
- **WHEN** the operator supplies a different `PUBLIC_API_BASE_URL` and rebuilds the frontend image
- **THEN** its browser assets use that URL directly, without relying on Docker-internal hostnames or runtime substitution

#### Scenario: Isolate CI ports
- **WHEN** Compose merges the CI override
- **THEN** the frontend has no published host port and the backend-only smoke remains independently runnable

### Requirement: Configure the public API address at build time

The frontend SHALL use `PUBLIC_API_BASE_URL` embedded at build time for direct browser requests to the API. The value SHALL contain no credentials or secrets. Changing it SHALL require rebuilding the static assets. Missing or malformed configuration, and an HTTP API address on an HTTPS page, SHALL produce a visible configuration error without requesting lockers or silently falling back to localhost.

#### Scenario: Hosted HTTPS frontend
- **WHEN** a static HTTPS page is built with an accessible HTTPS API URL and its origin is allowed by that API
- **THEN** the browser reads the configured API's `GET /lockers` directly without a frontend intermediary

#### Scenario: Missing or insecure configuration
- **WHEN** the configured URL is absent, invalid, or uses HTTP while the page uses HTTPS
- **THEN** the UI explains that the connection is not correctly configured, shows no fabricated results and performs no fallback request

#### Scenario: Change API after a build
- **WHEN** an operator changes the build environment's API URL but serves the previous `dist` unchanged
- **THEN** the page still uses its embedded URL until a new build is generated and published

### Requirement: Allow scoped browser access from explicit origins

CORS SHALL use the existing exact-origin allowlist, without credentials or wildcards. It SHALL permit GET generally and preflight for POST with JSON Content-Type only at /quotations. Other write preflights SHALL remain denied. Invalid origins SHALL fail configuration; absent/empty configuration SHALL allow none. Endpoint contracts and requests without Origin SHALL remain unchanged; CORS is not authorization.

#### Scenario: Allowed quotation creation and observation
- **WHEN** a listed origin requests preflight for POST /quotations with Content-Type and then submits valid JSON
- **THEN** browser CORS permits the existing POST and subsequent GET /quotations/{id}, without credentials or a proxy
- **AND** GET /lockers remains readable from that same exact origin

#### Scenario: Unlisted origin or unrelated write
- **WHEN** an unlisted origin requests access, or a client requests preflight for POST /lockers, PATCH, DELETE or an unsupported header
- **THEN** that preflight is denied and no broad write-method or origin wildcard is introduced
- **AND** the policy does not claim to prevent direct HTTP clients from invoking existing endpoints

#### Scenario: No Origin and invalid configuration
- **WHEN** requests omit Origin or the allowlist is configured with an invalid origin
- **THEN** normal endpoint behavior remains unchanged for requests without Origin, while invalid configuration fails clearly before application startup

### Requirement: Document static Cloudflare Pages publication

The repository SHALL document preparation for Cloudflare Pages static hosting using root `frontend`, build command `npm run build`, output `dist`, Node build version and locked dependency installation. It SHALL explain the build-time API URL and exact backend CORS origins, including explicitly configured preview origins. The API SHALL be documented as a separately hosted HTTPS prerequisite; no backend hosting or actual publication is implied.

#### Scenario: Prepare publication with project-specific values
- **WHEN** an operator follows the Pages instructions
- **THEN** placeholders identify the public HTTPS API and the exact Pages or custom-domain origin to configure
- **AND** the instructions describe static hosting without frontend server functions and require a rebuild when the API URL changes
