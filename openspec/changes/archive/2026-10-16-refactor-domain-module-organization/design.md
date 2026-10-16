# Design

## Context

Base: 8676035; motivación en proposal.md. El usuario aprobó separar Delivery/Return y eliminar los cinco archivos genéricos. Se preservan también los contratos del cambio anterior, implementado pero aún sin sincronizar. `skip_specs: true` corresponde a un refactor sin comportamiento nuevo.

## Goals / Non-Goals

**Goals:** módulos consistentes por flujo, responsabilidades compartidas concretas e imports acíclicos.

**Non-Goals:** dominios Parcel/custody, archivos common, frameworks genéricos, nuevas reglas, mover Dimensions, dividir ports.py o rediseñar transacciones.

## Decisions

### Implementaciones por flujo

Rutas relativas a backend. Se mantienen nombres de clases, estados, métodos y handlers.

| Capa | Delivery | Return |
| --- | --- | --- |
| Dominio | domain/deliveries.py: Delivery, DeliveryStatus | domain/returns.py: Return, ReturnStatus |
| Aplicación | application/delivery_use_cases.py: DeliveryService | application/return_use_cases.py: ReturnService |
| Esquemas | adapters/http/delivery_schemas.py: CreateDelivery, DeliveryResponse | adapters/http/return_schemas.py: CreateReturn, ReturnResponse |
| Rutas | adapters/http/delivery_routes.py: create_delivery_router | adapters/http/return_routes.py: create_return_router |
| Persistencia | adapters/database/sqlmodel_deliveries.py: tabla, fila, conversión y repositorio | adapters/database/sqlmodel_returns.py: tabla, fila, conversión y repositorio |

### Responsabilidades compartidas

- domain/validation.py conserva _text, _optional_text, _utc, _uuid, _exit_at y la única definición de CustodyConflictError. No importa Delivery/Return ni normaliza entidades completas. Cada __post_init__ aplica los validadores escalares en el orden actual; desaparece _normalize_common sin cambiar reglas, mensajes ni normalización.
- domain/lockers.py incorpora validate_assignment para la terna locker/celda/dimensiones y validate_reception para la pareja locker/dimensiones, trasladando las comprobaciones existentes. Dimensions permanece aquí.
- application/errors.py conserva la única definición de ParcelNotFoundError; application/clock.py conserva utc_now y su uso como default nombrado del reloj inyectable.
- adapters/http/locker_schemas.py recibe ReceptionInput y AssignmentResponse, cuyos campos describen la asignación a Locker. DimensionsInput ya está allí. adapters/http/request_validation.py recibe require_empty_action_body; capacity_http permanece en locker_routes.py.

Son responsabilidades técnicas o de Locker existentes, sin otro dominio. No se traslada el archivo mixto entero bajo otro nombre. Exportar explícitamente mediante __all__ los helpers privados reutilizados cuando Pyright lo requiera, sin ignorar diagnósticos ni renombrarlos innecesariamente.

Eliminar los cinco archivos originales: domain/models.py, application/use_cases.py, adapters/http/schemas.py, adapters/http/routes.py y adapters/database/sqlmodel_repositories.py. No dejar wrappers ni reexports de compatibilidad; actualizar todos sus consumidores.

### Persistencia sin ciclos

Cada repositorio conserva sus consultas, construcción/conversión de filas, CAS y límites de transacción. Desaparecen los helpers genéricos _read/_receive: su coordinación específica queda en cada repositorio, sin crear clases base o callbacks de un framework.

sqlmodel_lockers.py concentra elección de celda, registro de AssignmentRow, bloqueo de asignación y liberación. Recibe sesión, identificadores, dimensiones y columna FK explícita cuando corresponda; nunca importa entidades ni filas Delivery/Return. Conserva además utc_timestamp con la semántica del _utc de persistencia, incluidos None y el mensaje «Timestamp must include a timezone»; no sustituirlo por el validador de dominio.

Mantener orden de locks, flush y condiciones de actualización. La recepción construye la entidad asignada antes del commit; cualquier error revierte paquete y ocupación. La salida libera solo la asignación del paquete tras ganar su CAS, en la misma transacción. Repetir la salida de A después de ocupar B la celda no libera B.

### Composición y aceptación

main compone routers Locker/Delivery/Return en ese orden, conservando app.state, instancias y lifespan. Preservar nombres de handlers y modelos para mantener operationIds y componentes OpenAPI. Alembic env importa las nuevas filas y registra las mismas cinco tablas. Actualizar imports y README sin reorganizar suites por estética.

Registrar HEAD y capturar OpenAPI completo y DDL/índices antes de implementar; una captura temporal solo sirve si corresponde a esa base. Exigir igualdad posterior, API/errores/fechas actuales y migraciones 0001–0004 intactas. Conservar cobertura de rollback, última celda concurrente, liberación/reocupación, geografía y simuladores.

Desde backend ejecutar `uv run --extra dev pyright --project .. --warnings`: cero errores y advertencias, configuración intacta. Ejecutar unitarias sin servicios y suite completa con PostgreSQL aislado mediante unittest discover: referencia 95 pruebas, 52 unitarias y 43 de integración. Revisión independiente sdd_reviewer antes de completar.

## Risks / Trade-offs

Los movimientos pueden alterar imports, validación o metadata: verificar contratos completos y dependencias acíclicas. Se repite coordinación breve por flujo para mantener sus implementaciones explícitas; las reglas compartidas conservan una sola definición.

## Migration Plan

Sin migración de datos ni revisión Alembic nueva. El cambio anterior no se modifica, sincroniza ni archiva. Implementación autorizada el 2026-10-15; esta revisión solo actualiza documentación.
