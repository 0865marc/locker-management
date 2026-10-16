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

### Dirección y coordenadas del locker

`location_id` es un alias opcional; los clientes existentes pueden seguir creando
lockers únicamente con ese alias. También se puede crear un locker con dirección
completa y sin alias:

```json
{
  "address": {
    "country_code": "ES",
    "postal_code": "01001",
    "province": "Araba",
    "city": "Vitoria-Gasteiz",
    "street": "Calle Ejemplo",
    "street_number": "12B"
  },
  "coordinates": {"latitude": 42.8467, "longitude": -2.6726},
  "compartments": [{"quantity": 1, "dimensions": {"width_mm": 100, "height_mm": 200, "depth_mm": 300}}]
}
```

El alta exige alias no nulo o dirección completa; coordenadas solas no bastan.
La dirección admite solo país `ES`, código postal de cinco dígitos ASCII como
`01001` y provincia, ciudad, calle y número textuales no vacíos. Se recortan estos
textos; el número conserva valores como `12B` o `s/n`. No se consulta un catálogo
postal ni se infieren datos. Las coordenadas son una pareja WGS84 opcional de
números finitos: latitud entre −90 y 90 y longitud entre −180 y 180. No admiten
booleanos, cadenas, NaN ni infinitos.

Las configuraciones incluyen `location_id`, `address` y `coordinates`, también
cuando son `null`; los históricos conservan alias y geografía nula.
`PATCH /lockers/{id}` acepta un subconjunto no vacío de `active`, `address` y
`coordinates`: omitir conserva, un objeto reemplaza el valor completo y `null`
borra solo dirección o coordenadas. `active` no acepta `null`. Por ejemplo,
`{"address":null}` conserva coordenadas y actividad. Los cambios son atómicos y
pueden hacerse con celdas ocupadas, sin modificar identidad, alias o custodia.
Tras borrar la dirección de un locker sin alias, este sigue accesible.

Los lockers sin alias se gestionan por UUID y aparecen en `GET /lockers` sin
filtro. El filtro `location_id` y `/lockers/availability` siguen seleccionando
aliases exactos, recortados y sensibles a mayúsculas; no buscan por dirección,
código postal, coordenadas o radio ni fabrican aliases.

## Comparar proveedores desde Python

El comparador es una utilidad interna independiente de HTTP, lockers y base de
datos. Desde `backend/`, este ejemplo consulta los tres adaptadores simulados:

```python
import asyncio

from adapters.providers.simulated_shipping import (
    SimulatedEconomyProvider,
    SimulatedStandardProvider,
    SimulatedExpressProvider,
)
from application.shipping_quotes import ShippingQuoteService
from domain.lockers import Dimensions
from domain.shipping_quotes import ShippingQuoteRequest


async def main() -> None:
    comparator = ShippingQuoteService([
        SimulatedEconomyProvider(),
        SimulatedStandardProvider(),
        SimulatedExpressProvider(),
    ])
    request = ShippingQuoteRequest(
        origin_country_code="ES", origin_postal_code="01001",
        destination_country_code="ES", destination_postal_code="01002",
        weight_grams=1200, dimensions=Dimensions(200, 150, 100),
    )
    for result in await comparator.compare(request):
        for offer in result.offers:
            print(result.provider_code, result.status.value, offer.service_code,
                  offer.price_cents, offer.currency,
                  offer.transit_days_min, offer.transit_days_max)


asyncio.run(main())
```

Un resultado posible cuando los tres proveedores responden con éxito:

```text
sim-economy QUOTED economy 330 EUR 3 3
sim-express QUOTED express 830 EUR 1 1
sim-standard QUOTED standard 520 EUR 2 2
```

La colección inyectada es obligatoria, no vacía y tiene códigos abiertos,
recortados y únicos. `compare` devuelve una tupla de `ProviderResult` ordenada
por proveedor, con ofertas ordenadas por servicio. El resultado y sus estados
pertenecen a `application.shipping_quotes`; las solicitudes, ofertas y
`NoCoverage` pertenecen a `domain.shipping_quotes`. Cada proveedor puede ofrecer
varios servicios (`QuoteOffers`), rechazar cobertura (`NoCoverage`) o fallar de
forma aislada. Los estados son `QUOTED`, `NOT_COVERED` y `FAILED`; los errores
normalizados son `PROVIDER_ERROR` y `PROVIDER_TIMEOUT`, sin payloads externos.

