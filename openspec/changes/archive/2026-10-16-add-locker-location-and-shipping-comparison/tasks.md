# Tasks

Las tareas 1–4 y sus evidencias corresponden a la implementación y correcciones previas. La nueva petición explícita autoriza añadir Pyright, corregir todo el backend analizado y exigir el chequeo al cerrar cada spec; sustituye la restricción anterior de no añadir checker/dependencias. Las tareas 5.1–5.3 están completadas con evidencia actual al final de este documento. No se han solicitado ni realizado sincronización/archivado.

## 1. Anotaciones estándar de Python

- [x] 1.1 Completar anotaciones estándar de parámetros, retornos, colecciones, genéricos y opcionales en funciones existentes afectadas de Locker/Dimensions, servicios, HTTP, repositorios, recepción/custodia y composición, y mantenerlas en todo código nuevo. Corregir narrowing e incompatibilidades entre puertos/adaptadores sin Any o supresiones para ocultarlas; revisar contratos y ejecutar pruebas existentes afectadas. Revisar Pylance en VSCode si está disponible, registrando su disponibilidad real bajo la restricción de herramientas de aquella fase, hoy sustituida; mantener migraciones históricas intactas.

## 2. Ubicación de lockers

- [x] 2.1 Añadir Address/Coordinates y alias nullable en `domain/lockers.py`, adaptar contratos de `domain/ports.py`, `application/locker_use_cases.py` y `adapters/http/locker_{schemas,routes}.py`. Probar validación, altas legacy/dirección sin alias, respuestas nullables y PATCH omit/null/reemplazo con unitarias; documentar en README que el acceso sin alias es por UUID/listado general y que disponibilidad por alias no cambia.
- [x] 2.2 Persistir los valores geográficos mediante `adapters/database/sqlmodel_lockers.py` y metadata, conservando la transacción existente. Verificar en `tests/integration/test_locker_repositories.py` y `test_locker_http.py` lectura entre instancias, reemplazo/borrado atómico, rechazo sin cambios, históricos y ausencia de alias inventado; conservar contratos de listado/disponibilidad y reglas de custodia.
- [x] 2.3 Crear `0004_locker_geography.py` sin backfill ni índice postal; añadir checks de grupos completos/formatos/rangos y guardas de downgrade antes de DDL. Adaptar `tests/integration/test_migrations.py`/`test_postgresql.py` a head 0004 y verificar upgrade poblado 0003→0004, rechazos por geografía/alias null, round trip seguro y metadata; mantener explícito 0002→0003 y archivos 0001–0003 intactos. Documentar despliegue/rollback en README.

## 3. Comparador interno de proveedores

- [x] 3.1 Añadir request/oferta/resultados tipados en `domain/shipping_quotes.py` y `ShippingProvider`/error técnico en `domain/ports.py`, reutilizando Dimensions desde `domain/lockers.py` sin extraerlo ni crear Parcel. Verificar en `tests/unit/test_shipping_quotes.py` límites, códigos abiertos, ofertas múltiples e invariantes de precio/plazo/no cobertura, sin infraestructura.
- [x] 3.2 Implementar `QuoteShipping.compare` en `application/shipping_quote_use_cases.py` y tres adaptadores independientes en `adapters/providers/simulated_shipping.py`. Probar resultado por proveedor, cuarto double con dos servicios sin cambios centrales, configuración inválida, ejemplo 330/520/830 céntimos, extremos, fallos parciales, concurrencia 3, timeout 2 s y cancelación limpia mediante barreras/doubles. Documentar un ejemplo Python directo; no añadir endpoint, wiring en main, agregado, persistencia ni dependencia de transporte.

## 4. Verificación integrada y revisión

- [x] 4.1 Revisar anotaciones/contratos y ejecutar unitarias sin servicios e integración/suite completa con PostgreSQL aislado; conservar fallo explícito sin TEST_DATABASE_URL, contratos existentes, concurrencia de custodia y migraciones. Verificar el ejemplo directo documentado y `openspec validate add-locker-location-and-shipping-comparison --strict`; registrar resultados reales sin marcar comprobaciones no ejecutadas.
- [x] 4.2 Solicitar revisión independiente de la implementación a `sdd_reviewer`, resolver hallazgos y repetir las verificaciones afectadas antes de declarar completa la implementación, conforme a AGENTS.md.


## Evidencia histórica de verificación (2026-10-15, anterior a Pyright)

