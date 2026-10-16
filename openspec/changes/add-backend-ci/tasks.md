# Tasks

Implementar solo tras aprobar el plan. Preparar una rama aislada sobre una base que ya incluya las cotizaciones asíncronas, sin modificar ni cerrar aquel cambio. Un único escritor mantendrá este archivo; completar cada casilla solo con su evidencia.

## 1. Ruff y contrato local

- [x] 1.1 Añadir Ruff al extra `dev`, actualizar lo necesario en `backend/uv.lock` y configurar reglas, formato y exclusiones históricas exactas en `backend/pyproject.toml`; verificar `uv sync --locked --extra dev`, que `env.py` y futuras revisiones quedan incluidos y que Pyright mantiene su alcance.
- [x] 1.2 Normalizar mecánicamente los archivos Python permitidos, revisar imports con efectos de registro y documentar lint/formato y correcciones locales en README; verificar desde `backend/` ambos comandos Ruff, unitarias sin servicios y `uv run --extra dev pyright --project .. --warnings` con cero errores/advertencias, además de ausencia de diferencias en 0001–0005.

## 2. Imagen bloqueada y smoke reproducible

- [x] 2.1 Adaptar `backend/Dockerfile` a uv fijado y dependencias bloqueadas, conservando los comandos y contenido necesarios; verificar build, uso de `uv.lock`, disponibilidad de uvicorn/Alembic/Python y fallo ante inconsistencia declarada/lockfile mediante una copia temporal aislada.
- [x] 2.2 Añadir `compose.ci.yaml` y `scripts/ci/smoke.sh` con proyecto único, sin publicaciones de puertos, plazo HTTP, logs y cleanup propio; documentar requisitos y ejecución en README y verificar configuración Compose, sintaxis shell, GET `/lockers` con 200/`[]` y fallo no cero con limpieza ante un arranque fallido controlado, sin tocar el stack de desarrollo.

## 3. Los cinco checks en GitHub Actions

- [x] 3.1 Añadir `.github/workflows/backend-ci.yml` con los cinco jobs del diseño, eventos PR/main, Python 3.11, instalación bloqueada, caché, concurrencia, permisos mínimos, timeouts, PostgreSQL efímero y smoke compartido; verificar YAML y semántica del workflow, comandos/rutas, cinco nombres estables y propagación de fallos (usar actionlint si está disponible, sin sustituir por ello la ejecución de los comandos).
- [x] 3.2 Actualizar README con los eventos y cinco controles, dependencias/URLs, comandos equivalentes y diferencia entre las suites seleccionadas en CI y la suite completa local; verificar las unitarias sin URLs/servicios y la integración PostgreSQL sin broker, incluyendo migraciones, y confirmar fallo explícito si falta configuración de integración.

## 4. Verificación integrada y revisión

- [x] 4.1 Ejecutar y registrar sobre el resultado final los comandos Ruff, `uv run --extra dev pyright --project .. --warnings` desde `backend/` con cero errores/advertencias, la suite completa local `uv run --extra dev python -m unittest discover -s tests -t . -v -f` con ambas URLs según README y el smoke Docker; comprobar que las verificaciones no modifican código/lockfile y validar `openspec validate add-backend-ci --strict`. Repetir comprobaciones afectadas tras correcciones.
- [x] 4.2 Obtener revisión independiente contra `specs/backend-ci/spec.md`, arquitectura, migraciones intactas y evidencia; corregir hallazgos accionables y revalidar lo afectado antes de informar de implementación terminada, distinguiendo resultados locales de la ejecución real todavía pendiente en Actions.

## Workflow follow-up

- Comprobar eventos, nombres/resultados y cancelación en GitHub Actions cuando la publicación de la rama/PR esté autorizada; no afirmar ejecución remota a partir de validación local.
- Sincronización y archivo de este cambio se gestionarán separadamente cuando estén autorizados; no modificar `add-asynchronous-shipping-quotations` como parte de estas tareas.

## Evidencia de implementación (2026-10-16)

- Ruff: `uv run --extra dev ruff check .` correcto y `uv run --extra dev ruff format --check .` con 65 archivos conformes; comprobados también en Python 3.11.16.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings`: cero errores y cero advertencias, también en el entorno aislado Python 3.11.16. La configuración compartida permanece intacta.
- Python 3.11.16: 77 pruebas unitarias sin URLs de servicios y 50 de integración PostgreSQL 17 sin RabbitMQ, todas correctas. La integración sin URL falla explícitamente.
- Suite completa local en Python 3.14.7: `uv run --extra dev python -m unittest discover -s tests -t . -v -f`, con ambas URLs temporales: 128 pruebas correctas. Los servicios temporales se retiraron al terminar.
- Imagen Python 3.13 con uv 0.13.1: build y smoke correctos, `GET /lockers` devuelve HTTP 200 y `[]`. Una copia temporal con lockfile inconsistente falla; otra con migración deliberadamente fallida devuelve error y limpia sus recursos.
- `actionlint` 1.7.12, sintaxis shell, configuración Compose sin puertos, `git diff --check` y `openspec validate add-backend-ci --strict`: correctos. Migraciones 0001–0005 sin modificaciones.
- Revisión independiente de `sdd_reviewer`: sin hallazgos accionables. La ejecución remota de Actions y sus eventos/cancelación siguen pendientes de publicación; no hubo commit, push, sincronización ni archivo del cambio.
