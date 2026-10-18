# Application Runtime Specification

## Purpose

Run the API with its dependencies wired together, resolve the database connection, and coordinate startup readiness through Docker Compose.

## Requirements

### Requirement: Resolve the database connection

En el perfil PostgreSQL, la API SHALL resolver la conexión por URL explícita no vacía, DATABASE_URL y conexión predeterminada, en ese orden. Sus migraciones SHALL usar DATABASE_URL o el valor predeterminado `postgresql+asyncpg://locker_management_demo:locker_management_demo@localhost:5432/locker_management_demo`. El perfil Cloudflare SHALL usar el binding D1 de su entorno, sin interpretar DATABASE_URL como selección o respaldo de D1.

#### Scenario: Configuration through the environment
- **WHEN** DATABASE_URL está configurada y la API PostgreSQL no recibe URL explícita
- **THEN** tanto API como migraciones PostgreSQL usan ese valor
- **AND** los nombres y credenciales configurados previamente siguen siendo válidos

#### Scenario: Explicit URL
- **WHEN** se construye una instancia PostgreSQL con URL explícita no vacía
- **THEN** usa esa URL aunque DATABASE_URL tenga otro valor

#### Scenario: Default connection
- **WHEN** no hay DATABASE_URL ni URL explícita no vacía en el perfil PostgreSQL
- **THEN** API y migraciones usan la conexión local predeterminada

#### Scenario: Cloudflare binding does not fall back
- **WHEN** el perfil Cloudflare tiene un binding D1 ausente o incorrecto
- **THEN** informa del error de configuración y no abre PostgreSQL ni selecciona otra base silenciosamente

### Requirement: Manage resources per application instance

Cada perfil SHALL componer y reutilizar los servicios de entregas, devoluciones, lockers y cotizaciones. PostgreSQL SHALL mantener RABBITMQ_URL para su publicador y cerrar motor/broker al salir, incluso por excepción. Cloudflare SHALL usar únicamente los bindings del evento actual, aislar peticiones concurrentes y no abrir conexiones PostgreSQL/AMQP ni consultar bindings durante import/snapshot. La API SHALL no ejecutar comparaciones de proveedores.

#### Scenario: Resource reuse and cleanup
- **WHEN** una instancia PostgreSQL atiende operaciones y termina normalmente o por excepción
- **THEN** reutiliza sus servicios compuestos y cierra sus recursos de base de datos y broker

#### Scenario: Reuse Cloudflare services without mixing bindings
- **WHEN** dos eventos concurrentes usan entornos Cloudflare distintos y uno falla
- **THEN** cada operación accede exclusivamente a sus bindings, se limpia su contexto y eventos posteriores no heredan el entorno anterior
- **AND** importar el paquete no abre conexiones ni reconstruye las rutas en cada petición

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

El consumidor SHALL procesar cotizaciones secuencialmente con los tres simuladores autónomos construidos sin argumentos, sin migrar, reintentar ni recuperar trabajo consumido. PostgreSQL SHALL conservar DATABASE_URL/RABBITMQ_URL y cerrar recursos y cancelar/esperar llamadas al apagarse. Cloudflare SHALL usar su entorno de evento y limitar el procesamiento simultáneo a una cotización por consumidor, completando o cancelando sus tareas dentro del evento.

#### Scenario: Start and stop the worker
- **WHEN** el worker PostgreSQL arranca con configuración válida y después se detiene
- **THEN** consume secuencialmente sin cambiar el esquema y limpia recursos y llamadas activas sin reproducir trabajo incompleto

#### Scenario: Handle Cloudflare queue events
- **WHEN** hay varias cotizaciones en la cola Cloudflare
- **THEN** el consumidor las procesa secuencialmente con los perfiles internos fijos de los proveedores y no inicia un bucle AMQP ni deja tareas desprendidas del evento

#### Scenario: Ignore legacy simulation settings in both profiles
- **WHEN** cualquiera de los consumidores arranca con antiguas variables de simulación SHIPPING_* presentes
- **THEN** construye los proveedores sin argumentos y sus perfiles privados y tarifas permanecen iguales a los del uso directo

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

CORS SHALL use the existing exact-origin allowlist, without credentials or wildcards. It SHALL permit GET and POST preflights with Content-Type on every path, without route-specific policies. PATCH, DELETE and unsupported headers SHALL remain denied in preflight. Invalid origins SHALL fail configuration; absent/empty configuration SHALL allow none. Endpoint contracts and requests without Origin SHALL remain unchanged; CORS is not authorization.

#### Scenario: Allowed quotation creation and observation
- **WHEN** a listed origin requests preflight for POST /quotations with Content-Type and then submits valid JSON
- **THEN** browser CORS permits the existing POST and subsequent GET /quotations/{id}, without credentials or a proxy
- **AND** GET /lockers remains readable from that same exact origin

#### Scenario: Unlisted origin or unrelated write
- **WHEN** an unlisted origin requests access, or a client requests preflight for PATCH, DELETE or an unsupported header such as Authorization or X-Admin
- **THEN** that preflight is denied and no method or origin wildcard is introduced
- **AND** the policy does not claim to prevent direct HTTP clients from invoking existing endpoints

#### Scenario: No Origin and invalid configuration
- **WHEN** requests omit Origin or the allowlist is configured with an invalid origin
- **THEN** normal endpoint behavior remains unchanged for requests without Origin, while invalid configuration in the server profile fails clearly before application startup and database-engine allocation

#### Scenario: Uniform policy beyond quotations
- **WHEN** a listed origin requests GET or POST preflight with Content-Type for /lockers, /deliveries, /returns, /quotations/ or a nonexistent path
- **THEN** the same CORS policy permits that preflight without credentials, regardless of path
- **AND** preflight does not invoke business handlers or create an endpoint; subsequent requests still follow the existing routing and payload validation

