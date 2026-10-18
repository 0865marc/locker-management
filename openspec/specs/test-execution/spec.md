# test-execution Specification

## Purpose

Provide independent service-free unit tests and isolated PostgreSQL integration tests, with explicit execution failures and preserved behavioral coverage.

## Requirements

### Requirement: Run unit tests without database services

The documented unit-test command SHALL discover and execute domain, application, provider-contract, isolated HTTP-adapter and composition tests without TEST_DATABASE_URL, running services or a SQLite driver. Unit execution SHALL not create databases/schemas or service connections. The comparator SHALL be tested directly with in-process simulators and doubles without HTTP or locker persistence.

#### Scenario: Unit suite with no database configuration
- **WHEN** dependencies are installed without aiosqlite and the unit command runs with TEST_DATABASE_URL unset and PostgreSQL unavailable
- **THEN** unit scenarios execute successfully without contacting a database or importing an integration fixture that requires one

#### Scenario: Comparator without infrastructure
- **WHEN** transport data is compared directly using simulators or doubles without services
- **THEN** validation, normalized offers, no coverage and technical failures are verified without HTTP requests or database connections

### Requirement: Require PostgreSQL for integration and full execution

La suite PostgreSQL y la ejecución completa existente SHALL requerir TEST_DATABASE_URL explícita postgresql+asyncpg. Configuración ausente/inválida, servidor inaccesible o permisos insuficientes SHALL fallar con estado no cero y diagnóstico sin credenciales, sin omitir pruebas ni sustituir PostgreSQL por SQLite/D1. La verificación Cloudflare SHALL ejecutarse por separado y añadirse a la evidencia completa de los dos perfiles.

#### Scenario: Missing integration configuration
- **WHEN** la integración PostgreSQL o la suite completa existente corre sin TEST_DATABASE_URL
- **THEN** falla claramente con estado no cero, sin presentarse como éxito con pruebas omitidas

#### Scenario: Wrong backend or unreachable server
- **WHEN** TEST_DATABASE_URL selecciona otro driver o PostgreSQL no es accesible
- **THEN** falla con diagnóstico de configuración/conexión sin cambiar a otra URL, SQLite o D1

#### Scenario: Configured integration
- **WHEN** la base PostgreSQL dedicada es accesible con permisos de esquema
- **THEN** se ejecutan sus escenarios aplicables sin omisiones por entorno

### Requirement: Isolate integration data and clean up resources

Cada caso de integración PostgreSQL SHALL usar un esquema generado propio, sin alterar public ni otros esquemas. Su preparación SHALL usar migraciones salvo pruebas explícitas de esquema ausente. La limpieza SHALL cerrar clientes/conexiones/motores y retirar el esquema después de éxito, fallo o setup parcial. Los casos D1 SHALL usar almacenamiento local o remoto de prueba aislado y limpiar solo recursos creados por el caso.

#### Scenario: Test fails after schema creation
- **WHEN** setup o ejecución falla tras crear el esquema PostgreSQL del caso
- **THEN** la limpieza registrada elimina ese esquema y cierra recursos sin borrar datos ajenos

#### Scenario: Persistence across application instances
- **WHEN** una instancia escribe/cierra y otra abre el almacenamiento del mismo caso
- **THEN** la segunda observa datos confirmados y ambas permanecen aisladas de otros casos

### Requirement: Preserve database behavior coverage on PostgreSQL

The integration suite SHALL retain the existing repository, HTTP, rollback, constraint, migration and concurrency scenarios when removing SQLite. It SHALL verify aware UTC round trips, shared capacity and safe reoccupation, additive and protected historical migrations, and agreement between migrated PostgreSQL schema and current metadata. Equivalent consolidation SHALL preserve identifiable scenario evidence.

#### Scenario: Historical migration coverage survives the port
- **WHEN** the PostgreSQL migration suite executes
- **THEN** it checks 0001 legacy columns, empty history round trips, populated-legacy upgrade rejection, populated-custody downgrade rejection, additive 0002-to-0003 upgrade and rejection of locker-data loss, preserving snapshots on rejection

#### Scenario: No loss of concurrency or schema evidence
- **WHEN** the complete integration suite executes
- **THEN** independent database connections still exercise competing receptions/exits and rollback, and a migrated empty schema matches metadata with its active-occupancy unique index intact

### Requirement: Remove the active SQLite test dependency without rewriting history

La resolución CPython y los fixtures PostgreSQL SHALL seguir sin aiosqlite ni SQLite como sustituto del servidor real. Las migraciones históricas 0001–0005 SHALL permanecer intactas, incluidas opciones inertes de dialecto. La nueva suite Cloudflare SHALL comprobar D1 mediante su runtime oficial, de forma independiente, sin cambiar el comportamiento o la precedencia de URL PostgreSQL.

