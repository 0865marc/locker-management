# Arquitectura hexagonal con FastAPI

PoC de un **punto de entrega y recogida de paquetes**. **Delivery** registra un
paquete recibido del transportista para que lo recoja el destinatario; **Return**
registra uno depositado por el cliente para que lo retire el transportista.
Cada entidad representa un paquete y tiene un UUID independiente. La persistencia
usa **SQLModel asíncrono sobre PostgreSQL** y **Alembic** gestiona las migraciones.

Ambas entidades contienen `tracking_number`, `carrier_code` y `received_at` UTC
asignado por el sistema. Delivery añade `recipient_name` obligatorio, los campos
opcionales `recipient_phone` y `pickup_deadline_at`, `status`, `collected_at` y
`returned_to_carrier_at`.
Return añade `sender_name` opcional, `status` y `handed_over_at`. Los opcionales
omitidos se representan como `null`. Los textos se recortan; los obligatorios no
pueden estar vacíos y los opcionales blancos se normalizan a `null`.

Delivery empieza en `AWAITING_PICKUP` y permite una única salida: `COLLECTED` o
`RETURNED_TO_CARRIER`. Return empieza en `AWAITING_CARRIER` y pasa una sola vez a
`HANDED_OVER`. Cada salida registra una fecha UTC del sistema, posterior o igual
a la recepción. El plazo de recogida admite una fecha con zona y es informativo:
un paquete vencido sigue pendiente y se puede recoger. Seguimiento y transportista
no son claves únicas; el UUID identifica el registro.

## Arrancar

Necesitas Docker con Docker Compose. Ejecuta Compose desde la raíz del repositorio:

```bash
docker compose up --build
```

