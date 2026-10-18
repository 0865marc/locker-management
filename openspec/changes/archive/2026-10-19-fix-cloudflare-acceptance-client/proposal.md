# Proposal

## Why

El cliente de aceptación recibió 403/1010 en `/docs`; el usuario confirmó 200 al repetir ese GET cambiando únicamente su User-Agent a `LockerManagementAcceptance/0.1`. La campaña debe identificarse con ese nombre propio estable.

## What Changes

- Añadir ese User-Agent a todas las peticiones del cliente HTTP de aceptación, preservando el transporte y la campaña actuales.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `test-execution`: identificar explícitamente el cliente de aceptación HTTP Cloudflare.

## Impact

Solo `scripts/cloudflare/acceptance.py`. Sin cambios de diagnósticos, backend, despliegue, dependencias ni tests permanentes nuevos. Verificación con la suite de aceptación existente y ambos Pyright. El 200 informado acredita únicamente el GET de diagnóstico; campaña completa y aceptación Free siguen pendientes.
