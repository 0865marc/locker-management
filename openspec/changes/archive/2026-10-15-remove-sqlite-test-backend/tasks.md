# Tasks

Plan aprobado explícitamente por el usuario el 2026-10-15. Las tareas se marcan solo tras verificar su comportamiento. No modificar el cambio de lockers, especificaciones principales ni migraciones históricas.

## 1. Separación y soporte de pruebas

- [x] 1.1 Crear paquetes tests/unit y tests/integration y mover los once módulos según design.md; separar composición de HttpPostgresTests. Verificar descubrimiento sin duplicados y ejecutar unitarias sin TEST_DATABASE_URL ni conexión a servicios, conservando todos sus escenarios.
- [x] 1.2 Añadir soporte PostgreSQL común con validación explícita de TEST_DATABASE_URL, conexión acotada, esquemas UUID, migraciones y limpieza registrada desde setup; eliminar skips de las suites PostgreSQL. Verificar fallo no cero sin URL/con URL incompatible/servidor inaccesible y limpieza tras un fallo provocado después de crear el esquema.
- [x] 1.3 Actualizar árbol y comandos unit/integration/full del README, incluyendo permisos de esquemas y preparación automática por caso; verificar que los comandos usan unittest discover y no necesitan migrar public previamente.

## 2. Portado con conservación de escenarios

- [x] 2.1 Portar test_repositories y test_locker_repositories a fixtures PostgreSQL y conservar UTC, identidad, restricciones, rollback y reocupación; ejecutar ambos módulos y registrar correspondencia con los escenarios de origen.
- [x] 2.2 Portar HTTP de lockers y extraer test_application_http con aplicación/pools aislados en un mismo loop; verificar las quince rutas, persistencia entre instancias y esquema vacío sin DDL al arrancar. Actualizar en README la descripción de qué prueba cada suite.
- [x] 2.3 Portar los seis escenarios de test_migrations, incluidos 0001 legacy columns y command.check, y adaptar suites PostgreSQL existentes al soporte común sin perder sincronización ni conexiones independientes. Ejecutar migraciones y concurrencia y comprobar snapshots completos antes/después de rechazos.

## 3. Retirada de compatibilidad SQLite

- [x] 3.1 Eliminar aiosqlite de pyproject y uv.lock y las adaptaciones actuales de connection.py, sqlmodel_repositories.py y sqlmodel_lockers.py; verificar dependencias resueltas sin aiosqlite, UTC consciente/nulls y metadata PostgreSQL sin diferencias. Confirmar por diff que 0001/0002/0003 permanecen intactas y no aparece una nueva revisión.
- [x] 3.2 Ajustar README para PostgreSQL como único backend de integración y conservar la explicación de pruebas unitarias sin servicios; verificar ejemplos locales/Compose y retirar instrucciones antiguas que describían integración omitida o SQLite activo, sin editar documentación histórica OpenSpec.

## 4. Verificación integrada y revisión

- [x] 4.1 Ejecutar unitarias sin base configurada, integración PostgreSQL y suite completa con los comandos de design.md; verificar fallo explícito de integración/completa sin URL y con conexión inválida, ejecución efectiva sin skips por entorno, cleanup de esquemas y ausencia de modificaciones en public. Registrar resultados y cualquier limitación real.
- [x] 4.2 Revisar independientemente el mapa de escenarios portados, contratos API/UTC, historial Alembic intacto y límites hexagonales; resolver hallazgos y ejecutar `openspec validate remove-sqlite-test-backend --strict` antes de declarar terminada la implementación.

## Evidencia de verificación — 2026-10-15

- Unitarias: `uv run --frozen --extra dev python -m unittest discover -s tests/unit -t . -v`, sin TEST_DATABASE_URL y con DATABASE_URL dirigida a un puerto sin servidor: **35 OK**, 0,899 s.
- Integración con PostgreSQL 17.11 en la base dedicada `hexagonal_locker_test`: `uv run --frozen --extra dev python -m unittest discover -s tests/integration -t . -v -f`: **37 OK**, 14,265 s, sin omisiones.
- Suite completa con TEST_DATABASE_URL configurada: `uv run --frozen --extra dev python -m unittest discover -s tests -t . -v -f`: **72 OK**, 16,812 s, sin omisiones; cinco comprobaciones Alembic sin diferencias de metadata.
- Seis comprobaciones negativas: integración/completa sin URL, driver incompatible, URL mal formada e integración/completa con servidor inaccesible. Todas terminaron con código no cero y diagnóstico esperado, sin skips ni contraseña de comprobación en la salida.
- Se provocaron un fallo durante la migración de setup y otro durante la ejecución. Se comprobó que ambos esquemas desaparecieron y que los seis motores creados (incluidos los preflight) emitieron su evento de disposal.
- Snapshot antes/después idéntico de las seis tablas de public: datos, columnas, índices y restricciones intactos; al finalizar solo existía el esquema public. Huella SHA-256: `40b37460ef5b2b9b4271d76ed6344ffe6e37d07100a980d2679b9b5bede60d70`.
- `aiosqlite` ausente del entorno instalado, pyproject y lockfile. Todas las otras versiones resueltas permanecen iguales; uv actualizó únicamente su revisión de formato del lockfile además de retirar el paquete. Migraciones 0001/0002/0003 byte a byte iguales y sin nueva revisión.
- Correspondencia de cobertura: cuatro módulos unitarios se movieron intactos; composición se adaptó a dobles. Repositorios (6), lockers (6), HTTP de lockers (3), migraciones (6) y suites PostgreSQL (6 y 8) conservan sus métodos/escenarios. La integración HTTP original se extrajo a `test_application_http.py`, con un escenario adicional de esquema vacío sin DDL. Revisión independiente: los 71 métodos anteriores siguen presentes; hay 72 en total.
- `sdd_reviewer` cerró sin hallazgos pendientes tras revisar código y evidencia. Su intento independiente de TestClient quedó limitado por el sandbox; las ejecuciones completas del equipo con permisos para los sockets locales terminaron correctamente.
- `openspec validate remove-sqlite-test-backend --strict` y `git diff --check`: correctos. Implementación completa; sincronización de especificaciones y archivado no realizados.