#### Scenario: Install and verify with historical migrations retained
- **WHEN** se instalan dependencias y se ejecutan las verificaciones PostgreSQL y Cloudflare
- **THEN** PostgreSQL conserva sus fixtures y ausencia de aiosqlite, D1 se comprueba por separado y las revisiones históricas no cambian

### Requirement: Verify provider extensibility and cancellation

Tests SHALL demonstrate a fourth injected provider and multiple services without modifying common domain/comparison logic. They SHALL distinguish no coverage, technical failure and timeout, preserve other providers' offers, reject invalid collections, bound concurrent calls and verify cancellation cleanup. Concurrency evidence SHALL use observable barriers/events rather than timing assumptions or external provider APIs.

#### Scenario: Fourth provider with two services
- **WHEN** a double with its own code and two service offers is supplied alongside three simulators
- **THEN** direct comparison returns all four providers and the two normalized services without provider-specific branches

#### Scenario: Invalid configuration and cancellation
- **WHEN** tests supply empty/duplicate provider collections or cancel a comparison with active/waiting children
- **THEN** configuration fails clearly before calls and cancellation leaves no active or detached work

### Requirement: Preserve PostgreSQL geography and custody evidence

The PostgreSQL suite SHALL retain isolated schemas, explicit configuration failures, historical migration, metadata, rollback and custody-concurrency scenarios. It SHALL verify populated 0003-to-0004 geographic upgrade, guarded downgrade and compatible locker HTTP contracts. The comparator SHALL require no integration service. Only the new messaging suite SHALL require RabbitMQ; existing PostgreSQL tests SHALL remain executable without it.

#### Scenario: Geographic migration coverage
- **WHEN** historical migration tests run explicitly through 0004 and metadata tests run at current head
- **THEN** explicit 0002-to-0003 and geography evidence remains, current constraints agree with metadata and rejected downgrades preserve data/schema/revision without weakening occupancy constraints

#### Scenario: Compatible locker administration
- **WHEN** integration tests create legacy and address-only lockers and patch or clear geographic values
- **THEN** values persist atomically, historical nulls and alias filtering are preserved, and existing custody/availability contracts still pass

### Requirement: Keep standard Python annotations complete and coherent

Affected existing and new functions SHALL have standard Python annotations for parameters, returns, collections, generics and optional values. Ports and adapters SHALL agree on types, with correct narrowing. Real incompatibilities SHALL be corrected rather than hidden with generalized Any or suppressions. Historical migrations 0001–0003 SHALL remain unchanged. Verification SHALL include the configured Pyright check alongside annotation review and behavioral tests.

#### Scenario: Review affected function contracts
- **WHEN** affected functions, their callers and port implementations are reviewed
- **THEN** annotations describe actual inputs/results, optional values are handled explicitly and existing behavioral tests remain applicable and the configured type checker verifies compatibility

#### Scenario: Editor diagnostics when available
- **WHEN** Pylance diagnostics are available in VSCode during verification
- **THEN** relevant genuine type inconsistencies are corrected; if the editor is unavailable, the report records that limitation without claiming its diagnostics ran

### Requirement: Run a reproducible backend type check

Las dependencias bloqueadas SHALL proporcionar el chequeo Pyright compartido con cero errores/advertencias. SHALL conservar Python 3.11 para código compartido, strict en dominio/aplicación/adaptadores/composición/entradas y el análisis de tests, migraciones 0004/0005 y entorno Alembic. Fuentes exclusivas Workers podrán tener un entorno de análisis 3.13 sin rebajar lo anterior; SHALL no excluirse producción nueva ni ocultarse tipos con Any o supresiones.

#### Scenario: Check without services
- **WHEN** `uv run --extra dev pyright --project .. --warnings` se ejecuta desde backend con las dependencias declaradas y sin servicios
- **THEN** analiza el alcance existente y nuevo y solo termina con éxito con cero errores y cero advertencias, sin conexiones de infraestructura

#### Scenario: Correct the entire analyzed scope
- **WHEN** aparecen diagnósticos en producción, tests o migraciones incluidas
- **THEN** se corrigen sus causas sin exclusiones amplias, reglas desactivadas, Any generalizado o anotaciones falsas

### Requirement: Require type evidence before completing a spec

Completing implementation of each spec/change SHALL require the configured Pyright command to pass with zero errors and warnings, alongside relevant runtime tests. Builder and independent reviewer SHALL report the command and result; corrections affecting types SHALL trigger another check. Previous manual/AST inspection or editor screenshots SHALL not substitute for current CLI evidence.

