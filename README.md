# Arquitectura hexagonal con FastAPI

Ejemplo mínimo con **Delivery** (entregas) y **Return** (devoluciones).
Cada uno permite crear y listar registros mediante un repositorio **SQLModel
asíncrono sobre PostgreSQL**. **Alembic** gestiona las migraciones. Delivery y Return
son independientes para centrar el ejemplo en la organización; todavía no
relacionamos una devolución con una entrega.

## Arrancar

Necesitas Docker con Docker Compose. Ejecuta Compose desde la raíz del repositorio:

```bash
docker compose up --build
```

Compose espera a que PostgreSQL esté preparado, ejecuta `alembic upgrade head`
en el servicio `migrate` y arranca la API cuando la migración termina correctamente.
Si conservas una base de datos de la versión anterior, consulta primero
[cómo adoptar las tablas existentes](#base-de-datos-de-la-versión-anterior).

Abre [la documentación interactiva](http://127.0.0.1:8000/docs), o prueba:

```bash
curl -X POST http://127.0.0.1:8000/deliveries \
  -H 'Content-Type: application/json' \
  -d '{"address": "Calle Mayor 1"}'

curl http://127.0.0.1:8000/deliveries

curl -X POST http://127.0.0.1:8000/returns \
  -H 'Content-Type: application/json' \
  -d '{"reason": "Producto equivocado"}'

curl http://127.0.0.1:8000/returns
```

Crear devuelve `201` con un `id` UUID; listar devuelve `200` con una lista.
Una dirección o motivo vacío, incluidos solo espacios, devuelve `422`.
Los datos persisten en el volumen `postgres_data` al ejecutar `docker compose down`.

## Organización

```text
hexagonal_architecture/
├── backend/
│   ├── main.py
│   ├── domain/
│   │   ├── models.py
│   │   └── ports.py
│   ├── application/
│   │   └── use_cases.py
│   ├── adapters/
│   │   ├── http/
│   │   │   ├── routes.py
│   │   │   └── schemas.py
│   │   └── database/
│   │       ├── connection.py
│   │       ├── sqlmodel_repositories.py
│   │       └── migrations/
│   │           ├── env.py
│   │           ├── script.py.mako
│   │           └── versions/
│   │               └── 0001_create_delivery_and_return.py
│   ├── tests/
│   │   ├── test_application.py
│   │   ├── test_http.py
│   │   ├── test_repositories.py
│   │   ├── test_migrations.py
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
| `backend/domain/ports.py` | Puertos de salida `DeliveryRepository` y `ReturnRepository`: lo que la aplicación necesita de la persistencia. |
| `backend/application/use_cases.py` | Implementa los casos de uso; sus métodos públicos `create` y `list_all` actúan como puertos de entrada. Usa los puertos de salida sin conocer HTTP ni la base de datos. |
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

`create_app()` crea una vez por aplicación `DeliveryService` y `ReturnService`,
y conserva sus referencias en `app.state.delivery_service` y
`app.state.return_service`. Inyecta esas mismas instancias en
`create_router(delivery, returns)`, que construye el router de FastAPI. Las rutas
reutilizan los servicios recibidos, sin instanciarlos por petición ni buscarlos
en `app.state`. Todos los endpoints usan SQLModel a través de los casos de uso:

| Endpoint | Repositorio |
| --- | --- |
| `POST /deliveries` | `SqlModelDeliveryRepository` |
| `GET /deliveries` | `SqlModelDeliveryRepository` |
| `POST /returns` | `SqlModelReturnRepository` |
| `GET /returns` | `SqlModelReturnRepository` |

Cada servicio permite tanto crear como listar; no se separan por lectura y
escritura. Sustituir un repositorio por otro que cumpla su puerto no requiere
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

Los dos repositorios reciben la misma fábrica SQLAlchemy `async_sessionmaker`.
La fábrica crea sesiones SQLModel y las consultas usan `AsyncSession.exec()`. Cada operación
abre su propia sesión; guardar abre una transacción con `sessions.begin()`, que
confirma al terminar o revierte si falla. **No hay una `AsyncSession` global**.
Delivery y Return mantienen sus propias tablas y consultas.

Cada caso de uso escribe una sola vez. Si necesitara coordinar varias escrituras
atómicas, habría que ampliar el diseño para compartir una transacción entre ellas.

Para cambiar PostgreSQL por MySQL se cambiarían el controlador y la configuración
compartida, y se revisaría la compatibilidad de los adaptadores. El dominio y
los casos de uso conservarían sus contratos: ese es el beneficio de la separación,
aunque una migración pueda afectar a varios archivos de infraestructura.

## Migraciones

Hay **un único historial para toda la base de datos**, con las tablas `deliveries`
y `returns`. La revisión inicial es `0001`. `SQLModel.metadata` es la fuente del
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

La versión anterior creaba las tablas con `create_all()`, sin registrar un
historial de Alembic. No apliques la revisión inicial sobre esas tablas: intentaría
crearlas otra vez. Para adoptar esa base de datos:

1. Haz una copia de seguridad.
2. Comprueba que el esquema existente coincide con la revisión
   `backend/adapters/database/migrations/versions/0001_create_delivery_and_return.py`, incluidos tipos,
   nulabilidad y claves primarias. Si difiere, hay que reconciliarlo primero.
3. Solo tras comprobar esa coincidencia, registra la revisión inicial y aplica
   las posteriores:

   ```bash
   # Directorio de trabajo: backend/
   uv run alembic stamp 0001
   uv run alembic upgrade head
   ```

`stamp` registra una revisión sin ejecutar sus cambios: no corrige un esquema
incompatible. Este proyecto no adopta tablas existentes automáticamente ni
requiere borrar el volumen de datos.

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
repositorios se prueban con SQLite y `aiosqlite`: creación y listado, y recuperación
tras un UUID duplicado. Las pruebas de migraciones verifican el esquema sobre una base temporal.
Estas pruebas no sustituyen la integración con PostgreSQL.

Para ejecutar solo las pruebas del núcleo, sin instalar dependencias, desde `backend/`:

```bash
# Directorio de trabajo: backend/
python3 -m unittest discover -s tests -p test_application.py -v
```

Con Compose arrancado y las migraciones aplicadas, ejecuta también la prueba HTTP
sobre PostgreSQL desde la raíz del repositorio:

```bash
# Desde la raíz del repositorio.
docker compose exec \
  -e TEST_DATABASE_URL=postgresql+asyncpg://hexagonal:hexagonal@db:5432/hexagonal \
  api python -m unittest discover -s tests -v
```

Esta prueba crea una entrega y una devolución mediante SQLModel y las lista con
SQLModel en una segunda instancia de la aplicación. No elimina datos existentes.
Sin `TEST_DATABASE_URL`, la prueba de integración se omite. La imagen incluye las
dependencias de pruebas mediante el extra `dev`. Si ejecutas la prueba fuera de
Compose, migra previamente la base de datos que indique `TEST_DATABASE_URL`.

## Alcance del ejemplo

Las credenciales de Compose son locales y de demostración. No añadimos
autenticación, repositorios genéricos ni relaciones entre Delivery y Return para
mantener visible la arquitectura.

Compose coordina PostgreSQL, migraciones y API siguiendo
el [control de arranque de Docker Compose](https://docs.docker.com/compose/how-tos/startup-order/).
