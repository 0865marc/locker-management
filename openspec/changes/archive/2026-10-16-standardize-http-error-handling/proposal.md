# Proposal

## Why

Los endpoints de lockers traducen errores mediante `invoke()`, mientras que deliveries y returns muestran sus capturas directamente. Usar `try/except` explícito también en lockers permite leer la política de errores de cada endpoint con la misma convención, conservando el contrato HTTP actual.

## What Changes

- Sustituir las ocho llamadas a `invoke()` en las rutas de lockers por capturas explícitas equivalentes.
- Eliminar `invoke()` y sus tipos/importaciones exclusivos, preservando códigos, cuerpos de respuesta, encadenamiento de excepciones y frontera de captura.
- Verificar los contratos existentes de lockers, deliveries y returns y publicar el cambio aprobado en una rama nueva `refactor/explicit-http-error-handling`.

## Capabilities

### New Capabilities

Ninguna. Es una refactorización sin comportamiento nuevo.

### Modified Capabilities

Ninguna. Los contratos de `locker-management`, `delivery-management` y `return-management` permanecen vigentes. Se declara `skip_specs: true` porque no cambian requisitos observables; los escenarios de conservación se detallan en el diseño.

## Impact

- Único archivo de producción previsto: `backend/adapters/http/lockers/routes.py`.
- Artefactos de planificación: `.openspec.yaml`, `proposal.md`, `design.md` y `tasks.md` en este cambio.
- Se conserva `capacity_http()` y su ubicación, de la que dependen deliveries y returns. No se modifican otros adaptadores, dominio, aplicación, persistencia, esquemas HTTP, documentación, dependencias, configuración ni migraciones.
- Se reutilizan las pruebas existentes; no se prevén archivos de prueba nuevos ni modificaciones de los actuales.
- La implementación y publicación quedan pendientes de la revisión explícita de este plan. Sincronización de especificaciones, archivado, merge y despliegue quedan fuera de este cambio.
