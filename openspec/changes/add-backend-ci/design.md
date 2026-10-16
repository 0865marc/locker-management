# Design

## Context

Véase `proposal.md` para la motivación. No hay workflows existentes. El backend declara Python `>=3.11`, usa `uv.lock`, `unittest` y configuración Pyright compartida; la imagen ejecuta Python 3.13 pero instala dependencias con `pip` desde rangos sin usar el lockfile.

El árbol actual incluye el cambio completo `add-asynchronous-shipping-quotations`, aún sin sincronizar/archivar: `worker.py`, RabbitMQ, migración 0005 y `tests/messaging`. Sus deltas de runtime, migraciones y tests complementan las especificaciones principales anteriores. Las unitarias no necesitan servicios; integración usa PostgreSQL con un esquema UUID y Alembic por caso, sustituyendo el publicador por un doble. La suite completa también descubre mensajería y requiere ambas URLs.

`main.py` abre RabbitMQ en el lifespan. Compose ya ordena PostgreSQL saludable → migración → API y exige broker saludable. `GET /lockers` consulta PostgreSQL y devuelve `[]` en una base nueva; `/openapi.json` por sí solo no verifica acceso al esquema. Las migraciones existentes ya prueban guardas, recorridos históricos y `alembic check`.

## Goals / Non-Goals

**Goals:** materializar los cinco controles de la especificación con diagnósticos independientes, comandos reproducibles y cambios mecánicos de Python revisables. Conservar dependencias y límites entre dominio, aplicación y adaptadores.

**Non-Goals:** cambiar contratos funcionales, añadir un endpoint de salud, modificar `compose.yaml`, probar el worker en CI o convertir el workflow en un mecanismo de despliegue. Los cinco resultados no configuran por sí solos restricciones de merge en GitHub.

## Decisions

### 1. Un workflow y cinco jobs independientes

`.github/workflows/backend-ci.yml` ejecutará `pull_request` hacia `main` y `push` a `main`, sin filtros de rutas ni ejecuciones duplicadas en cada push a una rama. Nombres estables: `Ruff`, `Pyright`, `Unit tests`, `PostgreSQL integration` y `Docker smoke`. No hay dependencias entre jobs ni un sexto agregador.

Se usarán runners Ubuntu, `contents: read`, sin secretos de despliegue y sin `pull_request_target`. Cada job tendrá timeout; el grupo de concurrencia distinguirá workflow y PR/ref, cancelando la revisión anterior de esa PR sin afectar otras. No se usarán `continue-on-error` ni capturas que oculten códigos de fallo. Se fijarán versiones explícitas de las herramientas/actions, comprobando disponibilidad durante implementación.

Los cuatro jobs Python usarán 3.11, el mínimo declarado y objetivo de Pyright; el smoke conserva la imagen Python 3.13. Esto proporciona evidencia del mínimo y del runtime actual sin introducir una matriz amplia ni afirmar cobertura exhaustiva de versiones.

### 2. Dependencias bloqueadas y mismo contrato local

Los jobs Python instalarán uv en una versión fija, cachearán su caché usando `backend/uv.lock` y ejecutarán desde `backend/` `uv sync --locked --extra dev`. Las invocaciones posteriores mantendrán `UV_LOCKED=1`, incluido el comando exacto de Pyright requerido por el proyecto. Una caché no sustituye la comprobación del lockfile.

El Dockerfile incorporará `uv.lock` e instalará con uv fijado y `uv sync --locked --extra dev --no-editable`, exponiendo `/code/.venv/bin` en PATH. Se conservan `main.py`, `worker.py`, paquetes, tests y `alembic.ini`, así como los comandos actuales de uvicorn, Alembic, Python y worker. Mantener el extra `dev` conserva los comandos de pruebas documentados; separar imágenes de producción queda fuera. Solo se actualizará la resolución necesaria para añadir Ruff, sin actualizar dependencias ajenas deliberadamente.

### 3. Ruff moderado y normalización inicial

`backend/pyproject.toml` añadirá Ruff al extra `dev` y definirá `target-version = "py311"`, longitud 88, reglas `E4`, `E7`, `E9`, `F`, `I` y formato estándar estable. Desde `backend/`: `uv run --extra dev ruff check .` y `uv run --extra dev ruff format --check .`. En desarrollo se documentarán `ruff check --fix .` y `ruff format .`; CI solo comprueba.

Se normalizarán producción, tests y `adapters/database/migrations/env.py`, sin alterar comportamiento ni interfaces. Se revisarán las correcciones y los imports que registran modelos; no se eliminarán efectos necesarios para Alembic. No se aplicarán `--unsafe-fixes` ni desactivaciones amplias; una excepción localizada necesitará una causa concreta.

Las exclusiones Ruff enumerarán exactamente estos cinco archivos históricos, con `force-exclude` para respetarlas también al pasar rutas explícitas:

- `adapters/database/migrations/versions/0001_create_delivery_and_return.py`
- `adapters/database/migrations/versions/0002_parcel_custody.py`
- `adapters/database/migrations/versions/0003_lockers_and_custody.py`
- `adapters/database/migrations/versions/0004_locker_geography.py`
- `adapters/database/migrations/versions/0005_shipping_quotations.py`

Así no se reescribe historia aceptada ni se excluyen migraciones futuras con un glob. Pyright conserva su configuración actual: 0004, 0005 y `env.py` siguen analizados. No se añade una segunda herramienta de formato/imports ni una selección masiva de reglas.

### 4. Ejecutar las suites existentes con sus dependencias reales

Los comandos de los tres jobs restantes de Python, desde `backend/`, serán:

| Job | Comando | Servicios |
| --- | --- | --- |
| Pyright | `uv run --extra dev pyright --project .. --warnings` | Ninguno; cero errores y advertencias |
| Unit tests | `uv run --extra dev python -m unittest discover -s tests/unit -t . -v` | Ninguno; URLs de test ausentes |
| PostgreSQL integration | `uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f` | PostgreSQL 17 efímero y saludable; `TEST_DATABASE_URL` explícita |

El servicio de integración creará una base dedicada con permisos para crear/eliminar esquemas. Se reutiliza el aislamiento actual de los fixtures; no se migra `public` antes ni se sustituyen los casos de Alembic por un simple upgrade. Configuración ausente, permisos insuficientes, errores de conexión, regresiones y drift de esquema producen fallos. No se introduce SQLite ni un broker en este job.

No se ejecuta `discover -s tests` en CI: incluiría mensajería, fuera de los cinco bloques seleccionados. La verificación local de cierre sí ejecutará la suite completa con PostgreSQL y RabbitMQ, porque se formatean también esos tests y el proyecto exige evidencia de regresión.

### 5. Smoke Docker aislado y sin puertos publicados

`scripts/ci/smoke.sh` se ejecutará desde la raíz y usará un nombre de proyecto Compose único por ejecución, `compose.yaml` y el nuevo `compose.ci.yaml`. El override quitará las publicaciones de puertos de API y DB con `ports: !reset []`; se documentará el requisito de una versión Compose compatible. El stack de desarrollo podrá seguir funcionando sin colisiones ni cambios.

El script construirá y arrancará solo `api` y sus dependencias (`db`, `migrate`, `rabbitmq`), sin worker, sobre volúmenes nuevos del proyecto temporal. Esperará una respuesta de `GET /lockers` dentro de la API mediante `docker compose exec -T api python` y `urllib.request`, validando HTTP 200 y JSON `[]` con timeouts por petición y un plazo total acotado. Se requieren tanto migración exitosa como esa respuesta; el mero estado running del contenedor no basta.

Ante fallo se mostrarán estado y logs pertinentes, preservando el código de salida. El script registrará limpieza y el workflow garantizará el cleanup del proyecto en sus rutas de finalización: solo contenedores/red/volúmenes del nombre temporal, nunca un `down -v` sobre el proyecto de desarrollo ni un prune global. El mismo script sirve para reproducción local; una cancelación o pérdida del runner no se presentará como smoke aprobado.

## Risks / Trade-offs

- **Diff inicial amplio por formato** → limitarlo a cambios mecánicos y revisar imports con efectos; ejecutar tipos y pruebas después, manteniendo 0001–0005 sin diferencias.
- **Deriva entre Docker y checks Python** → usar la misma resolución bloqueada y mantener explícitos Python 3.11 y 3.13; no prometer imágenes idénticas bit a bit.
- **Dependencia de cotizaciones todavía en otra rama** → implementar en rama aislada sobre una base que contenga ese trabajo; si su integración cambia el runtime, revisar el plan antes de alterar el alcance.
- **Solo dos suites en CI** → documentar exactamente qué corre y conservar la suite completa local, sin afirmar que se verificó el procesamiento de mensajes en Actions.
- **Fallo o lentitud de servicios** → healthchecks, plazos y logs; no usar reintentos que conviertan errores de pruebas en éxito.

## Migration Plan

Tras aprobar este plan, preparar la rama aislada, añadir Ruff/lock y normalización, ajustar instalación Docker, añadir workflow y smoke y actualizar README. No hay migración de datos ni modificaciones remotas de GitHub en esta fase.

La verificación incluirá los comandos de cada job, suite local completa según README, smoke aislado, comparación de migraciones intactas, revisión de YAML/shell/Compose y `openspec validate add-backend-ci --strict`. La revisión independiente contrastará esos resultados con los escenarios. La ejecución real de Actions se comprobará cuando el workflow se publique mediante la PR autorizada; hasta entonces se informará como pendiente, diferenciándola de las comprobaciones locales. Revertir este cambio retira CI/Ruff y restaura empaquetado/formato sin modificar datos de negocio.