- Suite completa: `TEST_DATABASE_URL=… UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev python -m unittest discover -s tests -t . -v -f`, desde `backend/`: **95 pruebas OK en 21.430 s**, sin omisiones. PostgreSQL 17 local, base dedicada `hexagonal_test` y esquemas aislados por prueba; incluye migraciones, metadata, rollback y concurrencia de custodia.
- Unitarias: `env -u TEST_DATABASE_URL UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev python -m unittest discover -s tests/unit -t . -v`: **51 pruebas OK en 2.744 s**, sin base configurada ni conexiones a ella. TestClient/AnyIO requirió habilitar sockets en el sandbox; no se cambiaron pruebas ni dependencias para ello.
- Ausencia de configuración: `env -u TEST_DATABASE_URL … python -m unittest tests.integration.test_locker_repositories -v` falla explícitamente antes de ejecutar casos con `TEST_DATABASE_URL is required for PostgreSQL integration tests` (salida 5), sin omitir integración silenciosamente.
- Ejemplo Python extraído literalmente del README y ejecutado: `sim-economy` 330 céntimos/3 días, `sim-express` 830/1 y `sim-standard` 520/2, en orden por código.
- Anotaciones: inspección de contratos/puertos, opcionales y genéricos; auditoría AST sin parámetros o retornos sin anotar en 23 módulos productivos, incluida 0004 y excluidas migraciones históricas. Esto no equivale a diagnósticos de Pylance, que no está disponible. Sin nuevas herramientas, configuración de tipado ni dependencias.
- Revisión independiente `sdd_reviewer` cerrada sin hallazgos pendientes. Corregidos y comprobados los dos P2: respuestas 422 para cuerpo vacío/no finitos y restricciones de texto Unicode coherentes entre Python/PostgreSQL. El revisor ejecutó además las 15 pruebas del comparador (OK en 2.067 s).
- `openspec validate add-locker-location-and-shipping-comparison --strict` y `git diff --check` correctos. `pyproject.toml`, `uv.lock` y las migraciones 0001–0003 permanecen intactos.


## Seguimiento histórico de diagnósticos de Pylance (anterior a Pyright)

El usuario aportó 29 diagnósticos tras el commit `1daa877`: 4 en `locker_routes.py` y 25 en `sqlmodel_lockers.py`. La auditoría AST y las pruebas de ejecución anteriores no demostraban compatibilidad con el analizador estático. Se reabren las tareas 1.1, 4.1 y 4.2 para corregir los contratos de `Select`, el override de `__tablename__`, los tipos de colecciones y los diagnósticos auxiliares, incluyendo el mismo patrón de tablas en `sqlmodel_repositories.py`. En esa etapa se mantenían anotaciones estándar, sin nuevos checkers, dependencias, supresiones ni cambios funcionales; la petición actual sustituye la restricción de herramientas.


### Corrección verificada en aquella etapa

- Los 4 diagnósticos de JSON se atienden con `TypeGuard` hacia vistas `Mapping[object, object]` y `Sequence[object]`; la recursión conserva la validación existente sin elementos `Unknown`.
- Los 11 diagnósticos encadenados de consultas provienen del genérico incorrecto: SQLModel declara `Select` con `TypeVarTuple`, por lo que se usa `Select[LockerRow, CompartmentRow | None, UUID | None]`, no un único parámetro tupla. El cast sigue limitado a la nulabilidad real de los outer joins.
- Los 6 diagnósticos de `__tablename__` se atienden con el mapeo estándar `__table__: ClassVar[Table]`, compartiendo cada `Column` con el `Field` de SQLModel. Se aplica también a DeliveryRow/ReturnRow. Se descarta cambiar `.directive` por `declared_attr` con callback que devuelve `str`, porque ese constructor tipado requiere un atributo mapeado y causaría otra incompatibilidad.
- Los 6 diagnósticos de resultados se atienden con `list[LockerAvailability]`. Los 2 restantes se atienden reutilizando el validador `location_alias`, eliminando la validación duplicada y aprovechando su import.
- Comparación independiente contra `1daa877`: DDL PostgreSQL, índices y defaults de las cinco tablas idénticos. Las pruebas de migración no detectan nuevas operaciones. Sin cambios de dependencias, configuración, migraciones, reglas de negocio ni supresiones.
- Suite completa tras las correcciones: **95 pruebas OK en 20.176 s**, sin omisiones, con el mismo comando y PostgreSQL aislado anteriores. `git diff --check` correcto.
- `sdd_reviewer` contrastó las 29 entradas con sus causas y los patrones repetidos, revisó las firmas instaladas de SQLModel/SQLAlchemy y cerró sin hallazgos pendientes. **No se ha ejecutado Pylance/Pyright y no se afirma un resultado de cero diagnósticos del editor**; la comprobación disponible es el informe aportado, la revisión de contratos y las pruebas de regresión.

