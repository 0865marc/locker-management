# Implementación Cloudflare y evidencia local

Estado: 2026-10-17. Cambio OpenSpec `add-cloudflare-free-deployment`.
La rama parte de `main` en `6a5db11`; sus migraciones Alembic 0001–0005 se
conservan byte a byte. Este documento describe el backend real. El experimento
anterior permanece en `runtime_spike/` y su evidencia histórica en
`FEASIBILITY.md`.

## Código y selección del perfil

| Responsabilidad | Implementación |
| --- | --- |
| Composición de servicios y HTTP compartida | `backend/composition.py` |
| Entrada PostgreSQL/RabbitMQ | `backend/entrypoints/server/api.py`, `backend/entrypoints/server/consumer.py` |
| Entrada única HTTP/Queues Workers | `backend/entrypoints/cloudflare/api.py` |
| Composición del procesador y consumo secuencial Queues | `backend/entrypoints/cloudflare/consumer.py` |
| Conexión y repositorios PostgreSQL/SQLModel | `backend/adapters/database/sqlmodel/` |
| Repositorios D1 de lockers, entregas, devoluciones y cotizaciones | `backend/adapters/database/d1/` |
| Frontera nativa del SDK D1 | `backend/adapters/database/d1/native.py` |
| Publicación y consumo Queues, incluida `NativeMessage` | `backend/adapters/queue/cloudflare.py` |
| Contexto por evento y middleware ASGI Workers | `backend/entrypoints/cloudflare/runtime.py` |
| Esquema D1 inicial | `deploy/cloudflare/migrations/0001_initial.sql` |
| Preparación de fuentes del Worker | `scripts/cloudflare/prepare.py` |

Se selecciona el perfil mediante su entrypoint. Ambos reutilizan dominio,
casos de uso, simuladores y routers. Cambiar de perfil no mueve ni sincroniza
datos. La distribución Workers excluye PostgreSQL, SQLModel, Alembic y AMQP;
`deploy/cloudflare/` contiene herramientas, configuración, migraciones y pruebas.

La conexión SQLModel y los repositorios de entregas, devoluciones, lockers y
cotizaciones se importan desde `adapters.database.sqlmodel`. El binding D1 se
envuelve en `adapters.database.d1.native`; `NativeMessage` vive junto al transporte
de cola en `adapters.queue.cloudflare`, y el contexto compartido de DB/QUOTATIONS
en `entrypoints.cloudflare.runtime`. Las entradas se agrupan por perfil en
`backend/entrypoints/server/` y `backend/entrypoints/cloudflare/`. `server` nombra
los procesos CPython PostgreSQL/RabbitMQ, ejecutables dentro o fuera de Docker.
Los tres paquetes de entradas tienen un `__init__.py` vacío: importarlos no carga
ningún perfil. `composition.py` permanece en la raíz de `backend/`. Desde ese
directorio, la API arranca con `uvicorn entrypoints.server.api:app` y el consumidor
con `python -m entrypoints.server.consumer`. Alembic mantiene sus revisiones en
`backend/adapters/database/migrations/versions/`, con el registro de modelos en
`migrations/env.py`; el historial SQL D1 conserva su ubicación separada. La
preparación Workers selecciona runtime, D1 y Queues desde esas rutas y excluye
el paquete SQLModel y AMQP. De `entrypoints` incorpora el init padre vacío y el
paquete `cloudflare` con su init vacío, API, consumidor y runtime; excluye
`entrypoints/server`. Los adaptadores reciben proveedores tipados sin importar
las entradas.
Ambos manifiestos Wrangler de producción usan `main = ".production/entrypoints/cloudflare/api.py"`
y `base_dir = ".production"` para conservar los paquetes compartidos hermanos
en el inventario de módulos.

`entrypoints/cloudflare/api.py` conserva `Default.fetch` y un `Default.queue` que delega
el lote y el entorno al consumidor dentro del mismo despliegue. La fábrica de
`entrypoints/cloudflare/consumer.py` recibe el repositorio compartido y el reloj y compone
el procesador una sola vez. Este módulo no importa la API, la composición HTTP
ni routers. El consumidor instala y limpia el contexto del evento y procesa
los mensajes secuencialmente, con reconocimiento antes de leer sus cuerpos.

