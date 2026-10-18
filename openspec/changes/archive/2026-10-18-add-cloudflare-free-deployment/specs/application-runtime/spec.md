# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
