# Design

## Context

Ver `proposal.md` para la motivación. Delivery/Return son entidades Python inmutables de custodia física, no solicitudes de envío. Sus servicios generan la recepción y cada repositorio confirma `save` o `save_exit` por separado. Las salidas usan UPDATE condicionado al estado pendiente. No hay ubicación, capacidad ni asignación actuales. Los tests SQLite cubren persistencia secuencial; `test_postgresql.py` comprueba concurrencia con conexiones independientes y requiere `TEST_DATABASE_URL`.

## Goals / Non-Goals

**Goals:** conservar el núcleo independiente de HTTP/SQL, compartir capacidad física entre tipos de paquete, evitar recepciones parciales y liberar únicamente la asignación ganadora. Hacer explícita la compatibilidad aditiva del contrato.

**Non-Goals:** reservas o TTL, transferencias entre lockers, reasignar paquetes existentes, geocodificación, precios, RabbitMQ, outbox, autorización y control físico de puertas. La posterior cotización será una solicitud independiente con origen/destino/peso/dimensiones; este cambio solo aporta una consulta de capacidad que no garantiza espacio futuro.

## Decisions

### 1. Celdas identificables y dimensiones físicas

`Locker(id, location_id, active)` contiene celdas identificables. `location_id` es texto estable no vacío, recortado y sensible a mayúsculas, sin catálogo externo ni geobúsqueda. Varios lockers pueden compartir ubicación. La ubicación queda inmutable en esta fase.

`Compartment(id, locker_id, dimensions, enabled, retired)` tiene medidas útiles positivas enteras en milímetros (`width_mm`, `height_mm`, `depth_mm`), booleanos estrictos para habilitación y UUID generado. Las medidas usan el rango entero positivo 1..2147483647, coherente con INTEGER de persistencia. Las cantidades son enteros positivos y cada petición de creación de locker o adición de lotes admite como máximo 1000 celdas nuevas en total. Validar la suma antes de materializar celdas o escribir y devolver 422 si excede 1000; este límite es por petición, no por capacidad total del locker, que puede crecer en sucesivos lotes. No se admiten bool, floats ni strings como medidas/cantidades JSON. Retirar es irreversible en esta fase y exige celda libre. Se conserva su fila por las referencias históricas. No existe endpoint que marque arbitrariamente una celda ocupada/libre.

`Dimensions` admite rotaciones ortogonales: ordenar las tres medidas de ambos objetos y comparar componente a componente, incluyendo igualdad. No se consideran diagonales ni espacio de maniobra. Seleccionar entre libres compatibles por volumen ascendente y UUID ascendente como desempate. El volumen se calcula con enteros sin overflow; evitar multiplicar INTEGER de PostgreSQL sin promoción a NUMERIC (BIGINT tampoco cubre el producto máximo). S/M/L no es un catálogo obligatorio.

La cantidad se materializa creando celdas, y se calcula contando las no retiradas; no se persiste un contador de disponibilidad. La ocupación activa se deriva exclusivamente de las asignaciones no liberadas. Deshabilitar no equivale a retirar: mantiene la celda configurada pero no ofertable.

### 2. Contrato HTTP explícito

Las medidas usan siempre `{width_mm, height_mm, depth_mm}`. Entradas desconocidas o mal tipadas, IDs mal formados y texto vacío dan 422. IDs bien formados inexistentes dan 404. No hay eliminación de lockers.