La entrada exige países `ES`, códigos postales de cinco dígitos ASCII, peso entero
entre 1 y 30000 gramos y dimensiones entre 1 y 2000 mm. Los precios son céntimos
enteros EUR y los plazos intervalos de días naturales desde la futura expedición.
Los simuladores usan tarifas deterministas por peso real/volumétrico y prefijo
postal, con demoras y fallos estocásticos en cada llamada, también en uso directo.
Sus constructores no aceptan argumentos. Las llamadas directas a `quote` necesitan
un timeout o cancelación del llamador si el proveedor simula no responder. Hay como máximo tres llamadas concurrentes y dos segundos por llamada
tras conseguir un hueco, sin reintentos. Cancelar la comparación cancela y espera
sus tareas activas y pendientes. Añadir otro proveedor solo requiere implementar
el puerto; futuros adaptadores REST, SOAP o SDK traducirían sus contratos externos.
La API de cotizaciones y su almacenamiento se componen en `main.py`; el worker
ejecuta el comparador. No hay reserva ni contratación.

## Organización

```text
hexagonal_architecture/
├── backend/
│   ├── main.py
│   ├── worker.py
│   ├── domain/
│   │   ├── deliveries.py
│   │   ├── returns.py
│   │   ├── lockers.py
│   │   ├── shipping_quotes.py
│   │   └── ports.py
│   ├── application/
│   │   ├── deliveries.py
│   │   ├── returns.py
│   │   ├── lockers.py
│   │   ├── shipping_quotes.py
│   │   ├── quotation_models.py
│   │   ├── quotation_ports.py
│   │   └── quotations.py
│   ├── adapters/
│   │   ├── http/
│   │   │   ├── deliveries/
│   │   │   │   ├── routes.py
│   │   │   │   └── schemas.py
│   │   │   ├── returns/
│   │   │   │   ├── routes.py
│   │   │   │   └── schemas.py
│   │   │   ├── lockers/
│   │   │   │   ├── routes.py
│   │   │   │   └── schemas.py
│   │   │   ├── quotations/
│   │   │   │   ├── routes.py
│   │   │   │   └── schemas.py
│   │   │   ├── routes.py
│   │   │   └── request_validation.py
│   │   ├── queue/
│   │   │   └── rabbitmq.py
│   │   ├── providers/
│   │   │   └── simulated_shipping.py
│   │   └── database/
│   │       ├── connection.py
│   │       ├── sqlmodel_deliveries.py
│   │       ├── sqlmodel_returns.py
│   │       ├── sqlmodel_lockers.py
│   │       ├── sqlmodel_quotations.py
│   │       └── migrations/
│   │           ├── env.py
│   │           ├── script.py.mako
│   │           └── versions/
│   │               ├── 0001_create_delivery_and_return.py
│   │               ├── 0002_parcel_custody.py
│   │               ├── 0003_lockers_and_custody.py
│   │               ├── 0004_locker_geography.py
│   │               └── 0005_shipping_quotations.py
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_domain.py
│   │   │   ├── test_application.py
│   │   │   ├── test_http.py
│   │   │   ├── test_lockers.py
│   │   │   ├── test_shipping_quotes.py
│   │   │   └── test_main.py
│   │   └── integration/
│   │       ├── support.py
│   │       ├── test_repositories.py
│   │       ├── test_locker_repositories.py
│   │       ├── test_locker_http.py
│   │       ├── test_application_http.py
│   │       ├── test_migrations.py
│   │       ├── test_postgresql.py
│   │       └── test_locker_postgresql.py
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── .dockerignore
│   └── pyproject.toml
├── compose.yaml
└── README.md
```

Se omiten los archivos `__init__.py`. La organización prioriza las capas:
Delivery y Return tienen archivos propios para sus entidades, casos de uso y
adaptadores. Las reglas compartidas de asignación y capacidad permanecen en Locker.
Cada flujo conserva sus validadores y errores de dominio; sus servicios declaran
el error de registro inexistente. HTTP agrupa rutas y esquemas en paquetes por
área y conserva `request_validation.py` para los cuerpos de las acciones. La conexión,
los repositorios y las migraciones se agrupan en `backend/adapters/database/`; las rutas
y los modelos HTTP, en `backend/adapters/http/`. Ambos adaptadores son externos al núcleo,
pero se ejecutan en el mismo proceso: no son microservicios.

Las rutas siguientes son relativas a la raíz del repositorio. Lee el código en este orden:

