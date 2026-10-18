# Proposal

## Why

El spike nativo aborta al importar si `perf_counter()` comienza en cero, aunque ese origen es válido. Además, ambos ejecutores dejan escapar `RemoteDisconnected` durante el sondeo y sus errores de arranque no muestran suficiente información del proceso.

## What Changes

- Eliminar la precondición de reloj positivo conservando el orden de importación; indicar que una medición interna sin avance no está disponible.
- Tolerar desconexiones transitorias durante el plazo de arranque y mostrar el error, estado del proceso y un extracto acotado del log cuando falle cualquiera de los dos ejecutores.
- Añadir regresiones sin runtime nativo, ejecutarlas antes de su sincronización y aclarar las limitaciones de medición en `FEASIBILITY.md`.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `test-execution`: arranque del spike independiente del origen del reloj, mediciones internas honestas y sondeos nativos acotados con diagnóstico y limpieza.

## Impact

Archivos previstos: `deploy/cloudflare/runtime_spike/{bootstrap,import_clock,worker}.py`, `deploy/cloudflare/tests/run_spike.py`, `deploy/cloudflare/tests/run_runtime.py`, sus unidades y `deploy/cloudflare/FEASIBILITY.md`. Un helper de pruebas compartido es admisible si evita duplicar el sondeo. No cambia aplicación, contratos de negocio, dependencias, workflows ni evidencia histórica. Las comprobaciones Python/WASM, Queues y Free ausentes conservan su estado pendiente.
