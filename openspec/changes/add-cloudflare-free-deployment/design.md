# Design

## Context

Ver la motivación en `proposal.md`. La línea base es el `main` integrado: `add-asynchronous-shipping-quotations` y `add-backend-ci` ya están sincronizados y archivados. Las especificaciones principales actuales incorporan cotizaciones, CI, simuladores autónomos y la política de cierre OpenSpec; sus contratos se conservan al incorporar Cloudflare.

`backend/main.py` compone SQLModel y RabbitMQ y construye `app` al importar; `worker.py` mantiene un bucle AMQP. Los puertos en `application/{deliveries,returns,lockers,quotations}/ports.py` son asíncronos e independientes de infraestructura; los servicios viven en `use_cases.py` de cada funcionalidad. Cotizaciones concentra modelos/errores y `ShippingQuoteComparator` en `application/quotations/{models,errors,comparison}.py`. Los repositorios PostgreSQL usan transacciones, `FOR UPDATE`, checks específicos y un índice único parcial para ocupación. La selección de celda se hace en Python con volumen entero exacto y UUID. El contrato admite 1000 celdas nuevas por petición, crecimiento acumulado sin máximo y listas sin paginación.

## Goals / Non-Goals

**Goals:** dos composiciones sustituibles que satisfagan los mismos contratos de negocio; transacciones D1 verificables; una distribución Workers sin dependencias CPython incompatibles; instalación gratuita reproducible cuya viabilidad se demuestre antes de declararla terminada.

**Non-Goals:** ejecutar SQLModel/asyncpg o un proceso RabbitMQ dentro de Workers; usar la API REST D1 como transporte de producción; coordinar o copiar datos entre perfiles; añadir autenticación, reintentos de negocio o un sistema distribuido de recuperación. Los límites Free son restricciones de la plataforma, no una promesa de servicio ilimitado.

## Decisions

### 1. Dos entradas y una composición compartida

- `backend/main.py` conserva `create_app(database_url=None, publisher=...)`, `app`, precedencia de `DATABASE_URL`, recursos y compatibilidad Uvicorn/Compose. `backend/worker.py` conserva el proceso RabbitMQ.
- `backend/composition.py` reúne servicios, reloj, router y manejadores HTTP a partir de puertos ya construidos; no importa SQLModel, RabbitMQ ni SDK Cloudflare. Las reglas siguen en dominio/aplicación.
- `backend/cloudflare_worker.py` es la segunda raíz de composición: una entrada Python Workers con HTTP ASGI y `queue`. Construye FastAPI, rutas y servicios una sola vez durante el import/snapshot, pero no accede entonces a DB, Queues ni entorno de una petición. Los repositorios/publicador reciben un proveedor tipado de bindings, no un binding capturado.
- Un adaptador de contexto externo usa `ContextVar`: middleware ASGI obtiene `scope['env']`, instala DB/QUOTATIONS para ese evento y resetea el contexto en `finally`; el handler `queue` hace lo mismo con `self.env`. Las operaciones consultan el proveedor únicamente al ejecutarse. Todas las tareas se esperan/cancelan dentro del evento; no hay trabajo desprendido ni binding global mutable. Pruebas concurrentes con dos entornos y excepciones demuestran que no se mezclan. Esto reutiliza los routers que hoy cierran sobre servicios sin reconstruirlos por petición. El primer experimento verifica la delegación ASGI concreta y la propagación del contexto en el SDK.
- El perfil se selecciona mediante el entrypoint y su manifiesto de despliegue, no por cabecera, parámetro HTTP o conmutación de una base en caliente. Workers nunca importa `main` ni `worker`; la API Cloudflare no depende de abrir conexiones al iniciar.

Se evita un único módulo con imports globales de ambas infraestructuras. La API y el consumidor estarán en el mismo Worker: el runtime distingue eventos HTTP y de cola; la concurrencia del consumidor se configura aparte de HTTP. No se necesita un segundo servicio externo.

### 2. Paquete Workers reproducible y prueba inicial obligatoria