| Archivo | Responsabilidad |
| --- | --- |
| `backend/domain/deliveries.py` | Entidad `Delivery`, estado `DeliveryStatus`, validación y `DeliveryConflictError`. Solo Python. |
| `backend/domain/returns.py` | Entidad `Return`, estado `ReturnStatus`, validación y `ReturnConflictError`. Solo Python. |
| `backend/domain/lockers.py` | Dimensiones, celdas, lockers y reglas de asignación/recepción, sin infraestructura. |
| `backend/domain/shipping_quotes.py` | Solicitud de transporte, ofertas y respuesta de falta de cobertura (`NoCoverage`), inmutables y validadas. |
| `backend/domain/ports.py` | Puertos de repositorios y `ShippingProvider`: contratos de salida de la aplicación. |
| `backend/application/deliveries.py` y `returns.py` | Servicios `DeliveryService` y `ReturnService`; crean, listan y registran salidas con reloj explícito y puertos de persistencia. Declaran `DeliveryNotFoundError` y `ReturnNotFoundError`. |
| `backend/application/lockers.py` | Casos de uso de configuración y disponibilidad de lockers. |
| `backend/application/shipping_quotes.py` | `ShippingQuoteService` compara proveedores inyectados; `ProviderResult`, `ProviderStatus` y `ProviderErrorCode` expresan sus resultados. |
| `backend/adapters/http/deliveries/routes.py` y `schemas.py` | Router de Delivery y sus contratos HTTP. |
| `backend/adapters/http/returns/routes.py` y `schemas.py` | Router de Return y sus contratos HTTP. |
| `backend/adapters/http/lockers/routes.py` y `schemas.py` | Contratos HTTP de lockers, bases de recepción/asignación y traducción de errores de capacidad. |
| `backend/adapters/http/routes.py` | Agrega los cuatro routers mediante `create_router`, recibiendo servicios ya construidos. |
| `backend/adapters/http/request_validation.py` | Validación compartida de cuerpos vacíos en las acciones de salida. |
| `backend/adapters/database/sqlmodel_deliveries.py` y `sqlmodel_returns.py` | Tablas, filas, conversiones y repositorios SQLModel de cada flujo; conservan sus consultas y transacciones. |
| `backend/adapters/database/sqlmodel_lockers.py` | Persistencia de configuración y asignaciones, elección de celda, bloqueo/liberación y normalización UTC de persistencia. |
| `backend/adapters/database/connection.py` | Crea el motor y la fábrica de sesiones compartidos. |
| `backend/adapters/providers/simulated_shipping.py` | Tres adaptadores de transporte simulados, sin servicios externos. |
| `backend/main.py` | Punto de composición: conecta repositorios y servicios, proporciona `utc_now` e incluye el router agregado; gestiona motor y ciclo de vida. |
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

`create_app()` crea una vez por aplicación `DeliveryService`, `ReturnService`, `LockerService` y `QuotationService`,
y conserva sus referencias en `app.state.delivery_service`,
`app.state.return_service`, `app.state.locker_service` y `app.state.quotation_service`. Suministra `utc_now`,
que devuelve la hora UTC real, como segundo argumento obligatorio de
`DeliveryService` y `ReturnService`. Los consumidores directos también deben
proporcionar un `Callable[[], datetime]`; las pruebas usan relojes controlados.
El agregador `create_router(delivery_service, return_service, locker_service, quotation_service)`
recibe las instancias e incluye sus routers en orden Locker/Delivery/Return/Quotation,
sin construir dependencias. Las rutas
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
adaptador; los puertos reciben y devuelven las entidades de
`backend/domain/deliveries.py` y `backend/domain/returns.py`.
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
`reason`; `0002` incorpora el modelo de custodia y `0003` añade lockers y la revisión `0004` incorpora geografía nullable y `0005` añade cotizaciones. `upgrade 0001`
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

El upgrade **0003 → 0004** conserva paquetes, lockers, celdas y asignaciones;
añade dirección y coordenadas nullable y permite alias nulo, sin backfill ni índice
postal. Aplica `alembic upgrade head` antes de desplegar la API nueva. No hay tablas
de cotización. El downgrade **0004 → 0003** bloquea lockers y rechaza, antes de DDL,
cualquier campo geográfico no nulo o locker sin alias. El rechazo conserva filas,
estructura y revisión. Con geografía nula y aliases presentes, elimina únicamente
las columnas/checks nuevos y restaura `location_id NOT NULL`, conservando custodia.
Para volver a una aplicación que exige alias, primero verifica que todos los lockers
lo tengan; no inventes aliases ni borres direcciones para forzar el downgrade.

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
Un rollback de aplicación puede conservar el esquema actual. Una versión antigua
no sabe liberar asignaciones: **no debe procesar salidas de paquetes asignados**.
Detén las escrituras o conserva la versión capaz de liberarlas hasta resolverlo.
Para recuperar datos, usa la copia de seguridad según el procedimiento operativo;
no fuerces un downgrade destructivo ni borres volúmenes para superar las guardas.