## 5. Pyright y regla permanente de verificación

- [x] 5.1 Añadir Pyright al extra dev/uv.lock y pyrightconfig.json en raíz con backend incluido, producción strict, pruebas standard, Python 3.11, entorno/imports de backend y exclusiones acotadas de design.md. Documentar en README `uv run --extra dev pyright --project .. --warnings`, instalación y selección de intérprete; exigir su ejecución al completar cada spec en AGENTS.md y evidencia en sdd_builder/sdd_reviewer sin cambiar modelos/ajustes. Verificar que el comando carga esa configuración y analiza todo el alcance sin servicios, registrando sus diagnósticos iniciales.
- [x] 5.2 Corregir todos los diagnósticos del backend analizado, incluidos tests y migraciones no históricas, mediante anotaciones, genéricos, protocolos y narrowing veraces; no rebajar reglas ni ocultar problemas con Any/exclusiones. Ejecutar Pyright hasta obtener cero errores y advertencias, más las pruebas de comportamiento afectadas; mantener contratos, DDL y 0001–0003 intactos.
- [x] 5.3 Ejecutar el comando final de Pyright, unitarias sin servicios e integración/suite completa con PostgreSQL real aislado; comprobar documentación/configuración y validar OpenSpec estrictamente. Obtener revisión independiente sdd_reviewer, resolver hallazgos y repetir verificaciones afectadas; registrar resultados actuales separados de la evidencia histórica antes de marcar completa esta ampliación.

### Evidencia actual de Pyright y regresión (2026-10-15)

- Diagnóstico inicial real de Pyright 1.1.414 con el alcance acordado: **195 errores y 1 advertencia en 41 archivos**. El resultado previo de pruebas no sustituía este análisis.
- `uv.lock` fija Pyright 1.1.414 y su dependencia nueva nodeenv 1.11.0, sin actualizar las demás dependencias. Configuración compartida, README, AGENTS.md e instrucciones de builder/reviewer completadas; modelos y ajustes de agentes intactos.
- Comando final desde `backend/`: `env -u TEST_DATABASE_URL UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev pyright --project .. --warnings`: **0 errores, 0 advertencias, 0 informaciones**, salida 0. Analiza producción strict y pruebas standard; incluye env.py y 0004. El comando del README es el mismo sin opciones propias de este entorno.
- Corregidos contratos, genéricos y opcionales, con validación explícita de fronteras Python y respuestas de proveedores. Conservados todos los métodos y escenarios de prueba, incluidos datos inválidos y concurrencia; sin suprimir reglas ni añadir Any para esconder diagnósticos.
- Unitarias sin `TEST_DATABASE_URL`: `env -u TEST_DATABASE_URL UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev python -m unittest discover -s tests/unit -t . -v`: **52 pruebas OK en 2.811 s**. TestClient/AnyIO requirió sockets habilitados en el sandbox.
- Suite completa: `TEST_DATABASE_URL=… UV_CACHE_DIR=/tmp/uv-cache uv run --offline --extra dev python -m unittest discover -s tests -t . -v -f`: **95 pruebas OK en 20.610 s**, sin omisiones; 52 unitarias y 43 de integración. PostgreSQL 17, base dedicada `hexagonal_test`, esquemas aislados; siete comprobaciones de metadata sin nuevas operaciones de migración. Migraciones históricas y DDL conservados.
- Integración sin configurar `TEST_DATABASE_URL` continúa fallando explícitamente antes de los casos con `TEST_DATABASE_URL is required for PostgreSQL integration tests`, salida 5.
- `sdd_reviewer` ejecutó independientemente el comando final de Pyright y confirmó **0 errores y 0 advertencias**; revisión cerrada sin hallazgos pendientes tras revisar configuración, validaciones runtime, casos negativos y evidencia de pruebas.
- `openspec validate add-locker-location-and-shipping-comparison --strict` y `git diff --check` correctos. Implementación completada; sincronización y archivado permanecen fuera de esta petición.
