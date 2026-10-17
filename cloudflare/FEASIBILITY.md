# Experimento inicial de Python Workers

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

`evidence/harness.log` y `evidence/sync.log` conservan el comando y error exactos.
El harness termina con código no cero antes de migrar/iniciar el runtime cuando
falla el sync. El build de fuentes separado está en `evidence/build.log`: su
resultado no prueba que FastAPI/Pydantic puedan cargarse en WASM.

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

Desde la raíz, con Python >=3.13, uv, Node y npm disponibles:

```sh
uv sync --project cloudflare --locked
cd cloudflare
uv run --locked python tests/run_spike.py
```

El harness instala herramientas bloqueadas, prepara las fuentes actuales,
ejecuta `pywrangler sync`, construye sin publicar, crea únicamente las dos tablas
de prueba en D1 local aislado e inicia `pywrangler dev --local`. Usa un puerto
local libre; espera como máximo 90 segundos para arrancar, ejecuta cinco pruebas
y guarda logs/mediciones. Cancela su grupo de procesos y elimina exclusivamente
su directorio temporal de estado al terminar, también en caso de fallo. No
necesita cuenta, token ni D1 remoto; no ejecuta `deploy` sin `--dry-run`.

Para ver el bloqueo directamente:

```sh
cd cloudflare
uv run --locked pywrangler sync
```

Si el entorno tiene HOME de solo lectura, usar directorios de caché/configuración
escribibles mediante `UV_CACHE_DIR`, `npm_config_cache`, `XDG_CONFIG_HOME` y
`XDG_CACHE_HOME`; el harness los proporciona cuando faltan. Conservar proxy y
CA heredados. No compartir logs que contengan credenciales añadidas posteriormente.

Para comprobar únicamente el empaquetado de fuentes, sin confundirlo con runtime:

```sh
python scripts/cloudflare/prepare_spike.py
cd cloudflare
node node_modules/wrangler/bin/wrangler.js deploy --dry-run --outdir .wrangler/build
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
  (`evidence/context-mutation.log`). También se invoca dentro del runtime
  nativo cuando pueda arrancar; la unidad CPython no acredita ASGI/D1/Queues.
- D1 nativo ejecuta `prepare/bind/batch`: falla una sentencia intermedia por
  CHECK y se exige que no persista ninguna fila; luego `json_each(?)` inserta
  1000 filas en una sentencia con un parámetro JSON.
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