Compose espera a que PostgreSQL esté preparado, ejecuta `alembic upgrade head`
en el servicio `migrate` y arranca la API cuando la migración termina correctamente.
Si conservas una base de datos de la versión anterior, consulta primero
[el procedimiento de migración segura](#base-de-datos-de-la-versión-anterior).

Abre [la documentación interactiva](http://127.0.0.1:8000/docs), o prueba:

```bash
curl -X POST http://127.0.0.1:8000/deliveries \
  -H 'Content-Type: application/json' \
  -d '{"tracking_number":"PKG-42","carrier_code":"carrier-a","recipient_name":"Ana García","recipient_phone":"600123456","pickup_deadline_at":"2026-10-20T18:00:00+02:00"}'

curl http://127.0.0.1:8000/deliveries

# Sustituye DELIVERY_ID por el UUID de la respuesta de creación.
curl -X POST http://127.0.0.1:8000/deliveries/DELIVERY_ID/collect
# Sustituye OTHER_DELIVERY_ID por el UUID de otro paquete pendiente.
curl -X POST http://127.0.0.1:8000/deliveries/OTHER_DELIVERY_ID/return-to-carrier \
  -H 'Content-Type: application/json' -d '{}'

curl -X POST http://127.0.0.1:8000/returns \
  -H 'Content-Type: application/json' \
  -d '{"tracking_number":"RET-42","carrier_code":"carrier-a","sender_name":"Luis Pérez"}'

curl http://127.0.0.1:8000/returns

# Sustituye RETURN_ID por el UUID de la respuesta de creación.
curl -X POST http://127.0.0.1:8000/returns/RETURN_ID/hand-over
```

Crear devuelve `201`; listar y registrar una salida devuelven `200` con la
representación completa. Las fechas se serializan en UTC, por ejemplo
`2026-10-20T16:00:00Z` para el plazo anterior. El sistema genera UUID, recepción,
estado y fechas de salida; el cliente solo indica los datos de recepción y el
plazo opcional. Recoger devuelve `COLLECTED`, una fecha `collected_at` y
`returned_to_carrier_at: null`; devolver al transportista conserva
`collected_at: null`. Una Return entregada devuelve `HANDED_OVER` y su fecha.

Un UUID desconocido devuelve `404`; una salida repetida, incompatible o con
cronología inválida devuelve `409` sin modificar el paquete. Un UUID mal formado,
campos retirados, desconocidos o de sistema, tipos incorrectos, textos obligatorios
blancos o plazos sin zona devuelven `422`. Las acciones solo aceptan ausencia de
cuerpo o `{}`; incluso `null` se rechaza. Los datos persisten en el volumen
`postgres_data` al ejecutar `docker compose down`.

## Lockers: configuración y capacidad física

Un locker pertenece a una ubicación estable `location_id`, recortada y sensible a
mayúsculas: `MAD-01` y `mad-01` son ubicaciones diferentes. La búsqueda es exacta;
no hay geodistancia ni catálogo externo y varios lockers pueden compartir ubicación.
La ubicación del locker no cambia. Cada celda tiene UUID propio y medidas útiles
`width_mm`, `height_mm`, `depth_mm`, en milímetros. Se permiten rotaciones ortogonales:
se ordenan ambos tríos y se compara eje a eje, admitiendo igualdad. No se consideran
diagonales ni espacio de maniobra. Se elige la celda libre compatible de menor
volumen, con UUID ascendente como desempate.

Medidas y cantidades son enteros JSON positivos; no aceptan booleanos, decimales
ni cadenas. Las medidas admiten de 1 a 2147483647. Cada petición de creación o
adición admite como máximo **1000 celdas nuevas en total**, sumando sus lotes;
el límite se valida antes de crear celdas. El locker puede superar 1000 mediante
peticiones sucesivas. Los indicadores `active` y `enabled` son booleanos estrictos.

La capacidad se deriva de las celdas y sus asignaciones activas, compartidas por
Delivery y Return. Las celdas deshabilitadas siguen configuradas, pero no se ofrecen;
las retiradas dejan de aparecer y conservan su fila para el historial. Solo se
pueden redimensionar, deshabilitar o retirar celdas libres. Una celda ocupada da
`409` sin cambios. El retiro es irreversible y repetirlo da `404`. Inactivar un
locker impide recepciones nuevas, pero permite todas las salidas.

Este recorrido usa `curl` y `jq`, desde cualquier terminal con la API arrancada:

```bash
API=http://127.0.0.1:8000
DIMENSIONS='{"width_mm":100,"height_mm":200,"depth_mm":300}'

LOCKER=$(curl --fail-with-body -sS -X POST "$API/lockers" \
  -H 'Content-Type: application/json' \
  -d '{"location_id":"MAD-01","compartments":[{"quantity":1,"dimensions":{"width_mm":100,"height_mm":200,"depth_mm":300}}]}')
LOCKER_ID=$(jq -r '.id' <<< "$LOCKER")
CELL_ID=$(jq -r '.compartments[0].id' <<< "$LOCKER")

curl --fail-with-body -sS "$API/lockers?location_id=MAD-01"
curl --fail-with-body -sS "$API/lockers/$LOCKER_ID"
curl --fail-with-body -sS "$API/lockers/availability?location_id=MAD-01&width_mm=300&height_mm=100&depth_mm=200"

DELIVERY=$(curl --fail-with-body -sS -X POST "$API/deliveries" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg locker "$LOCKER_ID" --argjson dimensions "$DIMENSIONS" \
    '{tracking_number:"D-LOCKER",carrier_code:"carrier-a",recipient_name:"Ana",locker_id:$locker,parcel_dimensions:$dimensions}')")
DELIVERY_ID=$(jq -r '.id' <<< "$DELIVERY")
# La única celda está ocupada: reason FULL y available_count 0.
curl --fail-with-body -sS "$API/lockers/availability?location_id=MAD-01&width_mm=100&height_mm=200&depth_mm=300"
curl --fail-with-body -sS -X POST "$API/deliveries/$DELIVERY_ID/collect"

# Una devolución reutiliza la misma celda, porque comparte capacidad con Delivery.
RETURN=$(curl --fail-with-body -sS -X POST "$API/returns" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n --arg locker "$LOCKER_ID" --argjson dimensions "$DIMENSIONS" \
    '{tracking_number:"R-LOCKER",carrier_code:"carrier-a",locker_id:$locker,parcel_dimensions:$dimensions}')")
RETURN_ID=$(jq -r '.id' <<< "$RETURN")
# Incluso inactivo, el locker permite liberar su devolución.
curl --fail-with-body -sS -X PATCH "$API/lockers/$LOCKER_ID" \
  -H 'Content-Type: application/json' -d '{"active":false}'
curl --fail-with-body -sS -X POST "$API/returns/$RETURN_ID/hand-over"
curl --fail-with-body -sS -X PATCH "$API/lockers/$LOCKER_ID" \
  -H 'Content-Type: application/json' -d '{"active":true}'

# Cambiar una celda libre, añadir un lote y retirar la celda original.
curl --fail-with-body -sS -X PATCH "$API/lockers/$LOCKER_ID/compartments/$CELL_ID" \
  -H 'Content-Type: application/json' \
  -d '{"dimensions":{"width_mm":150,"height_mm":250,"depth_mm":350},"enabled":false}'
curl --fail-with-body -sS -X POST "$API/lockers/$LOCKER_ID/compartments" \
  -H 'Content-Type: application/json' \
  -d '{"compartments":[{"quantity":2,"dimensions":{"width_mm":100,"height_mm":200,"depth_mm":300}}]}'
curl --fail-with-body -sS -X DELETE "$API/lockers/$LOCKER_ID/compartments/$CELL_ID"
```

La disponibilidad devuelve `location_id`, `parcel_dimensions`, `checked_at` UTC,
`reason` y una lista `lockers`. Cada elemento contiene `locker_id`, `active`,
`compatible_count`, `available_count` y `reason`. Las compatibles son celdas
habilitadas no retiradas, incluidas las ocupadas; las disponibles son sus libres
si el locker está activo. La fotografía es coherente, **no reserva espacio** y no
promete capacidad futura. Las razones son `NO_LOCKER`, `LOCKER_INACTIVE`,
`NO_COMPATIBLE_CELL`, `FULL` y `AVAILABLE`. La recepción vuelve a comprobar bajo
bloqueo y confirma paquete y ocupación en una sola transacción. La salida confirma
estado y liberación de su propia asignación en otra transacción indivisible.

Las dos recepciones aceptan `locker_id` y `parcel_dimensions` juntos, ambos no
nulos, o ambos omitidos/null para seguir recibiendo sin locker. Una pareja parcial
o un `compartment_id` suministrado devuelve `422`; locker desconocido devuelve
`404`. Un conflicto de capacidad devuelve `409` con
`detail: {"code":"FULL","message":"..."}` (también `LOCKER_INACTIVE` o
`NO_COMPATIBLE_CELL`) sin guardar el paquete. No se puede ocupar una celda por ID
ni marcarla arbitrariamente como libre.

Todas las respuestas de paquetes añaden `locker_id`, `compartment_id` y
`parcel_dimensions`; son `null` para recepciones sin locker y filas históricas.
Los clientes que validen respuestas estrictamente deben admitir estos campos.
Una salida conserva la asignación histórica y las dimensiones del paquete,
incluso si la celda se redimensiona o retira después. Repetir una salida antigua
tras reocupar su celda da `409` y conserva intacto al nuevo ocupante.

## Organización

```text
hexagonal_architecture/
├── backend/
│   ├── main.py
│   ├── domain/
│   │   ├── models.py
│   │   ├── lockers.py
│   │   └── ports.py
│   ├── application/
│   │   ├── locker_use_cases.py
│   │   └── use_cases.py
│   ├── adapters/
│   │   ├── http/
│   │   │   ├── routes.py
│   │   │   ├── schemas.py
│   │   │   ├── locker_routes.py
│   │   │   └── locker_schemas.py
│   │   └── database/
│   │       ├── connection.py
│   │       ├── sqlmodel_repositories.py
│   │       ├── sqlmodel_lockers.py
│   │       └── migrations/
│   │           ├── env.py
│   │           ├── script.py.mako
│   │           └── versions/
│   │               ├── 0001_create_delivery_and_return.py
│   │               ├── 0002_parcel_custody.py
│   │               └── 0003_lockers_and_custody.py
│   ├── tests/
│   │   ├── test_domain.py
│   │   ├── test_application.py
│   │   ├── test_http.py
│   │   ├── test_repositories.py
│   │   ├── test_migrations.py
│   │   ├── test_postgresql.py
│   │   ├── test_lockers.py
│   │   ├── test_locker_http.py
│   │   ├── test_locker_repositories.py
│   │   ├── test_locker_postgresql.py
│   │   └── test_main.py
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── .dockerignore
│   └── pyproject.toml
├── compose.yaml
└── README.md
```

Se omiten los archivos `__init__.py`. La organización prioriza las capas:
Delivery y Return comparten los archivos de cada responsabilidad. La conexión,
los repositorios y las migraciones se agrupan en `backend/adapters/database/`; las rutas
y los modelos HTTP, en `backend/adapters/http/`. Ambos adaptadores son externos al núcleo,
pero se ejecutan en el mismo proceso: no son microservicios.

Las rutas siguientes son relativas a la raíz del repositorio. Lee el código en este orden:

| Archivo | Responsabilidad |
| --- | --- |
| `backend/domain/models.py` | Entidades `Delivery` y `Return` y sus validaciones. Solo Python. |
| `backend/domain/lockers.py` | Dimensiones, celdas, lockers y reglas físicas, sin infraestructura. |
| `backend/domain/ports.py` | Puertos de salida `DeliveryRepository`, `ReturnRepository` y `LockerRepository`: lo que la aplicación necesita de la persistencia. |
| `backend/application/use_cases.py` | Implementa los casos de uso; sus métodos públicos `create`, `list_all` y las operaciones de salida actúan como puertos de entrada. Obtiene fechas de un reloj UTC inyectable. Usa los puertos de salida sin conocer HTTP ni la base de datos. |
| `backend/application/locker_use_cases.py` | Casos de uso de configuración y disponibilidad de lockers. |
| `backend/adapters/http/locker_routes.py` y `locker_schemas.py` | Contratos HTTP de lockers y traducción de errores. |
| `backend/adapters/database/sqlmodel_lockers.py` | Persistencia compartida de configuración y asignaciones, con bloqueo por locker. |
| `backend/adapters/http/routes.py` | Recibe `DeliveryService` y `ReturnService`, define las rutas y traduce errores del dominio a respuestas HTTP. |
| `backend/adapters/http/schemas.py` | Modelos Pydantic para los cuerpos y respuestas HTTP. |
| `backend/adapters/database/sqlmodel_repositories.py` | Modelos de persistencia y repositorios SQLModel asíncronos. Traducen entre filas y entidades del dominio. |
| `backend/adapters/database/connection.py` | Crea el motor y la fábrica de sesiones compartidos. |
| `backend/main.py` | Punto de composición: conecta repositorios, servicios y router; crea la aplicación y gestiona su ciclo de vida. |
| `backend/adapters/database/migrations/env.py` | Conecta Alembic con la base de datos y con `SQLModel.metadata`. |
| `backend/adapters/database/migrations/versions/` | Historial de cambios del esquema, independiente del arranque de la API. |

El recorrido de una petición es **HTTP → caso de uso → repositorio → PostgreSQL**.
Los métodos públicos de `DeliveryService` y `ReturnService` son los puertos de
entrada: expresan las operaciones disponibles sin una interfaz adicional.
El adaptador HTTP depende directamente de estos servicios y de las entidades
del dominio; los servicios siguen sin conocer FastAPI ni SQLModel.

Los puertos de salida de `backend/domain/ports.py` sí usan `Protocol`: permiten a los casos
de uso trabajar con repositorios sin depender de su implementación concreta.

### Componer los servicios

`create_app()` crea una vez por aplicación `DeliveryService`, `ReturnService` y `LockerService`,
y conserva sus referencias en `app.state.delivery_service`,
`app.state.return_service` y `app.state.locker_service`. Inyecta las instancias de paquetes en
`create_router(delivery, returns)` y el servicio de lockers en su router. Las rutas
reutilizan los servicios recibidos, sin instanciarlos por petición ni buscarlos
en `app.state`. Todos los endpoints usan SQLModel a través de los casos de uso:

| Endpoint | Repositorio |
| --- | --- |
| `POST /deliveries` | `SqlModelDeliveryRepository` |
| `GET /deliveries` | `SqlModelDeliveryRepository` |
| `POST /deliveries/{id}/collect` | `SqlModelDeliveryRepository` |
| `POST /deliveries/{id}/return-to-carrier` | `SqlModelDeliveryRepository` |
| `POST /returns` | `SqlModelReturnRepository` |
| `GET /returns` | `SqlModelReturnRepository` |
| `POST /returns/{id}/hand-over` | `SqlModelReturnRepository` |
| `POST /lockers` | `SqlModelLockerRepository` |
| `GET /lockers` | `SqlModelLockerRepository` |
| `GET /lockers/availability` | `SqlModelLockerRepository` |
| `GET /lockers/{id}` | `SqlModelLockerRepository` |
| `PATCH /lockers/{id}` | `SqlModelLockerRepository` |
| `POST /lockers/{id}/compartments` | `SqlModelLockerRepository` |
| `PATCH /lockers/{id}/compartments/{cell_id}` | `SqlModelLockerRepository` |
| `DELETE /lockers/{id}/compartments/{cell_id}` | `SqlModelLockerRepository` |

Los servicios de paquetes permiten crear, listar y registrar salidas;
`LockerService` configura lockers y consulta disponibilidad. No se separan por lectura y escritura. Sustituir un repositorio por otro que cumpla su puerto no requiere
cambiar el dominio ni los casos de uso.

No es obligatorio construir los servicios en `lifespan`: aquí solo conservan
repositorios con una fábrica de sesiones y no necesitan inicialización asíncrona.
`lifespan` libera el motor al cerrar; Alembic crea y modifica las tablas. Crear estos
servicios ligeros por petición también sería válido, pero aquí basta con
reutilizarlos; cada operación del repositorio abre su propia sesión.

SQLModel se apoya en SQLAlchemy. Sus modelos de persistencia permanecen en el
adaptador; los puertos reciben y devuelven las entidades de `backend/domain/models.py`.
Se ha eliminado el adaptador SQLAlchemy independiente, pero SQLAlchemy sigue
proporcionando el motor, las sesiones asíncronas y los tipos de columnas.

### Qué se comparte y qué se separa

Los tres repositorios reciben la misma fábrica SQLAlchemy `async_sessionmaker`.
La fábrica crea sesiones SQLModel y las consultas usan `AsyncSession.exec()`. Cada operación
abre su propia sesión; guardar abre una transacción con `sessions.begin()`, que
confirma al terminar o revierte si falla. **No hay una `AsyncSession` global**.
Delivery y Return mantienen sus propias tablas y consultas; comparten `locker_assignments` para la capacidad física.

Cada salida consulta el paquete, valida la transición inmutable en el dominio y
ejecuta un `UPDATE` condicionado al estado pendiente. La transacción confirma
antes de responder; ante concurrencia solo una salida puede ganar y la otra
recibe `409`, sin sobrescribir estado ni fecha. Las restricciones de tabla
refuerzan la coherencia entre estado y fechas. Las operaciones asignadas adquieren primero el bloqueo del locker y releen capacidad antes de escribir. El adaptador coordina las escrituras de paquete y asignación dentro de una misma transacción, sin exponer sesiones al dominio ni a los casos de uso.

Para cambiar PostgreSQL por MySQL se cambiarían el controlador y la configuración
compartida, y se revisaría la compatibilidad de los adaptadores. El dominio y
los casos de uso conservarían sus contratos: ese es el beneficio de la separación,
aunque una migración pueda afectar a varios archivos de infraestructura.

## Migraciones

Hay **un único historial para toda la base de datos**, con `deliveries`, `returns`,
`lockers`, `locker_compartments` y `locker_assignments`. La revisión inicial `0001` conserva las columnas legacy `address` y
`reason`; `0002` incorpora el modelo de custodia y el head actual es `0003`, que añade lockers. `upgrade 0001`
prepara el esquema histórico y `upgrade head` prepara el contrato de la API actual. `SQLModel.metadata` es la fuente del
esquema para comparar modelos y base de datos; `backend/adapters/database/migrations/env.py`
importa los modelos del adaptador para registrar sus tablas. El dominio no participa
en las migraciones. `backend/alembic.ini` apunta a esta carpeta
mediante `script_location = %(here)s/adapters/database/migrations`.

Para desarrollar desde tu equipo, arranca PostgreSQL desde la raíz:

```bash
# Desde la raíz del repositorio.
docker compose up -d --wait db
```

Instala las dependencias y ejecuta Alembic desde `backend/`:

```bash
# Desde la raíz del repositorio.
cd backend
uv sync --extra dev
uv run alembic upgrade head
```

La API y Alembic usan `DATABASE_URL`. Si no se define, ambos conectan a
`postgresql+asyncpg://hexagonal:hexagonal@localhost:5432/hexagonal`.

Después de modificar los modelos de persistencia, desde `backend/`:

```bash
# Directorio de trabajo: backend/
uv run alembic revision --autogenerate -m "describe el cambio"
# Revisa y ajusta el archivo generado en adapters/database/migrations/versions/.
uv run alembic upgrade head
```

La autogeneración propone cambios; hay que revisar cada revisión antes de
aplicarla, especialmente los cambios de nombre y las transformaciones de datos.
Versiona las revisiones junto con el código. Véase la
[documentación de autogeneración de Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).

### Base de datos de la versión anterior

Antes de desplegar, haz una copia de seguridad y detén las escrituras. La
revisión `0002` bloquea ambas tablas y comprueba su contenido dentro de la
transacción PostgreSQL, antes de modificar columnas. Si cualquiera contiene
registros legacy, **rechaza el upgrade**: faltan datos reales de seguimiento,
transportista y recepción. El error identifica las tablas afectadas; filas,
esquema y revisión `0001` se conservan íntegros. Preserva esa base y prepara una
migración explícita con información real antes de continuar. No se generan datos
ficticios ni se borran tablas para superar el rechazo.

Si la base antigua proviene de `create_all()` y no tiene historial Alembic:

1. Haz una copia de seguridad y detén las escrituras.
2. Comprueba que coincide exactamente con
   `backend/adapters/database/migrations/versions/0001_create_delivery_and_return.py`,
   incluidos tipos, nulabilidad y claves primarias. Si difiere, reconcilia el esquema.
3. Solo tras verificarlo, registra la revisión histórica:

   ```bash
   # Directorio de trabajo: backend/
   uv run alembic stamp 0001
   uv run alembic upgrade head
   ```

`stamp` solo registra una revisión y no transforma datos. El upgrade también
rechazará registros existentes en esta base adoptada. Con ambas tablas vacías,
`0002` sustituye los campos antiguos por los campos de custodia. El arranque de
la API no crea ni migra tablas: prepara el esquema antes de arrancarla.

El upgrade de **0002 poblado a 0003 es aditivo**: añade las tres tablas de lockers
vacías, con FKs, restricciones e índice único parcial para la ocupación activa.
Conserva sin modificación paquetes pendientes y finalizados, sus columnas y valores.
No hay backfill ni ubicaciones, dimensiones o asignaciones ficticias. Aplica
`alembic upgrade head` antes de arrancar la nueva aplicación; después configura
lockers por API.

El downgrade **0003 → 0002** bloquea las tablas nuevas y rechaza cualquier fila
antes de DDL, incluidas celdas retiradas y asignaciones liberadas. Mantiene íntegros
esquema, índices, restricciones, filas y revisión 0003. Si las tres tablas están
vacías, elimina solo esas tablas y conserva los paquetes existentes aunque estén
poblados. El downgrade **0002 → 0001** conserva su protección: rechaza cualquier
paquete existente y mantiene datos y revisión 0002. En una base de pruebas vacía se puede
verificar el recorrido reversible desde `backend/`:

```bash
uv run alembic upgrade head
uv run alembic downgrade 0001
uv run alembic upgrade head
uv run alembic current
```

`downgrade base` solo es apropiado para una base vacía preparada para esa prueba.
Un rollback de aplicación puede conservar el esquema 0003. Una versión antigua
no sabe liberar asignaciones: **no debe procesar salidas de paquetes asignados**.
Detén las escrituras o conserva la versión capaz de liberarlas hasta resolverlo.
Para recuperar datos, usa la copia de seguridad según el procedimiento operativo;
no fuerces un downgrade destructivo ni borres volúmenes para superar las guardas.

## Pruebas

Instala las dependencias de desarrollo y ejecuta las pruebas sin PostgreSQL desde `backend/`:

```bash
# Directorio de trabajo: backend/
uv sync --extra dev
uv run --extra dev python -m unittest discover -s tests -v
```

El núcleo usa dobles asíncronos (`AsyncMock`) de los puertos de salida.
`test_http.py` prueba el adaptador HTTP con `AsyncMock` de `DeliveryService` y
`ReturnService`, sin importar `main.py` ni conectar con una base de datos. Los
repositorios se prueban con SQLite y `aiosqlite`: round trip de todos los campos,
instantes UTC, transiciones, rollback y recuperación tras UUID duplicados.
Las pruebas locales de migración usan una base temporal. La suite también cubre
normalización, invariantes, reloj controlado y contratos HTTP de las quince rutas y las reglas de lockers.
Estas pruebas no sustituyen la integración con PostgreSQL.

Para ejecutar solo las pruebas del núcleo, sin instalar dependencias, desde `backend/`:

```bash
# Directorio de trabajo: backend/
python3 -m unittest tests.test_domain tests.test_application -v
```

Prepara una **base de pruebas dedicada**, con un usuario con permiso para crear
esquemas, y aplica `alembic upgrade head` con `DATABASE_URL` apuntando a ella.
`TEST_DATABASE_URL` selecciona la base de integración; la prueba HTTP de aplicación
usa sus tablas migradas y las pruebas de concurrencia/migraciones crean esquemas
únicos y los eliminan al terminar. No uses la base de demostración ni producción.
Desde `backend/`, por ejemplo:

```bash
DATABASE_URL=postgresql+asyncpg://test_user:test_password@localhost:5432/hexagonal_test uv run alembic upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://test_user:test_password@localhost:5432/hexagonal_test \
  uv run --extra dev python -m unittest discover -s tests -v
```

Si has preparado esa base dedicada en el PostgreSQL de Compose, desde la raíz:

```bash
# Desde la raíz del repositorio.
docker compose exec \
  -e TEST_DATABASE_URL=postgresql+asyncpg://hexagonal:hexagonal@db:5432/hexagonal_test \
  api python -m unittest discover -s tests -v
```

La integración HTTP crea paquetes, registra salidas y verifica sus representaciones
en una segunda instancia de aplicación. Las pruebas PostgreSQL adicionales verifican
con conexiones independientes y sincronización explícita la última celda compartida
(un `201` y un `409`), rollback del primer contendiente, configuración frente a
recepción, salidas concurrentes y reocupación segura. Comprueban además restricciones,
upgrade aditivo y downgrade protegido con snapshots completos.
Sin `TEST_DATABASE_URL`,
las comprobaciones PostgreSQL se omiten; SQLite no demuestra sus garantías de
concurrencia y bloqueo. La imagen incluye las
dependencias de pruebas mediante el extra `dev`. Si ejecutas la prueba fuera de
Compose, migra previamente la base de datos que indique `TEST_DATABASE_URL`.

## Alcance del ejemplo

Las credenciales de Compose son locales y de demostración. No añadimos
autenticación ni repositorios genéricos. Delivery y Return son paquetes independientes
que comparten capacidad de lockers. Ubicaciones y múltiples lockers ya están incluidos.
Quedan para otras ampliaciones notificaciones e integraciones con transportistas,
reservas, TTL, transferencias, geobúsqueda, RabbitMQ y outbox. Las cotizaciones y
su procesamiento asíncrono serán una fase posterior; consultar disponibilidad no
contrata un envío ni reserva espacio. No se gestionan
direcciones, instrucciones de entrega, pedidos, productos, cantidades de productos
ni resoluciones comerciales de devolución.

Compose coordina PostgreSQL, migraciones y API siguiendo
el [control de arranque de Docker Compose](https://docs.docker.com/compose/how-tos/startup-order/).
