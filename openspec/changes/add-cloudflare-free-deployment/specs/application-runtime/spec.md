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

## ADDED Requirements

### Requirement: Select infrastructure at deployment composition

El sistema SHALL ofrecer perfiles PostgreSQL/RabbitMQ y Cloudflare/D1/Queues seleccionados por su configuración de despliegue. Los contratos HTTP y de negocio SHALL ser compartidos, conservando PostgreSQL/RabbitMQ por defecto en Compose y en sus comandos documentados. La elección SHALL no depender de entradas HTTP ni copiar o escribir datos en ambos perfiles.

#### Scenario: Preserve an existing Compose installation
- **WHEN** una instalación existente ejecuta los mismos comandos, URLs y credenciales Compose
- **THEN** usa PostgreSQL/RabbitMQ con los mismos volúmenes, migraciones y semántica y no requiere herramientas ni cuenta Cloudflare

#### Scenario: Package the Cloudflare profile independently
- **WHEN** se prepara el paquete Cloudflare desde un checkout limpio
- **THEN** puede construir su runtime sin cargar SQLModel, asyncpg, Alembic o aio-pika y mantiene los mismos endpoints y reglas
- **AND** incluye la API Cloudflare, su módulo consumidor y todos sus módulos compartidos, excluyendo las entradas API/RabbitMQ CPython

#### Scenario: Start the grouped CPython entrypoints
- **WHEN** se ejecutan `uvicorn entrypoints.api:app` y `python -m entrypoints.rabbitmq_consumer` con la configuración PostgreSQL/RabbitMQ correspondiente
- **THEN** conservan la API, el procesamiento secuencial y la limpieza de recursos del perfil original

#### Scenario: Import the entrypoint package without selecting a profile
- **WHEN** se importa únicamente `entrypoints`
- **THEN** no se importan sus entradas ni se construyen aplicaciones, SDKs o recursos de ningún perfil

#### Scenario: Delegate Cloudflare messages within the same deployment
- **WHEN** la entrada `cloudflare_api.py` recibe eventos HTTP y de cola sucesivos
- **THEN** `Default.fetch` sirve la API y `Default.queue` delega en `cloudflare_consumer.py`, reutilizando una aplicación y un procesador con el repositorio compartido
- **AND** el consumidor conserva reconocimiento previo, secuencia y limpieza del contexto del evento sin otro despliegue

#### Scenario: Import the Cloudflare consumer independently
- **WHEN** se importa `entrypoints.cloudflare_consumer` sin importar la API
- **THEN** no se carga `cloudflare_api`, la composición HTTP ni sus routers, ni se construye una aplicación o consulta bindings
