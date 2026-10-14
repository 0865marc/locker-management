# Proposal

## Why

El repositorio implementa entregas, devoluciones y su infraestructura, pero `openspec/specs/` todavía no describe estos contratos. Registrar el comportamiento existente permitirá revisar cambios futuros con requisitos y escenarios trazables al código y las pruebas.

## What Changes

- Incorporar cinco especificaciones en ingles sobre capacidades ya implementadas, con escenarios de éxito, validación y límites relevantes.
- Mantener la separación hexagonal entre dominio, casos de uso, adaptadores y composición.
- Distinguir evidencia estática, pruebas existentes y ejecución de comprobaciones; los huecos de cobertura no añaden funcionalidades ni tareas de desarrollo.
- Esta propuesta añade documentación normativa a OpenSpec; no cambia comportamiento, código, pruebas, dependencias, README ni configuración.

## Capabilities

### New Capabilities

Son nuevas en el catálogo de OpenSpec, no funcionalidades nuevas de la aplicación.

- `delivery-management`: crear y listar entregas, normalizar la dirección y describir las respuestas HTTP.
- `return-management`: crear y listar devoluciones independientes, normalizar el motivo y describir las respuestas HTTP.
- `record-persistence`: almacenar y recuperar las entidades en tablas separadas, con sesiones por operación y transacciones por escritura.
- `database-migrations`: gestionar el esquema con Alembic y documentar la adopción manual de tablas anteriores.
- `application-runtime`: componer servicios y recursos, resolver la conexión y coordinar el arranque mediante Compose.

### Modified Capabilities

Ninguna: todavía no hay especificaciones principales.

## Impact

La planificación queda en `openspec/changes/document-existing-capabilities/`. Tras aprobar el plan, los únicos archivos de producto documental que se crearán son:

- `openspec/specs/delivery-management/spec.md`
- `openspec/specs/return-management/spec.md`
- `openspec/specs/record-persistence/spec.md`
- `openspec/specs/database-migrations/spec.md`
- `openspec/specs/application-runtime/spec.md`

La sincronización será una operación posterior del coordinador. No se archivará el cambio sin petición. No se requiere arrancar Docker, alterar bases de datos ni ampliar las pruebas para este trabajo documental.