| Endpoint | Entrada y resultado |
| --- | --- |
| `POST /lockers` | `{location_id, active?: true, compartments: [{quantity, dimensions, enabled?: true}]}`; lista de lotes no vacía y cantidades positivas. 201 devuelve configuración completa con IDs generados. Todo el lote se confirma o revierte junto. |
| `GET /lockers?location_id=...` | Filtro exacto opcional; 200 lista ordenada por UUID. Cada locker incluye `id`, `location_id`, `active`, `compartment_count` y `compartments`. |
| `GET /lockers/{id}` | 200 misma configuración, 404 desconocido. Cada celda no retirada incluye `id`, `dimensions`, `enabled`, `occupied`; no expone identidad/contacto del ocupante. `compartment_count` incluye habilitadas y deshabilitadas no retiradas. |
| `PATCH /lockers/{id}` | Solo `{active: boolean}`; 200 configuración. Inactivar impide nuevas asignaciones, pero permite todas las salidas. |
| `POST /lockers/{id}/compartments` | `{compartments: [{quantity, dimensions, enabled?: true}]}`; 201 configuración completa tras añadir lotes atómicamente. |
| `PATCH /lockers/{id}/compartments/{cell_id}` | Objeto no vacío con `dimensions` y/o `enabled`; 200 celda actualizada. Si está ocupada, 409 sin cambio, incluso para deshabilitar. |
| `DELETE /lockers/{id}/compartments/{cell_id}` | 204 retira lógicamente una celda libre; 409 ocupada; 404 desconocida, ajena al locker o ya retirada. |
| `GET /lockers/availability?location_id=...&width_mm=...&height_mm=...&depth_mm=...` | 200 snapshot descrito abajo; no escribe ni reserva. Registrar ruta estática antes de `/{id}`. |

Snapshot: `{location_id, parcel_dimensions, checked_at, reason, lockers: [...]}`. Por locker: `{locker_id, active, compatible_count, available_count, reason}`. `compatible_count` cuenta celdas habilitadas no retiradas donde cabe el paquete, ocupadas o libres; `available_count` cuenta sus libres si el locker está activo, de lo contrario cero. Razones por locker: `LOCKER_INACTIVE`, `NO_COMPATIBLE_CELL`, `FULL`, `AVAILABLE`, en ese orden de evaluación. Razón global: `NO_LOCKER` si lista vacía; `AVAILABLE` si alguno disponible; `FULL` si algún locker activo tiene compatibles ocupadas y ninguno disponible; `NO_COMPATIBLE_CELL` si hay activos sin compatibles; `LOCKER_INACTIVE` si todos inactivos. Conteos y estados pertenecen a una única lectura coherente; `checked_at` UTC es el instante de consulta, no una vigencia contractual.

Se mantienen los siete endpoints Delivery/Return. Sus dos POST de recepción aceptan opcionalmente `locker_id` y `parcel_dimensions`: ambos no nulos o ambos omitidos/null. Una sola parte da 422; `compartment_id` sigue siendo entrada prohibida. Sin ambos se conserva la recepción actual. Con ambos se devuelve 201 solo después de asignar; locker desconocido da 404, inactivo da 409 `LOCKER_INACTIVE`, sin celda compatible 409 `NO_COMPATIBLE_CELL`, sin hueco 409 `FULL`. Los errores de capacidad usan `detail: {code, message}`; errores anteriores mantienen su forma actual.

Todas las representaciones de paquetes añaden `locker_id`, `compartment_id`, `parcel_dimensions`, presentes con null para registros sin asignación. Si hay asignación se conservan esos valores incluso tras salida, cambio posterior de medidas de la celda o retiro de la celda. Las dimensiones son las del paquete recibido, no las actuales del compartimento. El estado del paquete sigue indicando custodia; no se añaden estados de envío o reserva.

### 3. Modelo relacional compartido

Nueva revisión crea tres tablas sin modificar columnas actuales:

- `lockers`: UUID PK, location_id requerido e indexado, active requerido.
- `locker_compartments`: UUID PK, locker_id FK RESTRICT, tres medidas positivas, enabled y retired requeridos. CHECK impide retired AND enabled. Índice por locker_id. El locker de una celda nunca cambia.
- `locker_assignments`: UUID PK, compartment_id FK RESTRICT, delivery_id FK nullable, return_id FK nullable, medidas positivas del paquete, assigned_at UTC, released_at UTC nullable. CHECK exige exactamente una de delivery_id/return_id y released_at >= assigned_at. Unicidad independiente de delivery_id y return_id impide más de una asignación histórica a la mismo paquete. Índice único parcial sobre compartment_id WHERE released_at IS NULL impide dos ocupaciones activas entre ambos tipos de paquete. Mantener las restricciones en Alembic y metadata SQLModel.