#### Scenario: Validate the Workers event configuration before handling requests
- **WHEN** a Workers HTTP event supplies its own CORS_ALLOWED_ORIGINS binding
- **THEN** that binding is validated before invoking business handlers, routes or persistence/queue I/O, including for requests without Origin
- **AND** missing or empty configuration allows no browser origin; invalid configuration fails without falling back to process configuration or another event's allowlist
- **AND** imports do not read event bindings, concurrent events do not leak configuration to each other, and the event context is restored after success or failure

### Requirement: Document static Cloudflare Pages publication

The repository SHALL document preparation for Cloudflare Pages static hosting using root `frontend`, build command `npm run build`, output `dist`, Node build version and locked dependency installation. It SHALL explain the build-time API URL and exact backend CORS origins, including explicitly configured preview origins. The API SHALL be documented as a separately hosted HTTPS prerequisite; no backend hosting or actual publication is implied.

#### Scenario: Prepare publication with project-specific values
- **WHEN** an operator follows the Pages instructions
- **THEN** placeholders identify the public HTTPS API and the exact Pages or custom-domain origin to configure
- **AND** the instructions describe static hosting without frontend server functions and require a rebuild when the API URL changes

### Requirement: Select infrastructure at deployment composition

El sistema SHALL ofrecer perfiles PostgreSQL/RabbitMQ y Cloudflare/D1/Queues seleccionados por su configuración de despliegue. Los contratos HTTP y de negocio SHALL ser compartidos, conservando PostgreSQL/RabbitMQ por defecto en Compose y en sus comandos documentados. La elección SHALL no depender de entradas HTTP ni copiar o escribir datos en ambos perfiles.

#### Scenario: Preserve an existing Compose installation
- **WHEN** una instalación existente ejecuta los mismos comandos, URLs y credenciales Compose
- **THEN** usa PostgreSQL/RabbitMQ con los mismos volúmenes, migraciones y semántica y no requiere herramientas ni cuenta Cloudflare

#### Scenario: Package the Cloudflare profile independently
- **WHEN** se prepara el paquete Cloudflare desde un checkout limpio
- **THEN** puede construir su runtime sin cargar SQLModel, asyncpg, Alembic o aio-pika y mantiene los mismos endpoints y reglas
- **AND** incluye los init de `entrypoints` y `entrypoints.cloudflare`, su API, consumidor, runtime y todos sus módulos compartidos, excluyendo `entrypoints.server`

#### Scenario: Start the grouped CPython entrypoints
- **WHEN** se ejecutan `uvicorn entrypoints.server.api:app` y `python -m entrypoints.server.consumer` con la configuración PostgreSQL/RabbitMQ correspondiente, dentro o fuera de Docker
- **THEN** conservan la API, el procesamiento secuencial y la limpieza de recursos del perfil original

#### Scenario: Import the entrypoint package without selecting a profile
- **WHEN** se importa únicamente `entrypoints`, `entrypoints.server` o `entrypoints.cloudflare`
- **THEN** no se importan sus entradas ni se construyen aplicaciones, SDKs o recursos de ningún perfil

#### Scenario: Delegate Cloudflare messages within the same deployment
- **WHEN** la entrada `entrypoints/cloudflare/api.py` recibe eventos HTTP y de cola sucesivos
- **THEN** `Default.fetch` sirve la API y `Default.queue` delega en `entrypoints/cloudflare/consumer.py`, reutilizando una aplicación y un procesador con el repositorio compartido
- **AND** el consumidor conserva reconocimiento previo, secuencia y limpieza del contexto del evento sin otro despliegue

#### Scenario: Import the Cloudflare consumer independently
- **WHEN** se importa `entrypoints.cloudflare.consumer` sin importar la API
- **THEN** no se carga `entrypoints.cloudflare.api`, la composición HTTP ni sus routers, ni se construye una aplicación o consulta bindings

#### Scenario: Keep event context within the Cloudflare entrypoints
- **WHEN** las entradas Cloudflare resuelven los bindings de un evento mediante `entrypoints.cloudflare.runtime`
- **THEN** conservan el aislamiento y la limpieza del contexto, y los adaptadores de base de datos y cola reciben sus proveedores sin importar `entrypoints`

### Requirement: Accept the Cloudflare queue event invocation

Las entradas Queues de producción y del spike SHALL aceptar el lote, entorno y contexto suministrados por el runtime, además de la llamada abreviada con solo lote. SHALL conservar los bindings de la instancia del evento, el reconocimiento previo y la restauración del contexto, sin reintentos ni cambios en el procesamiento.

#### Scenario: Invoke with the complete platform arguments
- **WHEN** el runtime entrega lote, entorno y contexto a cualquiera de las dos entradas
- **THEN** la entrada alcanza el consumidor sin error por número de argumentos y utiliza el entorno de su instancia, sin sustituirlo por el argumento adicional del callback
- **AND** reconoce cada mensaje antes de leer su cuerpo o realizar trabajo de persistencia o aplicación

#### Scenario: Preserve the abbreviated invocation
- **WHEN** una llamada suministra únicamente el lote a una instancia con su entorno establecido
- **THEN** conserva la misma delegación y procesamiento que la invocación completa

#### Scenario: Restore the event context after success or failure
- **WHEN** termina el procesamiento o falla el reconocimiento o el trabajo posterior
- **THEN** el contexto anterior queda restaurado; un reconocimiento fallido impide leer el cuerpo o iniciar trabajo y no se añade ningún reintento
