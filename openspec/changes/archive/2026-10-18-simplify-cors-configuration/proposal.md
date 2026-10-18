# Proposal

## Why

El usuario considera innecesario el wrapper CORS por ruta y solicita una configuración estándar más simple. La política resultante permitirá GET/POST para los orígenes configurados, sin excepciones según endpoint.

## What Changes

- Sustituir `ScopedCORSMiddleware` por una única instancia de `CORSMiddleware` estándar, configurada en `main.py` con GET/POST y `Content-Type`.
- Mantener `CORS_ALLOWED_ORIGINS`, su validador y `allow_credentials=False`; actualizar pruebas y documentación de la política global.
- Los preflight POST permitidos dejan de limitarse a `/quotations`. CORS no crea rutas ni sustituye autorización o validación HTTP.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `application-runtime`: aplicar la misma política CORS de GET/POST a todas las rutas, conservando orígenes exactos y configuración validada.

## Impact

`backend/main.py`, `backend/adapters/http/cors.py`, `backend/tests/unit/test_cors.py` y la sección CORS de `README.md`. Sin cambios de endpoints, servicios, frontend, dependencias, persistencia ni Compose.