## Tipos: Pyright y Pylance

El extra `dev` incluye Pyright, fijado en `uv.lock`. Desde `backend/`:

```bash
uv sync --extra dev
uv run --extra dev pyright --project .. --warnings
```

Este comando es obligatorio al terminar cada spec/cambio y debe devolver **cero
errores y cero advertencias**. Se repite después de corregir tipos, junto con las
pruebas de comportamiento afectadas. No necesita PostgreSQL ni variables de base
de datos; una revisión manual, auditoría AST o captura del editor no lo sustituye.

`pyrightconfig.json` en la raíz incluye todo `backend`: producción en modo strict
(dominio, aplicación, adaptadores y `main.py`) y pruebas en standard, con objetivo
Python 3.11 e imports desde `backend`. Solo excluye entornos/cachés y migraciones
históricas 0001–0003; `env.py`, 0004 y 0005 se analizan. No se desactivan reglas para
ocultar diagnósticos. En VSCode abre la raíz del repositorio y selecciona
`backend/.venv` como intérprete para que Pylance use el entorno/configuración
compartidos. La extensión y CLI pueden emitir diagnósticos distintos si usan
versiones diferentes; la evidencia reproducible de cierre es el comando anterior.

## Pruebas

Las suites usan `unittest`: `tests/unit` contiene pruebas sin servicios y
`tests/integration` usa PostgreSQL y `tests/messaging` añade RabbitMQ. Instala las
dependencias de desarrollo y ejecuta las unitarias desde `backend/`:

```bash
# Directorio de trabajo: backend/
uv sync --extra dev
uv run --extra dev python -m unittest discover -s tests/unit -t . -v
```

Las unitarias cubren dominio, reglas físicas de lockers, casos de uso con
`AsyncMock`, adaptador HTTP con dobles de servicios y composición/lifecycle con
motor simulado. Se pueden ejecutar sin `TEST_DATABASE_URL` ni un servidor de base
de datos. No requieren un driver SQLite.

Para integración, usa una **base de pruebas dedicada** ya existente y un usuario
con permisos para conectar y crear/eliminar esquemas en ella. Define
`TEST_DATABASE_URL` explícitamente con el driver `postgresql+asyncpg`; cada caso
crea un esquema UUID aislado, lo prepara con Alembic y lo elimina al terminar,
incluso tras un fallo. Las pruebas de historia eligen su revisión inicial y las
de arranque sin tablas conservan el esquema vacío. No hace falta migrar `public`
previamente; la preparación y los datos quedan dentro del esquema de cada caso.
Usa esta base dedicada en lugar de la base de demostración o producción.

Desde `backend/`, ejecuta integración o la suite completa:

```bash
# Solo integración.
TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@localhost:5432/hexagonal_test' \
  uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f

# Suite completa, incluyendo mensajería (necesita ambas URLs).
TEST_RABBITMQ_URL='amqp://test_user:test_password@localhost/hexagonal_test' \
TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@localhost:5432/hexagonal_test' \
  uv run --extra dev python -m unittest discover -s tests -t . -v -f
```

`-t .` mantiene las importaciones de paquetes inequívocas; `-f` detiene la ejecución
ante el primer error. Integración y suite completa fallan con diagnóstico explícito
y código distinto de cero si falta `TEST_DATABASE_URL`, el driver es incompatible,
PostgreSQL no responde o faltan permisos. Las comprobaciones de base de datos no se
omiten por falta de configuración y no recurren a `DATABASE_URL`.

Si esa base dedicada está preparada en el PostgreSQL de Compose, ejecuta desde la
raíz del repositorio:

```bash
docker compose exec \
  -e TEST_DATABASE_URL=postgresql+asyncpg://hexagonal:hexagonal@db:5432/hexagonal_test \
  api python -m unittest discover -s tests/integration -t . -v -f
```

La imagen incluye las dependencias de pruebas mediante el extra `dev`. El comando
de Compose usa igualmente esquemas aislados dentro de la base dedicada indicada.

