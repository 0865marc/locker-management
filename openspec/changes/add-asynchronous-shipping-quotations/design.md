# Design

## Context

`ShippingQuoteService.compare` ya limita a tres llamadas concurrentes, aplica dos segundos de timeout por llamada y devuelve resultados normalizados sin reintentos. Sus tipos de resultado pertenecen a aplicación. Reutilizaremos ese servicio y los tres simuladores existentes; la motivación está en `proposal.md`.

## Goals / Non-Goals

**Goals:** encolar una comparación, ejecutarla una vez y guardar la solicitud y sus resultados.

**Non-Goals:** reintentos, reconciliadores, leases, heartbeat, fencing, snapshots de perfiles, recuperación automática y ejecución distribuida. Se despliega un solo worker.

## Decisions

### 1. Flujo sencillo

API -> guardar solicitud -> publicar UUID una vez -> RabbitMQ -> worker -> compare -> guardar resultados.

La cola `shipping.quotations` es durable y los mensajes persistentes. El adaptador `aio-pika` publica con mandatory y confirms; el cuerpo contiene solo `quotation_id`, sin versionado de mensajes ni otra infraestructura de tareas.

El consumidor tiene prefetch 1 y un bucle secuencial. Hace ack manual temprano, al recibir y antes de leer la solicitud o llamar a proveedores. Si el ack falla, no empieza la comparación. No usa requeue, republicación ni recuperación de solicitudes desde PostgreSQL. Esta elección mantiene explícito que el trabajo consumido puede perderse ante una caída.

Para un UUID válido que siga PENDING, el worker marca PROCESSING, llama `compare` una vez y guarda el lote final junto con COMPLETED en una transacción. Ignora solicitudes inexistentes o que ya no estén PENDING; es una comprobación simple, no un protocolo entre workers. Mensajes inválidos se descartan.

### 2. API y fallos

POST `/quotations` acepta los campos actuales de `ShippingQuoteRequest`, con `dimensions: {width_mm, height_mm, depth_mm}`, validación estricta y campos extra prohibidos. Guarda PENDING y publica una vez; únicamente tras confirmación devuelve `202 {id, status: "PENDING"}` y `Location: /quotations/{id}`. Cada POST crea una solicitud nueva.

Si falla la escritura inicial, responde 503 y no publica. Si falla la publicación, responde 503 con el identificador ya guardado e intenta registrar FAILED/PUBLISH_ERROR si PostgreSQL está disponible y la solicitud sigue PENDING. No inventa resultados de proveedores que no fueron llamados ni vuelve a publicar.

GET `/quotations/{id}` devuelve id, request, status, created_at, finished_at, process_error_code y results. UUID desconocido devuelve 404; entrada inválida, 422; persistencia no disponible, 503 sin detalles sensibles. PENDING/PROCESSING tienen resultados vacíos y finished_at null. COMPLETED contiene todos los resultados y error de proceso null; FAILED tiene un error de proceso y no tiene ofertas inventadas.

Los fallos normales de proveedores terminan en sus resultados actuales FAILED/PROVIDER_ERROR o FAILED/PROVIDER_TIMEOUT; la cotización queda COMPLETED aunque ninguno devuelva ofertas. Una excepción inesperada del procesamiento intenta registrar FAILED/PROCESSING_ERROR una vez si la base de datos permite escribir y la solicitud sigue PROCESSING. Si el proceso muere o la DB no está disponible, no se garantiza registrar ese error.

### 3. Persistencia y arquitectura

Se añaden tres tablas: `shipping_quotations` para transporte, UUID, estado, timestamps UTC y error de proceso; `shipping_provider_results` para estado/error de cada proveedor; `shipping_offers` para sus servicios, céntimos EUR y plazos. Claves/FK protegen identidad, referencias y unicidad por proveedor/servicio.

El lote de resultados y COMPLETED se guarda atómicamente. GET lee una representación coherente; ninguna transacción permanece abierta mientras se esperan proveedores. No se guarda configuración, historial de intentos ni metadatos de recuperación.

Los modelos/puertos nuevos viven en `application/quotation_models.py` y `quotation_ports.py`; `application/quotations.py` orquesta submit/get/process. `ProviderResult`, `ProviderStatus` y `ProviderErrorCode` siguen en `application/shipping_quotes.py`, sin dependencias dominio -> aplicación.

