# Tasks

Plan aprobado por el usuario. La evidencia local de este cambio no completa la aceptación Python Workers/Free; no se autorizan despliegues, nuevos recursos remotos ni limpieza de datos mediante estas tareas.

## 1. Selección y recepción D1

- [x] 1.1 Crear `backend/adapters/database/d1/selection.py` con lectura única, resultado compacto, compatibilidad por rotación y orden entero high/low/UUID; verificar el SQL real contra el selector del dominio en `backend/tests/unit/test_d1_selection.py`, incluyendo permutaciones, empates, valores casi iguales, máximos y errores de decisión.
- [x] 1.2 Integrar el selector en `custody.py` para entregas/devoluciones conservando batch, guardas y tres intentos totales; ampliar `deploy/cloudflare/tests/test_d1_repositories.py` y comprobar sobre D1 local el caso de 2000 celdas, una fila de selección, cuatro sentencias por intento exitoso y las regresiones existentes de concurrencia, rollback y commit desconocido.

## 2. Verificación integrada

- [x] 2.1 Preparar fuentes con `scripts/cloudflare/prepare.py`, comprobar su frescura y la inclusión del nuevo módulo, y ejecutar unidades afectadas más `scripts/cloudflare/check.sh --d1-only`; desde `backend/`, pasar Ruff y `uv run --extra dev pyright --project .. --warnings` y `uv run --extra dev pyright --project ../deploy/cloudflare --warnings` con cero errores y advertencias.
- [x] 2.2 Obtener revisión independiente del cálculo entero, equivalencia con el dominio, límites de transferencia y preservación del CAS; resolver hallazgos, repetir únicamente verificaciones afectadas y registrar resultados locales separados de la comprobación nativa/remota pendiente.

## Workflow follow-up

- El usuario aprobó el plan antes de implementar; el coordinador es el único escritor de estados de tareas.
- Una comprobación posterior autorizada deberá medir CPU y consumo D1 de esta versión en recepciones asignadas de ambos tipos con 2000 celdas, conservando pendientes los demás escenarios Free. No repetir la campaña sobre fixtures previos ni borrar datos automáticamente para prepararla.
- La descarga Python Workers sigue bloqueada en este entorno: no reintentar esa descarga ni convertir el puente CPython/D1 en evidencia de CPU nativa. Sin aceptación remota completa, no declarar cumplido el objetivo Cloudflare Free.

## Verification evidence

- `uv run --extra dev python -m unittest discover -s tests/unit -p 'test_d1_*.py' -v`, desde `backend/`: 15 pruebas pasan, incluidas siete nuevas de SQL contra el dominio.
- `scripts/cloudflare/check.sh --d1-only`: 35 pruebas pasan (4 puente, 25 contratos D1, 1 campaña HTTP, 3 presupuesto y 2 historial de esquema). La campaña HTTP ejecutó 421 peticiones, con un máximo de ocho sentencias y trece parámetros; es evidencia CPython/D1 local.
- Recepciones de ambos tipos con 2000 celdas: una fila de cinco campos, cuatro sentencias por recepción exitosa y doce tras tres conflictos CAS.
- Repetición focalizada de `test_every_existing_locker_writer_cas_zero_changes` tras reforzar la aserción de doce sentencias: pasa (1 prueba).
- `uv run --extra dev pyright --project .. --warnings` y `uv run --extra dev pyright --project ../deploy/cloudflare --warnings`, desde `backend/`: cero errores y cero advertencias en ambos.
- Ruff lint y formato pasan para los cuatro archivos de implementación/pruebas. Preparación y `prepare.py --check`: 60 fuentes frescas, incluido `selection.py`.
- `openspec validate optimize-cloudflare-custody-selection --strict`: válido. No se ha ejecutado ni desplegado esta versión en Python Workers remoto; CPU y aceptación Free siguen pendientes.
- Revisión independiente de `sdd_reviewer`: sin hallazgos pendientes; equivalencia, cálculo entero, transferencia acotada y CAS revisados. Implementación completa; sincronización de especificaciones y archivo del cambio pendientes.
