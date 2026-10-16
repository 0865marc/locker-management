# Proposal: separar Delivery y Return de forma consistente

## Why

Delivery y Return comparten archivos de implementación, mientras Locker y cotizaciones tienen módulos propios. Separar ambos flujos con el mismo criterio facilita localizar sus entidades, servicios y adaptadores.

## What Changes

- Separar entidades/estados, servicios, esquemas/rutas HTTP y filas/repositorios por Delivery y Return.
- Eliminar domain/models.py, application/use_cases.py, adapters/http/routes.py, adapters/http/schemas.py y adapters/database/sqlmodel_repositories.py.
- Situar las reglas y operaciones compartidas de asignación, celdas y ocupación en los módulos existentes de Locker. Conservar validación, errores, reloj y validación del cuerpo HTTP en módulos técnicos concretos, sin nuevos dominios ni archivos common/custody.
- Actualizar imports, composición, registro Alembic, pruebas y README, manteniendo contratos y comportamiento.

Dimensions, ports.py y connection.py permanecen donde están. No se añaden funcionalidades, dependencias, clases base, migraciones ni dominios; los errores existentes conservan sus nombres.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

Ninguna. `skip_specs: true`: reorganización sin cambios funcionales.

## Impact

Archivos por flujo en domain, application, adapters/http y adapters/database; consumidores en main.py, ports.py, migrations/env.py, tests y README. Las migraciones 0001–0004 y el cambio anterior permanecen intactos. Se exigirán OpenAPI/DDL equivalentes, Pyright sin diagnósticos y la suite existente.

El 2026-10-15 el usuario aprobó esta organización y su implementación con «coincidimos, adelante». Esta actualización solo modifica el plan y no requiere otra aprobación del mismo alcance.