No se usa un identificador polimórfico sin FK ni dos índices de capacidad separados por tabla de paquetes. Los UUID de Delivery y Return pueden coincidir sin confundir su identidad. `assigned_at` coincide con received_at y `released_at` con la salida. La pertenencia locker/celda se reconstruye por FK, sin duplicar locker_id en la asignación. La asignación histórica permanece tras liberación.

### 4. Puertos y atomicidad sin infraestructura genérica

Añadir valores puros de dimensiones/asignación y modelos Locker/Compartment en `domain/lockers.py`; entidades Delivery/Return admiten datos opcionales de asignación coherentes (los tres campos juntos o todos null). No fabricar una entidad parcialmente asignada.

Conservar `save(entity) -> None` para la vía sin locker y fixtures existentes, rechazando explícitamente su uso para nuevas entidades ya asignadas. Ampliar cada puerto con `receive_in_locker(entity_without_assignment, locker_id, dimensions) -> entity_with_assignment`. El servicio construye una entidad válida sin asignación, invoca esta operación cuando procede y devuelve su resultado; el adaptador devuelve una nueva entidad inmutable completa tras commit. La operación incluye inserción de paquete y asignación. No invocar primero `save` y después otro repositorio con una transacción distinta.

`save_exit(terminal_entity) -> bool` conserva su contrato pero confirma transición y liberación juntas. Obtiene de persistencia la asignación de ese paquete, sin confiar en un compartment_id arbitrario del llamante. Tras el UPDATE condicionado ganador, actualiza únicamente su asignación activa, nunca la ocupación actual localizada solo por cell_id. Para un paquete asignado pendiente, no encontrar exactamente su ocupación activa es inconsistencia: rollback, no éxito silencioso. Un contendiente perdedor no cambia asignaciones. Las lecturas reconstruyen la asignación histórica mediante joins, evitando consultas por paquete.

Añadir un puerto LockerRepository para configuración y snapshots y LockerService para validar/configurar/consultar. Usar un helper interno del adaptador de base de datos para bloqueo y elección compartidos por ambos tipos; ninguna clase de SQLAlchemy cruza el puerto. `main.py` compone el servicio y router nuevos usando la fábrica de sesiones existente.

### 5. Concurrencia deliberadamente simple

PostgreSQL READ COMMITTED: toda recepción, configuración de celdas, activación/inactivación y salida con asignación adquiere primero `SELECT ... FOR UPDATE` de su Locker, antes de bloquear/actualizar celdas, asignaciones o paquetes. Ninguna operación afecta dos lockers. Obtener primero un identificador de asignación mediante lectura sin bloqueo es seguro porque no se reasigna un paquete ni se mueve una celda. Tras adquirir el lock, volver a evaluar estado y ocupación con una lectura nueva; no reutilizar un snapshot anterior a la espera.

Este orden serializa operaciones de un locker, mantiene paralelismo entre lockers y evita carreras con reconfiguración. La última celda compartida produce un 201 y un 409 FULL después del commit ganador; si el primero revierte, el segundo puede asignarla. No usar SKIP LOCKED para inferir que el locker está lleno. El índice único parcial es protección adicional, no sustituto del protocolo. Errores de infraestructura/lock timeout no deben convertirse en FULL.

En salida: locker lock, CAS de paquete, liberación por FK de el paquete/asignación, commit. Recoger dos veces A después de que B ocupe su antigua celda devuelve 409 y deja B intacto. Un locker inactivo sigue permitiendo liberar. En configuración: mismo lock, comprobar ausencia de asignación activa antes de cambiar/retirar celda; si la recepción gana, configuración devuelve 409, y si configuración gana, recepción usa la nueva configuración o devuelve conflicto sin filas huérfanas.

SQLite se usa secuencialmente con FKs habilitadas para validar restricciones y rollback; no se afirma equivalencia de sus locks con PostgreSQL. Las lecturas de disponibilidad agregan en una sola sentencia o snapshot de lectura equivalente, sin bloquear ni consumir capacidad.

### 6. Archivos afectados y verificación

