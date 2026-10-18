# Tasks

El usuario ya aprobó este plan. El coordinador mantiene las casillas tras la entrega del planner.

## 1. Corregir y cubrir ambas entradas

- [x] 1.1 Añadir los parámetros opcionales explícitos a la entrada productiva conservando `self.env` y su delegación. Ampliar y pasar las unidades afectadas para invocación completa y abreviada, entorno adicional distinto, reconocimiento previo y restauración del contexto en éxito/fallo, sin trabajo cuando ack falla.
- [x] 1.2 Aplicar la misma firma al spike y añadir/pasar regresiones de ambas invocaciones sobre su entrada real con dobles CPython, conservando orden de reconocimiento y limpieza. Verificar que las nuevas unidades se ejecutan automáticamente antes del sync nativo, ajustando únicamente la selección existente si hace falta.

## 2. Verificar el conjunto

- [x] 2.1 Ejecutar las unidades afectadas de backend y Cloudflare, Ruff y, desde `backend/`, `uv run --extra dev pyright --project .. --warnings` y `uv run --extra dev pyright --project ../deploy/cloudflare --warnings`, ambos con cero errores y advertencias. Obtener revisión independiente, resolver hallazgos y repetir las comprobaciones afectadas.

## Verificación local (2026-10-18)

- Pasan las 9 pruebas de `backend/tests/unit/test_cloudflare_context.py` y las 13 de `deploy/cloudflare/tests/test_probe_units.py`, estas últimas con el entorno Cloudflare. Las regresiones invocan las entradas reales mediante dobles de plataforma en ambas formas y observan reconocimiento, procesamiento y restauración del contexto.
- Una ejecución controlada del ejecutor del spike confirma que la selección existente incluye la nueva regresión antes de `pywrangler sync`; no se necesitan cambios del ejecutor ni comandos nativos para comprobarlo.
- Ambos comandos Pyright de 2.1 terminan con cero errores y cero advertencias; Ruff lint y formato pasan para los cuatro archivos Python afectados.
- Revisión independiente sin hallazgos pendientes. Solo cambia la firma de las dos entradas; sus cuerpos y el uso del entorno envuelto permanecen iguales.

## Evidencia pendiente

- Conservar el resultado parcial informado por el usuario: cuatro de cinco pruebas nativas pasaron, mientras Queues falló por la firma antes de procesar. Las unidades nuevas no convierten ese resultado en éxito nativo.
- Repetir el smoke nativo en un entorno accesible; este entorno mantiene el bloqueo 403 y no se reintenta la descarga. Validación nativa completa y aceptación Free permanecen separadas de la corrección local.

## Workflow follow-up

- El coordinador publicará la corrección verificada en la misma rama, conforme a la autorización del usuario, sin crear una PR ni sincronizar o archivar este cambio como parte de su planificación.