#### Scenario: Type failures block completion
- **WHEN** functional tests pass but the final type command reports errors or warnings
- **THEN** implementation remains incomplete until the causes are corrected, the command passes and affected runtime tests are repeated

#### Scenario: Preserve earlier evidence honestly
- **WHEN** an earlier implementation was verified before the checker was introduced
- **THEN** its prior test/review evidence remains historical and no clean checker result is claimed until the configured command actually runs successfully

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

### Requirement: Verify D1 contracts on the native runtime

La suite Cloudflare SHALL ejecutar los contratos HTTP/persistencia aplicables mediante Workers y bindings D1 oficiales, con migraciones reales, fixtures aislados y fallo explícito si falta el entorno requerido. SHALL comprobar concurrencia, rollback, integridad, precisión y lotes máximos. Dobles o SQLite CPython SHALL no sustituir esa evidencia.

#### Scenario: Exercise custody concurrency and rollback
- **WHEN** se ejecutan las carreras de última celda, configuración contra recepción, salidas concurrentes, fallo de batch y reocupación segura
- **THEN** se verifican los mismos resultados de negocio que PostgreSQL, además de pérdida de CAS sin escrituras y contención agotada 503

#### Scenario: Verify maxima and the query budget
- **WHEN** se crean/amplían 1000 celdas, se consultan configuraciones acumuladas y se prueban dimensiones máximas y fechas con microsegundos
- **THEN** se conservan precisión y atomicidad, sin truncar listas, exceder parámetros o superar el presupuesto D1 definido en el diseño

### Requirement: Supplement native evidence with a local D1 test bridge

Los adaptadores Python reales SHALL probarse desde el entorno CPython bloqueado de Cloudflare contra D1 local de Miniflare mediante un puente JavaScript/HTTP exclusivo de tests, con migraciones reales y recursos aislados que se limpian tras éxito o fallo. El puente SHALL preservar batches atómicos y excluirse de producción. Esta evidencia SHALL informarse por separado y no sustituir Python/WASM, eventos/Queues nativos ni aceptación Free.

#### Scenario: Exercise real adapters against local D1
- **WHEN** el harness CPython ejecuta los adaptadores reales mediante el puente local
- **THEN** sus consultas y batches se ejecutan en D1 de Miniflare, permitiendo comprobar contratos, CAS y rollback sin copiar reglas de negocio ni SQL en el puente
- **AND** el batch se envía como una sola operación al binding, sin commits parciales ni reintentos añadidos por el transporte de tests

#### Scenario: Preserve pending native evidence
- **WHEN** el puente pasa pero el runtime Python Workers no puede ejecutarse
- **THEN** solo se acredita la integración CPython/D1 local, las comprobaciones nativas ausentes siguen pendientes y el check nativo no se presenta como aprobado

#### Scenario: Verify the Cloudflare dependency resolution
- **WHEN** se ejecutan las suites complementarias HTTP/D1/aceptación mediante `scripts/cloudflare/check.sh`
- **THEN** usan `deploy/cloudflare/.venv` con las dependencias bloqueadas del perfil Cloudflare, aunque el entorno backend tenga otras versiones
- **AND** comprueban los contratos existentes de validación y serialización sin sustituirlos por tests que solo comparan pins

#### Scenario: Reject a missing Cloudflare environment
- **WHEN** falta el intérprete del entorno Cloudflare requerido por el ejecutor
- **THEN** el comando falla con diagnóstico de instalación bloqueada y no recurre al entorno backend ni instala dependencias automáticamente

### Requirement: Verify Cloudflare messaging and event isolation

Pruebas unitarias y nativas SHALL cubrir publicación confirmada/fallida, ack previo, ack fallido, duplicados, resultados atómicos y ausencia de reejecución. SHALL verificar aislamiento de bindings entre eventos concurrentes y cleanup en error, manteniendo el smoke RabbitMQ existente. La emulación SHALL identificarse como evidencia local, no de cuotas Free remotas.

#### Scenario: Duplicate and failed deliveries
- **WHEN** se inyectan duplicados, un error de ack y un fallo posterior al reconocimiento
- **THEN** el primer caso compara como máximo una vez, el segundo no inicia trabajo y el tercero no provoca retry/republicación automática

#### Scenario: Complete from the wrong state
- **WHEN** se intenta persistir resultados desde un estado distinto de PROCESSING
- **THEN** se observa rechazo sin estado o resultados parciales y no un éxito silencioso

#### Scenario: Bindings are not leaked between events
- **WHEN** dos eventos con bases/colas de prueba distintas se intercalan y uno termina por excepción
- **THEN** cada escritura se limita a su entorno y el evento siguiente no reutiliza bindings anteriores