| Suite de integración | Qué verifica |
| --- | --- |
| `test_repositories.py`, `test_locker_repositories.py` | Identidad, valores/nulls, UTC, transiciones, configuración, capacidad compartida, restricciones reales y rollback. |
| `test_locker_http.py`, `test_application_http.py` | Las quince rutas, validación y representaciones, persistencia entre instancias de aplicación y arranque sobre esquema vacío sin DDL. |
| `test_migrations.py` | Columnas legacy de `0001`, round trip vacío hasta base/head, metadata sin diferencias, rechazo de upgrade/downgrade destructivos y upgrade aditivo desde `0002` poblado. |
| `test_postgresql.py`, `test_locker_postgresql.py` | `timestamptz`, FKs/checks/índice parcial, locks de migración, salidas concurrentes y última celda compartida (un `201` y un `409`), rollback del primer contendiente, configuración frente a recepción y reocupación segura con conexiones independientes y sincronización explícita. |

Los rechazos de migración comparan snapshots completos de columnas, índices,
restricciones, filas y revisión. Las pruebas conservan las migraciones históricas
`0001`, `0002` y `0003` sin cambios; `0004` añade geografía y sus guardas.

## Alcance del ejemplo

Las credenciales de Compose son locales y de demostración. No añadimos
autenticación ni repositorios genéricos. Delivery y Return son paquetes independientes
que comparten capacidad de lockers. Ubicaciones y múltiples lockers ya están incluidos.
Quedan para otras ampliaciones notificaciones e integraciones con transportistas,
reservas, TTL, transferencias, geobúsqueda y outbox. La API de cotizaciones guarda
solicitudes y resultados y usa RabbitMQ con un worker; los proveedores reales
quedan para una fase posterior. Consultar disponibilidad no contrata un envío
ni reserva espacio. No se gestionan
direcciones de Delivery/Return, instrucciones de entrega, pedidos, productos, cantidades de productos
ni resoluciones comerciales de devolución.