Nuevos: `backend/domain/lockers.py`, `backend/application/locker_use_cases.py`, `backend/adapters/http/locker_schemas.py`, `backend/adapters/http/locker_routes.py`, `backend/adapters/database/sqlmodel_lockers.py`, `backend/adapters/database/migrations/versions/0003_lockers_and_custody.py`, `backend/tests/test_lockers.py`, `backend/tests/test_locker_http.py`, `backend/tests/test_locker_repositories.py`, `backend/tests/test_locker_postgresql.py`.

Modificar: `backend/domain/models.py`, `backend/domain/ports.py`, `backend/application/use_cases.py`, `backend/adapters/http/schemas.py`, `backend/adapters/http/routes.py`, `backend/adapters/database/sqlmodel_repositories.py`, `backend/adapters/database/connection.py` (FKs SQLite si necesario), `backend/adapters/database/migrations/env.py` (registro metadata), `backend/main.py`, `backend/tests/test_domain.py`, `backend/tests/test_application.py`, `backend/tests/test_http.py`, `backend/tests/test_repositories.py`, `backend/tests/test_main.py`, `backend/tests/test_migrations.py`, `backend/tests/test_postgresql.py`, `README.md`.

Pruebas: dominio de compatibilidad/rotación/tipos; HTTP de validación, razones y campos adicionales; SQLite de restricciones/FKs/joins/rollback; PostgreSQL real con conexiones y eventos de sincronización para competir por última celda, configuración y salida. Inyectar fallo antes del commit en recepción y salida y verificar que ambas mitades revierten. Probar secuencia A-sale/B-ocupa/A-repite para Delivery collect, return-to-carrier y Return hand-over. No sustituir concurrencia real por mocks de repositorios ni sleeps arbitrarios.

Actualizar expectativas head 0002 a 0003 y snapshots de migración para incluir las tres tablas nuevas, índices, restricciones y revisión. Mantener pruebas específicas de 0001 poblado rechazado por 0002. Verificar suites con `uv run --extra dev python -m unittest discover -s tests -v` desde backend, y la misma suite con TEST_DATABASE_URL PostgreSQL configurada; reportar omisiones si el entorno no permite PG. No hay nuevos paquetes ni modificación de Compose.

## Risks / Trade-offs

- [Respuesta aditiva] → documentar tres campos nullable nuevos y ajustar tests que comparan claves; las solicitudes existentes siguen siendo válidas.
- [Cuello de botella por locker] → aceptable para esta primera capacidad; medir antes de sustituir por bloqueo fino.
- [Lectura de disponibilidad envejece] → no reservar y revalidar dentro de la transacción de recepción.
- [Recepciones históricas o sin locker] → no consumen capacidad; mostrar claramente asignación null, sin fingir que fueron almacenadas físicamente.
- [Retiro lógico acumula historial] → conserva integridad y trazabilidad; no añadir borrado administrativo en este cambio.
- [SQLite no prueba PostgreSQL] → exigir evidencia de pruebas PG para concurrencia y migración antes de declarar implementación verificada.

## Migration Plan

1. Backup y comprobación de revisión actual según README. Mantener intactas 0001/0002.
2. Añadir 0003 creando tablas/constraints/índices; permitir upgrade desde 0002 con Delivery/Return pendientes o finalizadas, conservando todas sus columnas y valores. Sin backfill ni lockers ficticios.
3. Ejecutar migración antes de arrancar la versión nueva; configurar lockers mediante API. API startup sigue sin DDL.
4. Downgrade 0003 -> 0002: bajo locks de las tablas nuevas, rechazar antes de DDL si cualquiera contiene filas, incluso celdas retiradas/asignaciones liberadas. Si están vacías, eliminarlas y conservar tablas de paquetes actuales aunque estén pobladas. Para bajar de 0002 a 0001, sigue vigente el bloqueo de 0002 con paquetes existentes.
5. Rollback de aplicación puede conservar esquema 0003; no revertir esquema borrando datos. Las operaciones sin soporte de lockers no deben procesar salidas de paquetes asignados durante un rollback: detener escrituras o mantener la versión capaz de liberar hasta resolverlo.
