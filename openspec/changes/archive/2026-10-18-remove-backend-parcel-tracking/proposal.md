# Proposal

## Why

El usuario solicita retirar las funcionalidades de seguimiento añadidas al backend y acepta conservar el frontend sin integración operativa. La retirada debe limitarse a ese código, preservando entregas, devoluciones, lockers, cotizaciones y sus datos.

## What Changes

- **BREAKING**: retirar `GET /tracking/{id}`, sus modelos, servicio y composición; la ruta deja de aparecer en OpenAPI y devuelve el 404 normal de una ruta inexistente.
- Eliminar las pruebas exclusivas del servicio retirado y comprobar su ausencia junto con las regresiones de la API existente.
- Mantener intacto `frontend/src`: su pestaña, validación, cancelación y tratamiento de errores quedan como integración pendiente. Adaptar únicamente el soporte de pruebas que dependía del endpoint retirado, sin recrearlo en el servidor de pruebas.
- Corregir la documentación vigente y los requisitos de `parcel-tracking`; conservar íntegro el cambio anterior archivado.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `parcel-tracking`: retirar sus cuatro requisitos de backend, exigir la ausencia del endpoint y conservar los dos requisitos de interacción del cliente, expresamente condicionados a una futura integración compatible.

## Impact

- Eliminar `backend/application/tracking/`, `backend/adapters/http/tracking/`, `backend/tests/unit/test_tracking.py` y `backend/tests/integration/test_tracking_http.py`.
- Ajustar `backend/main.py`, `backend/adapters/http/routes.py`, `backend/tests/unit/test_main.py`, `frontend/tests/cors_server.py`, los casos afectados de `frontend/tests/e2e/explorer.spec.ts` y la sección de seguimiento de `README.md`.
- Sin cambios de dominio, puertos de repositorio, persistencia, migraciones, CORS, cotizaciones, generador, dependencias, Compose ni frontend de producción. Los campos de negocio `tracking_number` de entregas/devoluciones permanecen.
