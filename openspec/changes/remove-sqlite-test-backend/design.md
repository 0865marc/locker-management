# Design

## Context

Ver proposal.md para la motivación. `aiosqlite` solo se declara en el extra dev, aunque la imagen instala ese extra. Cinco módulos usan SQLite: repositorios, repositorios de lockers, HTTP de lockers, migraciones y parte de test_main. Las suites PostgreSQL existentes usan esquemas UUID aislados, pero se omiten sin TEST_DATABASE_URL. El HTTP integrado de test_main escribe actualmente en las tablas de la URL configurada. Las pruebas de dominio/aplicación y test_http ya usan valores puros o dobles, sin base de datos.

Las especificaciones principales de runtime/persistencia/migraciones no exigen SQLite. El cambio completo de lockers contiene decisiones anteriores de pruebas SQLite; se conserva como historial, sin editarlo ni sincronizarlo. Este cambio introduce únicamente el contrato de ejecución de pruebas; no cambia comportamiento funcional de lockers/custodia.

## Goals / Non-Goals

**Goals:** un solo motor real de integración; unitarias sin servicios; conservar cobertura de escenarios y aislamiento; comandos estándar y fallo explícito de requisitos ausentes.

**Non-Goals:** runner propio, nuevo framework/dependencias, CI nueva, Docker/Compose nuevos, modificar dominio/casos de uso/rutas, imponer nuevas validaciones de URL en runtime, reescribir migraciones o limpiar referencias históricas a SQLite.

## Decisions

### 1. Separar por necesidad de infraestructura

Usar paquetes `tests/unit` y `tests/integration`, cada uno con __init__.py vacío. Mantener unittest y descubrir por directorio en lugar de una lista manual de módulos o un runner personalizado. Conservar `tests/__init__.py`.

| Origen en backend/tests | Destino | Adaptación |
| --- | --- | --- |
| test_domain.py | unit/test_domain.py | Movimiento; conservar escenarios puros. |
| test_application.py | unit/test_application.py | Movimiento; conservar AsyncMock de puertos. |
| test_http.py | unit/test_http.py | Movimiento; conservar dobles de servicios HTTP. |
| test_lockers.py | unit/test_lockers.py | Movimiento; conservar reglas puras. |
| test_main.py | unit/test_main.py | Conservar composición y lifecycle con motor/sesiones simulados; retirar la dependencia del archivo SQLite para demostrar que no hay conexiones/DDL al arrancar. |
| test_repositories.py | integration/test_repositories.py | Conservar escenarios secuenciales y portar fixture/datos a PostgreSQL. |
| test_locker_repositories.py | integration/test_locker_repositories.py | Conservar escenarios de configuración, ocupación, rollback y restricciones; PostgreSQL. |
| test_locker_http.py | integration/test_locker_http.py | Aplicación real, PostgreSQL y cliente HTTP asíncrono. |
| test_migrations.py | integration/test_migrations.py | Portar sus seis escenarios, consultas y snapshots a PostgreSQL; no eliminarlos por aparente duplicación. |
| test_postgresql.py | integration/test_postgresql.py | Reutilizar soporte común, quitar skips y conservar pruebas específicas/concurrentes. |
| test_locker_postgresql.py | integration/test_locker_postgresql.py | Reutilizar soporte común sin perder pools independientes, StatementGate ni observación de locks. |
| HttpPostgresTests de test_main.py | integration/test_application_http.py | Extraer persistencia entre instancias y añadir arranque sobre esquema vacío sin DDL; dejar de usar public. |

Comandos canónicos, desde `backend/` tras `uv sync --extra dev`:

```bash
uv run --extra dev python -m unittest discover -s tests/unit -t . -v
TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@localhost:5432/hexagonal_test' uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f
TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@localhost:5432/hexagonal_test' uv run --extra dev python -m unittest discover -s tests -t . -v -f
```

