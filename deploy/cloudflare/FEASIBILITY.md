# Experimento inicial de Python Workers

## Requisitos vigentes y diagnóstico de compatibilidad

La distribución Cloudflare requiere Python `>=3.13,<3.14`, FastAPI 0.135.3 y
Pydantic 2.10.6 con pydantic-core 2.27.2. El
[manifiesto oficial de Pyodide 0.28.3](https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide-lock.json)
publica esas versiones de Pydantic/core para CPython 3.13.2 y ABI `2025_0`.
Se mantienen workers-py 1.17.8, workers-runtime-sdk 1.9.4, Wrangler 4.151.1 y
`compatibility_date = "2026-08-01"`. Esta correspondencia del manifiesto no
acredita la resolución completa ni la ejecución WASM.

El error observado con Pydantic 2.12.5 exige pydantic-core 2.41.5, para el que
no había wheel WASM utilizable en el destino seleccionado. El aviso
`VIRTUAL_ENV` por un entorno distinto no es la causa de ese fallo. La migración
D1 local había terminado correctamente: no hace falta borrar su estado para
corregir las dependencias. El rango Python corregido selecciona 3.13 aunque
la máquina disponga de 3.14; se puede indicar `--python 3.13` explícitamente al
sincronizar de nuevo.

Preparación actual desde la raíz:

```bash
uv sync --project deploy/cloudflare --locked
npm ci --ignore-scripts --prefix deploy/cloudflare
deploy/cloudflare/.venv/bin/python scripts/cloudflare/prepare.py
```

Para seleccionar explícitamente Python 3.13 al sustituir un entorno anterior,
usar `uv sync --project deploy/cloudflare --locked --python 3.13`.
`scripts/cloudflare/check.sh` ejecuta sus suites y harness con
`deploy/cloudflare/.venv/bin/python`, sin fallback al backend. Su modo `--d1-only`
sigue siendo complementario; el modo completo exige el runtime nativo.
`uv.lock` describe CPython y no sustituye `pylock.toml`: la resolución nativa,
Python/WASM, Queues y Free continúan pendientes. El acceso de este entorno a
`index.pyodide.org` sigue bloqueado; la instalación host y el build de fuentes
se verifican por separado.

