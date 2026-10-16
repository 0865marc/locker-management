# Proposal

## Why

El repositorio ya ofrece un backend de puntos de recogida y lockers; su identidad actual describe la arquitectura inicial en lugar del producto. Adoptar **Locker Management Demo** hará coherentes la presentación, la instalación y los ejemplos operativos.

## What Changes

- Usar `Locker Management Demo` como nombre visible y `locker-management-demo` como nombre del paquete, proyecto Compose y repositorio/carpeta.
- Actualizar README, título OpenAPI, descripción del paquete y lockfile; conservar las referencias técnicas a arquitectura hexagonal y las evidencias históricas de OpenSpec.
- **BREAKING:** cambiar las credenciales PostgreSQL/RabbitMQ y base locales de demostración a `locker_management_demo`, y los ejemplos de base/vhost de pruebas a `locker_management_demo_test`. API, migrador y worker usarán una configuración coherente. Documentar cómo conservar credenciales, proyecto y volúmenes existentes mediante configuración explícita.
- Planificar el renombrado de GitHub a `0865marc/locker-management-demo`, verificar que sigue siendo el mismo repositorio antes de actualizar `origin` y adaptar la carpeta local cuando el espacio de trabajo permita conservar su vinculación. La operación remota está actualmente bloqueada por falta de una herramienta autenticada que permita renombrar.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `application-runtime`: identidad visible de la API, nueva conexión local por defecto y valores Compose coherentes, con continuidad explícita para volúmenes existentes.

## Impact

Archivos de implementación: `README.md`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/main.py`, `backend/adapters/database/connection.py` y `compose.yaml`. La sincronización posterior afectará a `openspec/specs/application-runtime/spec.md`. El renombrado remoto, `origin` y la carpeta del checkout son pasos operativos separados y verificables.

La adaptación a `main` en `021dfc216a87dbc23ca56b29e9ff63eb17726dd7` conserva sus cotizaciones asíncronas, worker, RabbitMQ, Ruff/CI, dependencias y revisiones Alembic hasta `0005`. Se mantienen las rutas, contratos y reglas de negocio de esa base; el cambio sigue limitado a la identidad dentro de los mismos seis archivos. No se reescriben archivos archivados, instrucciones arquitectónicas ni metadatos generados. No se renombran bases/roles/volúmenes existentes ni se ejecutan operaciones sobre datos del usuario.