`-t .` mantiene importaciones de paquetes inequívocas; `-f` detiene integración/completa ante el primer error. No se necesita aplicar migraciones a public previamente: cada prueba prepara su esquema. Mantener ejemplos Compose usando `api python -m unittest discover -s tests/integration -t . -v -f`, con TEST_DATABASE_URL de la base dedicada existente. No aprovisionar infraestructura nueva en este cambio.

### 2. Soporte PostgreSQL compartido y fallos explícitos

Nuevo `tests/integration/support.py`, pequeño soporte de unittest basado en el patrón ya usado. Su importación no conecta ni exige variables; ningún módulo unitario importa soporte de integración. Cada clase de integración comprueba sus requisitos antes de crear fixtures, mediante setUpClass y un preflight con motor temporal que se cierra en el mismo event loop. Exigir TEST_DATABASE_URL no vacío con driver `postgresql+asyncpg`, usando el parser de SQLAlchemy. No recurrir a DATABASE_URL ni a la URL por defecto de la aplicación.

El preflight prueba conexión con plazo acotado (cinco segundos), comunica fallo de configuración/conexión sin mostrar contraseña ni URL completa, y eleva error de setup; no usa skipUnless/SkipTest ni convierte indisponibilidad en éxito. Conexión, autenticación o permisos insuficientes para crear esquemas producen fallo claro y código no cero. No reutilizar motores del preflight en los loops de las pruebas.

Cada caso usa un esquema `test_<uuid>` propio en una base de pruebas dedicada, con search_path limitado a ese esquema. Crear motores/pools independientes cuando la prueba represente actores concurrentes. Las migraciones reciben la conexión aislada mediante Config.attributes['connection']; admitir esquema vacío o revisión inicial elegida para pruebas de historia. No crear tablas mediante metadata.create_all en integración: prepararlas con Alembic, salvo el caso explícito que verifica arranque sin esquema preparado.

Registrar limpieza inmediatamente al adquirir recursos para ejecutarla incluso si setUp/migración falla: cerrar clientes y conexiones, disponer motores, eliminar exclusivamente el esquema generado y cerrar el motor administrativo. No truncar ni modificar tablas public; no borrar bases o volúmenes. No envolver la prueba completa en un rollback externo: ocultaría commits reales, pruebas entre instancias y locks de concurrencia.

Para HTTP integrado, usar IsolatedAsyncioTestCase y httpx.AsyncClient con ASGITransport, manteniendo engines/clients en un solo loop. Abrir explícitamente `app.router.lifespan_context(app)` para ejercitar startup/disposal; no añadir dependencia de lifecycle. Inyectar la fábrica de base de datos aislada en el composition root como ya hacen los tests concurrentes. Reabrir la aplicación con otro pool y el mismo esquema para probar persistencia entre instancias. Para ausencia de DDL, inspeccionar el esquema vacío antes/después de startup y de consultar OpenAPI.

### 3. Conservar escenarios, no solo número de tests

| Área | Evidencia que debe sobrevivir al cambio |
| --- | --- |
| Repositorios | Identidad/valores/nulls/UTC entre instancias, UUID duplicado sin overwrite y recuperación posterior, CAS de salida, fallo antes de commit, estados/fechas inválidos. |
| Lockers | Creación por lotes y límites, compatibilidad y snapshot de solo lectura, configuración ocupada/retiro, capacidad compartida, tres salidas, locker inactivo, historial y A-sale/B-ocupa/A-repite. |
| HTTP | Validación/status/representaciones de quince rutas, cuerpos de acciones, entrada pareada de locker y datos históricos nullable; aplicación completa y segunda instancia. |
| Migraciones SQLite portadas | 0001 conserva columnas legacy; round trip vacío a base/head y metadata sin diferencias; 0001 poblado bloquea upgrade; 0002 poblado bloquea downgrade; 0002 poblado -> 0003 es aditivo y reversible si lockers vacíos; datos de lockers activos o históricos bloquean downgrade sin cambios. |
| PostgreSQL específico | timestamptz, FKs/checks/índice parcial, locks de migración, última celda concurrente, rollback del primer contendiente, reconfiguración concurrente y salidas/reocupación seguras. |