Mantener los comandos y dependencias de ejecución actuales para CPython 3.11. Actualizar `backend/pyproject.toml` para incluir `composition` en `setuptools.py-modules` y `backend/Dockerfile` para copiarlo: hoy ambos enumeran solo `main`/`worker`. Verificar el wheel instalado fuera del árbol fuente y el smoke Docker existente; no basta que los imports funcionen desde el checkout. Cambiar el lockfile CPython únicamente si la declaración efectiva de dependencias lo requiere.

Añadir `cloudflare/pyproject.toml`/`uv.lock` con Python >=3.13, FastAPI y las dependencias requeridas por el código compartido; grupo de desarrollo `workers-py` y `workers-runtime-sdk`, conforme a la herramienta oficial `uv run pywrangler`. Fijar versiones compatibles y `compatibility_date` en el experimento inicial, sin inventar ahora una combinación que no se ha ejecutado.

`scripts/cloudflare/prepare.py` genera un árbol ignorado y reproducible desde una lista explícita de fuentes: dominio, aplicación, HTTP, composición, D1, Queues, simuladores y entrada Workers. No mantiene copias manuales de lógica ni incluye SQLModel, Alembic, asyncpg, aio-pika, Uvicorn, tests o secretos. El manifiesto y los checksums permiten verificar que se empaqueta el código actual. CI prueba instalación bloqueada, preparación y build; deriva rutas/comandos exactos del SDK fijado en vez de depender de archivos locales fuera del paquete.

Mantener el experimento acotado de construir y ejecutar FastAPI/Pydantic, imports de los casos de uso, acceso D1, `batch()` con rollback, `json_each`, productor y consumidor Python con ack temprano. Medir además petición pequeña, validación y serialización reales de 1000 celdas, lectura de 2000 celdas y arranque frío/caliente. Comprobar en cuenta Free tanto CPU HTTP como el presupuesto efectivo de eventos de cola. Una incompatibilidad demostrada de empaquetado, CPU o semántica esencial detiene la implementación dependiente; otro lenguaje, funcionalidad reducida o un plan de pago requieren un diseño revisado. El bloqueo de descarga de Pyodide o la falta de cuenta son ausencia de evidencia, no incompatibilidad: por autorización del usuario, continuar adaptadores reales, composición y pruebas locales disponibles, manteniendo pendientes las verificaciones Python Workers/Queues y Free que no puedan ejecutarse. Sus resultados posteriores pueden exigir correcciones; esta continuación no cierra el experimento ni acredita viabilidad Free.

### 3. D1 nativo, tipos y lecturas

Añadir `backend/adapters/database/d1/` con frontera tipada de bindings, conversión de filas, SQL y los cuatro repositorios. Las llamadas usan `prepare/bind/first/all/batch` del binding nativo; los proxies JS se convierten y validan en el adaptador. Ningún SDK llega a los puertos. Los errores de transporte/cuota/contención se normalizan a un error de persistencia de aplicación y un manejador HTTP devuelve `503` sin SQL, tokens o credenciales. Cotizaciones conserva su error de almacenamiento y su contrato HTTP existente. Errores de programación no se convierten indiscriminadamente en fallos de infraestructura.

UUID: texto canónico minúsculo con formato fijo, conservando orden equivalente al UUID. Fechas: texto UTC canónico con seis decimales y `Z`, producido/parseado en Python; se conservan microsegundos y comparación cronológica. Dimensiones, precios, estados y opcionales conservan sus tipos y validaciones. Reemplazar checks PostgreSQL por equivalentes SQLite: dígitos ASCII con longitud/GLOB, recorte con el conjunto Unicode explícito, claves foráneas, XOR de parcela, checks de estados/fechas y único parcial de asignación activa. No aceptar pérdida de precisión por convertir enteros grandes a `float` en el puente JS.

Cada lectura de configuración/disponibilidad o de cotización con resultados usa una consulta con joins, o un batch de lectura con snapshot coherente demostrado. Evitar N+1 por celda/proveedor. Las listas devuelven su contenido completo según el contrato actual. No activar read replication ni cachés que puedan ocultar una escritura recién confirmada; cualquier futura optimización debe conservar esa coherencia.

