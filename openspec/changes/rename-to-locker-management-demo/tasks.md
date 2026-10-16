# Tasks

## 1. Identidad y configuración

- [x] 1.1 Reconciliar README, metadatos Python/lock y título API con `main` en `021dfc216a87dbc23ca56b29e9ff63eb17726dd7`, conservando cotizaciones, worker, `aio-pika`, Ruff/CI y sus versiones; verificar el mapa de nombres, `uv lock --check`, `uv sync --locked --extra dev` y OpenAPI respecto a esa base sin diferencias salvo `info.title`.
- [x] 1.2 Extender las conexiones Compose a worker y RabbitMQ con defaults/overrides coherentes; actualizar ejemplos y transición en README: detener solo API/worker, conservar credenciales/volúmenes y no recrear el broker. Verificar precedencia de URLs, fallback AMQP guest intacto y `docker compose config` nuevo/antiguo; ensayar cotización completa, registros/revisión `0005` conservados, ambos volúmenes físicos y contenedor/nodo RabbitMQ idénticos durante la transición, sin afirmar migración de mensajes.

## 2. Verificación integrada

- [x] 2.1 Repetir auditoría de referencias, Ruff check/format, Pyright con 0 errores/0 advertencias y unitarias sobre la base actual; ejecutar integración PostgreSQL, mensajería con ambas URLs de prueba y Docker smoke/Compose aislados según el diseño. Registrar evidencia nueva y cualquier bloqueo real; las verificaciones de la base anterior son históricas.
- [x] 2.2 Ejecutar `openspec validate rename-to-locker-management-demo --strict`, obtener revisión independiente `sdd_reviewer` del diff contra `main`, escenarios y evidencia actual, y resolver hallazgos repitiendo las comprobaciones afectadas.

## 3. Repositorio y espacio de trabajo

- [ ] 3.1 Cuando haya capacidad autenticada, comprobar disponibilidad y renombrar GitHub a `0865marc/locker-management-demo`; verificar ID 1420522580 antes de actualizar `origin` y comprobar la nueva URL. Mantener esta tarea pendiente si sigue bloqueada; no apuntar a un remoto inexistente o distinto.
- [ ] 3.2 Tras las verificaciones, trasladar el checkout a `/workspace/locker-management-demo` cuando pueda conservarse su vinculación con el espacio de trabajo; verificar destino libre, estado Git, remoto y raíz OpenSpec desde la nueva ruta. Mantenerla pendiente si la herramienta de gestión no permite el traslado seguro.

## Workflow follow-up

- Plan aprobado explícitamente por el usuario antes de implementar: «adelante pues, implementa el plan».
- La solicitud posterior de abrir un PR contra `main` autoriza commits, publicación y resolución de conflictos dentro del mismo alcance. El coordinador publicará el PR tras reconciliar y verificar la nueva base; no requiere completar el renombrado remoto ni el traslado local bloqueados.
- Sincronizar el delta con `application-runtime` y archivar únicamente cuando se autoricen esas fases, indicando por separado su estado y cualquier tarea operativa pendiente.

## Evidencia histórica de implementación y revisión — 2026-10-16, base anterior a 021dfc2

Estos resultados corresponden a la implementación inicial sobre `a974adf` y se conservan sin reinterpretarlos. Las tareas 1.1–2.2 se reabrieron para reconciliar y verificar el avance de `main`; la evidencia actual de cotizaciones, RabbitMQ y migración `0005` figura a continuación.

- Se actualizaron los seis archivos previstos. `uv lock --check` y `uv sync --locked --extra dev` terminaron correctamente. Comparación semántica completa del lock: solo cambia el nombre del proyecto editable; los 26 registros de dependencias conservan versiones, fuentes y artefactos.
- OpenAPI antes/después: única diferencia en `info.title`, con diez paths conservados; `/docs` y `/openapi.json` muestran el nombre nuevo. Comprobaciones puntuales correctas de conexión predeterminada, URL explícita y `DATABASE_URL`, incluidos valores anteriores. Evidencia temporal: `/tmp/locker-openapi-before.json` y `/tmp/locker-openapi-after.json`.
- Desde `backend/`, `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev python -m unittest discover -s tests/unit -t . -v`: **52 pruebas OK**, 3.099 s. Evidencia: `/tmp/locker-unit-network.log`.
- Desde `backend/`, `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pyright --project .. --warnings`: **0 errores, 0 advertencias**; repetido por el revisor independiente con el mismo resultado. Configuración compartida intacta. Evidencia: `/tmp/locker-pyright-review.log`.
- `docker compose config --format json` validado con valores predeterminados y con `COMPOSE_PROJECT_NAME=hexagonal_architecture` y credenciales anteriores: nombres físicos de volumen, usuario/base/contraseña y URLs de API/migrador coherentes.
- Arranque real con PostgreSQL 17 en proyectos temporales con UUID único: instalación nueva correcta; transición desde el Compose original al nuevo conservando exactamente el volumen, una entrega creada y la revisión Alembic `0004`. Se usó una variante temporal del Dockerfile que monta la CA del entorno únicamente durante pip; el Dockerfile del repositorio no cambia.
- Suite completa en el contenedor API, con `TEST_DATABASE_URL` dirigido a la base dedicada `locker_management_demo_test`, mediante `python -m unittest discover -s tests -t . -v -f`: **95 pruebas OK**, 35.171 s, sin omisiones. Evidencias: `/tmp/locker-rename-check/full-suite.log` y `/tmp/locker-rename-check/runtime-evidence.json`. Los contenedores, redes y volúmenes creados para el ensayo se limpiaron; los volúmenes se identificaron por una etiqueta exclusiva de la ejecución antes de eliminarlos.
- `git diff --check` y `openspec validate rename-to-locker-management-demo --strict`: correctos. Auditoría: referencias antiguas limitadas a arquitectura, transición documentada, historia y spec principal pendiente de sincronizar. `sdd_reviewer` completó revisión independiente sin hallazgos accionables.