Compose coordina PostgreSQL, migraciones, RabbitMQ, API y worker siguiendo
el [control de arranque de Docker Compose](https://docs.docker.com/compose/how-tos/startup-order/).

## Cotizaciones asíncronas

`POST /quotations` guarda una solicitud nueva y publica su UUID una sola vez en
RabbitMQ. Devuelve `202`, `{ "id": "…", "status": "PENDING" }` y
`Location: /quotations/{id}` únicamente tras confirmar la publicación. Ejemplo:

```bash
curl -i http://localhost:8000/quotations -H 'Content-Type: application/json' -d '{
  "origin_country_code":"ES", "origin_postal_code":"01001",
  "destination_country_code":"ES", "destination_postal_code":"28001",
  "weight_grams":1200,
  "dimensions":{"width_mm":200,"height_mm":150,"depth_mm":100}
}'
curl http://localhost:8000/quotations/UUID_DEVUELTO
```

Se rechazan campos extra, países distintos de ES, códigos postales que no sean
texto ASCII de cinco dígitos, peso fuera de 1–30000 g y dimensiones fuera de
1–2000 mm o valores no enteros (incluidos booleanos). Una escritura inicial
fallida devuelve `503` sin publicar. Si falla la publicación, `503` incluye
`detail.id` y `PUBLISH_ERROR`; se intenta guardar `FAILED/PUBLISH_ERROR` si la
solicitud sigue PENDING. Nunca se inventan fallos de proveedores por este error.

GET devuelve `id`, `request`, `status`, `created_at`, `finished_at`,
`process_error_code` y `results`, con fechas UTC, ofertas en céntimos EUR y los
estados originales `QUOTED`, `NOT_COVERED`, `FAILED`. PENDING/PROCESSING no tienen
resultados ni fecha final; COMPLETED expone el lote entero, incluso cuando todos
los proveedores fallan. FAILED conserva un error de proceso. Un UUID desconocido
devuelve 404, uno mal formado 422, y persistencia no disponible 503.

`application/quotation_models.py`, `quotation_ports.py` y `quotations.py` definen
el estado persistido, los puertos y los casos de uso. Los adaptadores son
`adapters/database/sqlmodel_quotations.py`, `adapters/http/quotations/` y
`adapters/queue/rabbitmq.py`; `main.py` compone API y `worker.py` el proceso de
trabajo. API comparte servicios por instancia y cierra motor y broker incluso
si falla el arranque. Solo el worker llama a `ShippingQuoteService.compare`.

`docker compose up --build` inicia PostgreSQL, migraciones, RabbitMQ 4, API y
**un único worker**. API/worker esperan migraciones correctas y broker saludable;
las migraciones esperan PostgreSQL saludable. Los volúmenes `postgres_data` y
`rabbitmq_data` se conservan con `docker compose down` sin `-v`. Para arrancar
por separado, ejecutar `alembic upgrade head`, `uvicorn main:app` y
`python worker.py` desde backend, con DATABASE_URL y RABBITMQ_URL configurados.
El valor local por defecto de RabbitMQ es `amqp://guest:guest@localhost/`.
Ni API ni worker crean tablas ni ejecutan migraciones al arrancar.

La cola `shipping.quotations` es durable y los mensajes son persistentes, con
publicación mandatory y confirms. El worker usa prefetch 1 y extracción
secuencial sin buffer, con comprobación de cola cada 0.1 s cuando está vacía.
Confirma cada entrega **antes** de leer PostgreSQL o llamar a proveedores; si
falla el ack, no ejecuta. Procesa solo PENDING, marca PROCESSING y llama compare
una vez. Guarda resultados/ofertas y COMPLETED en una sola transacción. Los
errores/timeout de proveedor se conservan por separado sin retries; una excepción
inesperada intenta FAILED/PROCESSING_ERROR solo si todavía está PROCESSING.

No hay requeue explícito, republicación, retry de trabajos, reconexión robusta,
reconciliador ni recuperación automática. Commit y publicación no son atómicos:
una caída o confirmación incierta puede dejar trabajo incompleto. Después del
ack temprano, una caída puede perder el trabajo y dejar PENDING/PROCESSING
indefinidamente. No se garantiza ejecución exactamente una vez ni que un fallo
de infraestructura permita registrar un error final. El apagado cancela y espera
las llamadas activas y cierra los recursos; no reejecuta trabajo pendiente.

Cada simulador declara su propio perfil privado e inmutable. El worker y los
consumidores directos construyen `SimulatedEconomyProvider()`,
`SimulatedStandardProvider()` y `SimulatedExpressProvider()` sin argumentos:

| Proveedor | Demora uniforme (s) | Sin respuesta | Error |
| --- | --- | --- | --- |
| Economy | 0.2–0.8 | 0.10 | 0.15 |
| Standard | 0.1–0.5 | 0.05 | 0.10 |
| Express | 0.05–0.2 | 0.02 | 0.05 |

Un sorteo elige categorías excluyentes; tras la demora uniforme, el proveedor
responde, falla o espera cancelablemente hasta el timeout del comparador. Las
tarifas de respuestas exitosas permanecen iguales. Estos perfiles no se
configuran por constructor, variables de entorno ni almacenamiento; se retira
la configuración pública de perfil/RNG/espera. El worker solo configura sus
conexiones. Las pruebas controlan funciones privadas de azar y espera al ejecutar,
sin semillas ni dependencia del orden concurrente.

El head actual es **0005**: añade únicamente `shipping_quotations`,
`shipping_provider_results` y `shipping_offers`, con FK y unicidad por
solicitud/proveedor/servicio. 0001–0004 permanecen intactas. Upgrade 0004→0005
preserva los datos anteriores; downgrade a 0004 bloquea las tablas y rechaza
cualquier dato de cotización antes de DDL. Si están vacías, elimina solo las
tres tablas nuevas aunque existan paquetes o lockers. Se mantiene el protocolo
de revisión y preparación de migraciones descrito arriba.

La suite PostgreSQL continúa sin requerir RabbitMQ. El smoke de mensajería exige
ambas URLs explícitas; crea y elimina solo su schema/cola aislados. Configuración
faltante o inaccesible produce un fallo claro sin exponer credenciales.

```bash
# Desde backend; unidades sin servicios:
env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL uv run --extra dev python -m unittest discover -s tests/unit -t . -v
# Con TEST_DATABASE_URL PostgreSQL+asyncpg de prueba:
uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f
# Además TEST_RABBITMQ_URL AMQP de prueba:
uv run --extra dev python -m unittest discover -s tests/messaging -t . -v -f
uv run --extra dev pyright --project .. --warnings
```

Pyright incluye estrictamente `worker.py`, migración 0005 y el entorno Alembic,
con las mismas reglas y exclusiones históricas. Las pruebas cubren ack antes de
proveedores, publicación única, batch atómico, estados/errores, no requeue tras
fallos de proveedor, simulación controlada y guardas de migración.
