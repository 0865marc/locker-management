# Locker Management Demo

Demo de backend para gestionar **lockers y puntos de entrega y recogida de paquetes**,
con arquitectura hexagonal y FastAPI. **Delivery** registra un
paquete recibido del transportista para que lo recoja el destinatario; **Return**
registra uno depositado por el cliente para que lo retire el transportista.
El [mapa de lockers](#mapa-de-lockers-frontend-estático) permite consultar su
disponibilidad y comparar envíos simulados hacia un locker desde el navegador. Cada entidad representa un paquete y tiene un UUID independiente. La persistencia
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

## Mapa de lockers: frontend estático

Con **Docker Compose**, `docker compose up --build` desde la raíz arranca toda
la aplicación y sirve el mapa en [http://127.0.0.1:4321](http://127.0.0.1:4321).
No necesitas instalar Node o npm para este arranque. Nginx sirve los archivos
estáticos generados; el navegador consulta directamente la API del puerto 8000.
El frontend puede arrancar aunque la API no esté disponible: en ese caso muestra
el estado de error y permite reintentar cuando el backend esté preparado.

### Navegar y buscar una ubicación

La vista inicial se acerca a la península. Usa la rueda sobre el mapa para
acercar o alejar, o sus controles de zoom. Puedes navegar también a Baleares,
Canarias, Ceuta y Melilla. Las cargas vacías conservan tu encuadre. La rueda dentro de un panel desplaza ese panel sin cambiar el mapa.

El panel ofrece dos pestañas: **Cotizar envío**, seleccionada al entrar, y
**Localizar paquete**. Usa Tab, flechas izquierda/derecha o Home/End para navegar.
El contenido inactivo queda oculto y sin foco. Cambiar de pestaña conserva valores
y destino, cierra sugerencias/cotizador y detiene las esperas locales; no vuelve
a consultar automáticamente ni cancela trabajos persistidos del worker.

Cotización contiene **Dirección de recogida** y **Dirección de entrega**, medidas
y contadores vivos al final. Cada buscador tiene sus propias sugerencias, errores,
petición y cancelación: al menos tres caracteres y 350 ms sin cambios, sin botón
Buscar ni consultas duplicadas por Enter. Cinco dígitos ASCII usan búsqueda
postal estructurada, conservando ceros iniciales como `01001`.

Selecciona siempre un resultado, incluso si solo aparece uno. Recogida rellena
el CP de origen únicamente desde `properties.postcode` español de cinco dígitos;
si falta, requiere entrada manual. Editar esa recogida borra solo el CP derivado:
un CP introducido manualmente se conserva hasta elegir otra recogida. Elegir
otra recogida reemplaza el CP o lo vacía si no dispone de uno, e invalida ofertas
anteriores. No mueve la zona de entrega ni elige locker.

Entrega sitúa el punto azul y encuadra la zona para explorar lockers, sin elegir
uno automáticamente ni modificar su CP. Los dos campos conservan el texto ajeno,
no filtran lockers ni envían medidas. Las sugerencias admiten flechas, Enter,
click o toque; Escape devuelve foco al campo y salir cierra/cancela. La animación
breve respeta movimiento reducido y las respuestas obsoletas no reabren listas.

La consulta se envía directamente desde tu navegador al servicio público
[Photon](https://photon.komoot.io/), basado en datos de OpenStreetMap, con país
España. Las direcciones usan `/api/` y los códigos postales `/structured`, según
[Photon API v1](https://github.com/komoot/photon/blob/master/docs/api-v1.md).
No requiere claves ni proxy y el frontend sigue siendo estático y compatible
con Cloudflare Pages. Es un servicio de demostración para uso razonable, sin
garantía de disponibilidad: los errores y el límite de cinco segundos tienen
su propio estado y reintento, sin interrumpir la consulta de lockers. Cambiar la
búsqueda cancela la anterior; sus respuestas obsoletas se descartan. No se guardan
las consultas ni se hacen reintentos automáticos. Las pruebas controlan Photon
y las teselas; no demuestran conectividad real o CORS del proveedor externo en
este entorno.

### Desarrollo opcional con npm

Para editar el frontend con recarga automática necesitas **Node 24 LTS** y npm.
Arranca solo el backend con `docker compose up --build api worker` desde la raíz;
si antes arrancaste todo el stack, libera el puerto con `docker compose stop frontend`.
En otra terminal:

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Abre `http://localhost:4321`. El ejemplo configura explícitamente
`PUBLIC_API_BASE_URL=http://127.0.0.1:8000`; es una URL pública incorporada al
JavaScript, sin secretos. El navegador consulta directamente `GET /lockers`,
sin credenciales, con una lectura nueva en cada actualización y un límite de
cinco segundos. La API debe ser accesible desde el navegador: el nombre Docker
`api` no sirve como dirección pública. Una URL ausente o inválida, o HTTP bajo
una página HTTPS, produce un error visible sin recurrir a otra API.

Para comprobar y generar la web (el build funciona con el backend apagado):

```bash
# Desde frontend/
npm run check
npm test
npm run build
npm run preview
# Alternativa a preview: servir dist con un servidor HTTP estático genérico.
python3 -m http.server 4321 --bind 127.0.0.1 --directory dist
```

Usa npm dev, preview, el servidor genérico o Nginx de Compose por separado:
todos ocupan el puerto 4321. Detén el proceso anterior antes de cambiar de modo.
`dist/` contiene HTML, CSS y JavaScript estáticos, sin instantáneas de lockers.
No necesita Node en producción, SSR, Workers, funciones ni proxy frontend.
Cambiar `PUBLIC_API_BASE_URL` requiere **un nuevo build** y volver a distribuir
`dist`: las variables del host no cambian los archivos ya compilados.

### URL de API al construir la imagen

Compose pasa `PUBLIC_API_BASE_URL` como argumento de build, con el valor local
por defecto `http://127.0.0.1:8000` cuando no está definida. Un valor explícitamente
vacío se conserva y provoca el error de configuración del frontend. Puedes
definirlo en el entorno o en `.env`
de la raíz y reconstruir el servicio. Por ejemplo, para una API HTTPS propia:

```bash
PUBLIC_API_BASE_URL=https://api.example.com docker compose up --build frontend
```

Sustituye la URL de ejemplo por la API accesible desde tu navegador y autoriza
el origen del frontend en su configuración CORS. El nombre interno `api` de
Docker no es una URL pública para el navegador.

El Dockerfile instala con `npm ci` y compila con Node 24; la imagen final contiene
Nginx Alpine y únicamente el contenido de `dist`, sin Node, npm, fuentes o archivos
`.env`. `.dockerignore` excluye entornos locales y salidas: `frontend/.env` no
configura el build de Docker. La URL queda incorporada en los assets, no se
sustituye al arrancar Nginx ni se utiliza un proxy. Cambiar una variable de runtime
o reiniciar el contenedor no la actualiza; reconstruye con `--build`.
El mismo build estático sigue siendo apto para Cloudflare Pages.

Las pruebas de navegador necesitan `python3` para servir los archivos estáticos
y el entorno local `backend/.venv`, incluso si normalmente ejecutas la API con
Docker. Prepáralo con uv y ejecuta desde la raíz:

```bash
cd backend
uv sync --locked --extra dev
cd ../frontend
npx playwright install chromium
npm run test:e2e
```

Como alternativa al Chromium de Playwright, puedes indicar un navegador instalado
con `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:e2e`.
La suite levanta su servidor estático y FastAPI con middleware CORS real y dobles
de persistencia; no necesita PostgreSQL ni RabbitMQ. Deja libres los puertos
4321 y 8765 antes de ejecutarla.

El mapa ocupa toda la pantalla. «Tu paquete» permite introducir largo, ancho y
alto en centímetros y peso en kilogramos. Los datos empiezan vacíos y permanecen
locales hasta pulsar **Comparar envíos**. Buscar una dirección no los envía.

### Comparar envíos hacia un locker

Elige un marcador o usa el enlace de teclado **Elegir destino y cotizar**. El
panel «Enviar a este locker» incluye un selector accesible con todos los lockers
disponibles, también los que carecen de coordenadas. Los nombres repetidos se
distinguen con un número. No hay catálogo técnico ni se muestran identificadores
de lockers. Cierra con su botón o Escape para devolver el foco al origen.

Introduce el CP de origen. El CP de destino procede exclusivamente de la dirección
estructurada española del locker, si contiene cinco dígitos; de lo contrario,
el panel pide introducirlo manualmente. Conserva ceros iniciales. Cambiar de
locker borra el CP manual anterior y conserva origen, medidas y peso.

**Comparar envíos** valida dimensiones entre 0,1 y 200 cm (milímetros enteros) y
peso entre 0,001 y 30 kg (gramos enteros). No redondea fracciones incompatibles:
`1.001 kg` son exactamente `1001 g`. Largo se envía como profundidad. Envía
únicamente países ES, códigos postales y paquete al contrato existente de
`POST /quotations`; no envía UUID de locker, dirección ni coordenadas. La
cotización usa esos CP, sin comprobar que el paquete cabe, reservar ni crear un
envío. Las tarjetas son una **demo con proveedores, precios y plazos simulados**:
pueden mostrar ofertas en EUR, ausencia de cobertura o fallo/timeout de proveedor.
Un fallo del proceso se presenta por separado.

Tras un 202 consulta `GET /quotations/{id}` secuencialmente, aproximadamente cada
segundo. Cada petición tiene límite de cinco segundos y cada espera local,
treinta segundos. Un fallo de lectura o fin de espera permite **Seguir consultando**
la misma referencia sin otro POST. No hay reintentos automáticos de creación.
Una creación no confirmada puede haberse guardado; un error de publicación con
referencia permite consultar ese estado. El backend persiste las solicitudes.
Editar datos, cerrar el panel o salir detiene la espera local y descarta respuestas
obsoletas; no cancela el trabajo remoto. No se usa almacenamiento del navegador.

Solo aparecen lockers activos con alguna celda habilitada y libre. Los contadores
muestran lockers disponibles y posicionables, no celdas. La lectura inicial y el
reintento tras fallo consultan disponibilidad; no hay actualización periódica.
Los lockers sin coordenadas siguen siendo destinos seleccionables sin inventar
ubicación. Una respuesta vacía o un error no mueve el mapa.

El fondo utiliza teselas de [OpenStreetMap, © sus colaboradores](https://www.openstreetmap.org/copyright),
con atribución visible. Si fallan, el selector y cotizador siguen utilizables.
Las pruebas controlan teselas y Photon; el recorrido CORS de cotización usa la
aplicación FastAPI real con repositorios y publicación de prueba, sin interceptar
las peticiones de lockers o cotizaciones. No demuestra conectividad del proveedor
externo ni la integración del worker real.

### Localizar un paquete

En **Localizar paquete**, introduce el **UUID de una entrega o devolución** y
pulsa su botón o Enter. El UUID de una cotización no identifica un paquete.
La validación se realiza antes de HTTP; cada intento hace un único
`GET /tracking/{id}` directo, sin credenciales, caché, polling ni escrituras.
Editar, intentar de nuevo o cambiar de pestaña cancela/invalida la lectura local,
con límite de cinco segundos. Errores, ausencia y ambigüedad tienen mensajes y
reintento explícito. Al salir se retira el resultado y marcador, conservando UUID.

El estado guardado distingue pendiente de recogida, recogido, devuelto al
transportista, pendiente de entrega al transportista y entregado al transportista.
**Locker actual** indica custodia pendiente con asignación; **Último locker
registrado** indica una asignación de la que ya salió el paquete. No es ubicación
en tiempo real ni una instantánea histórica de la dirección: se muestran los datos
registrados actuales del locker. Sin asignación, metadata o coordenadas se indica
su ausencia y nunca se infiere o geocodifica una ubicación.

El marcador oscuro de seguimiento es independiente de destinos disponibles:
puede mostrar un locker lleno o inactivo, sin cambiar contadores, destino o CP de
cotización. Pulsar marcadores en seguimiento no abre el cotizador ni cambia modo.
El resultado textual funciona aunque fallen disponibilidad o teselas.

`GET /tracking/{id}` devuelve exclusivamente
`{id, kind, status, locker_relation, locker_id, locker}`. `kind` es `delivery` o
`return`; `locker_relation` es `current`, `last_known` o `unassigned`. `locker` es
null o `{location_id, address, coordinates}`, con los mismos campos públicos de
dirección/coordenadas de lockers. Sin asignación ambos campos de locker son null;
si falta metadata, conserva `locker_id` y la relación con `locker: null`.
Devuelve 404 sin coincidencia, 422 para UUID inválido y 409 si existe en ambos
flujos. No enumera paquetes ni expone nombres, teléfonos, tracking del
transportista o compartimentos; no altera custodia ni cotizaciones. Utiliza GET
con la política CORS existente, que no es autorización.

### Generar lockers sintéticos de demostración

El generador es manual: no se ejecuta al arrancar, compilar o abrir el mapa.
Añade por defecto **250 lockers**, con **semilla 42**, a
`http://127.0.0.1:8000`. Comprueba primero los payloads con `--dry-run`, que
imprime un array JSON y no hace peticiones. Desde la raíz, con una API de
**demostración** y su imagen reconstruida para incluir el script:

```bash
docker compose up --build -d api
docker compose exec -T api python scripts/seed_lockers.py --dry-run > /tmp/lockers-demo.json
# Tras revisar el JSON, creación explícita en la API de demostración:
docker compose exec api python scripts/seed_lockers.py
# Cantidad personalizada:
docker compose exec api python scripts/seed_lockers.py --count 12 --seed 42
```

También puedes ejecutarlo localmente desde `backend/`:

```bash
uv run python scripts/seed_lockers.py --dry-run > /tmp/lockers-demo.json
uv run python scripts/seed_lockers.py --base-url http://127.0.0.1:8000
# Cantidad personalizada:
uv run python scripts/seed_lockers.py --count 12 --seed 42
```

`--count` exige un entero positivo; `--seed` acepta un entero y `--base-url`
selecciona la API HTTP(S). Cada locker lleva alias `DEMO-<seed>-<índice>`, dirección
`null`, estado activo y seis celdas habilitadas y libres de 400×400×600 mm. Sus
posiciones se muestrean dentro de los polígonos terrestres españoles de Natural
Earth, respetando huecos; no se usa Photon. La [procedencia y licencia del dato](backend/scripts/data/README.md)
identifica el extracto local de dominio público y su versión. Son ubicaciones
sintéticas con límites generalizados, sin instalaciones o direcciones reales ni
cuotas iguales por territorio. Puedes explorar las islas desplazando y alejando el mapa.

La misma semilla reproduce los payloads y las coordenadas, no los UUID asignados
por el servidor. **Repetir añade nuevos registros**, incluso con la misma semilla;
no hay idempotencia. El script crea secuencialmente mediante `POST /lockers` y se
detiene al primer fallo, informa cuántas creaciones se confirmaron y sale con
código no cero. La última respuesta incierta puede corresponder a una creación:
no reintenta escrituras ni borra los datos existentes o ya creados. Revisa el
resultado antes de volver a ejecutarlo. Los smoke tests de generación usan solo
stacks desechables y conservan los datos del usuario.

### CORS local y de producción

FastAPI lee `CORS_ALLOWED_ORIGINS` al arrancar: orígenes HTTP(S) exactos separados
por comas, recortando espacios. Sin variable o con valor vacío no permite ningún
origen de navegador. Rechaza comodines, credenciales, rutas (también `/` final),
query, fragmentos y entradas inválidas. Permite GET general y, exclusivamente en
la ruta exacta `/quotations`, POST JSON con `Content-Type` y su preflight. No
permite POST en otras rutas, credenciales ni cabeceras personalizadas adicionales;
CORS no es autenticación ni impide que un cliente HTTP use las rutas existentes.

Compose configura solo en API los orígenes locales explícitos
`http://localhost:4321,http://127.0.0.1:4321`. Para una API fuera de Compose,
exporta la variable antes de arrancarla. Para sustituirlos en Compose, define
`CORS_ALLOWED_ORIGINS` en el entorno o `.env` raíz y recrea el servicio API con
su configuración actualizada. Un valor explícitamente vacío conserva la lista
vacía. Revisa `docker compose config` antes de arrancar.

### Preparar Cloudflare Pages

Este repositorio prepara una web estática; no publica ni proporciona alojamiento
para FastAPI, PostgreSQL o RabbitMQ. Antes de publicar necesitas una API **HTTPS**
independiente y accesible públicamente, y configurar en esa API los orígenes
concretos del frontend. Sustituye los placeholders siguientes por tus valores:

| Ajuste de Pages | Valor |
| --- | --- |
| Directorio raíz | `frontend` |
| Comando de build de Astro | `npm run build` |
| Directorio de salida | `dist` |
| Versión Node | `NODE_VERSION=24` |
| Variable pública de build | `PUBLIC_API_BASE_URL=https://<api-publica>` |

Para garantizar la instalación bloqueada con `npm ci`, configura también
`SKIP_DEPENDENCY_INSTALL=1` y usa **`npm ci && npm run build`** como comando de
build de Pages. Así se desactiva su instalación automática y se utiliza el
lockfile del repositorio. La opción está documentada en la
[imagen de build oficial de Pages](https://developers.cloudflare.com/pages/configuration/build-image/#skip-dependency-install).
Configura las variables tanto para producción como para los previews que uses.

En el backend, un ejemplo de allowlist de producción es:

```dotenv
CORS_ALLOWED_ORIGINS=https://<proyecto>.pages.dev,https://<dominio-propio>
```

Cada preview que deba leer la API necesita añadir su origen exacto, por ejemplo
`https://<identificador-preview>.<proyecto>.pages.dev`; no se admite `*.pages.dev`.
Los orígenes no llevan rutas ni `/` final. Si cambia la URL API, recompila y
publica el nuevo `dist`; si cambia un origen frontend, actualiza la allowlist y
reinicia la API. El alojamiento estático de Pages y el despliegue de la API son
operaciones independientes y no se ejecutan como parte de esta preparación.

## Arrancar

Necesitas Docker con Docker Compose. Ejecuta Compose desde la raíz del repositorio:

Una instalación nueva usa el proyecto Compose `locker-management-demo` y la base,
usuario y contraseña PostgreSQL locales `locker_management_demo`; RabbitMQ usa
el mismo usuario y contraseña de demostración. Si ya tienes datos,
aplica primero la [transición de identidad](#transición-de-identidad-en-instalaciones-existentes).

```bash
docker compose up --build
```

Compose espera a que PostgreSQL esté preparado, ejecuta `alembic upgrade head`
en el servicio `migrate` y arranca la API cuando la migración termina correctamente.
También sirve el frontend estático con Nginx, sin depender del arranque de la API.
Abre [el mapa de lockers](http://127.0.0.1:4321); no hace falta ejecutar npm aparte.
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

### Transición de identidad en instalaciones existentes

Antes del primer arranque con este nombre, haz una copia de seguridad. El nuevo
proyecto predeterminado selecciona otros volúmenes; cambiar `POSTGRES_*` o
`RABBITMQ_DEFAULT_*` tampoco modifica los usuarios ni credenciales ya existentes.

Identifica el proyecto anterior, ambos contenedores y sus volúmenes reales:

```bash
docker compose ls
# Sustituye PROYECTO_ANTERIOR por el nombre encontrado.
docker compose -p PROYECTO_ANTERIOR ps -q db rabbitmq
# Guarda los IDs y comprueba los volúmenes montados de cada contenedor.
docker inspect CONTENEDOR_DB CONTENEDOR_RABBITMQ --format '{{.Id}} {{json .Mounts}}'
docker volume inspect VOLUMEN_POSTGRES_EXISTENTE VOLUMEN_RABBITMQ_EXISTENTE
# Guarda también la identidad del nodo del broker.
docker compose -p PROYECTO_ANTERIOR exec rabbitmq rabbitmq-diagnostics -q status
# Detén únicamente los escritores, manteniendo PostgreSQL y RabbitMQ en marcha.
docker compose -p PROYECTO_ANTERIOR stop api worker
```

Comprueba las etiquetas `com.docker.compose.project` y `com.docker.compose.volume`
de ambos volúmenes: deben corresponder al proyecto anterior y, respectivamente,
a `postgres_data` y `rabbitmq_data`. Sin personalizaciones, el proyecto era
`hexagonal_architecture` y los volúmenes `hexagonal_architecture_postgres_data`
y `hexagonal_architecture_rabbitmq_data`; si usaste `-p` o `COMPOSE_PROJECT_NAME`,
conserva los valores reales verificados.

Guarda la selección en el archivo local `.env` de la raíz, ignorado por Git.
Este ejemplo corresponde únicamente a los valores originales; sustitúyelos si
tu instalación tenía otros:

```dotenv
COMPOSE_PROJECT_NAME=hexagonal_architecture
POSTGRES_USER=hexagonal
POSTGRES_PASSWORD=hexagonal
POSTGRES_DB=hexagonal
RABBITMQ_DEFAULT_USER=hexagonal
RABBITMQ_DEFAULT_PASS=hexagonal
```

Para API, worker y Alembic ejecutados fuera de Compose, exporta las conexiones
existentes en esa terminal; `uv run` no carga automáticamente ese `.env`:

```bash
export DATABASE_URL='postgresql+asyncpg://hexagonal:hexagonal@localhost:5432/hexagonal'
# Usa el host/puerto reales del broker accesible desde esa terminal.
export RABBITMQ_URL='amqp://hexagonal:hexagonal@localhost/'
```

Revisa `docker compose config`: las URLs PostgreSQL de `api`, `migrate` y `worker`
deben coincidir con `db`, y las URLs AMQP de API/worker con `rabbitmq`. Los nombres
físicos de `volumes.postgres_data` y `volumes.rabbitmq_data` deben ser los existentes
comprobados. La salida contiene las contraseñas configuradas; consérvala localmente.
También puedes fijar el proyecto con `-p` en **cada** comando. Antes de continuar,
verifica que la configuración de `db` y `rabbitmq` coincide con la existente para
que Compose conserve sus contenedores. Arranca la configuración revisada:

```bash
docker compose config
docker compose up --build
```

Durante esta transición no ejecutes `down` ni `--force-recreate`, ni recrees el
broker para aplicar el nombre. Comprueba después los IDs, montajes e identidad de
nodo con los mismos comandos: el contenedor y nodo RabbitMQ deben ser los mismos,
y ambos volúmenes físicos deben conservarse. Si Compose propone recrear el broker,
detén la transición y revisa la configuración conservada antes de continuar.

Comprueba los registros existentes y la revisión con
`docker compose run --rm migrate alembic current`, y prueba una cotización nueva.
La transición de nombre no requiere otra revisión Alembic. Esta comprobación
supone una instalación ya en el head actual `0005`; las versiones de esquema
anteriores siguen el procedimiento de
[migración segura](#base-de-datos-de-la-versión-anterior). No se añade recuperación
ni migración de mensajes; se conserva el comportamiento actual de RabbitMQ.
Conserva proyecto, credenciales y URLs explícitos también si reviertes el cambio
de contenido. Cambiar un valor predeterminado no mueve ni recupera datos. No
borres, copies ni renombres los volúmenes, la base o los roles para esta transición.

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
from application.quotations.comparison import ShippingQuoteComparator
from domain.lockers import Dimensions
from domain.shipping_quotes import ShippingQuoteRequest


async def main() -> None:
    comparator = ShippingQuoteComparator([
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
pertenecen a `application.quotations.models`; las solicitudes, ofertas y
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
locker-management-demo/
├── backend/
│   ├── main.py
│   ├── worker.py
│   ├── domain/
│   │   ├── deliveries.py
│   │   ├── returns.py
│   │   ├── lockers.py
│   │   └── shipping_quotes.py
│   ├── application/
│   │   ├── deliveries/
│   │   │   ├── ports.py
│   │   │   └── use_cases.py
│   │   ├── returns/
│   │   │   ├── ports.py
│   │   │   └── use_cases.py
│   │   ├── lockers/
│   │   │   ├── ports.py
│   │   │   └── use_cases.py
│   │   └── quotations/
│   │       ├── models.py
│   │       ├── ports.py
│   │       ├── errors.py
│   │       ├── comparison.py
│   │       └── use_cases.py
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
Delivery, Return, Locker y Quotation tienen paquetes propios en aplicación.
Cada área agrupa sus casos de uso en `use_cases.py` y los puertos de salida que
consume en `ports.py`. Las entidades y reglas permanecen en dominio, incluidas
las reglas compartidas de asignación y capacidad de Locker. Cada flujo conserva
sus validadores y errores de dominio; los servicios de entregas y devoluciones
declaran el error de registro inexistente junto a sus casos de uso. HTTP agrupa
rutas y esquemas en paquetes por área y conserva `request_validation.py` para los cuerpos de las acciones. La conexión,
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
| `backend/application/deliveries/use_cases.py` y `backend/application/returns/use_cases.py` | Servicios `DeliveryService` y `ReturnService`; crean, listan y registran salidas con reloj explícito y puertos de persistencia. Declaran `DeliveryNotFoundError` y `ReturnNotFoundError`. |
| `backend/application/lockers/use_cases.py` | Casos de uso de configuración y disponibilidad de lockers. |
| `backend/application/{deliveries,returns,lockers}/ports.py` | Protocolos de repositorio propiedad del área de aplicación que los consume. |
| `backend/application/quotations/models.py` | `Quotation`, sus estados y errores de proceso, y `ProviderResult`, `ProviderStatus` y `ProviderErrorCode`; independientes del comparador. |
| `backend/application/quotations/ports.py` | Contratos de salida `ShippingProvider`, `QuotationRepository` y `QuotationPublisher`. |
| `backend/application/quotations/errors.py` | Errores compartidos de persistencia, publicación, envío y fallo técnico de proveedor. |
| `backend/application/quotations/comparison.py` | `ShippingQuoteComparator` compara proveedores inyectados y normaliza sus resultados. |
| `backend/application/quotations/use_cases.py` | `QuotationService` envía y consulta solicitudes; `QuotationProcessor` ejecuta la comparación y guarda resultados. |
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

Los puertos de salida usan `Protocol` y pertenecen al paquete de aplicación que
los consume: `deliveries/ports.py`, `returns/ports.py`, `lockers/ports.py` y
`quotations/ports.py`. Permiten trabajar con repositorios, proveedores y publicación
sin depender de implementaciones concretas. El dominio conserva datos, entidades
y reglas y no depende de aplicación. Los modelos de cotización dependen solo de
la biblioteca estándar y del dominio; los adaptadores importan esos modelos desde
`application.quotations.models` y los errores desde `application.quotations.errors`.
Los paquetes tienen `__init__.py` vacíos: cada consumidor importa desde el módulo
propietario, sin reexports ni wrappers de compatibilidad. Los consumidores Python
deben actualizar las rutas anteriores y usar `ShippingQuoteComparator`.

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
uv sync --locked --extra dev
uv run alembic upgrade head
```

La API y Alembic usan `DATABASE_URL`. Si no se define, ambos conectan a
`postgresql+asyncpg://locker_management_demo:locker_management_demo@localhost:5432/locker_management_demo`.

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

## CI del backend y comprobaciones locales

El workflow `.github/workflows/backend-ci.yml` ejecuta cinco checks independientes
para todas las PR dirigidas a `main` y cada push a `main`, sin filtros por rutas.
Los jobs corren en paralelo, tienen tiempos máximos y cancelan una ejecución
anterior de la misma PR cuando llega otro commit. Usa permisos de lectura y
caché de uv; la instalación bloqueada comprueba siempre `backend/uv.lock`.

| Check | Comprobación | Dependencias |
| --- | --- | --- |
| `Ruff` | Lint, imports y formato sin modificar archivos. | Python 3.11. |
| `Pyright` | Análisis configurado, cero errores y advertencias. | Python 3.11, sin servicios. |
| `Unit tests` | `tests/unit`, dominio, aplicación y adaptadores aislados. | Python 3.11, sin URLs de test ni servicios. |
| `PostgreSQL integration` | `tests/integration`, persistencia, API y migraciones Alembic. | Python 3.11, PostgreSQL 17 temporal y `TEST_DATABASE_URL` explícita; sin RabbitMQ. |
| `Docker smoke` | Construcción bloqueada, migraciones y `GET /lockers` → HTTP 200 con `[]` en una base nueva. | Imagen Python 3.13, Docker Compose, PostgreSQL y RabbitMQ temporales. |

Para reproducir los checks Python desde `backend/`, instala uv y Python 3.11 y
usa las dependencias bloqueadas. CI fija uv 0.13.1 y Docker usa la misma versión.

```bash
uv sync --python 3.11 --locked --extra dev
export UV_LOCKED=1
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pyright --project .. --warnings
env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL \
  uv run --extra dev python -m unittest discover -s tests/unit -t . -v
# Base dedicada, con permisos para crear/eliminar esquemas; sin broker.
env -u TEST_RABBITMQ_URL \
  TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@localhost:5432/locker_management_demo_test' \
  uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f
```

`UV_LOCKED=1` evita que `uv run` cambie silenciosamente la resolución. Las URLs,
la preparación de la base de pruebas y el comando de la suite completa se explican
en [Pruebas](#pruebas). Actions selecciona unitarias e integración; la suite
completa local también incluye `tests/messaging` y requiere ambas URLs de test.
Los cinco checks no configuran por sí mismos la protección de `main`.

Ruff usa `backend/pyproject.toml`: Python 3.11, longitud 88 y reglas `E4`, `E7`,
`E9`, `F` e `I`. Analiza producción y tests, incluido `migrations/env.py`.
Solo excluye exactamente las cinco revisiones históricas `0001`–`0005`, también
si se pasan sus rutas explícitamente; las revisiones futuras se analizan.
Para aplicar correcciones seguras e igualar el formato local, desde `backend/`:

```bash
uv run --locked --extra dev ruff check --fix .
uv run --locked --extra dev ruff format .
```

Revisa el diff antes de integrar, especialmente los imports que registran modelos
SQLModel. CI ejecuta únicamente las variantes de comprobación.

Para reproducir Docker smoke desde la raíz necesitas Docker y Docker Compose
**2.24.0 o superior**, con soporte para `!reset`:

```bash
scripts/ci/smoke.sh
```

El script combina `compose.yaml` y `compose.ci.yaml`, genera un proyecto temporal
con volúmenes nuevos y construye/arranca API, migraciones, PostgreSQL y RabbitMQ.
Espera el arranque hasta 120 segundos y la respuesta HTTP interna hasta 60 segundos.
No publica puertos ni arranca el worker; comprueba también el acceso al esquema
migrado. En caso de fallo muestra estado y logs, devuelve un código no cero y
limpia solo contenedores, red y volúmenes de ese proyecto temporal, conservando
los datos de desarrollo. No requiere URLs ni credenciales externas.

## Cierre de cambios OpenSpec

Antes de integrar en `main`, no debe quedar ningún directorio activo directamente
en `openspec/changes`, salvo `archive`. Las propuestas, los cambios sin tareas y
los que tienen todas sus tareas completadas siguen activos hasta archivarse;
también cuentan los directorios ocultos y los enlaces a directorios. Los archivos
auxiliares y el contenido de `archive` no afectan a esta comprobación.

Desde la raíz del repositorio, ejecuta el mismo comando que CI:

```bash
scripts/ci/check-openspec-closed.sh
```

El comando lista todos los cambios activos y falla si encuentra alguno o no puede
inspeccionar el directorio. No necesita OpenSpec ni servicios y no modifica el
checkout. Antes del merge, completa y verifica la implementación, valida el cambio
con `openspec validate NOMBRE --strict`, sincroniza sus deltas con las specs
principales y valida el resultado con `openspec validate --specs --strict`.
Después archiva localmente el cambio, preservando sus tareas y evidencia, y repite
la comprobación. Marcar tareas como completas no sustituye sincronizar y archivar.

El workflow `OpenSpec CI` publica el check independiente **OpenSpec closure** para
todas las PR dirigidas a `main`, sin filtros por rutas, al abrirlas, reabrirlas o
actualizarlas. Un push a una rama con una PR abierta hacia `main` vuelve a ejecutar
el check mediante el evento `pull_request` de tipo `synchronize`. Los commits
locales y los pushes sin PR, incluidos los de ramas nuevas y los pushes directos
a `main`, no ejecutan este workflow. Para bloquear merges que incumplan esta
política, configura **OpenSpec closure** como
check requerido en las reglas de protección de `main`; el workflow no configura
esas reglas ni archiva cambios automáticamente. Los cinco checks del backend
conservan su funcionamiento.

## Tipos: Pyright y Pylance

El extra `dev` incluye Pyright, fijado en `uv.lock`. Desde `backend/`:

```bash
uv sync --locked --extra dev
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
uv sync --locked --extra dev
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
TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@localhost:5432/locker_management_demo_test' \
  uv run --extra dev python -m unittest discover -s tests/integration -t . -v -f

# Suite completa, incluyendo mensajería (necesita ambas URLs).
TEST_RABBITMQ_URL='amqp://test_user:test_password@localhost/locker_management_demo_test' \
TEST_DATABASE_URL='postgresql+asyncpg://test_user:test_password@localhost:5432/locker_management_demo_test' \
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
  -e TEST_DATABASE_URL=postgresql+asyncpg://locker_management_demo:locker_management_demo@db:5432/locker_management_demo_test \
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

`application/quotations/models.py`, `ports.py`, `errors.py`, `comparison.py` y
`use_cases.py` separan el estado persistido y los resultados, los contratos de
salida, los errores compartidos, la comparación y los casos de uso. Los adaptadores
son `adapters/database/sqlmodel_quotations.py`, `adapters/http/quotations/` y
`adapters/queue/rabbitmq.py`; `main.py` compone API y `worker.py` el proceso de
trabajo. API comparte servicios por instancia y cierra motor y broker incluso
si falla el arranque. Solo el worker llama a `ShippingQuoteComparator.compare`.

`docker compose up --build` inicia el frontend estático Nginx, PostgreSQL,
migraciones, RabbitMQ 4, API y **un único worker**. API/worker esperan migraciones correctas y broker saludable;
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
