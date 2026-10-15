# Tasks

Plan aprobado explícitamente por el usuario el 2026-10-15. Las rutas concretas y los contratos están en design.md; los cinco deltas contienen los escenarios de aceptación. Las tareas se marcan solo después de verificar su comportamiento.

## 1. Dominio y contratos de aplicación

- [x] 1.1 Añadir Dimensions, Locker, Compartment y valores de asignación en domain/lockers.py; verificar en test_lockers.py enteros/rangos, rotación, encaje por ejes, igualdad, volumen mínimo y desempate UUID.
- [x] 1.2 Ampliar Delivery/Return con datos opcionales de asignación completos o todos null; verificar en test_domain.py que las transiciones inmutables conservan la asignación y rechazan estados parciales.
- [x] 1.3 Definir LockerRepository y receive_in_locker en los puertos, adaptar los servicios existentes y añadir LockerService; verificar con dobles en test_application.py que la vía asignada devuelve la entidad elegida y no llama primero a save.
- [x] 1.4 Documentar en README ubicación exacta, dimensiones/rotación, disponibilidad sin reserva y capacidad derivada; verificar que ejemplos y terminología coinciden con locker-management.

## 2. Persistencia y migración aditiva

- [x] 2.1 Añadir metadata de lockers, celdas y asignaciones compartidas con FKs, XOR, unicidad por paquete, índice único parcial y restricciones de dimensiones/fechas; verificar violaciones y round trips en test_locker_repositories.py con FKs SQLite activas.
- [x] 2.2 Añadir revisión 0003_lockers_and_custody sin modificar 0001/0002, registrar metadata en Alembic y guardar el downgrade antes de cualquier DDL; verificar 0002 poblado -> 0003, esquema vacío reversible y rechazo con datos nuevos en test_migrations.py y test_postgresql.py.
- [x] 2.3 Actualizar head esperado y snapshots para incluir tablas, índices, restricciones y revisión; verificar que 0001 poblado sigue rechazado por 0002 y que downgrade 0003 vacío conserva paquetes de 0002.
- [x] 2.4 Documentar upgrade, guardas de downgrade y límites de rollback de aplicación en README; verificar que las instrucciones respetan datos existentes y no incluyen backfills ficticios ni borrado de volúmenes.

## 3. Configuración y disponibilidad operativas

- [x] 3.1 Implementar repositorio de lockers con altas por lotes, cambios por identidad y retiro lógico, bloqueando el locker antes de mutar; verificar atomicidad de lote, límite de 1000 celdas nuevas por petición validado antes de materializar/escribir, crecimiento mediante lotes sucesivos, protección de ocupadas e identidad histórica en test_locker_repositories.py.
- [x] 3.2 Implementar consulta coherente por ubicación/dimensiones con razones y conteos derivados; verificar sin locker, inactivo, incompatibilidad, lleno, mezcla de lockers y ausencia de escrituras en test_locker_repositories.py.
- [x] 3.3 Añadir schemas/router de lockers e inyectarlos en main.py; verificar todos los endpoints, precedencia de ruta availability, tipos estrictos, IDs, 404/409/422 y ciclo de vida en test_locker_http.py y test_main.py.
- [x] 3.4 Añadir ejemplos reproducibles de crear/configurar/consultar lockers al README; verificarlos contra el contrato OpenAPI y un entorno preparado con migraciones.

## 4. Recepción y salida con ocupación atómica

- [x] 4.1 Implementar receive_in_locker para Delivery y Return con lock por locker, nueva lectura de capacidad, selección determinista y una transacción paquete/asignación; verificar éxito, conflicto, entidad devuelta completa y rollback inyectado antes del commit en test_locker_repositories.py.
- [x] 4.2 Ampliar save_exit para liberar solo la asignación del paquete tras CAS ganador en la misma transacción, y reconstruir campos de asignación en lecturas; verificar las tres salidas, locker inactivo, fallo antes del commit y A-sale/B-ocupa/A-repite sin afectar B.
- [x] 4.3 Ampliar schemas/rutas HTTP existentes con pareja opcional de entrada, campos nullable de salida y errores de capacidad; verificar solicitudes antiguas, históricos, campos prohibidos, parejas parciales y respuestas completas en test_http.py y test_locker_http.py. Documentar ejemplos de recepción/liberación y compatibilidad aditiva en README.

## 5. Garantías PostgreSQL y migración con datos

- [x] 5.1 Añadir test_locker_postgresql.py con conexiones independientes y sincronización explícita para Delivery/Return sobre última celda y primer contendiente que revierte; verificar un 201/un 409 con ganador confirmado, ausencia de paquetes huérfanos y adquisición del hueco tras rollback.
- [x] 5.2 Verificar en PostgreSQL recepción contra resize/disable/retire/inactivación y salidas concurrentes con reocupación; comprobar que solo se observan resultados serializables según las especificaciones y que ninguna salida vieja libera al nuevo ocupante.
- [x] 5.3 Verificar en PostgreSQL migración 0002 poblado -> 0003, restricciones/índices reales y downgrade bloqueado sin alterar snapshots completos; documentar en README cómo configurar TEST_DATABASE_URL y distinguir pruebas omitidas.

## 6. Verificación integrada y revisión

- [x] 6.1 Ejecutar desde backend `uv run --extra dev python -m unittest discover -s tests -v` con PostgreSQL de pruebas configurado; comprobar contratos existentes, nuevas suites, Alembic sin diferencias de metadata y resultados de demo crear -> consultar -> recibir -> liberar -> reutilizar. Registrar fallos u omisiones sin atribuirles éxito.
- [x] 6.2 Solicitar revisión independiente contra escenarios, límites hexagonales y evidencia de concurrencia/migración; resolver hallazgos y ejecutar `openspec validate add-locker-availability-and-custody --strict` antes de declarar implementación terminada.

## Evidencia de verificación — 2026-10-15

- Suite completa desde `backend`, con `TEST_DATABASE_URL` apuntando a PostgreSQL 17.11 de pruebas: `uv run --frozen --extra dev python -m unittest discover -s tests -v`. Resultado: **71 pruebas OK, sin omisiones**.
- Revisión independiente de `sdd_reviewer`: sin bugs funcionales observados. El único hallazgo P3, cobertura de razones/conteos combinados de disponibilidad, se corrigió en `test_locker_repositories.py`; sus **6 pruebas** se volvieron a ejecutar correctamente y el revisor confirmó el cierre.
- `alembic upgrade head` y `alembic check` sobre la base dedicada `hexagonal_locker_test`: revisión `0003_lockers_and_custody`, sin diferencias de metadata. Las suites verificaron migraciones pobladas, snapshots intactos tras rechazo y restricciones PostgreSQL.
- Demo de lockers del README ejecutada con `curl`/`jq` contra una API temporal y PostgreSQL: AVAILABLE → FULL → recogida → reutilización de la misma celda por Return → salida con locker inactivo → modificación/adición/retiro. Estado final comprobado: dos celdas libres; repetir la salida devuelve 409. API temporal detenida al terminar.
- `openspec validate add-locker-availability-and-custody --strict`: válido. `git diff --check`: correcto.
- Implementación completa; sincronización de especificaciones y archivado pendientes de solicitud. No se han realizado commits ni push.
