# Tasks

El 2026-10-15 el usuario aprobó implementar esta separación y eliminar los cinco archivos genéricos. Las tareas se marcan tras verificar su implementación. Specs se omite porque no cambia comportamiento.

## 1. Separación por flujo

- [x] 1.1 Registrar HEAD y capturar OpenAPI y DDL/índices antes de editar código. Separar entidades/estados y servicios; trasladar validadores/error a domain/validation.py, reglas de asignación/recepción a domain/lockers.py y error/reloj a application/errors.py y clock.py. Eliminar models.py/use_cases.py, actualizar imports, tests y README; verificar dominio/aplicación sin modificar mensajes, orden de validación ni reloj inyectado.
- [x] 1.2 Separar esquemas y routers Delivery/Return; mover ReceptionInput/AssignmentResponse a locker_schemas.py y require_empty_action_body a request_validation.py. Eliminar schemas.py/routes.py, actualizar main, consumidores y README; verificar HTTP/lifespan y OpenAPI idéntico, incluidos handlers, operationIds y componentes.
- [x] 1.3 Separar tablas, filas, conversiones y repositorios en sqlmodel_deliveries.py/sqlmodel_returns.py; trasladar operaciones compartidas de asignación y utc_timestamp a sqlmodel_lockers.py, sin imports de ambos flujos desde Locker. Eliminar sqlmodel_repositories.py y actualizar env.py, consumidores, pruebas y README. Verificar DDL/metadata idénticos, migraciones 0001–0004 intactas y PostgreSQL: rollback, concurrencia y liberación/reocupación, preservando CAS y límites transaccionales.

## 2. Verificación final

- [x] 2.1 Ejecutar `uv run --extra dev pyright --project .. --warnings` desde backend con cero errores/advertencias y configuración intacta; unitarias sin servicios y suite completa PostgreSQL (referencia: 95 casos, 52 unitarios y 43 de integración). Confirmar igualdad OpenAPI/DDL, eliminación de los cinco archivos y ausencia de imports obsoletos; validar `openspec validate refactor-domain-module-organization --strict`. Obtener revisión independiente sdd_reviewer, resolver hallazgos y repetir verificaciones afectadas antes de completar implementación.

## Evidencia de verificación (2026-10-15)

- Base de comparación: `86760350a1ea442c90d0611015af44bfdd3feb53`. OpenAPI completo, DDL/índices y los 95 métodos de prueba coinciden con la captura previa al refactor. Los cinco módulos antiguos están eliminados y no quedan imports a ellos.
- Desde `backend/`, `env -u TEST_DATABASE_URL UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev pyright --project .. --warnings`: **0 errores, 0 advertencias y 0 informaciones**. Configuración de Pyright y dependencias intactas.
- Unitarias sin `TEST_DATABASE_URL`: **52 pruebas aprobadas** en 2,726 s.
- Desde `backend/`, con `TEST_DATABASE_URL` apuntando a PostgreSQL 17 y esquemas aislados, `UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev python -m unittest discover -s tests -t . -v -f`: **95 pruebas aprobadas** en 19,477 s, sin omisiones. Las siete comprobaciones de Alembic indicaron `No new upgrade operations detected.`; migraciones 0001–0004 intactas.
- `openspec validate refactor-domain-module-organization --strict` y `git diff --check`: correctos.
- Revisión independiente de `sdd_reviewer`: sin hallazgos pendientes. Verificó validaciones, errores, límites transaccionales, CAS, liberación de asignaciones e imports acíclicos; ejecutó también Pyright sin diagnósticos.

Implementación completa. El cambio permanece sin sincronizar ni archivar.
