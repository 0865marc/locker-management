# Proposal

## Why

La aplicación trabaja con PostgreSQL, pero parte de las pruebas usa SQLite y obliga a mantener compatibilidad adicional que no demuestra los bloqueos ni los tipos reales. Unificar la integración sobre PostgreSQL simplifica el repositorio conservando pruebas unitarias rápidas sin servicios.

## What Changes

- Separar `tests/unit` y `tests/integration` y ejecutarlos mediante `unittest discover`, sin runner ni framework nuevo.
- Portar a PostgreSQL los escenarios actuales de repositorios, migraciones, HTTP de lockers y arranque; reutilizar esquemas aislados por prueba y conservar las pruebas de concurrencia existentes.
- Hacer que integración y suite completa fallen claramente cuando falta `TEST_DATABASE_URL`, no es una URL PostgreSQL compatible o el servidor no está disponible, en vez de omitir las pruebas.
- Retirar `aiosqlite` del extra dev y lockfile, el PRAGMA de SQLite, su conversión de fechas sin zona y la opción SQLite del índice en metadata actual; conservar normalización UTC.
- Conservar sin cambios las migraciones `0001`, `0002`, `0003`, datos, API y resolución de `DATABASE_URL`. No añadir migraciones ni rechazos de URL a la aplicación.
- Actualizar README con comandos por suite y requisitos de integración. **BREAKING para desarrollo:** la suite completa necesita PostgreSQL; los comandos y rutas de módulos de tests cambian. La API no cambia.

## Capabilities

### New Capabilities

- `test-execution`: ejecución separada de pruebas sin servicios e integración PostgreSQL aislada, con fallos explícitos y conservación de escenarios.

### Modified Capabilities

Ninguna capacidad funcional cambia. Se conservan los contratos de runtime, persistencia, migraciones y lockers.

## Impact

Reorganización de tests y soporte común PostgreSQL, cambios acotados en tres archivos del adaptador de base de datos, `backend/pyproject.toml`, `backend/uv.lock` y `README.md`. Se mantienen unittest, SQLModel, Alembic, asyncpg y Compose existentes. El cambio de lockers completo permanece intacto y sin sincronizar/archivar por este trabajo.