La distribución se encuentra en `deploy/cloudflare/`; las rutas antiguas de
los registros históricos describen su organización anterior. La transición de
estado ignorado tras Git está en el
[README](../../README.md#conservar-estado-local-después-del-traslado).
El arranque de ambas APIs comunicado por el usuario se conserva como reporte,
sin acreditar entrega real de Queues ni aceptación Free.

## Reloj y diagnóstico de arranque

El origen de `perf_counter()` puede ser cero; no es una condición de arranque.
Las medidas internas de importación, validación, construcción y serialización
conservan sus campos `*_wall_ms`: un delta positivo identifica únicamente el
reloj del runtime, nunca CPU. Si el reloj no avanza, cada campo vale `null` y su
campo `*_unavailable_reason` explica el motivo. La pared medida por el host se
registra por separado; ninguna de ambas medidas acredita cuotas Free.

Los dos ejecutores toleran `RemoteDisconnected` durante el plazo original de
90 segundos. Ante fallo muestran la causa, el estado anterior a la limpieza y
las últimas 120 líneas / 64 KiB del log disponible. El log productivo vive en su
directorio temporal; el spike conserva su ubicación histórica. Las regresiones
unitarias de reloj y sondeo se ejecutan antes de sincronizar el runtime. No
prueban Python/WASM, Queues, Free ni la causa de un fallo previo de CI sin log.

## Evidencia histórica del experimento

Los resultados y versiones anteriores que siguen se conservan como registro de
cada ejecución. Los archivos de `deploy/cloudflare/evidence/` se retiraron del
checkout al cerrar estos cambios; las rutas `evidence/` citadas a continuación
identifican evidencia histórica consultable en el historial Git. Las nuevas
ejecuciones pueden regenerar logs locales ignorados. El pin Pydantic
2.12.5/core 2.41.5 de ese registro queda sustituido por los requisitos vigentes
anteriores; no representa una nueva verificación.

Estado al 2026-10-17: **gate local pendiente por acceso de red**. No se ha
establecido ni incompatibilidad del runtime ni viabilidad en Free. Las tareas
1.1–1.3 siguen incompletas. Esto es un experimento aislado, no una distribución
terminada de la aplicación ni un manifiesto de despliegue de producción.

## Resultado observado

| Comprobación | Resultado real |
| --- | --- |
| `uv sync --locked` | Pasa; resolución CPython reproducible con `uv.lock` |
| `npm ci --ignore-scripts` | Pasa; herramientas oficiales con `package-lock.json` |
| Preparación de fuentes | Pasa; lista explícita, árbol regenerado y SHA-256 |
| Wrangler `deploy --dry-run` | Pasa para el árbol de fuentes; **sin dependencias Pyodide todavía** |
| `uv run --locked pywrangler sync` | Falla: política de salida impide `index.pyodide.org/0.28.3/pydantic/` |
| ContextVar misma tarea (CPython) | Pasa; éxito/excepción, con valor previo y sin valor; mutación sin reset falla |
| Orquestación de cola/batch (CPython) | Pasan 12 tests de orden/fallos; tres mutaciones deliberadas hacen fallar la suite |
| Runtime Python/ASGI/D1/Queues | No ejecutado; no hay resultado de los contratos nativos |
| Imports/snapshot, 1000/2000 celdas | Mediciones nativas pendientes; no se publican tiempos CPython como sustituto |
| Pyright raíz obligatorio | Pasa: cero errores y cero advertencias |
| Pyright estricto del experimento | Pasa: cero errores y cero advertencias |
| Ruff lint/formato | Pasa para las fuentes nuevas del experimento |
| Cuenta/CPU/cuotas Free | Pendiente; no hay destino remoto autorizado/configurado |

La autorización para ampliar la red no cambia por sí sola la política aplicada.
El último estado observado mantiene únicamente dominios de gestores de paquetes;
el reintento siguió fallando. Hace falta guardar/aplicar la incorporación de
`index.pyodide.org` mediante la configuración soportada. No se han cambiado
proxies, deshabilitado TLS ni sustituido el índice por un espejo alternativo.
Si aparecen otros destinos necesarios, deben identificarse por un fallo real.

Los registros históricos `evidence/harness.log` y `evidence/sync.log` conservaron
el comando y error exactos; se consultan en el historial Git.
El harness termina con código no cero antes de migrar/iniciar el runtime cuando
falla el sync. El build de fuentes separado quedó registrado en
`evidence/build.log`: su resultado no prueba que FastAPI/Pydantic puedan cargarse en WASM.

## Actualización al integrar main

La integración de `origin/main` en `6a5db11` reorganiza aplicación por módulos
`application.<feature>.use_cases`, con puertos dentro de cada feature y
cotizaciones en `application.quotations`. El spike importa ahora estos módulos
concretos, incluido el comparador, en lugar de los `__init__.py` vacíos. El
preparador recursivo incluye las nuevas rutas sin copias manuales adicionales.

Se repitieron imports de cinco módulos de casos de uso/comparación y los cuatro
esquemas reales desde el árbol preparado bajo CPython, sin cargar infraestructura
PostgreSQL/AMQP. La preparación produce 42 fuentes, con 43 archivos idénticos en
dos ejecuciones, incluido el manifiesto. Pasan de nuevo la unidad de contexto,
Ruff y ambos Pyright (cero errores/advertencias); el build de esa integración **solo de
fuentes** mide 81.65 KiB / gzip 15.75 KiB. El resultado histórico se consulta
en Git como `evidence/quality.txt`.

Los registros históricos `build.log` y `context-unit.log` contienen resultados
refrescados de las fuentes integradas; `harness.log`, `sync.log` y la prueba de
mutación corresponden a las ejecuciones previas. Todos se consultan en Git.
No se reintentó el sync Pyodide ni se ejecutaron contratos nativos;
el gate y la aceptación Free siguen pendientes.

## Correcciones de auditoría de los sondeos

Se corrigieron dos falsos positivos posibles sin cerrar ninguna tarea del gate:

- La marca persistida `ack_sync=1` y `max_retries=0` no prueban por sí solas el
  orden del reconocimiento. `Default.queue` llama ahora al helper compartido
  `process_spike_message`; cinco unidades observan directamente `ack`, lectura
  de cuerpo, `prepare`, `bind` y escritura. Un ack que lanza impide incluso leer
  el cuerpo y no alcanza D1. Se comprueban mensajes inválidos, error de escritura
  y fallo posterior al ack sin una segunda escritura. El smoke nativo conserva
  sus marcadores, pero su resultado no se presenta como prueba independiente
  del orden ack→I/O ni como garantía de exactamente una vez.
- El sondeo de rollback usa primero un control positivo de tres sentencias con
  el mismo `prepare/bind/batch`, y exige tres filas con suma de valores seis.
  Después prepara otro lote con el valor negativo solo en la segunda sentencia.
  Únicamente acepta el CHECK nombrado `spike_value_nonnegative`; un error de
  preparación, del control positivo, de transporte u otra constraint se propaga.
  La ausencia del fallo esperado también falla, y se exige cero filas tras él.
  Solo entonces se prueba `json_each` con 1000 filas. El esquema local del
  harness aislado declara ese nombre de constraint explícitamente.

Pasan 12 unidades CPython de orquestación/inyección de fallos y la unidad de
contexto existente. Tres copias temporales mutadas —ack eliminado, ack movido
tras la escritura y aceptación indiscriminada de excepciones del batch— producen
fallos observables de tests. Sus registros históricos se consultan en Git como
`evidence/probe-units.txt` y `evidence/probe-mutations.txt`. Los dobles no simulan
ni demuestran la atomicidad real de D1: se mantiene pendiente ejecutar el mismo helper en WASM/D1 oficial.

La preparación actual produce 44 fuentes/45 archivos idénticos entre ejecuciones;
Ruff comprueba 14 archivos y ambos Pyright terminan con cero errores/advertencias.
El build **solo de fuentes** mide 82.82 KiB / gzip 16.20 KiB. No se ha reintentado
Pyodide ni desplegado nada. El bloqueo histórico y la aceptación Free pendiente
siguen vigentes.

## Versiones instaladas y compatibilidad provisional

- CPython local 3.13.5; uv 0.12.23; Node 24.19.0.
- `workers-py` 1.17.8 / `workers-runtime-sdk` 1.9.4.
- Wrangler 4.151.1; Miniflare 5.20261012.1-beta; workerd 1.20261012.1.
- FastAPI 0.135.3; Pydantic 2.12.5; pydantic-core 2.41.5; Starlette 1.8.0.
- `compatibility_date = 2026-08-01`, `python_workers`: el CLI oficial selecciona
  Python 3.13.2/Pyodide 0.28.3 para esta fecha. Una fecha desde 2026-09-08
  seleccionaría Python 3.14 según la metadata instalada; no se usa implícitamente.

Estas versiones de las dependencias están probadas solo en la instalación
CPython. La disponibilidad de sus wheels WASM sigue pendiente. El CLI requiere
además `pylock.toml` propio para las dependencias Pyodide; todavía **no existe**
porque su resolución fue bloqueada. `uv.lock` no sustituye ese lock. Antes de
cerrar 1.1 se debe obtener/revisar/versionar `pylock.toml`, repetir su sync sin
cambios y ejecutar el runtime. Una combinación de versiones que no tenga wheel
compatible debe resolverse dentro de esta prueba y verificarse, sin afirmar que
la configuración provisional ya sirve para producción.

## Reproducir

Desde la raíz, con Python `>=3.13,<3.14`, uv, Node y npm disponibles:

```sh
uv sync --project deploy/cloudflare --locked
npm ci --ignore-scripts --prefix deploy/cloudflare
cd deploy/cloudflare
uv run --locked python tests/run_spike.py
```

El harness instala herramientas bloqueadas, prepara las fuentes actuales,
ejecuta las unidades CPython de contexto/orquestación y `pywrangler sync`,
construye sin publicar, crea únicamente las dos tablas
de prueba en D1 local aislado e inicia `pywrangler dev --config wrangler.spike.jsonc --local`. Usa un puerto
local libre; espera como máximo 90 segundos para arrancar, ejecuta cinco pruebas
y guarda logs/mediciones. Cancela su grupo de procesos y elimina exclusivamente
su directorio temporal de estado al terminar, también en caso de fallo. No
necesita cuenta, token ni D1 remoto; no ejecuta `deploy` sin `--dry-run`.

Para ver el bloqueo directamente:

```sh
cd deploy/cloudflare
uv run --locked pywrangler sync
```

Si el entorno tiene HOME de solo lectura, usar directorios de caché/configuración
escribibles mediante `UV_CACHE_DIR`, `npm_config_cache`, `XDG_CONFIG_HOME` y
`XDG_CACHE_HOME`; el harness los proporciona cuando faltan. Conservar proxy y
CA heredados. No compartir logs que contengan credenciales añadidas posteriormente.

Para comprobar únicamente el empaquetado de fuentes, sin confundirlo con runtime:

```sh
deploy/cloudflare/.venv/bin/python scripts/cloudflare/prepare_spike.py
cd deploy/cloudflare
node node_modules/wrangler/bin/wrangler.js deploy --config wrangler.spike.jsonc --dry-run --outdir .wrangler/build
```

## Contratos que probará el harness nativo

- Importa los cuatro esquemas HTTP reales y los casos de uso del backend, sin
  `main`, SQLModel, asyncpg, Alembic ni aio-pika. Construye FastAPI una sola vez.
- El bootstrap empieza un reloj antes de importar FastAPI/esquemas. El código no
  consulta bindings al importar: únicamente accede al proveedor dentro del evento.
  `/` expondrá tiempo de importación y contador de construcciones. Esos tiempos
  de pared son indicativos locales; no equivalen a CPU ni a arranque remoto.
- ASGI obtiene `scope['env']`; el ContextVar se instala/resetea con `finally`.
  Tres llamadas ASGI oficiales concurrentes reciben etiquetas A/B/C distintas;
  C genera HTTP 500 y D comprueba reutilización posterior. Estos entornos
  sintéticos comparten los bindings D1/Queues reales del evento exterior; prueban
  aislamiento del proveedor por identidad/etiqueta, no dos bases remotas.
  El adaptador oficial devuelve la respuesta 500 que FastAPI emite antes de
  volver a lanzar su excepción; no se presupone propagación de ValueError.
- Además, un helper invoca `EventContext.__call__` y verifica en la **misma
  tarea** la restauración del ContextVar tras éxito y excepción, con valor
  anterior y con `Context()` vacío. Este helper ya pasa en CPython: una copia
  temporal mutada eliminando `reset(token)` provoca el fallo esperado
  (registro histórico `evidence/context-mutation.log`, consultable en Git).
  También se invoca dentro del runtime nativo cuando pueda arrancar; la unidad CPython no acredita ASGI/D1/Queues.
- D1 nativo ejecutará el helper `verify_d1_batch`: control positivo de tres
  sentencias, fallo de CHECK nombrado deliberado en la segunda sentencia del
  control negativo y cero filas tras el rollback; luego `json_each(?)` insertará
  1000 filas en una sentencia con un parámetro JSON. Las unidades de orquestación
  ya pasan, pero ninguno de estos resultados nativos se ha observado todavía.
- Python publica con `await send`. El consumidor llama a `message.ack()` de forma
  síncrona antes de escribir D1; confirma que el resultado no es awaitable.
  Un caso falla después del ack; la prueba observa una sola escritura durante
  una ventana local acotada. No demuestra exactamente una vez ni confirma qué
  sucede si el proceso cae antes de registrar el ack. Los retries son cero.
- Valida el `CreateLocker` real de 1000 celdas y rechaza 1001. Mide muestras de
  una celda, 1000 y una respuesta `LockerResponse` de 2000; también confirma que
  crear 2000 de golpe se rechaza. Separa validación, construcción, serialización,
  bytes y HTTP de pared. Estas muestras no son aún operaciones de negocio D1
  completas ni mediciones de CPU Free; no sustituyen la campaña final.

## Frontera de tipos

`runtime_spike/bindings.py` define Protocols estrechos para los bindings dinámicos
convertidos por el SDK: statements, batch, cola, mensaje y entorno. Los casts están
limitados al borde de SDK/ASGI; se validan los valores de filas/cuerpos usados.
No se introduce Any ni se desactiva ninguna regla.

El SDK instalado contiene referencias a tipos JavaScript generados no disponibles
para Pyright y una firma ASGI parcialmente desconocida. `typings/workers/` aporta
solo las firmas consumidas, comprobadas contra el código de `workers-runtime-sdk`
1.9.4 (`request.py`, `entrypoints.py`, `asgi.py`, `rpc.py`); mantiene env como
`object`, obligando a cruzar la frontera explícita. Los stubs son exclusivamente
para análisis y no sustituyen módulos durante ejecución. Su verificación nativa
está pendiente junto con el resto del gate. La integración futura debe incorporar
estas fuentes, stubPath y entorno 3.13 al chequeo raíz sin rebajar su alcance 3.11;
no se ha modificado la configuración raíz en esta fase.

```sh
# Desde la raíz:
PYTHONPATH=cloudflare/runtime_spike uv run --project cloudflare --locked python -m unittest discover -s cloudflare/tests -p test_event_context.py -v
PYTHONPATH=cloudflare/runtime_spike uv run --project cloudflare --locked python -m unittest discover -s cloudflare/tests -p test_probe_units.py -v
uv run --project backend --extra dev pyright --project cloudflare --warnings
uv run --project backend --extra dev ruff check cloudflare/runtime_spike cloudflare/tests scripts/cloudflare
uv run --project backend --extra dev ruff format --check cloudflare/runtime_spike cloudflare/tests scripts/cloudflare
# Obligatorio, desde backend:
uv run --extra dev pyright --project .. --warnings
```

No hay evidencia de CPU remota, tamaño de snapshot/memoria, consumo de cuotas,
retención Free ni límites efectivos de cola. El tamaño de fuentes del build
provisional se registra en el log; falta el tamaño del paquete con dependencias.
Ninguno de estos resultados permite declarar aceptado el objetivo Free.


## Selección explícita de harness tras añadir producción

`wrangler.jsonc` selecciona ahora la aplicación de producción; el experimento
histórico permanece en `wrangler.spike.jsonc`. `tests/run_spike.py` pasa ese
manifiesto explícitamente a build, migración local y dev. Las conclusiones y
mediciones históricas de este documento no cambian por esa selección.
`pywrangler sync` usa las dependencias/fecha comunes del proyecto y conserva su
bloqueo Pyodide mientras la política de red no cambie.

Desde la raíz, `scripts/cloudflare/check.sh --d1-only` ejecuta únicamente el
complemento CPython/adaptadores/D1 de Miniflare. El comando sin argumentos exige
además los contratos Python Workers/Queues del spike y la aplicación real
(`tests/run_runtime.py`, manifiesto `wrangler.production.jsonc`). Un runtime
inaccesible produce fallo; el complemento no convierte ese fallo en éxito.
La campaña HTTP está en `scripts/cloudflare/acceptance.py --base-url URL`; usa
un destino de prueba nuevo autorizado, conserva sus datos y limita toda la
campaña a como máximo 1000 peticiones, incluso con override. Los tiempos HTTP
son de pared: CPU, filas D1, operaciones Queues y cuota remota se verifican por
separado antes de aceptar Free.

## Evidencia complementaria CPython/D1 de los adaptadores reales

La campaña HTTP local del 2026-10-17 pasó 421 peticiones con los adaptadores de
producción y el D1 oficial de Miniflare/workerd. Conserva diez lockers, uno
ampliado de 1000 a 2000 celdas; cien entregas y cien devoluciones, cada flujo con
25 elementos de cada combinación asignado/sin asignar y pendiente/terminal; y
30 cotizaciones. Comprueba listas completas/identificadores, cuatro peticiones
normales simultáneas, carrera de última celda, ejes máximos y volúmenes próximos
con desempate UUID exacto, y snapshots UTC con microsegundos tras persistencia,
salida y repetición. El fixture de cola usa el handler/comparador reales con
mensajes y tres proveedores deterministas de tests; prueba resultados completos
QUOTED/NOT_COVERED/FAILED con los códigos de proveedores de producción, sin
configurar ni modificar los simuladores reales.

El máximo observado fue ocho sentencias D1 por ventana HTTP y trece parámetros
por sentencia. En peticiones concurrentes la ventana incluye también consultas
intercaladas de otra petición: es un conteo conservador. Los metadatos de
respuestas D1 exitosas registraron 425519 filas leídas, 7910 escritas y un máximo
de `size_after` de 630784 bytes. Excluyen operaciones fallidas o sin metadatos y
no son métricas de cuota remota. La campaña corta tráfico auxiliar al alcanzar
su presupuesto y rechaza overrides fuera de 1–1000 antes de efectuar I/O.

Cuatro tests del puente pasaron además rollback intermedio, constraints en
concurrencia, aislamiento/bounds/cleanup y cierre/reinicio completo de workerd
con almacenamiento poblado e historial de migraciones preservados. Cada caso
posee su estado temporal; al recibir un directorio externo de tests, el puente
no lo elimina al cerrar. Los comandos individuales ejecutados fueron:

```bash
PYTHONPATH=backend:cloudflare/tests backend/.venv/bin/python -m unittest discover -s cloudflare/tests/test_support -v
PYTHONPATH=backend:cloudflare/tests backend/.venv/bin/python -m unittest discover -s cloudflare/tests -p test_cloudflare_http.py -v
PYTHONPATH=backend:cloudflare/tests backend/.venv/bin/python -m unittest discover -s cloudflare/tests -p test_acceptance.py -v
```

Esta evidencia no ejecuta Python en WASM, no acredita entrega nativa de Queues y
no mide CPU/arranque/snapshot/cuotas Free. Sus verificaciones obligatorias y la
aceptación remota continúan pendientes; el check completo exige esos niveles
por separado y no convierte un bloqueo del runtime en éxito.
