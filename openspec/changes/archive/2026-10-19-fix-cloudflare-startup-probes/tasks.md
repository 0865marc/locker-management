# Tasks

El plan de esta corrección ya fue presentado y aprobado. El coordinador mantiene las casillas tras la entrega del planner. No incluye cambios de CI, dependencias ni contratos del producto.

## 1. Corregir instrumentos y sondeos

- [x] 1.1 Corregir bootstrap y medidas internas del spike conservando el orden de importación; añadir unidades con origen cero, reloj congelado y delta positivo y aclarar su interpretación en `deploy/cloudflare/FEASIBILITY.md`. Verificar que no hay precondición sobre el origen y que la falta de avance se representa como no disponible, sin modificar evidencia histórica.
- [x] 1.2 Corregir ambos ejecutores para recuperar `RemoteDisconnected` dentro del plazo existente y mostrar causa, estado previo a limpieza y log acotado. Añadir y pasar unidades de recuperación, timeout, salida del proceso, error inesperado y log ausente, comprobando fallo y limpieza sin runtime nativo ni datos reales.

## 2. Integrar y verificar

- [x] 2.1 Incorporar las nuevas unidades a la secuencia automática del spike anterior a `pywrangler sync`; ejecutar las unidades existentes y nuevas con las dependencias Cloudflare y verificar mediante ejecución controlada que la selección automática las incluye sin descargar el runtime.
- [x] 2.2 Ejecutar Ruff en los archivos afectados y, desde `backend/`, `uv run --extra dev pyright --project .. --warnings` y `uv run --extra dev pyright --project ../deploy/cloudflare --warnings`, ambos con cero errores y advertencias. Obtener revisión independiente del delta y de la evidencia, corregir hallazgos y repetir las comprobaciones afectadas.

## Verificación local (2026-10-18)

- Con `deploy/cloudflare/.venv/bin/python`, descubrimiento unitario de `test_startup_*.py`: 9 casos correctos; `test_event_context.py`: 1; `test_probe_units.py`: 12. Total: 22 pruebas. Los dobles de plataforma y proceso no sustituyen la ejecución nativa.
- Una mutación temporal que elimina la inicialización anticipada del reloj hace fallar la regresión de orden de importación.
- Los dos comandos Pyright indicados en 2.2 terminaron con cero errores y cero advertencias; Ruff lint y formato pasan para los ocho archivos Python afectados.
- Revisión independiente sin hallazgos pendientes. Se corrigieron y verificaron el rechazo de respuestas posteriores al plazo y la regresión que exige inicializar el reloj antes de importar la aplicación.

## Evidencia pendiente fuera de esta corrección local

- La ejecución nativa de ambos perfiles sigue pendiente mientras `index.pyodide.org` esté bloqueado por 403; registrar esa limitación, sin reintentos ni resultados nativos ficticios. Cuando sea accesible, comprobar los ejecutores con sus fixtures aislados.
- Python/WASM, Queues y aceptación Free conservan sus comprobaciones independientes pendientes. Las unidades de este cambio no las completan ni prueban la causa del fallo anterior de CI sin su log.
