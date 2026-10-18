# Proposal

## Why

La rama `codex/cloudflare-free-deployment` conserva cuatro cambios implementados sin archivar y once evidencias locales históricas que el usuario pide retirar. El cierre debe incorporar sus deltas a las especificaciones vigentes, mantener trazabilidad y actualizar la PR #10 existente hacia `main`.

## What Changes

- Eliminar los once archivos versionados de `deploy/cloudflare/evidence/`, ignorar las evidencias locales regeneradas y retirar las excepciones correspondientes de `.gitignore`.
- Ajustar únicamente las referencias afectadas de `deploy/cloudflare/FEASIBILITY.md`: identificar los resultados retirados como históricos consultables en Git, conservando conclusiones, limitaciones y verificaciones pendientes.
- Sincronizar y archivar `fix-cloudflare-acceptance-client`, `fix-cloudflare-queue-entrypoints`, `fix-cloudflare-startup-probes` y `optimize-cloudflare-custody-selection`, preservando sus tareas y evidencia de verificación.
- Tras verificar y revisar esta limpieza, archivar también este cambio, dejar cero cambios activos, hacer commit/push en la rama actual y reutilizar la PR #10 hacia `main`.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

Ninguna nueva en este cambio: limpieza documental y cierre administrativo, con `skip_specs: true`. Los seis requisitos pendientes pertenecen a los cuatro cambios existentes; se incorporan a `test-execution`, `application-runtime` y `record-persistence` mediante su sincronización, sin duplicarlos aquí.

## Impact

Archivos afectados: `.gitignore`, `deploy/cloudflare/FEASIBILITY.md`, los once archivos de `deploy/cloudflare/evidence/`, las tres specs principales mencionadas y los directorios de los cinco cambios al trasladarlos al archivo fechado. Se conservarán `domain/`, `application/`, adaptadores, entradas, migraciones, runners, dependencias y tests existentes. El harness podrá seguir generando logs locales ignorados.

La publicación actualiza https://github.com/0865marc/locker-management/pull/10; no requiere otra PR ni fusionar en `main`. Se exige aprobación explícita de este plan antes de implementar, sincronizar, archivar o publicar.
