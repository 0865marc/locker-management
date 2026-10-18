# Tasks

## 1. Configuración y documentación

- [x] 1.1 Sustituir el wrapper por `CORSMiddleware` estándar en `backend/main.py` y eliminar solo la clase/imports huérfanos de `backend/adapters/http/cors.py`, conservando el validador. Ajustar y ejecutar `backend/tests/unit/test_cors.py`: GET/POST con Content-Type admitidos globalmente, PATCH/DELETE/cabeceras ajenas y orígenes no incluidos rechazados en preflight, sin credenciales ni cambio de contratos o ejecución de handlers durante OPTIONS.
- [x] 1.2 Actualizar la sección CORS de `README.md` y comprobar que describe una política global GET/POST, orígenes exactos y la diferencia entre preflight y autorización, sin prometer restricciones por ruta.

## 2. Verificación integrada

- [x] 2.1 Ejecutar las regresiones unitarias pertinentes de CORS, composición, HTTP y cotizaciones; desde `backend/`, `uv run --extra dev pyright --project .. --warnings` debe terminar con cero errores y cero advertencias. Validar `openspec validate simplify-cors-configuration --strict`, comprobar el diff y obtener revisión independiente sin hallazgos pendientes. Registrar evidencia y confirmar que frontend, endpoints, configuración de orígenes y persistencia permanecen intactos; sin nuevo stack Docker ni migración.


## Evidencia — 2026-10-18

- Sustituido el wrapper por una sola instancia estándar de `CORSMiddleware` en la composición. Política global GET/POST, `Content-Type`, lista exacta de orígenes y `allow_credentials=False`. `get_cors_allowed_origins` permanece idéntico byte a byte; no cambian endpoints, frontend, datos, dependencias ni Compose.
- Suite unitaria completa del backend: 103 pruebas correctas en 3,608 s, incluidas composición, HTTP, CORS y cotizaciones. Los casos CORS existentes comprueban preflight uniforme, restricciones de origen/método/cabeceras y que permitir OPTIONS no crea una ruta: las peticiones reales a `/missing` siguen devolviendo 404. Log `/tmp/simplify-cors-backend-unit.log`.
- Desde `backend/`, `UV_CACHE_DIR=/tmp/codex-uv-cache uv run --extra dev pyright --project .. --warnings`: cero errores y cero advertencias. Ruff correcto y sus tres archivos ya formateados. Logs `/tmp/simplify-cors-pyright.log`, `/tmp/simplify-cors-ruff.log` y `/tmp/simplify-cors-format-check.log`.
- Desde `frontend/`, `ASTRO_TELEMETRY_DISABLED=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e -- --grep 'real cross-origin FastAPI|removed tracking returns a real CORS-readable 404'`: 3/3 escenarios correctos en 6,9 s. Cubren cotización real mediante preflight/POST/GET y 404 de tracking legible por CORS en escritorio/móvil. Log `/tmp/simplify-cors-e2e.log`.
- Las pruebas backend y E2E usaron permiso de sockets locales. Sin cambios de frontend ni repetición de su suite completa/check/unit/build independientes; se conserva su evidencia anterior. Sin PostgreSQL de integración ni un nuevo stack Docker; teselas/Photon controlados, sin verificar su conectividad pública.
- Cambio validado estrictamente antes de sincronizar. Spec `application-runtime` sincronizada con un requisito modificado: sus tres escenarios previos se mantienen actualizados y se añade la política uniforme; Purpose y otros 13 requisitos idénticos. Las 13 specs principales pasan validación estricta. `git diff --check` limpio.
- Revisión independiente de `sdd_reviewer` aprobada sin hallazgos de implementación ni sincronización. Historial archivado anterior intacto.

## Cierre — 2026-10-18

Tres tareas completas, implementación y sincronización aprobadas. Archivado por el coordinador conservando sus cinco artefactos. `openspec list --json` sin cambios activos y `scripts/ci/check-openspec-closed.sh` correcto.