Todas las escrituras de capacidad sobre lockers existentes usan revisión y un
token nuevo por intento. Lectura coherente, selección exacta con enteros Python
y batch atómico evitan dobles ocupaciones y escrituras parciales. Solo un CAS
con cero cambios confirmado admite relectura, hasta tres intentos totales.
Una respuesta de commit desconocida no se reintenta. La contención agotada o
un fallo de infraestructura devuelve 503; un conflicto de negocio sigue siendo
404/409 según el contrato.

Las cotizaciones esperan la confirmación de publicación antes de responder 202.
El consumidor solicita ack antes de leer el cuerpo o procesar, y el start
condicional ignora duplicados. El batch publica todos los resultados junto con
el estado final. No hay transacción conjunta D1/Queues, outbox, requeue ni
recuperación automática de trabajos interrumpidos.

## Compatibilidad vigente del entorno Cloudflare

Cloudflare requiere Python `>=3.13,<3.14`, FastAPI 0.135.3, Pydantic 2.10.6 y
pydantic-core 2.27.2. El
[manifiesto oficial Pyodide 0.28.3](https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide-lock.json)
publica Pydantic/core con esas versiones para CPython 3.13.2 y ABI `2025_0`.
Se mantienen workers-py 1.17.8, workers-runtime-sdk 1.9.4, Wrangler 4.151.1 y
`compatibility_date = "2026-08-01"`. El pin anterior Pydantic 2.12.5 exigía core
2.41.5, sin wheel WASM utilizable para ese destino. El aviso `VIRTUAL_ENV` no era
la causa; la migración D1 local había terminado correctamente y no requiere
borrar su estado.

Preparación vigente desde la raíz:

```bash
uv sync --project deploy/cloudflare --locked
npm ci --ignore-scripts --prefix deploy/cloudflare
deploy/cloudflare/.venv/bin/python scripts/cloudflare/prepare.py
```

El rango Python selecciona 3.13 también en máquinas con 3.14. Para sustituir un
entorno anterior se puede añadir `--python 3.13` al sync. `check.sh` exige
`deploy/cloudflare/.venv/bin/python` para suites y harness y falla si falta; no utiliza
el backend como alternativa. `uv.lock` corresponde a CPython y no sustituye
`pylock.toml`, que debe obtenerse mediante resolución nativa cuando el acceso
lo permita. El manifiesto fundamenta los pins, pero no acredita ejecución
Python/WASM ni entrega nativa de Queues. El bloqueo de `index.pyodide.org` sigue
vigente; instalación host, build de fuentes y aceptación Free se verifican por
separado.

El registro de verificaciones conserva también resultados de organizaciones
anteriores. Los nombres de módulos, comandos e inventarios corresponden a cada
ejecución; las rutas e instrucciones vigentes son las descritas en esta sección.

