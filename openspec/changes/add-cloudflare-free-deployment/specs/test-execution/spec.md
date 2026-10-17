# Spec Delta

## MODIFIED Requirements

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

### Requirement: Remove the active SQLite test dependency without rewriting history

La resolución CPython y los fixtures PostgreSQL SHALL seguir sin aiosqlite ni SQLite como sustituto del servidor real. Las migraciones históricas 0001–0005 SHALL permanecer intactas, incluidas opciones inertes de dialecto. La nueva suite Cloudflare SHALL comprobar D1 mediante su runtime oficial, de forma independiente, sin cambiar el comportamiento o la precedencia de URL PostgreSQL.

#### Scenario: Install and verify with historical migrations retained
- **WHEN** se instalan dependencias y se ejecutan las verificaciones PostgreSQL y Cloudflare
- **THEN** PostgreSQL conserva sus fixtures y ausencia de aiosqlite, D1 se comprueba por separado y las revisiones históricas no cambian

### Requirement: Run a reproducible backend type check

Las dependencias bloqueadas SHALL proporcionar el chequeo Pyright compartido con cero errores/advertencias. SHALL conservar Python 3.11 para código compartido, strict en dominio/aplicación/adaptadores/composición/entradas y el análisis de tests, migraciones 0004/0005 y entorno Alembic. Fuentes exclusivas Workers podrán tener un entorno de análisis 3.13 sin rebajar lo anterior; SHALL no excluirse producción nueva ni ocultarse tipos con Any o supresiones.

#### Scenario: Check without services
- **WHEN** `uv run --extra dev pyright --project .. --warnings` se ejecuta desde backend con las dependencias declaradas y sin servicios
- **THEN** analiza el alcance existente y nuevo y solo termina con éxito con cero errores y cero advertencias, sin conexiones de infraestructura

#### Scenario: Correct the entire analyzed scope
- **WHEN** aparecen diagnósticos en producción, tests o migraciones incluidas
- **THEN** se corrigen sus causas sin exclusiones amplias, reglas desactivadas, Any generalizado o anotaciones falsas

## ADDED Requirements

### Requirement: Verify D1 contracts on the native runtime

La suite Cloudflare SHALL ejecutar los contratos HTTP/persistencia aplicables mediante Workers y bindings D1 oficiales, con migraciones reales, fixtures aislados y fallo explícito si falta el entorno requerido. SHALL comprobar concurrencia, rollback, integridad, precisión y lotes máximos. Dobles o SQLite CPython SHALL no sustituir esa evidencia.

#### Scenario: Exercise custody concurrency and rollback
- **WHEN** se ejecutan las carreras de última celda, configuración contra recepción, salidas concurrentes, fallo de batch y reocupación segura
- **THEN** se verifican los mismos resultados de negocio que PostgreSQL, además de pérdida de CAS sin escrituras y contención agotada 503

#### Scenario: Verify maxima and the query budget
- **WHEN** se crean/amplían 1000 celdas, se consultan configuraciones acumuladas y se prueban dimensiones máximas y fechas con microsegundos
- **THEN** se conservan precisión y atomicidad, sin truncar listas, exceder parámetros o superar el presupuesto D1 definido en el diseño

### Requirement: Supplement native evidence with a local D1 test bridge

Los adaptadores Python reales SHALL probarse también desde CPython contra D1 local de Miniflare mediante un puente JavaScript/HTTP exclusivo de tests, con migraciones reales y recursos aislados que se limpian tras éxito o fallo. El puente SHALL preservar batches atómicos y excluirse de producción. Esta evidencia SHALL informarse por separado y no sustituir Python/WASM, eventos/Queues nativos ni aceptación Free.

#### Scenario: Exercise real adapters against local D1
- **WHEN** el harness CPython ejecuta los adaptadores reales mediante el puente local
- **THEN** sus consultas y batches se ejecutan en D1 de Miniflare, permitiendo comprobar contratos, CAS y rollback sin copiar reglas de negocio ni SQL en el puente
- **AND** el batch se envía como una sola operación al binding, sin commits parciales ni reintentos añadidos por el transporte de tests

#### Scenario: Preserve pending native evidence
- **WHEN** el puente pasa pero el runtime Python Workers no puede ejecutarse
- **THEN** solo se acredita la integración CPython/D1 local, las comprobaciones nativas ausentes siguen pendientes y el check nativo no se presenta como aprobado

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
