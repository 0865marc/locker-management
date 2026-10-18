# Tasks

Plan aprobado explícitamente por el usuario con «adelante». Implementación, verificación y revisión independiente completadas; cierre coordinado en curso.

## 1. Retirar las evidencias históricas

- [x] 1.1 Eliminar los once archivos versionados de `deploy/cloudflare/evidence/`; sustituir sus dieciséis excepciones actuales/antiguas en `.gitignore` por los ignores completos indicados en el diseño; ajustar las referencias históricas afectadas de `FEASIBILITY.md`. Verificar con `git diff --check`, inspección del diff y `git check-ignore --no-index` sobre rutas representativas `.log` y `.txt` en ambos directorios; comprobar que el harness y los artefactos históricos no se modificaron.

## 2. Verificar y preparar el cierre

- [x] 2.1 Desde `backend/`, ejecutar `uv run --extra dev pyright --project .. --warnings` y exigir cero errores y advertencias; ejecutar `env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL uv run --extra dev python -m unittest discover -s tests/unit -t . -v`. Registrar resultados reales en este archivo, distinguiendo esta verificación de las históricas. No añadir tests permanentes para replicar la limpieza ni ejecutar campañas remotas.
- [x] 2.2 Obtener revisión independiente del diff, escenarios de aceptación y mapa de sincronización de seis requisitos en tres specs, resolviendo hallazgos pertinentes. Validar este cambio y cada uno de los cuatro previos con `openspec validate NOMBRE --strict`; registrar resultado y revisión aquí antes de marcar completada esta preparación.

## Workflow follow-up

- El coordinador sincronizará `fix-cloudflare-acceptance-client` y `fix-cloudflare-startup-probes` en `openspec/specs/test-execution/spec.md`, `fix-cloudflare-queue-entrypoints` en `openspec/specs/application-runtime/spec.md` y `optimize-cloudflare-custody-selection` en `openspec/specs/record-persistence/spec.md`, siguiendo las instrucciones actuales de cada cambio.
- Comparará los seis bloques y todo el contenido anterior, y ejecutará `openspec validate --specs --strict`. La aprobación de este plan incluirá conservar la omisión deliberada del diseño condicional de `fix-cloudflare-acceptance-client`, ya explicada en sus tareas; no se inventará un diseño retrospectivo.
- Solo tras verificar las sincronizaciones, archivará los cuatro cambios previos en `openspec/changes/archive/YYYY-MM-DD-NOMBRE/` con la fecha real del cierre. Archivará este cambio una vez sus tres tareas estén verificadas y completas; no tiene delta propio que sincronizar. Preservará la evidencia histórica y evitará carreras entre sincronización y movimiento.
- Confirmará cero cambios activos con `openspec list --json`, ejecutará `scripts/ci/check-openspec-closed.sh`, repetirá `git diff --check` y comprobará el alcance final antes de publicar.
- Hará commit/push en `codex/cloudflare-free-deployment` y actualizará la PR abierta #10 hacia `main` con el resultado y la evidencia, sin duplicarla ni fusionarla. Informará del estado real de sus checks, separando los nuevos de los anteriores.

## Evidencia nueva del cierre

- Tarea 1.1: retirados exactamente los once archivos versionados; `git diff --check` pasa. Inspección del diff: únicamente `.gitignore`, `FEASIBILITY.md` y las once eliminaciones, aparte de los artefactos de este cierre; harness y artefactos históricos sin cambios. `git check-ignore --no-index -v` confirma `.log` y `.txt` bajo `/deploy/cloudflare/evidence/` y `/cloudflare/evidence/`, con reglas de directorio completo.
- Tarea 2.1: desde `backend/`, `UV_CACHE_DIR=/tmp/locker-management-uv-cache uv run --extra dev pyright --project .. --warnings` termina con código 0: **0 errors, 0 warnings, 0 informations**. La preparación inicial falló por DNS al descargar dependencias; se completó con escalación autorizada, sin cambiar versiones ni archivos de configuración. CPython seleccionado por uv: 3.14.7.
- Tarea 2.1: `env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL UV_CACHE_DIR=/tmp/locker-management-uv-cache uv run --extra dev python -m unittest discover -s tests/unit -t . -v`, desde `backend/` con escalación por el bloqueo de TestClient en sandbox, termina con código 0: **135 tests en 6.671 s, OK**, sin skips. El primer intento en sandbox quedó bloqueado en el subprocess de TestClient y se interrumpió (código 130); no se presenta como éxito. Salida completa de la ejecución válida: `/tmp/locker-closure/unit-tests-escalated.log` (temporal, no versionada). No se ejecutaron campañas nativas/remotas, PostgreSQL ni RabbitMQ.
- Tarea 2.2: `openspec validate NOMBRE --strict` pasa (código 0) para `finalize-cloudflare-branch`, `fix-cloudflare-acceptance-client`, `fix-cloudflare-queue-entrypoints`, `fix-cloudflare-startup-probes` y `optimize-cloudflare-custody-selection`. El primero acepta cero deltas por `skip_specs: true`. Revisión independiente de `sdd_reviewer` completada sin hallazgos accionables: limpieza conforme, alcance arquitectónico y configuración Pyright intactos, evidencia actual de tipos y 135 unidades verificada.
- Sincronización verificada antes del archivo: seis requisitos y dieciséis escenarios añadidos exactamente una vez, conservando íntegramente el contenido anterior. Recuentos finales: `test-execution` 19, `application-runtime` 16 y `record-persistence` 10. `openspec validate --specs --strict`: **14 specs válidas, cero fallos**. El reviewer comprobó también los bloques y la preservación del contenido contra las copias anteriores.