### 4. Capacidad: snapshot, revisión y batch atómico

D1 no ofrece la transacción interactiva de SQLAlchemy. Incorporar a `lockers` campos internos `revision` y `mutation_token`, invisibles para dominio/HTTP. Toda modificación de un locker existente —metadata/active, añadir/modificar/retirar celdas, recibir entregas o devoluciones y liberar cualquiera de ellas— participa en el mismo protocolo:

1. Leer en un único snapshot la revisión, configuración y ocupación necesarias. Reutilizar `Dimensions.fits_in` y `select_compartment` en Python: los volúmenes con ejes hasta 2147483647 exceden 64 bits y no deben ordenarse mediante multiplicación SQLite o números JS.
2. Preparar un token UUID nuevo para ese intento y un `DB.batch` indivisible. Su primera sentencia hace CAS: actualiza revisión/token solo si coincide la revisión leída y las precondiciones de la operación.
3. **Cada** escritura posterior se condiciona a que el locker contenga ese token y revisión nueva. Un CAS con cero cambios produce cero escrituras de negocio; el token jamás se reutiliza entre intentos. Constraints/FK/índice único abortan el batch completo ante error.
4. Recepción inserta paquete y asignación en ese batch. Salida comprueba pendiente y asignación concreta, cambia estado/fecha y libera solamente esa asignación. Reconfiguración solo actúa sobre la celda libre/activa del snapshot validado. Obtener la representación de respuesta dentro del mismo batch cuando proceda.
5. Solo ante una respuesta D1 concluyente de CAS con cero cambios, volver a leer y reevaluar; máximo **tres intentos totales**. Si ahora hay un conflicto de negocio, devolver su 404/409 correspondiente. Si sigue la contención al agotar intentos, devolver `503`, nunca `FULL` por haber perdido el CAS. No reintentar timeouts, errores de cuota, transporte, integridad ni resultados de commit desconocidos.

El protocolo se prueba con todos los writers; omitir cualquiera invalidaría la exclusión. Las sentencias condicionadas deben garantizar por construcción el número esperado de cambios tras ganar el CAS; comprobar contadores después de commit no sustituye esa garantía. Un test inserta un fallo real dentro del batch y demuestra que tampoco persisten revisión/token. Las pruebas usan barreras antes del CAS para controlar el intercalado, no sleeps ni simulación de `FOR UPDATE`.

Creación de un locker nuevo y celdas usa un batch sin CAS previo. Altas/salidas de paquetes sin locker usan INSERT y UPDATE condicional por estado, respectivamente. Nunca se comparten claves de entrega/devolución por su UUID ni se libera una celda buscando solo su identificador: se mantiene la identidad de asignación histórica.

Alternativas descartadas: trasladar los locks PostgreSQL, confiar solo en que D1 serialice escrituras o hacer `SELECT`/`INSERT` sin guardas permite decisiones obsoletas o paquetes huérfanos. Durable Objects añadiría otra autoridad/almacenamiento sin resolver por sí solo la atomicidad con D1; no se introduce.

### 5. Presupuesto SQL y cotizaciones

Para hasta 1000 celdas, generar UUID/valores en Python y enviar un parámetro JSON a `INSERT ... SELECT ... FROM json_each(?)`, condicionado al token cuando sea una ampliación. Así no se emiten 1000 consultas ni se exceden 100 parámetros. Todo el lote permanece en una transacción; dividir commits para eludir límites no es válido. Verificar el tamaño real del parámetro y de cada respuesta.

Presupuesto de diseño: **como máximo 24 sentencias D1 por invocación HTTP**, contando cada sentencia dentro de un batch, lecturas de aplicación, tres intentos CAS y respuestas; ninguna sentencia con más de 100 parámetros. Se instrumenta en pruebas. No se cambian los límites públicos de negocio si el presupuesto falla: se optimiza SQL sin alterar contratos o se declara bloqueada la aceptación Free.