Se añaden `adapters/http/quotations/{__init__.py,routes.py,schemas.py}`, `adapters/database/sqlmodel_quotations.py` y `adapters/queue/rabbitmq.py`. El router agregado y `main.py` componen la API; `worker.py` compone el único worker. Cada proceso cierra sus propios recursos.

### 4. Simulación y runtime

Cada clase de proveedor declara su propio perfil privado e inmutable y se construye sin argumentos. Una implementación compartida aplica la demora uniforme y un sorteo de categorías excluyentes; después de la demora, devuelve la tarifa actual, lanza error o espera cancelablemente hasta el timeout existente. Perfiles aprobados:

| Proveedor | Demora (s) | Sin respuesta | Error |
| --- | --- | --- | --- |
| Economy | 0.2–0.8 | 0.10 | 0.15 |
| Standard | 0.1–0.5 | 0.05 | 0.10 |
| Express | 0.05–0.2 | 0.02 | 0.05 |

Se elimina la configuración pública por constructor, incluidos `profile`, `rng`, `sleep`, `SimulationProfile` y `SimulationRandom`. El worker instancia `SimulatedEconomyProvider()`, `SimulatedStandardProvider()` y `SimulatedExpressProvider()`; desaparecen `worker.simulation_profile()` y las variables `SHIPPING_DELAY_MIN_SECONDS`, `SHIPPING_DELAY_MAX_SECONDS`, `SHIPPING_NO_RESPONSE_PROBABILITY` y `SHIPPING_ERROR_PROBABILITY` de worker/Compose/README. No hay sustitutos ni configuración persistida.

Los perfiles distinguen proveedores de demostración y sus demoras normales quedan por debajo del timeout de dos segundos. La ejecución directa también usa el perfil estocástico: solo las tarifas de respuestas exitosas son deterministas. README presenta el resultado ilustrativo como un caso exitoso posible. Las llamadas directas a `quote` conservan la responsabilidad de cancelación/timeout del llamador.

Las pruebas parchean funciones privadas de azar y espera consultadas al ejecutar, sin parámetros de test en constructores, semillas ni secuencias dependientes del orden concurrente. Se verifican perfiles, umbrales, tarifas, error/timeout y limpieza por cancelación; las pruebas de comparación fuerzan éxito cuando comprueban precios. El proveedor de éxito del smoke de mensajería devuelve una oferta desde un doble de prueba, sin invocar un simulador estocástico.

Compose añade RabbitMQ 4 y un worker. API/worker esperan migraciones y broker saludable al arrancar; `RABBITMQ_URL` configura ambas conexiones. Se conservan `postgres_data` y `rabbitmq_data`. Conexiones ordinarias, sin reconexión/republicación automática de trabajos; los fallos se comunican y no disparan bucles de retry. Ni API ni worker crean tablas al arrancar.

### 5. Migración y verificación

`0005_shipping_quotations.py` crea las tres tablas e incorpora metadata sin modificar datos previos ni revisiones 0001–0004. El downgrade usa la guarda estándar con locks previos: rechaza datos de cotización y, con tablas nuevas vacías, elimina solo ese almacenamiento.

La verificación cubre unidades sin servicios, persistencia/HTTP PostgreSQL, un smoke RabbitMQ del flujo normal y consumo sin requeue, y Pyright con cero errores/warnings. Se conserva la revisión independiente; no se añaden pruebas distribuidas de recuperación o contención.

Para la revisión de perfiles se repiten unidades, smoke PostgreSQL/RabbitMQ, Pyright y revisión independiente; no se modifica esquema ni se requiere repetir verificaciones de migración sin cambios. La evidencia anterior se mantiene identificada como histórica en tasks.md.

## Risks / Trade-offs

- Commit PostgreSQL y publicación no son atómicos: una caída o confirmación incierta puede dejar estado incompleto o respuesta ambigua; esta fase no lo repara.
- Tras el ack temprano, una caída puede dejar PENDING/PROCESSING sin resultados; no se reejecuta automáticamente ni se promete ejecución exactamente una vez.
- Los errores de proveedor se guardan si el worker y PostgreSQL siguen operativos; una caída de infraestructura no garantiza un registro final.
- Un broker caído impide aceptar nuevas cotizaciones; las ya guardadas siguen consultables mientras API y PostgreSQL estén disponibles.
