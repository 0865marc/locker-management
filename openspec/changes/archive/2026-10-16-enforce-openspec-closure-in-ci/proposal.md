# Proposal

## Why

Los cambios OpenSpec implementados siguen activos cuando no se sincronizan ni archivan, por lo que `main` no distingue trabajo abierto de historial terminado. Hace falta cerrar los cambios actuales y comprobar esta condición en CI antes de integrar otros.

## What Changes

- Añadir un check independiente `OpenSpec closure` para todas las PR dirigidas a `main` y los pushes a `main`, sin filtros por rutas.
- Fallar si existe cualquier directorio activo directamente bajo `openspec/changes`, excepto `archive`, aunque sus tareas estén completas; listar los cambios y explicar cómo completar, validar, sincronizar y archivar localmente.
- Compartir la comprobación entre CI y un comando local ligero que no modifica archivos ni necesita servicios o el CLI de OpenSpec.
- Sincronizar y archivar los cambios actuales cuya implementación y evidencia estén completas, preservando requisitos y escenarios posteriores; cerrar también este cambio tras implementarlo y revisarlo.
- Documentar la política y el nombre del check que debe exigirse en la protección de `main` para bloquear merges.

## Capabilities

### New Capabilities

- `openspec-closure`: política verificable de ausencia de cambios activos en revisiones destinadas a `main`, diagnóstico y cierre explícito de los cambios terminados.

### Modified Capabilities

Ninguna nueva modificación de comportamiento del backend. La sincronización de cambios previos incorporará sus contratos ya implementados sin redefinirlos en este delta.

## Impact

- Nuevo workflow `.github/workflows/openspec-ci.yml` y script `scripts/ci/check-openspec-closed.sh`.
- README con comando local, cierre de cambios y relación con la protección de rama.
- Especificaciones principales afectadas por los cambios pendientes y sus movimientos a `openspec/changes/archive/`, además de la nueva especificación `openspec-closure`.
- Se conservan los cinco checks del backend y las fronteras hexagonales; no cambian código de aplicación, APIs, dependencias ni migraciones.
- No se configuran automáticamente reglas de protección, despliegues ni archivado desde CI.