La distribución vive en `deploy/cloudflare/`; las referencias a la antigua
carpeta raíz `cloudflare/` en los resultados y comandos históricos siguientes
corresponden a sus ejecuciones originales. Para trasladar estado ignorado tras
Git, seguir la sección «Conservar estado local después del traslado» del
[README](../../README.md#conservar-estado-local-después-del-traslado).
El usuario informó del arranque de ambas APIs en su máquina; es un reporte de
uso y no acredita entrega de Queues ni aceptación Free. Los comandos actuales
de análisis, desde `backend/`, son `uv run --extra dev pyright --project .. --warnings`
y `uv run --extra dev pyright --project ../deploy/cloudflare --warnings`.

## Verificación del perfil existente

| Comprobación | Resultado local |
| --- | --- |
| Unidades: `uv run --extra dev python -m unittest discover -s tests/unit -t . -v` | 99 pruebas, correctas |
| PostgreSQL/Alembic: `uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f` | 50 pruebas, correctas; PostgreSQL 17 desechable |
| RabbitMQ: `uv run --extra dev python -m unittest discover -s tests/messaging -t . -v -f` | 1 smoke, correcto; PostgreSQL 17 y RabbitMQ 4 desechables |
| Wheel instalado fuera del checkout | Imports de `main`, `worker`, `composition`, D1 y Queues correctos; OpenAPI incluye los endpoints |
| `scripts/ci/smoke.sh` | Build bloqueado, migraciones y `GET /lockers` → 200, `[]`; recursos eliminados |

Los comandos Python se ejecutaron desde `backend/`, con `UV_CACHE_DIR` en `/tmp`
y URLs de pruebas explícitas para los servicios desechables. El smoke Docker
usó una configuración temporal del entorno: el certificado CA se montó como
secreto de BuildKit y RabbitMQ usó dos schedulers. No se desactivó TLS ni se
incluyó el certificado en la imagen. El script del repositorio no se modificó.

## Alcance de las pruebas D1

El puente de tests ejecuta los adaptadores Python reales en CPython y envía cada
operación a un binding D1 de Miniflare/workerd. No reimplementa sus consultas ni
fragmenta los batches. Usa estado temporal y loopback; queda excluido del
paquete publicado. Sus resultados prueban SQL y contratos de los adaptadores,
pero no la conversión de proxies ni la ejecución Python/WASM.

Los contratos cubren constraints, UUID/UTC, 1000/2000 celdas, selección de
volúmenes casi iguales con ejes máximos, carreras de recepción/configuración,
salidas históricas, rollback intermedio, contención agotada y commit desconocido.
Las pruebas de cotizaciones cubren resultados mixtos, estados condicionales,
duplicados, fallo de publicación y ausencia de resultados parciales.

Ejecución final de `scripts/cloudflare/check.sh`, tras preparar las fuentes:

| Nivel | Resultado |
| --- | --- |
| Puente, aislamiento, rollback y reapertura de workerd | 4 pruebas correctas |
| Repositorios y esquema D1 | 23 pruebas correctas |
| Campaña HTTP completa | 421 peticiones; una prueba correcta |
| Presupuesto de campaña | 3 pruebas correctas |
| Guard de compatibilidad sobre historial Wrangler poblado | 2 pruebas correctas; comprobación compatible y rechazo incompatible sin escrituras |
| Experimento: unidades de contexto/ack/batch | 13 pruebas correctas en CPython |
| Python Workers y Queues nativos | Bloqueado en `pywrangler sync`; el comando completo termina con error |

La campaña conserva 10 lockers y 100 entregas/100 devoluciones, con 25 de cada
combinación asignado/sin asignar y pendiente/finalizado por flujo, y 30
cotizaciones. Verifica contenido y listas completas, concurrencia de cuatro,
volúmenes exactos y fechas con microsegundos. La ventana HTTP observó como
máximo ocho sentencias (incluye intercalados de peticiones concurrentes) y
trece parámetros; los contratos de tres intentos CAS comprueban por separado
el techo de 24 sentencias. Los metadatos D1 locales exitosos sumaron 425518
filas leídas, 7910 escritas y un máximo de `size_after` de 622592 bytes. Son
datos de esa ejecución; excluyen fallos y no equivalen al consumo remoto.

La revisión independiente detectó un fallo al traducir errores de `prepare/bind`:
podían escapar como HTTP 500. Se corrigió la frontera y se añadieron pruebas
HTTP 503 para ambas operaciones, conservando visibles los errores de programación.
También se corrigieron los imports del guard en el harness y se reforzaron las
aserciones de aceptación. La revisión final no dejó hallazgos materiales locales.

Ruff lint y formato pasan en 122 archivos. Desde `backend/`, el comando
obligatorio `uv run --extra dev pyright --project .. --warnings` y el análisis
adicional `uv run --extra dev pyright --project ../cloudflare --warnings`
terminan con **cero errores y cero advertencias**. OpenSpec valida en modo
estricto; esa validación documental no sustituye las pruebas pendientes.

## Verificaciones que siguen pendientes

- Ejecutar los harnesses oficiales de Python Workers y entrega real de Queues.
  El entorno restringido sigue sin permitir `index.pyodide.org`, necesario para
  resolver los paquetes WASM. El check completo debe fallar ante ese bloqueo.
- Medir CPU, arranque, memoria y cuotas reales en una cuenta Free autorizada.
  No hay destino ni credenciales configurados; no se han creado recursos remotos
  ni publicado un Worker.
- Ensayar allí el despliegue y la parada/reversión del consumidor. El guard de
  compatibilidad y las migraciones locales no sustituyen ese ensayo.

El build de fuentes desde un árbol limpio produjo 128.12 KiB (23.57 KiB gzip),
sin resolver los paquetes WASM. Ese tamaño no mide el snapshot completo, la CPU
remota ni demuestra que el contrato máximo quepa en Free. El cambio OpenSpec
permanece activo hasta completar sus verificaciones; no se ha sincronizado ni
archivado como terminado.

## Verificación de la reorganización de adaptadores

La reorganización por responsabilidad se verificó el 17 de octubre de 2026,
sin cambiar comportamiento, dependencias ni los bytes/rutas de las revisiones
Alembic y migraciones D1. La revisión independiente no encontró hallazgos
materiales en movimientos, imports o empaquetado.

| Comprobación repetida sobre las rutas nuevas | Resultado |
| --- | --- |
| Unidades / PostgreSQL-Alembic / RabbitMQ | 99 / 50 / 1 pruebas correctas |
| `scripts/ci/smoke.sh` | Build, migraciones y `GET /lockers` → 200, `[]`; recursos eliminados |
| `scripts/cloudflare/check.sh --d1-only` | 33 pruebas correctas, incluida la campaña de 421 peticiones HTTP; máximo de 8 sentencias y 13 parámetros |
| Preparación Workers | 56 fuentes; determinista, staging obsoleto rechazado e imports comprobados; SQLModel/AMQP excluidos |
| Build Workers de fuentes, sin publicación ni resolución WASM | 127.88 KiB; 23.60 KiB gzip |
| Wheel instalado fuera del checkout | Imports y OpenAPI correctos; módulos retirados ausentes |
| Ruff lint y formato | Correctos en 122 archivos |
| `uv run --extra dev pyright --project .. --warnings`, desde `backend/` | Cero errores y cero advertencias |
| `uv run --extra dev pyright --project ../cloudflare --warnings`, desde `backend/` | Cero errores y cero advertencias |

El smoke Docker reutilizó el ajuste temporal de CA/schedulers descrito arriba.
Los metadatos D1 locales exitosos de esta campaña sumaron 425494 filas leídas,
7910 escritas y un máximo de `size_after` de 626688 bytes; excluyen fallos y no
miden consumo remoto. Estas pruebas de regresión no sustituyen las verificaciones
nativas de Python Workers/Queues ni la aceptación Free pendientes.

## Verificación de las entradas agrupadas

La agrupación en `backend/entrypoints/` se verificó el 17 de octubre de 2026.
Las tres entradas, `composition.py` y las seis migraciones conservan exactamente
sus bytes; solo cambian las rutas de entrada, sus referencias y el empaquetado.
El paquete tiene un `__init__.py` vacío y su import no carga ningún perfil.
La revisión independiente no encontró hallazgos en código, configuración ni
empaquetado.

| Comprobación sobre las nuevas entradas | Resultado |
| --- | --- |
| Unidades / PostgreSQL-Alembic / RabbitMQ | 99 / 50 / 1 pruebas correctas |
| Smoke Docker basado en `scripts/ci/smoke.sh`, ampliado temporalmente al consumidor | API: `GET /lockers` → 200, `[]`; un proceso `python -m entrypoints.rabbitmq_worker` consume el mensaje confirmado y termina con código 0 al detenerlo |
| Wheel instalado fuera del checkout | Imports del paquete, API, consumidor y composición, objetivo Uvicorn y OpenAPI correctos |
| Preparación y build de fuentes Workers | 57 fuentes; preparación determinista y rechazo de staging obsoleto; inventario real y contenido del build coinciden con los 57 módulos seleccionados |
| Aislamiento del perfil Workers | Solo entrada Cloudflare e init; entradas API/RabbitMQ y adaptadores SQLModel/AMQP excluidos |
| Ruff lint y formato | Correctos en 123 archivos |
| Pyright raíz y Cloudflare, con los comandos documentados arriba | Cero errores y cero advertencias en ambos |

Ambos manifiestos Wrangler fijan `base_dir=.production`. El build emite la
entrada principal como `cloudflare_worker.py` en su salida y conserva las rutas
de los otros 56 módulos; la comparación de inventarios tiene en cuenta ese
nombre de salida y comprueba el contenido de todos ellos. Tamaño del build de
fuentes: 127.88 KiB, 23.60 KiB gzip. El import de la entrada Cloudflare también
se comprobó con dobles explícitos del SDK bajo CPython.

El smoke Docker usó el ajuste temporal de CA/schedulers descrito arriba y retiró
sus contenedores, volúmenes y red. La comprobación verifica el consumo efectivo
del mensaje: `basic_get` consulta la cola sin registrar un consumidor.
Estas comprobaciones no ejecutan Python/WASM ni entrega nativa de Queues y no
completan la aceptación Free pendiente.

## Verificación de API y consumidores separados

El 17 de octubre de 2026 se verificó la organización en cuatro módulos, con
`cloudflare_api.py` como entrada única de plataforma y delegación de mensajes
a `cloudflare_consumer.py`. La revisión independiente no encontró hallazgos.

| Comprobación actual | Resultado |
| --- | --- |
| Unidades | 100 correctas, incluida delegación, import independiente del consumidor, repositorio/reloj compartidos, secuencia ack/cuerpo/procesamiento y restauración del contexto ante errores |
| Pyright raíz y Cloudflare | Cero errores y cero advertencias en ambos, usando los comandos documentados arriba |
| Ruff lint y formato | Correctos en 124 archivos |
| Wheel nuevo instalado fuera del checkout | API/Uvicorn/OpenAPI, RabbitMQ y consumidor Cloudflare importan correctamente; módulos retirados ausentes; entrada Cloudflare comprobada con dobles explícitos del SDK |
| Preparación y build Workers de fuentes | Preparación determinista y rechazo de staging obsoleto; los 58 módulos del build coinciden en contenido con la selección, sin entradas CPython |
| Docker desechable con API y consumidor | `GET /lockers` → 200, `[]`; `python -m entrypoints.rabbitmq_consumer` consume un mensaje confirmado y se detiene con código 0; recursos retirados |

El build de fuentes mide 128.60 KiB, 23.72 KiB gzip. El consumidor Cloudflare
importa sin FastAPI, composición HTTP ni SDK, y recibe repositorio y reloj al
construir el procesador. La API PostgreSQL, el consumidor RabbitMQ renombrado,
`composition.py` y las seis migraciones conservan sus bytes. El smoke Docker
empleó el ajuste temporal de CA/schedulers ya documentado. Esta verificación
no sustituye Python/WASM, entrega nativa de Queues ni aceptación Free.

## Verificación de las entradas agrupadas por perfil

El 17 de octubre de 2026 se verificó la organización vigente en
`entrypoints/server/{api,consumer}.py` y
`entrypoints/cloudflare/{api,consumer,runtime}.py`. Las secciones anteriores
conservan la evidencia de las disposiciones previas.

| Comprobación sobre los paquetes por perfil | Resultado |
| --- | --- |
| Unidades | 100 pruebas correctas en 4.501 s |
| PostgreSQL/Alembic | 50 pruebas correctas en 23.515 s |
| `uv run --extra dev pyright --project .. --warnings`, desde `backend/` | Cero errores y cero advertencias |
| `uv run --extra dev pyright --project ../cloudflare --warnings`, desde `backend/` | Cero errores y cero advertencias |
| Ruff lint y formato | Correctos en 125 archivos |
| Wheel nuevo instalado fuera del checkout, en `/tmp` | Tres init vacíos y cinco módulos de perfil presentes; módulos retirados ausentes; objetivo Uvicorn/OpenAPI e imports de API y consumidor server correctos |
| Imports Cloudflare desde el wheel | Consumidor independiente sin SDK ni composición HTTP; API comprobada con dobles explícitos del SDK bajo CPython |
| Preparación Workers | 58 fuentes; preparación fresca y determinista; staging obsoleto rechazado sin reparación automática |
| Inventario real del build de fuentes Wrangler | Los 58 nombres y hashes coinciden exactamente con las fuentes seleccionadas; `server` y `adapters/runtime` excluidos; entrada principal emitida como `api.py` |
| Docker desechable con API y consumidor | `GET /lockers` → 200, `[]`; un único proceso `python -m entrypoints.server.consumer` consume un mensaje inválido publicado con confirmación y termina con código 0 tras SIGTERM; recursos retirados |

El build de fuentes mide 128.60 KiB, 23.66 KiB gzip. Las seis migraciones,
`composition.py`, la API y el consumidor server y el runtime trasladado conservan
sus bytes respecto a la disposición anterior. La revisión independiente del
código no encontró hallazgos.

Las pruebas complementarias D1 no se repitieron en esta reorganización: no
cambió el código de persistencia D1 y su evidencia anterior permanece intacta.
Los imports con dobles del SDK y el build de fuentes no prueban ejecución
Python/WASM, entrega nativa de Queues ni cuotas Free; esas verificaciones
siguen pendientes.

## Verificación de la corrección de Pydantic y del entorno Cloudflare

El 17 de octubre de 2026 se verificó la instalación bloqueada Cloudflare con
Python 3.13.5, FastAPI 0.135.3, Pydantic 2.10.6, pydantic-core 2.27.2 y
workers-runtime-sdk 1.9.4. Los resultados anteriores conservan sus versiones y
entornos originales; esta sección registra la comprobación con los pins
corregidos.

| Comprobación con el entorno Cloudflare | Resultado |
| --- | --- |
| `scripts/cloudflare/check.sh --d1-only` | 33 pruebas correctas ejecutadas con `cloudflare/.venv/bin/python` |
| Puente Miniflare/D1 | 4 pruebas correctas en 18.041 s |
| Contratos D1 | 23 pruebas correctas en 67.170 s |
| Campaña HTTP | 1 prueba correcta en 14.369 s; 421 peticiones |
| Presupuesto de aceptación | 3 pruebas correctas en 0.004 s |
| Guard de compatibilidad de esquema | 2 pruebas correctas en 10.647 s |
| Unidades afectadas HTTP/contexto/composición/dominio/aplicación/lockers | 44 pruebas correctas en 1.995 s con las dependencias Cloudflare |
| `uv run --extra dev pyright --project .. --warnings`, desde `backend/` | Cero errores y cero advertencias |
| `uv run --extra dev pyright --project ../cloudflare --warnings`, desde `backend/` | Cero errores y cero advertencias |
| Ruff lint y formato | Correctos en 125 archivos |
| Staging fresco y build de fuentes | 58 módulos con hashes coincidentes; 128.60 KiB, 23.66 KiB gzip |
| Resolución offline de `uv.lock` Cloudflare | Reproducción byte a byte idéntica |
| Fixtures aislados del script de verificación | La ausencia del entorno Cloudflare falla con instrucciones de instalación, sin fallback backend; un fallo nativo simulado conserva la salida no cero |

La campaña observó un máximo de ocho sentencias D1 y trece parámetros por
ventana HTTP. Los metadatos locales registraron 425517 filas leídas, 7910
escritas y un máximo de `size_after` de 630784 bytes; no son métricas remotas.
Los locks y configuraciones server, los manifiestos Wrangler, el lock Node y
las migraciones permanecieron sin cambios.

Los fixtures del script comprueban propagación de errores, no ejecución
nativa. No se repitió `pywrangler sync` ni el arranque nativo porque sigue
bloqueado `index.pyodide.org`. La resolución de `pylock.toml`, Python/WASM,
la entrega real de Queues y la aceptación Free continúan pendientes.

## Verificación del traslado a deploy/cloudflare

El traslado se verificó el 17 de octubre de 2026, conservando la evidencia
histórica anterior. `uv sync --project deploy/cloudflare --locked --python 3.13`
recreó el entorno host con 24 paquetes y las mismas versiones.

| Comprobación desde la ubicación nueva | Resultado |
| --- | --- |
| `scripts/cloudflare/check.sh --d1-only` | 33 pruebas correctas: puente 4, contratos D1 23, campaña HTTP 1, presupuesto 3 y guard de esquema 2 |
| Campaña HTTP | 421 peticiones; máximo de 8 sentencias D1 y 13 parámetros |
| Unidades de contexto y probes | 1 y 12 pruebas correctas, respectivamente |
| `uv run --extra dev pyright --project .. --warnings`, desde `backend/` | Cero errores y cero advertencias |
| `uv run --extra dev pyright --project ../deploy/cloudflare --warnings`, desde `backend/` | Cero errores y cero advertencias |
| Ruff lint y formato | Correctos en 125 archivos |
| Preparación y build Wrangler sin publicación | Producción: 58 fuentes; spike: 45. Los 58 módulos del build coinciden byte a byte con la selección, normalizando el nombre de salida de la API principal; 128.60 KiB, 23.66 KiB gzip |
| Conservación de contenido | 147 de los 156 archivos del baseline idénticos; 9 diferencias limitadas a documentación, Pyright Cloudflare y rutas de pruebas. Todo el backend, locks, manifiestos y migraciones idénticos; 415 hashes de estado preservados inmediatamente después del traslado |
| Transición manual del README, ejecutada literalmente en fixtures | Preservación y repetición correctas, incluido checkout vacío; colisiones de directorio, archivo o enlace roto y enlaces de origen rechazados sin movimientos |
| Guard de entorno ausente e ignores | Fallo con instrucciones de la ruta nueva y sin fallback; 16 rutas antiguas/nuevas ignoradas; 49 candidatos versionados sin extras |

No se reintentó el runtime nativo bloqueado. El arranque de ambas APIs
comunicado por el usuario sigue siendo un reporte de uso: esta verificación
local no acredita entrega nativa de Queues ni aceptación Free.

La revisión independiente no encontró hallazgos y
`openspec validate add-cloudflare-free-deployment --strict` terminó correctamente.