## Evidencia actual para la PR — base 021dfc2

- Resueltos los conflictos de README, Compose y lockfile conservando las funciones, worker, RabbitMQ, Ruff/CI y dependencias de `main`. El diff de implementación sigue limitado a seis archivos.
- uv **0.13.1**: `uv lock --check` y `uv sync --locked --extra dev` correctos. Comparación semántica completa del lock y su cabecera: las 33 dependencias coinciden con `origin/main`; solo cambia el nombre del proyecto editable.
- `uv run --extra dev ruff check .`: correcto; `uv run --extra dev ruff format --check .`: 65 archivos ya formateados. `uv run --extra dev pyright --project .. --warnings` desde backend: **0 errores, 0 advertencias**, confirmado por revisión independiente. Evidencia: `/tmp/locker-rebase-pyright-review.log`.
- Unitarias sin ambas URLs de pruebas: **77 OK**, 3.335 s. Integración PostgreSQL por separado sin `TEST_RABBITMQ_URL`: **50 OK**, 27.912 s. Mensajería aislada en la rama, con ambas URLs: **1 OK**, 0.500 s. Evidencias: `/tmp/locker-rebase-unit.log`, `/tmp/locker-pr-check/integration-diagnostic.log` y `branch-messaging.log`.
- La ejecución completa inicial se detuvo tras 51 pruebas por un timeout RPC de mensajería en `tests/messaging/test_quotations.py:184`, seguido de un error de limpieza. El mismo fallo se reprodujo sobre una copia de `origin/main` sin modificar, con las mismas dependencias y servicios; el posterior ensayo aislado de la rama pasó. No se afirma una ejecución completa única sin fallos. El test y adaptador RabbitMQ no se modificaron. Evidencias: `/tmp/locker-pr-check/full-suite.log`, `baseline-messaging.log` y `diagnostic-results.json`.
- OpenAPI comparado con `main` actual: doce paths conservados y única diferencia `info.title`; docs y precedencia PostgreSQL/AMQP comprobados. Configuración Compose nueva/antigua coherente para API, migrador, worker y broker, con ambos volúmenes resueltos correctamente.
- Compose real con PostgreSQL 17 y RabbitMQ 4: instalación nueva y transición deteniendo solo API/worker correctas; ambos volúmenes y contenedor RabbitMQ idénticos, entrega y revisión `0005` conservadas. Cotización API→RabbitMQ→worker→PostgreSQL completada con ambas configuraciones; smoke `GET /lockers` devuelve 200 y `[]`. Evidencias: `/tmp/locker-pr-check/runtime-results.json` y `diagnostic-results.json`. Se limpiaron únicamente los recursos temporales identificados por UUID/etiqueta de esta ejecución.
- `scripts/ci/smoke.sh` local falló al construir por `UnknownIssuer`, debido a la CA del proxy del entorno dentro de Docker. La variante temporal del mismo Dockerfile con CA montada como secreto y `SSL_CERT_FILE` construyó correctamente usando uv 0.13.1 y el lock final; esa imagen pasó el smoke y los ensayos anteriores. Dockerfile, script y workflow del repositorio siguen intactos. Evidencias: `/tmp/locker-pr-check/official-smoke.log` y `build-final.log`.
- `openspec validate rename-to-locker-management-demo --strict` y `git diff --check`: correctos. Revisión independiente del diff contra `main` y de los diagnósticos: sin hallazgos accionables para el renombrado; se conservan expresamente los límites anteriores.

## Pasos operativos pendientes

- **3.1:** GitHub sigue identificando `0865marc/hexagonal_architecture` con ID `1420522580`; la consulta del nombre propuesto devuelve 404. El conector permite consultar el repositorio pero no renombrarlo, y `gh auth status` informa de credencial inválida. `origin` se conserva hasta que se pueda verificar el mismo ID con el nombre nuevo.
- **3.2:** No hay una herramienta disponible para trasladar y volver a vincular este checkout gestionado. La consulta de proyectos/artefactos de Codex no ofrece una vinculación editable para esta ruta. Se conserva `/workspace/hexagonal_architecture`, conforme a la condición del diseño.
- Estado actual: adaptación y revisión contra `021dfc2` completas (4/6 tareas), con los límites de verificación registrados arriba. Rama `chore/rename-locker-management-demo` preparada para el PR autorizado contra `main`, tras resolver el rebase. Renombrado remoto y traslado siguen pendientes; el spec principal no se ha sincronizado ni el cambio archivado.