Cotizaciones: `start` usa `UPDATE ... WHERE status='PENDING' RETURNING ...` atómico. Solo el ganador llama proveedores. `complete` inserta resultados/ofertas por lotes condicionados a PROCESSING y cambia a COMPLETED en el mismo batch; un fallo revierte todo. Si el estado no era PROCESSING, todas las sentencias quedan sin cambios y el adaptador devuelve rechazo, nunca éxito silencioso; comprobar ese resultado no intenta deshacer un commit previo. `fail` actualiza solo el estado esperado. La lectura completa evita estados finales con resultados parciales. No se mantiene transacción mientras se esperan proveedores.

### 6. Queues conserva la ejecución única prevista

El publicador serializa únicamente `quotation_id` y espera `send()` antes de permitir `202`. Guardar D1 y publicar siguen sin ser atómicos; un fallo conserva el `503` con id y el intento de marcar PUBLISH_ERROR, sin outbox ni republicación.

Configurar consumidor con `max_batch_size=1`, `max_concurrency=1`, `max_retries=0`, retención Free de 24 horas y sin dead-letter/reconciliador. El handler solicita `message.ack()` **antes** de leer D1/procesar; en la API Python actual es síncrono, no un await con confirmación AMQP. Si esa llamada falla, no empieza el trabajo. La documentación promete que un mensaje explícitamente reconocido no se vuelve a entregar aunque el handler falle después; no se extrapola esa propiedad a un proceso que muere antes de registrar el ack.

Queues puede duplicar entregas: cada copia se reconoce y `start` condicional deja que solo PENDING pase una vez a PROCESSING. Los estados inexistente/PROCESSING/COMPLETED/FAILED y mensajes inválidos se ignoran. Una caída puede dejar PENDING/PROCESSING indefinidamente; no se reabre el estado ni se promete exactamente una vez. No hay reintento de comparación/proveedores. Se reutiliza `ShippingQuoteComparator` con timeout de dos segundos y los tres simuladores construidos sin argumentos: conservan sus perfiles privados fijos y tarifas actuales. Workers, igual que el worker PostgreSQL, no configura demoras/probabilidades ni lee las antiguas variables `SHIPPING_*`; los tests controlan azar/esperas en ejecución sin convertir esos controles en configuración de producción.

### 7. Historial D1 y excepción explícita a instrucciones del repositorio

`cloudflare/migrations/0001_initial.sql` crea directamente el esquema actual de las ocho tablas de negocio, constraints, índices y metadata interna D1; Wrangler registra su historial. No simula las revisiones heredadas de PostgreSQL ni usa `alembic stamp`. Alembic y revisiones 0001–0005 permanecen intactos para PostgreSQL. D1 tiene migraciones SQL versionadas hacia delante; el rollback normal revierte código compatible, no elimina tablas con datos.

Durante implementación, actualizar de forma acotada `AGENTS.md`: Alembic para PostgreSQL, SQL/Wrangler para D1; `main.py` conserva la composición CPython y `cloudflare_worker.py` es la entrada específica adicional. Esta excepción forma parte del plan que se revisará, no una omisión de la regla actual. Ningún runtime crea tablas/migra al arrancar.

### 8. Fuentes y límites que se verificarán

Valores oficiales consultados el 2026-10-17; registrar nuevamente fecha y plan en la aceptación, porque pueden cambiar:

| Servicio | Restricción relevante Free |
| --- | --- |
| Workers HTTP | 100000 peticiones/día; 10 ms CPU por petición, excluyendo espera de I/O; 128 MB; arranque de 1 s |
| D1 | 5 millones de filas leídas/día; 100000 escritas/día, incluidos efectos de índices; 500 MB/base y 5 GB/cuenta |
| D1 por invocación | 50 consultas, 100 parámetros/sentencia, 2 MB por fila/cadena, 30 s por consulta |
| Queues | 10000 operaciones/día, normalmente tres por mensaje; retención fija de 24 h |

