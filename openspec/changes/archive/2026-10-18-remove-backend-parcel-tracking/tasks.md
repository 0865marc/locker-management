# Tasks

## 1. Retirada acotada

- [x] 1.1 Eliminar los paquetes `backend/application/tracking/` y `backend/adapters/http/tracking/`, su composición en `main.py`/`adapters/http/routes.py` y las dos suites exclusivas. Añadir a `backend/tests/unit/test_main.py` regresiones de ausencia de ruta/esquemas OpenAPI y `app.state.tracking_service`, y 404 para UUID válido e inválido. Verificar los tests de composición y ausencia de importaciones huérfanas sin modificar dominio, puertos, datos ni CORS.
- [x] 1.2 Adaptar únicamente `frontend/tests/cors_server.py` y los E2E afectados: limpiar fixtures huérfanos, comprobar 404 real con CORS y retorno a cotización en escritorio/móvil, y conservar casos de cliente exitosos mediante la interceptación explícita existente cuando la necesiten. Ejecutar esos E2E, sin recrear una ruta tracking en el servidor de pruebas, y comprobar que `frontend/src` permanece idéntico.
- [x] 1.3 Actualizar la sección de seguimiento de `README.md` para indicar integración pendiente, ausencia del endpoint y limitación del mensaje 404 del cliente conservado. Revisar que no promete seguimiento operativo ni una API sustituta, y que no modifica documentación de funcionalidades ajenas.

## 2. Verificación integrada

- [x] 2.1 Ejecutar la suite unitaria del backend y las regresiones pertinentes de HTTP/CORS/cotizaciones; frontend `npm run check`, `npm test`, build estático con API apagada y E2E afectados. Desde `backend/`, ejecutar `uv run --extra dev pyright --project .. --warnings` con cero errores y cero advertencias. Validar este cambio con `openspec validate remove-backend-parcel-tracking --strict`, comprobar el diff frente a `origin/main` y obtener revisión independiente sin hallazgos pendientes; registrar resultados y limitaciones reales. No se requiere migración ni un nuevo stack Docker.

## Workflow follow-up

- Cuando el coordinador sincronice este cambio, aplicar las cuatro retiradas, las dos modificaciones del cliente y el requisito de ausencia; actualizar también el Purpose base al texto de `design.md`, pues el delta no lo cambia automáticamente.
- Conservar íntegros los artefactos y evidencias de `archive/2026-10-18-add-astro-locker-map`; la sincronización y el archivo de este nuevo cambio pertenecen al cierre posterior del coordinador.


## Evidencia de retirada — 2026-10-18

- Eliminados los seis archivos de los paquetes de tracking y sus dos suites exclusivas, sin servicio ni ruta sustitutos. `backend/adapters/http/routes.py` vuelve a coincidir con `origin/main`; el diff restante de `backend/main.py` frente a esa base contiene únicamente CORS. La regresión de composición comprueba ausencia de estado, ruta y esquemas OpenAPI, y 404 normal para UUID válido e inválido sin tocar la base de datos.
- Desde `backend/`, `env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL UV_CACHE_DIR=/tmp/codex-uv-cache uv run --extra dev python -m unittest discover -s tests/unit -t . -v`: 103 pruebas correctas (3,746 s), incluyendo composición, HTTP, CORS y cotizaciones. Log `/tmp/remove-tracking-backend-unit.log`.
- Desde `frontend/`, `ASTRO_TELEMETRY_DISABLED=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e`: 51/51 pruebas correctas en una corrida completa (1,3 min). Los dos casos de retirada prueban 404 real legible con CORS, reintento, ausencia de marcador/resultado y regreso conservando datos de cotización. La prueba de limpieza visual usa una respuesta interceptada explícitamente; el servidor de pruebas no implementa tracking. Log `/tmp/remove-tracking-e2e.log`.
- `npm test`: 146 pruebas en ocho archivos. `ASTRO_TELEMETRY_DISABLED=1 npm run check` tras los ajustes de pruebas: 35 archivos, cero errores, advertencias o hints. Logs `/tmp/remove-tracking-frontend-unit.log` y `/tmp/remove-tracking-frontend-check-final.log`.
- Tras finalizar Playwright y cerrar sus servidores, `ASTRO_TELEMETRY_DISABLED=1 PUBLIC_API_BASE_URL=http://127.0.0.1:8765 npm run build` genera una página estática con la API configurada apagada. Log `/tmp/remove-tracking-build-api-off.log`.
- Pyright final desde `backend/`: `UV_CACHE_DIR=/tmp/codex-uv-cache uv run --extra dev pyright --project .. --warnings`, cero errores y cero advertencias; Ruff final y `git diff --check` correctos. Logs `/tmp/remove-tracking-pyright-final.log` y `/tmp/remove-tracking-ruff-final.log`.
- Las primeras ejecuciones backend se detuvieron bajo la restricción inicial de sockets del entorno; la corrida final y los E2E se ejecutaron con permiso para sockets locales. No se ejecutó PostgreSQL de integración ni un nuevo stack Docker; no hay cambios de persistencia ni migraciones. Photon y teselas están controlados en pruebas, sin verificar conectividad pública.
- `frontend/src`, dominio, puertos, persistencia, CORS, cotizaciones, generador, Compose, dependencias e historial anterior permanecen intactos. README explica que la pestaña queda pendiente de integración y que su mensaje de no encontrado deriva de una ruta inexistente.
- Revisión independiente de `sdd_reviewer` aprobada sin hallazgos. Base `parcel-tracking` sincronizada: cuatro requisitos retirados, dos modificados y uno añadido; Purpose ajustado al diseño, bloques contrastados y las 13 specs principales válidas en modo estricto. El cambio se validó estrictamente antes de sincronizar y conserva sus cuatro tareas completadas.

## Cierre — 2026-10-18

Archivado por el coordinador tras completar y revisar las cuatro tareas y verificar la sincronización. `openspec list --json` no muestra cambios activos y `scripts/ci/check-openspec-closed.sh` pasa. Se conservan los artefactos y la evidencia del cambio anterior.