Adaptar fixtures SQL al tipado PostgreSQL con parámetros tipados; no reemplazar comprobaciones por valores literales que eviten restricciones. Sustituir sqlite_master/PRAGMA por inspección PostgreSQL/SQLAlchemy; snapshot incluye columnas, índices, FKs, unicidad, checks, filas y revisión. Ejecutar Alembic command.check sobre la misma conexión/esquema aislados y alinear en soporte la introspección del esquema por defecto cuando sea necesario, sin alterar env.py de producción. Registrar en el informe de implementación el destino de cada grupo de escenarios; consolidar duplicados solo si queda evidencia equivalente identificable.

### 4. Eliminar solo compatibilidad actual de SQLite

- `backend/pyproject.toml` y `backend/uv.lock`: quitar aiosqlite sin actualizar innecesariamente otras dependencias; conservar httpx y asyncpg.
- `backend/adapters/database/connection.py`: eliminar listener PRAGMA y su import event. Mantener get_database_url, precedencia, fábrica y lifecycle actuales.
- `backend/adapters/database/sqlmodel_repositories.py`: retirar la reinterpretación de timestamps naive como UTC específica de SQLite. Mantener nulls y conversión de instantes conscientes a UTC; un datetime sin zona no debe aceptarse tomando la zona local del proceso. Puede conservarse una comprobación explícita de awareness coherente con el dominio.
- `backend/adapters/database/sqlmodel_lockers.py`: retirar sqlite_where del índice actual, conservando postgresql_where y la unicidad de ocupación activa.

Mantener las tres migraciones históricas byte a byte, incluido sqlite_where de 0003: es inerte para PostgreSQL y no requiere aiosqlite. No generar 0004 porque el esquema PostgreSQL no cambia. No añadir whitelists ni cambiar errores/configuración de DATABASE_URL en runtime; SQLite deja de ser backend de pruebas soportado, no se añade una política general sobre todos los drivers posibles.

### 5. Archivos afectados

Fuera de tests: modificar únicamente `backend/pyproject.toml`, `backend/uv.lock`, los tres archivos del adaptador listados arriba y `README.md` (seis archivos). En tests: once movimientos detallados en la tabla, más cuatro archivos nuevos (`tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/integration/support.py`, `tests/integration/test_application_http.py`); no mantener copias duplicadas en la raíz. Actualizar imports internos que cambien de paquete. Conservar Dockerfile, compose.yaml, dominio, aplicación, HTTP de producto y migraciones.

## Risks / Trade-offs

- [Integración exige un servicio y es más lenta] → unitarias separadas; reutilizar PostgreSQL existente, esquemas independientes y sin framework adicional.
- [Cambio de motor oculta pérdida de escenarios] → mantener mapa anterior y revisar cada portado, especialmente 0001 y metadata Alembic que no cubre por sí sola la suite PostgreSQL actual.
- [Motores compartidos entre loops de tests HTTP] → usar cliente asíncrono y recursos por caso/loop; cerrar antes de borrar esquema.
- [Éxito aparente con integración omitida] → quitar skips por entorno; probar comandos sin URL, con servidor inaccesible y con PostgreSQL real.
- [Referencias históricas SQLite permanecen] → conservar migraciones y OpenSpec anteriores; ausencia de driver/uso operativo importa más que borrar toda coincidencia textual.

## Migration Plan

No hay migración de base de datos. Tras aprobar el plan: mover/separar suites, introducir soporte común, portar escenarios, quitar compatibilidad actual y actualizar documentación. Instalar dependencias resueltas y ejecutar unitarias sin PostgreSQL, integración con PostgreSQL y suite completa. Verificar que las migraciones históricas no cambian y que Alembic no propone alteraciones de esquema. Un rollback del código/dependencias revierte este cambio sin tocar datos.