No equiparar peticiones a filas leídas/escritas ni mensajes a operaciones de cola. No aplicar automáticamente el presupuesto HTTP al consumidor: la documentación de Queues describe presupuestos de eventos y remite a límites por plan; confirmar el efectivo en Free. Verificar también límites actuales de paquete y herramientas durante build, sin copiar límites históricos de tamaño.

Fuentes: [Python Workers y paquetes](https://developers.cloudflare.com/workers/languages/python/packages/), [FastAPI y env ASGI](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/), [snapshot Python](https://developers.cloudflare.com/workers/languages/python/how-python-workers-work/), [límites Workers](https://developers.cloudflare.com/workers/platform/limits/), [API D1 y batch](https://developers.cloudflare.com/d1/worker-api/d1-database/), [límites D1](https://developers.cloudflare.com/d1/platform/limits/), [precio D1](https://developers.cloudflare.com/d1/platform/pricing/), [API Queues Python](https://developers.cloudflare.com/queues/configuration/javascript-apis/), [batching y ack](https://developers.cloudflare.com/queues/configuration/batching-retries/), [precio Queues](https://developers.cloudflare.com/queues/platform/pricing/), [límites Queues](https://developers.cloudflare.com/queues/platform/limits/).

### 9. Verificación y aceptación de gratuidad

Conservar los escenarios de dominio/HTTP/SQL y las suites PostgreSQL y RabbitMQ. Añadir contratos compartidos donde sea útil sin convertir PostgreSQL en un fallback D1. Las pruebas Cloudflare corren con la herramienta oficial sobre Workers/D1/Queues local; SQLite de CPython o dobles no demuestran semántica D1. El workflow de backend añade un sexto resultado estable `Cloudflare local`, sin cuenta ni secretos; la medición remota es evidencia separada. El workflow independiente `OpenSpec closure` permanece intacto: exige cierre antes de integrar una PR a main y falla mientras este cambio siga activo, sin que eso autorice archivarlo incompleto o desactivar el check.

Añadir un nivel complementario de contratos: ejecutar los adaptadores Python de producción en CPython, inyectando en su frontera tipada un cliente de pruebas que llama por HTTP local a un Worker JavaScript de Miniflare con D1 real. El puente solo traduce operaciones a `prepare/bind/batch` del binding; no duplica SQL ni reglas de los repositorios, no reintenta escrituras y conserva cada batch en una única llamada D1, con resultados y errores observables. El harness usa loopback, almacenamiento temporal aislado, migraciones reales y cleanup incluso tras fallo. Este transporte vive exclusivamente en tests y queda excluido del paquete de producción, que sigue usando el binding Python nativo. Permite verificar SQL, CAS, rollback y contratos de los adaptadores contra D1 local sin sustituir la ejecución Python/WASM, conversión de proxies JS, aislamiento ASGI, semántica de Queues ni mediciones Free. Informar esos niveles por separado; un puente correcto no convierte en verde un check nativo bloqueado.

Fixtures mínimas de aceptación remota: diez lockers (uno pasa de 1000 a 2000 celdas en dos peticiones; los otros nueve tienen diez cada uno), cien entregas y cien devoluciones entre pendientes/finalizadas y asignadas/no asignadas, y treinta cotizaciones con resultados mixtos. Ejercitar todos los endpoints, `/docs`/`openapi.json`, alta/ampliación de 1000 celdas, listas completas, disponibilidad y carreras controladas; añadir casos de ejes máximos/volúmenes casi iguales y UTC con microsegundos. La prueba inicial puede usar una muestra equivalente de serialización; la final requiere operaciones reales.

Repetir rutas pequeñas en frío/caliente y con concurrencia HTTP de cuatro, con hasta 1000 solicitudes y 100 cotizaciones en la campaña; presupuestar antes filas/índices/operaciones y detener cargas auxiliares antes de consumir la cuota disponible. Registrar versiones, tamaño, CPU p95/máximo, tiempos, errores de límite, consultas, filas leídas/escritas, operaciones de cola y espacio final. Todos los casos obligatorios deben funcionar dentro de Free; un p95 bajo no compensa fallos por CPU en el máximo de 1000 celdas. No atribuir el tiempo de espera simulado a CPU.

Este conjunto es evidencia acotada, no un nuevo máximo de API ni garantía con datos ilimitados. Las listas siguen sin paginación; documentar el crecimiento probado y el riesgo de superar el presupuesto. Si 1000 celdas o los casos obligatorios no caben, la meta completa Free queda bloqueada: no recortar respuestas, cambiar límites ni activar pago.

### 10. Archivos previstos

| Área | Archivos/directorios |
| --- | --- |
| Composición | `backend/main.py`, `backend/composition.py`, `backend/cloudflare_worker.py`; `worker.py` solo si se comparte construcción de simuladores sin cambiar su lifecycle |
| Distribución CPython | `backend/pyproject.toml` y `backend/Dockerfile` para incluir la composición en wheel/imagen; `backend/uv.lock` solo si se necesitan dependencias de tipado/verificación compatibles |
| Adaptadores | `backend/adapters/database/sqlmodel/`, `backend/adapters/database/d1/`, `backend/adapters/queue/cloudflare.py`, `backend/adapters/runtime/cloudflare.py`, manejador HTTP de errores y tipos de error en `backend/application/` |
| Distribución y migraciones | `cloudflare/pyproject.toml`, `cloudflare/uv.lock`, `cloudflare/wrangler.jsonc`, `cloudflare/migrations/`, `scripts/cloudflare/prepare.py` y comandos locales/aceptación |
| Pruebas | nuevas unidades en `backend/tests/unit/`, harness nativo y puente local CPython/Miniflare exclusivo de tests en `cloudflare/tests/`, helpers de contratos compartibles; suites PostgreSQL/RabbitMQ conservadas |
| Calidad y documentación | `.github/workflows/backend-ci.yml`, `pyrightconfig.json`, configuración Ruff si necesita incluir fuentes externas, `README.md`, `AGENTS.md`, `.gitignore`, documento reproducible de resultados en `cloudflare/` |

El chequeo obligatorio `uv run --extra dev pyright --project .. --warnings` continúa desde `backend/` con cero errores y advertencias. Incluir entrada/adaptadores/composición nuevos en strict y harness/scripts en el alcance adecuado; mantener Python 3.11 del código compartido y añadir un entorno de análisis 3.13 únicamente para fuentes específicas Workers si el SDK lo exige. Resolver tipos del puente mediante Protocol/conversión o declaraciones precisas verificadas, sin Any generalizado, exclusiones nuevas de producción ni relajar reglas. Ruff cubre nuevas fuentes y las migraciones históricas Python conservan sus exclusiones actuales.

### 11. Organización aprobada de adaptadores

Refactorizar ubicación e imports sobre la implementación existente, sin cambiar contratos, SQL, concurrencia, ack ni ciclo de vida. Aplicar este mapa relativo a `backend/adapters/`:

| Origen | Destino |
| --- | --- |
| `database/sqlmodel_{deliveries,returns,lockers,quotations}.py` | `database/sqlmodel/{deliveries,returns,lockers,quotations}.py` |
| `database/connection.py` | `database/sqlmodel/connection.py` |
| `cloudflare/d1.py` | `database/d1/native.py` |
| `cloudflare/queue.py` (`NativeMessage` y helpers) | Integrar en `queue/cloudflare.py` |
| `cloudflare/context.py` | `runtime/cloudflare.py` |

El contexto Workers sigue reuniendo DB/QUOTATIONS y middleware ASGI, separado de persistencia y transporte de cola. Los adaptadores de cola conservan publicación/consumo; `backend/main.py`, `worker.py`, `cloudflare_worker.py` y `composition.py` conservan composición y arranque en sus rutas actuales, sin añadir otro bootstrap. Dominio/aplicación siguen sin importar infraestructura.

Actualizar consumidores, imports de registro de modelos en `database/migrations/env.py`, pruebas/patches, documentación vigente y la lista de preparación Workers. Crear los paquetes necesarios y retirar los módulos sustituidos; los imports de pruebas/runtime deben apuntar a las ubicaciones nuevas. Las revisiones Alembic 0001–0005 y migraciones D1 permanecen byte a byte y en las mismas rutas; no cambiar `script_location`. Verificar wheel instalado fuera del checkout, imagen Docker y árbol Workers fresco, manteniendo sus entradas, selección de fuentes y ausencia de dependencias CPython en Workers. La reorganización no requiere nuevas dependencias ni cambios de comportamiento; no reescribe evidencia histórica ni completa comprobaciones Python/WASM, Queues o Free todavía pendientes.

## Risks / Trade-offs

- **CPU/Python o paquete incompatibles con Free** → detener la solución dependiente ante incompatibilidad demostrada; no confundir bloqueo de descarga con ese resultado ni garantizar viabilidad por pasar CPython/Miniflare.
- **CAS incompleto o escritura sin token** → revisión de cada writer, pruebas de intercalado/rollback y presupuesto máximo de intentos; no confundir respuesta desconocida con CAS fallido.
- **Listas y número acumulado de celdas sin límite** → medir fixtures explícitas, eliminar N+1, documentar alcance real; cualquier paginación o límite nuevo exige otro acuerdo de contrato.
- **Pérdida de trabajos tras ack o retención de 24 h** → documentar la semántica heredada y la diferencia operativa de Queues; no añadir recuperación implícita.
- **Divergencia de dos esquemas y paquetes** → contratos de comportamiento comunes, migraciones específicas comprobadas, build desde fuentes compartidas y regresión del perfil original.
- **Descarga del runtime, cuenta o métricas Free no disponibles** → continuar implementación y evidencia local disponible, dejando cada comprobación nativa/remota ausente pendiente, sin declararla aprobada ni usar credenciales ajenas.

## Migration Plan

1. Continuar el experimento y, cuando exista un destino Free autorizado, su prueba remota mínima; documentar resultados o bloqueos del entorno. Mientras solo falte acceso a runtime/cuenta, avanzar con implementación y pruebas locales complementarias sin cerrar la aceptación nativa/remota. La autorización actual no despliega recursos.
2. Completar implementación, pruebas y revisión independiente. Preparar manifiesto con placeholders `ACCOUNT_ID`, `D1_DATABASE_ID`, nombre de cola/Worker y `workers.dev`; credenciales solo en entorno/secrets local, nunca en Git ni logs. Separar desarrollo local y remoto y fijar recursos exactos antes de un comando con efectos remotos.
3. Para instalación nueva autorizada: verificar plan Free/cuota, crear D1 y Queues, rellenar identificadores, aplicar migraciones D1 **antes** del Worker, comprobar esquema, y desplegar código con bindings/productor/consumidor. No hace falta dominio de pago. No tocar PostgreSQL ni sus volúmenes.
4. Ejecutar smoke completo y campaña de aceptación en ese destino. Confirmar `202`/persistencia/resultados por GET y el recorrido recepción/salida/reocupación, además de métricas Free. Sin esa evidencia, distinguir implementación local lista de despliegue gratuito aceptado.
5. Para reversión: detener nueva recepción de trabajo en el destino afectado y desactivar el consumidor antes de intervenir; volver a una versión Workers declarada compatible con el esquema existente. No resetear D1, purgar Queues ni deshacer migraciones con datos. Si no hay versión compatible, dejar el servicio detenido con diagnóstico y usar export/copia de seguridad para una reparación explícita; nunca fingir que volver a PostgreSQL recupera los datos D1.

## Open Questions

Solo quedan datos operativos que no alteran el diseño: cuenta/destino Free autorizado, nombres finales de recursos y acceso a métricas. Versiones exactas del SDK y forma concreta de delegar ASGI se resuelven en la prueba inicial definida; si esa prueba contradice la arquitectura o el contrato, se registra bloqueo y se revisa el plan antes de continuar.
