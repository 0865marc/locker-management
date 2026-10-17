# Proposal

## Why

La demo necesita un despliegue completo en servicios gratuitos de Cloudflare que conserve su API, la gestión de capacidad y las cotizaciones asíncronas. Los puertos actuales permiten incorporar otra infraestructura, pero el runtime CPython/PostgreSQL/RabbitMQ y sus transacciones no pueden trasladarse cambiando solamente una URL.

## What Changes

- Añadir un perfil Cloudflare con Python Workers/FastAPI, D1 y Queues, sobre `workers.dev`, manteniendo el perfil PostgreSQL/RabbitMQ y sus contratos. La selección ocurre al componer el despliegue; no hay sincronización ni doble escritura.
- Incorporar cuatro repositorios D1, publicador/consumidor Queues y entrada Workers; reutilizar dominio, casos de uso y rutas HTTP. Aislar los imports y dependencias CPython del paquete Workers.
- Organizar los adaptadores por responsabilidad: agrupar SQLModel y su conexión, integrar las envolturas nativas con D1/Queues y ubicar el contexto compartido de Workers en runtime. Agrupar las tres entradas en `backend/entrypoints/`, conservando `composition.py` en la raíz y los contratos y migraciones existentes; actualizar los comandos y el empaquetado correspondientes.
- Conservar recepción/ocupación y salida/liberación atómicas, protección de celdas ocupadas, selección exacta de capacidad, lectura coherente y publicación/ejecución de cotizaciones. Diferenciar contención o fallo D1 con `503`, sin convertirlo en `FULL` ni filtrar detalles internos.
- Añadir historial SQL propio para D1 y procedimientos de preparación, despliegue, comprobación y reversión compatibles con datos. Proponer la excepción explícita de D1 a la regla de Alembic y la entrada Workers adicional en `AGENTS.md`; mantener intactas las revisiones PostgreSQL existentes.
- Añadir pruebas sobre bindings D1/Queues y runtime Workers real, regresión PostgreSQL/RabbitMQ, CI local sin credenciales y una aceptación remota posterior en una cuenta realmente Free. Como evidencia complementaria, probar los adaptadores Python desde CPython contra D1 local de Miniflare mediante un puente exclusivo de tests.
- Mantener la prueba de viabilidad que fija herramientas/versiones y mide CPU, consultas, tamaño y memoria. Una incompatibilidad demostrada bloquea la solución dependiente; un bloqueo de red o la falta de cuenta permiten avanzar con implementación y pruebas locales, dejando pendientes las verificaciones nativas/remotas ausentes. La meta gratuita sigue condicionada a toda esa evidencia, sin activar pago, reducir contratos ni cambiar de lenguaje automáticamente.

Se asumen una base D1 nueva, la demo sin autenticación ya existente, los tres transportistas simulados y ninguna migración de datos PostgreSQL. Quedan fuera dominio personalizado, frontend nuevo, sincronización entre bases, alta disponibilidad, recuperación de trabajos y servicios de pago. El usuario ha autorizado continuar la implementación local de este plan; crear recursos remotos y desplegar siguen requiriendo un destino autorizado.

## Capabilities

### New Capabilities

- `cloudflare-deployment`: perfil desplegable íntegramente en Cloudflare Free, preparación reproducible, presupuesto medido y aceptación operativa.

### Modified Capabilities

- `application-runtime`: selección explícita de perfiles, recursos/bindings y composición sin imports de infraestructura ajena.
- `record-persistence`: aplicar los contratos de atomicidad y concurrencia también a D1 y distinguir contención de conflictos de negocio.
- `database-migrations`: mantener Alembic PostgreSQL e incorporar un historial D1 separado, preparado antes del runtime.
- `asynchronous-shipping-quotations`: precisar publicación, consumo secuencial, duplicados y reconocimiento temprano para Queues sin introducir recuperación automática.
- `test-execution`: añadir verificación D1/Workers independiente conservando las pruebas PostgreSQL y la ausencia de SQLite como sustituto de PostgreSQL.
- `backend-ci`: conservar los cinco resultados actuales del backend y añadir verificación Cloudflare local reproducible sin despliegue ni secretos, manteniendo intacto el check independiente `OpenSpec closure`.

Las capacidades `asynchronous-shipping-quotations` y `backend-ci` ya están sincronizadas en `openspec/specs/`, y sus cambios de origen están archivados en `main`. Las especificaciones principales actuales son la línea base; este cambio no recrea esas capacidades ni modifica su historia.

## Impact

La implementación afectará las entradas `backend/entrypoints/{api,rabbitmq_worker,cloudflare_worker}.py`, composición HTTP compartida, adaptadores D1/Queues, anotaciones/errores de infraestructura y pruebas; añadirá `cloudflare/` con configuración, resolución de dependencias, migraciones y pruebas del runtime, más herramientas de preparación/verificación en `scripts/cloudflare/`. Actualizará empaquetado, Docker/Compose, manifiestos Wrangler, CI, documentación y alcance estricto de tipos. Los nombres concretos y responsabilidades se detallan en `design.md`.

La reorganización aprobada agrupa SQLModel, D1 nativo y runtime en sus adaptadores respectivos. Trasladar `main.py` a `entrypoints/api.py`, `worker.py` a `entrypoints/rabbitmq_worker.py` y `cloudflare_worker.py` a `entrypoints/cloudflare_worker.py`; `composition.py` permanece en la raíz. Las migraciones conservan ubicación y contenido, salvo los imports de `migrations/env.py` ya ajustados al reorganizar adaptadores.

No se modifica el contrato de éxito ni los límites públicos existentes, incluido crear hasta 1000 celdas por petición. Las listas sin paginación y el crecimiento acumulado impiden prometer capacidad ilimitada dentro de Free; la aceptación publicará un conjunto de datos y carga reproducible, incluirá esos extremos y fallará explícitamente si el contrato no cabe.

Dependencias: partir del `main` integrado, con aplicación organizada por funcionalidad y simuladores autónomos de perfil fijo. Conservar los contratos actuales de cotizaciones, CI, identidad y runtime. El cambio Cloudflare permanece activo e incompleto: la sincronización de la rama no lo archiva ni elude la política `OpenSpec closure`.
