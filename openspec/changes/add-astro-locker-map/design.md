# Design

## Context

Ver `proposal.md`. El frontend estático y las cotizaciones asíncronas existen. Las dos pestañas y el seguimiento mínimo por UUID están implementados. El usuario ha aprobado sustituir las direcciones por selección de lockers de recogida/entrega, separar la búsqueda geográfica y trasladar la comparación al menú principal con resultados a la derecha. `shipping-quotes` y `asynchronous-shipping-quotations` definen los contratos que se reutilizan; API/worker ya componen tres proveedores simulados.

## Goals / Non-Goals

**Goals:** mantener Astro estático, interacción en navegador y fronteras hexagonales; reutilizar los datos del paquete y cotizaciones persistidas existentes sin cambiar su contrato, y conservar el seguimiento mediante los puertos de lectura existentes. La selección por UUID pertenece al navegador; no amplía el contrato postal de cotización.

**Non-Goals:** SSR/proxy, cambios de dominio o persistencia, proveedores reales, reservas, pago/contratación o validación de encaje en celdas. Editar datos no cotiza automáticamente; solo «Comparar envíos» crea una solicitud. No se publica en Cloudflare ni se proporciona alojamiento al backend.

## Decisions

### 1. Build Astro estático

Crear `frontend/` con `output: 'static'`, TypeScript estricto y Leaflet importado solo por código de navegador. Astro genera el documento español y estructura de la interfaz; JavaScript carga y valida los lockers, calcula disponibilidad y gestiona mapa y paneles. El build no consulta la API ni incorpora snapshots o fixtures de lockers. CSS, iconos y scripts se empaquetan localmente; no hace falta React/Vue.

Node 24 LTS se utiliza exclusivamente para herramientas. Fijar dependencias compatibles en `package-lock.json`, instalar con `npm ci` y ofrecer scripts `dev`, `check`, `build`, `preview`, `test` y `test:e2e`. La salida `dist` debe funcionar servida por cualquier servidor HTTP estático. Desarrollo y preview local usarán el puerto 4321 para compartir los orígenes documentados.

### 2. Conexión directa configurada al compilar

`PUBLIC_API_BASE_URL` se incorpora a los assets en build time: es una URL pública, no un secreto. `frontend/.env.example` propone explícitamente `http://127.0.0.1:8000` para uso local, sin fallback oculto en código. En producción debe apuntar a una API HTTPS accesible desde el navegador; el nombre de servicio Docker `api` no sirve como URL pública. Cambiar la variable requiere recompilar y volver a publicar los archivos.

El cliente valida la URL configurada antes de consultar: HTTP(S), sin credenciales, query ni fragmento; construye la ruta de lockers de forma determinista. Si falta o es inválida, o si la página HTTPS apunta a HTTP, muestra un error de configuración sin pedir datos. Una configuración local HTTP explícita permite probar `dist` contra otro origen local. La aplicación no conoce ni necesita la URL definitiva durante esta planificación.

Usar fetch GET con `credentials: 'omit'`, `cache: 'no-store'`, sin headers personalizados y `AbortController` con cinco segundos para completar la lectura. La carga inicial y cada reintento hacen una nueva petición; no almacenar disponibilidad en localStorage, service worker o caché propia. Red/CORS, HTTP no exitoso, timeout o payload malformado se reflejan como errores en la interfaz, sin inventar códigos de respuesta. El navegador no distingue de forma fiable CORS de otros fallos de red: el mensaje no afirmará una causa que desconoce.

### 3. CORS limitado a la capa HTTP

Usar el middleware CORS estándar de FastAPI/Starlette, configurado en el punto de composición; si se necesita un helper, ubicarlo en `backend/adapters/http/cors.py`. `CORS_ALLOWED_ORIGINS` contendrá orígenes exactos HTTP(S) separados por comas, recortando espacios. Ausente o vacío significa lista vacía. Rechazar comodines, credenciales, rutas, query, fragmentos y entradas inválidas con diagnóstico claro. No usar expresiones que admitan todos los proyectos `pages.dev`.

Conservar GET general y permitir además POST con `Content-Type: application/json` únicamente en la ruta exacta `/quotations`, con los mismos orígenes y `allow_credentials=False`. Un adaptador ASGI pequeño en `backend/adapters/http/cors.py` puede elegir entre dos instancias de `CORSMiddleware` según la ruta; `main.py` lo compone. No ampliar `allow_methods` globalmente. GET `/quotations/{id}` usa la política general; no hace falta exponer `Location`, pues el id viene en JSON. Mantener denegados preflight POST `/lockers` y otras escrituras, métodos y headers no requeridos. CORS controla exposición/preflight, no autentica ni bloquea clientes HTTP directos. Probar orígenes permitidos/denegados, ambas rutas, JSON, configuración vacía/inválida y ausencia de `Origin`.

`compose.yaml` solo pasa esta variable al servicio API, con valores locales explícitos por defecto `http://localhost:4321,http://127.0.0.1:4321`. Para producción se sustituirán por el origen Pages concreto y/o dominio propio. Un preview de Pages necesita autorizar explícitamente su origen si debe acceder al backend. El backend y sus volúmenes siguen gestionados por el Compose existente.

### 4. Disponibilidad y representación

Validar en el cliente los campos usados a partir de `unknown`: lista, UUID, activo booleano, alias/dirección nullable y estados booleanos de celdas. Una forma esencial inválida invalida la carga; coordenadas null, incompletas, no numéricas, no finitas o fuera de rango conservan el locker como no posicionable. No convertir valores falsy ni cadenas en booleanos.

`freeCount` cuenta `enabled === true && occupied === false`; disponible requiere además `active === true`. UUID permanece como identidad interna. Conservar todos los disponibles para el selector compacto, incluidos los que no tienen coordenadas. Mostrar alias o dirección y, si faltan, una etiqueta neutra numerada; distinguir etiquetas repetidas sin una ficha técnica con UUID/celdas. Conservar `postalCode: string | null` desde `address.postal_code` estructurado, válido solo con país ES y cinco dígitos ASCII. Un CP ausente/inválido requiere entrada manual para cotizar; nunca analizar la dirección formateada ni deducirlo de coordenadas/Photon. Usar DOM/textContent para todos los datos externos. La disponibilidad no implica encaje ni reserva.

### 5. Mapa, selección de lockers y cotización

Leaflet conserva teselas OSM con atribución, vista inicial peninsular aproximadamente `[35.8, -9.4]` a `[43.9, 3.4]`, rueda y controles de zoom. Península, islas, Ceuta y Melilla siguen accesibles mediante navegación y selección; no reaparece «Ver España». El mapa ocupa `100dvh` con fallback `100vh`, conserva su encuadre durante cargas y no desplaza coordenadas reales para separar lockers coincidentes. Los paneles no cambian sus dimensiones.

Un pequeño panel geográfico precede a las pestañas «Cotizar envío» y «Localizar paquete». Cotización, inicialmente activa, reúne los selectores «Locker de recogida»/«Locker de entrega», los CP que correspondan, Largo/Ancho/Alto (cm), Peso (kg), «Comparar envíos» y contadores vivos al final. Seguimiento conserva UUID, acción y resultado propios. Mantener retirados el catálogo técnico, sección de éxito, «Ver lockers», «Actualizar», hora y nota informativa. Carga, vacío, error/reintento y aviso de teselas aparecen solo cuando proceda; no añadir polling de disponibilidad.

#### Búsqueda geográfica independiente

Reutilizar una instancia de `LocationSearch.astro`/`setupAutocomplete` fuera de los paneles de pestaña. Conservar mínimo de tres caracteres, debounce de 350 ms, hasta cinco sugerencias, selección explícita incluso con una, timeout de cinco segundos, cancelación/generación y reintento manual. Dirección usa `https://photon.komoot.io/api/?q=...&countrycode=ES&limit=5`; cinco dígitos ASCII usan `/structured?postcode=...&countrycode=ES&limit=5`, manteniendo ceros iniciales. Photon es un servicio público de demostración sin garantía de disponibilidad; no añadir claves, proxy ni Nominatim. Su acceso real/CORS no están verificados en esta red.

Elegir una sugerencia rellena solo ese buscador, centra/marca su zona (zoom aproximado 16 para dirección y 13 para CP) y cierra sin otra petición. No completa CP, selecciona lockers, cambia pestaña, invalida cotizaciones ni modifica seguimiento. El CP que pueda conservar el helper geográfico no se utiliza para el formulario. Las ubicaciones arbitrarias se encuentran aquí; los selectores locales no prometen búsqueda por proximidad ni consultan Photon.

Mantener normalización de GeoJSON desde `unknown`, solo puntos finitos españoles, texto seguro y estados independientes. La animación breve de sugerencias respeta `prefers-reduced-motion`; Escape/foco/blur/clic seguros, cierre inmediatamente inerte y generaciones de animación evitan reaperturas obsoletas. No formularios anidados ni validación numérica sobre campos de búsqueda. Cambiar de pestaña cierra/cancela sugerencias pendientes, conserva el texto geográfico y no consulta de nuevo.

#### Selecciones locales por rol y popup

Ambos selectores usan la colección de lockers disponibles ya cargada, incluidos los no posicionables. Filtrar localmente por etiqueta, dirección o CP registrados, sin distinguir mayúsculas y sin llamadas HTTP. Una lista compacta con scroll y teclado permite acceder a todos los candidatos coincidentes; no truncar permanentemente lockers con etiquetas o posiciones iguales. Los resultados siempre representan lockers, y su identidad es el UUID, nunca el texto o las coordenadas. La etiqueta neutra existente identifica también registros sin alias/dirección.

Mantener por rol el locker seleccionado, texto de búsqueda y CP suplementario. Seleccionar un candidato o una acción de popup fija ese rol y no altera el otro ni los datos del paquete. Editar el texto de un rol invalida inmediatamente su UUID, CP derivado/manual y comparación previa, aunque después se vuelva a escribir la misma etiqueta. Elegir otro UUID limpia su suplemento manual; no transferir CP entre roles o lockers. Mantener la selección actual sin borrados espurios al abrir/cerrar sugerencias o volver a elegir el mismo UUID. En una nueva carga, dejar de ofrecer selecciones que ya no estén disponibles y descartar sus resultados anteriores. No filtrar por tamaño del paquete ni prometer compatibilidad/stock reservado.

Pulsar un marcador disponible, también con Enter/Espacio, abre un popup con nombre, dirección registrada o ausencia y los botones «Seleccionar como locker de entrega» y «Seleccionar como locker de recogida». Abrirlo no cambia roles, pestaña o cotización. Una acción explícita activa cotización si es necesario, fija el rol, cierra el popup y dirige el foco a su selección en el menú. Escape/cerrar devuelve foco al marcador cuando exista; encuadrar el popup y permitir scroll interno en pantallas pequeñas, sin omitir las acciones por falta de espacio. Usar DOM/textContent para el contenido externo y aislar eventos del mapa. Los selectores permiten elegir individualmente puntos coincidentes sin desplazar coordenadas.

El enlace de salto activa cotización y enfoca el selector de recogida del menú, sin abrir resultados. Los marcadores de seguimiento conservan su relación actual/histórica; si su UUID coincide con un locker actualmente disponible, las acciones pueden usar ese registro disponible, nunca asumir disponibilidad de los metadatos de tracking. Sin esa correspondencia, el marcador de seguimiento es informativo y no ofrece selección. Pulsar un marcador nunca cambia de modo por sí solo. Esta excepción de acción expresa sustituye la prohibición anterior absoluta en seguimiento.

#### CP y validación del paquete

Para cada rol, el CP estructurado del locker (ES y cinco dígitos ASCII) se muestra sin editar. Si falta o es inválido, mostrar «CP del locker no registrado» y pedir un suplemento manual para esa selección; no inferirlo desde etiquetas, Photon o coordenadas ni guardar cambios en la API. Los dos CP son obligatorios, conservan ceros iniciales y pertenecen al rol/UUID escogido. Los seeds con dirección null quedan así utilizables sin inventar sus direcciones.

Los cuatro campos existentes empiezan vacíos y permanecen locales. Convertir decimal exacto ancho→`width_mm`, alto→`height_mm`, largo→`depth_mm` (cm×10) y peso→`weight_grams` (kg×1000); exigir enteros 1–2000 mm y 1–30000 g sin redondeo silencioso. «Comparar envíos» se habilita solo con los dos UUID vigentes, ambos CP y las cuatro medidas válidos, y sin solicitud/espera en curso. Mostrar errores junto a los campos y revalidar en submit para impedir envíos por Enter o eventos programáticos inválidos. Seleccionar, editar o buscar no envía automáticamente.

La API recibe exclusivamente países ES, CP y medidas/peso mediante el contrato existente; no `locker_id`, direcciones ni otros extras. Los UUID de origen y destino forman parte de la instantánea local junto al payload, por lo que cambiar de locker invalida resultados incluso si conserva el mismo CP. Esto contextualiza una simulación postal y no crea un traslado entre instalaciones ni verifica encaje en celdas.

#### Panel de resultados y asincronía

El panel derecho, cerrado inicialmente, contiene solo estado/referencia, tarjetas, aviso de simulación y cierre/continuación; se eliminan su selector, CP y botón de comparación. Comparar explícitamente abre resultados y anuncia el estado; cerrar/Escape restaura foco al botón principal y detiene espera local sin borrar los campos. En móvil se superpone abajo con scroll interno; preservar acceso al menú, popup, pestañas y atribución a 375×480 sin desbordamiento. Las acciones de lectura de una referencia conocida deben seguir accesibles tras cerrar/volver, solo para la instantánea vigente, y nunca crear un POST como efecto de reabrir resultados.

Reutilizar `quotations.ts` y `quotation-api.ts`: POST JSON `/quotations` con credenciales omitidas y timeout de cinco segundos, aceptación 202/id validada y bloqueo de doble envío; GET `/quotations/{id}` secuencial aproximadamente cada segundo con `no-store`, timeout de cinco segundos y límite local de treinta segundos. Validar id, solicitud, estados y ofertas desde `unknown`. PENDING/PROCESSING esperan; COMPLETED/FAILED detienen polling. Error de lectura o plazo agotado permite «Seguir consultando» el mismo UUID sin POST nuevo. Cerrar o cambiar de modo cancela el trabajo local y permite continuar explícitamente solo si la instantánea no cambió.

Editar cualquier selección, CP o medida invalida instantánea, ofertas, referencia reanudable y generación; abortar peticiones y no permitir que una respuesta antigua reabra resultados. Distinguir error 422, creación incierta y fallo de proceso; POST fallido nunca se reintenta automáticamente. Si 503 incluye PUBLISH_ERROR/id, conservarlo para lectura explícita mientras los datos sigan vigentes. La cancelación no elimina registros ni cancela el worker.

Mostrar todos los proveedores/servicios devueltos, precio EUR desde céntimos y rango en días sin reinterpretar su tipo. Conservar QUOTED/NOT_COVERED/FAILED y éxito parcial; todos los proveedores fallidos no convierten COMPLETED en fallo de proceso. Identificar claramente la simulación, sin marcas inventadas, ranking, reservas o garantías de cobertura. El fallo de teselas no impide seleccionar cualquiera de los dos roles o cotizar.

### 6. Nginx estático y arranque completo con Compose

Añadir `frontend/Dockerfile` multietapa: Node 24 instala el lockfile con `npm ci` y ejecuta el build Astro; la etapa final Nginx Alpine copia únicamente `dist` al directorio de archivos públicos. La imagen final no incluye Node, npm, fuentes o dependencias de desarrollo. La configuración estática predeterminada de Nginx basta para esta página; no añadir proxy, SSR ni sustitución de variables durante el arranque. El build y la página estática funcionan sin que la API esté disponible.

`PUBLIC_API_BASE_URL` se pasa como argumento de build con defecto local `http://127.0.0.1:8000`, también configurable desde Compose. Debe ser alcanzable por el navegador, nunca el hostname interno `api`. `.dockerignore` excluye `node_modules`, `dist`, `.astro`, resultados de pruebas y archivos `.env` locales, para que el build use el argumento explícito. Cambiarlo requiere reconstruir la imagen; una variable de runtime no reescribe los assets.

Añadir `frontend` al arranque por defecto de `compose.yaml`, con contexto `./frontend` y puerto `127.0.0.1:4321:80`. No necesita dependencias de arranque: Nginx puede servir la interfaz mientras el cliente trata los estados de disponibilidad de API. La API tampoco depende del frontend. Los orígenes CORS actuales ya incluyen el puerto 4321. `compose.ci.yaml` resetea además los puertos de frontend; el smoke backend existente sigue seleccionando solo sus servicios.

README presenta `docker compose up --build` como arranque completo y conserva npm como desarrollo opcional. Explicar URL pública de build, reconstrucción al cambiarla y que npm/preview y Compose no pueden ocupar simultáneamente el puerto 4321. El mismo `dist` sigue siendo válido para Pages; no cambian los requisitos de despliegue público.

### 7. Preparación de Cloudflare Pages y archivos afectados

Documentar raíz del proyecto `frontend`, build `npm run build`, directorio de salida `dist`, Node 24 y variable de build `PUBLIC_API_BASE_URL=https://<api-publica>`. La instalación debe usar el lockfile con `npm ci`; en Pages documentar la opción de desactivar la instalación automática y usar `npm ci && npm run build` si resulta necesaria para garantizar ese comando. Ningún comando publica desde esta tarea. Los placeholders de API, proyecto Pages y dominio propio se resolverán al preparar el despliegue real. La URL pública de la API y su allowlist CORS son prerrequisitos separados del alojamiento estático gratuito.

| Área | Rutas previstas |
| --- | --- |
| Astro y configuración | `frontend/package.json`, `frontend/package-lock.json`, `frontend/astro.config.mjs`, `frontend/tsconfig.json`, `frontend/.env.example` |
| Interfaz | `frontend/src/pages/index.astro`, `frontend/src/components/LockerExplorer.astro`, `frontend/src/scripts/locker-map.ts`, `frontend/src/styles/` |
| Datos en navegador | `frontend/src/lib/lockers.ts`, `frontend/src/lib/locker-api.ts` |
| Pruebas frontend | `frontend/tests/` y configuración Vitest/Playwright |
| CORS backend | `backend/main.py`, posible `backend/adapters/http/cors.py`, `backend/tests/unit/test_main.py` o prueba HTTP específica |
| Contenedor estático | `frontend/Dockerfile`, `frontend/.dockerignore` |
| Integración/documentación | `compose.yaml`, `compose.ci.yaml`, `.gitignore`, `README.md` |

Los ignores cubrirán `node_modules`, `.astro`, `dist` y resultados de pruebas conservando lockfile y `.env.example`. La ampliación de Compose no cambia código de interfaz, contratos API, migraciones ni workflows.

La ampliación de pantalla completa se limita a `frontend/src/pages/index.astro`, `frontend/src/components/LockerExplorer.astro`, `frontend/src/styles/global.css`, `frontend/src/scripts/locker-map.ts`, `frontend/tests/e2e/explorer.spec.ts` y una nota de uso en `README.md`. No modifica configuración de despliegue, dependencias ni backend.

La ampliación de navegación y generador afecta al componente, script y CSS del mapa; añade `frontend/src/lib/geocoder.ts` y sus pruebas, amplía los E2E y documenta el uso en README. El generador añade `backend/scripts/seed_lockers.py`, `backend/scripts/data/spain.geojson`, un archivo de procedencia/licencia junto al dato y `backend/tests/unit/test_seed_lockers.py`. Añadir `COPY scripts ./scripts` en `backend/Dockerfile` para incluir el CLI y sus datos en la imagen API y permitir el comando manual de Compose tras reconstruirla. No necesita nuevas dependencias de producción, cambios Compose, dominio, API o migraciones.

La unificación de menús y sugerencias automáticas se limita a `frontend/src/components/LockerExplorer.astro`, `frontend/src/scripts/locker-map.ts`, `frontend/src/styles/global.css`, pruebas frontend afectadas y README. Reutilizar el helper geográfico y su contrato; no añadir dependencias ni modificar backend, Compose, generador o configuración de despliegue.

La ampliación pública de cotizaciones modifica `frontend/src/pages/index.astro`, `components/LockerExplorer.astro`, `scripts/locker-map.ts`, `styles/global.css` y `lib/lockers.ts`; añade los dos módulos de cotización y sus pruebas, adapta `tests/e2e/explorer.spec.ts` y `tests/cors_server.py`, y actualiza README. Backend solo cambia `backend/main.py`, `backend/adapters/http/cors.py` y pruebas CORS. No cambia dependencias, Compose, worker, contratos, dominio ni migraciones.

### 8. Generador manual de lockers de demostración

Crear un CLI Python con biblioteca estándar, invocable desde `backend/` mediante `uv run python scripts/seed_lockers.py` o, tras reconstruir la imagen API, con `docker compose exec api python scripts/seed_lockers.py`, apuntando al puerto 8000 del mismo contenedor. Opciones: `--count` positivo, por defecto 250; `--seed` entero, por defecto 42; `--base-url`, por defecto `http://127.0.0.1:8000`; y `--dry-run`, que imprime los payloads JSON sin efectuar ninguna petición. Validar opciones y cargar geografía antes de escribir. El script es un cliente externo del contrato HTTP, sin acceso directo a repositorios o base de datos y sin integrarse en startup/build.

Bundlear el extracto `ADM0_A3 == ESP` de [Natural Earth admin 0 a escala 1:10m](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson), fijando commit de origen y registrando procedencia y [dominio público](https://www.naturalearthdata.com/about/terms-of-use/) junto al archivo. El extracto inspeccionado contiene 23 polígonos e incluye península, islas, Ceuta, Melilla y Llívia. Muestrear con `random.Random(seed)` y rechazo contra esos polígonos, respetando huecos; comprobar también el par redondeado que se enviará. Una caja rectangular sin comprobar pertenencia no es suficiente. Los límites son generalizados: estos puntos son datos sintéticos, no instalaciones o direcciones reales; no se promete distribución idéntica por territorio ni precisión catastral.

Generar alias deterministas `DEMO-<seed>-<índice>`, `address: null`, coordenadas válidas y `active: true`. Una configuración sencilla de seis celdas habilitadas de 400×400×600 mm por locker basta; la API crea las celdas libres. La semilla reproduce los payloads y coordenadas con el mismo dato de referencia, no los UUID del servidor. No usar Photon para generar puntos ni inventar direcciones.

Enviar `POST /lockers` secuencialmente con timeout acotado, contando únicamente respuestas de creación confirmadas. Ante primer fallo o respuesta incierta, detenerse, informar del índice y número confirmado y salir con código no cero, sin reintentar escrituras, borrar existentes o simular rollback global. Otra ejecución añade nuevos registros, aunque repita semilla/alias: no se añade idempotencia. README muestra primero dry-run y después ejecución explícita contra una API de demostración; las comprobaciones escribirán solo en un stack desechable, nunca en los datos del usuario.

### 9. Verificación

Conservar las 39 tareas/evidencias previas. Para la selección de dos lockers:

- Unitarias de filtrado/identidad local, CP estructurado/suplementario por rol, edición y limpieza, habilitación del botón, instantánea con ambos UUID y conversiones/polling existentes. Cambiar entre lockers con el mismo CP debe invalidar ofertas y lecturas.
- E2E de buscador independiente, popup sin selección implícita, ambas acciones/roles, búsqueda local sin HTTP, lockers coincidentes/sin posición/CP y panel derecho sin formulario. Cubrir teclado, Escape/foco, movimiento reducido, scroll/encuadre y escritorio/375×480.
- Regresiones de seguimiento: cinco estados, independencia de marcadores/contadores, apertura de popup sin cambiar pestaña y transición solo por acción explícita para un registro disponible. Cubrir cancelación, respuesta obsoleta y ausencia de nuevas llamadas por selección o geografía.
- `npm run check`, `npm test`, `npm run build` con API apagada y E2E afectados. Smoke de navegador con Nginx/API/PostgreSQL/RabbitMQ/worker reales en stack desechable, comprobando POST/GET y CORS sin interceptar la API; al menos un CP suplementario, resultados coherentes y seguimiento conservado. No tocar datos del usuario ni repetir el seed masivo.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings` con cero errores y advertencias. Validación OpenSpec estricta y revisión independiente antes de completar las cuatro tareas.

Teselas/Photon controlados solo en pruebas; la conectividad externa real sigue sin verificarse. No ampliar suites backend, CI o servicios cuando no cambian.

### 10. Pestañas y seguimiento por UUID

Pestañas con `tablist`/`tab`/`tabpanel`, selección anunciada, foco y navegación de teclado; el contenido inactivo queda `hidden` e `inert`. Conservar los textos y selecciones de ambos lockers, búsqueda geográfica, medidas, CP y UUID de tracking al cambiar, sin persistencia ni envíos automáticos. Cancelar autocomplete geográfico, espera de cotización y lectura de tracking mediante sus controladores/generaciones; cerrar resultados/sugerencias/popup al cambiar y ocultar el marcador de tracking al salir de seguimiento. No cancelar ni borrar trabajo del worker. Volver permite acciones explícitas, incluida reanudación de una cotización conocida solo con su instantánea vigente.

Contrato estable: `GET /tracking/{id}` devuelve 200 con exactamente `{id, kind, status, locker_relation, locker_id, locker}`. `id` es UUID; `kind` es `delivery` o `return`; `status` conserva el enum del flujo. `locker_relation` es `current`, `last_known` o `unassigned`; `locker_id` es UUID/null; `locker` es null o `{location_id: string|null, address: Address|null, coordinates: Coordinates|null}`. Address conserva los seis textos públicos existentes y Coordinates latitude/longitude finitos en límites WGS84. No incluir nombres, teléfonos, tracking_number, compartimentos ni modelos completos de recepción.

AWAITING_PICKUP/AWAITING_CARRIER con asignación significan `current`; COLLECTED/RETURNED_TO_CARRIER/HANDED_OVER con asignación significan `last_known`. Sin asignación: `unassigned`, locker_id y locker null. Metadata ausente: conservar id y relación del locker, devolver locker null y mostrar «Datos del locker no disponibles». Dirección/coordenadas ausentes no se inventan. Usar metadata registrada actual del locker sin afirmar snapshot histórico; un plazo de recogida vencido no cambia estado. El resumen de locker no se filtra por activo/capacidad.

Nuevo `application/tracking/` con DTO y caso de lectura que recibe DeliveryRepository, ReturnRepository y LockerRepository existentes. Consultar ambos `get_by_id` una vez: ninguno→404; ambos→409 sin elegir arbitrariamente; uno→proyectar y consultar su locker si está asignado. UUID inválido→422 antes del caso de uso. Fallos de infraestructura no se convierten en 404. El adaptador `adapters/http/tracking/` define schema/router; `main.py` reutiliza instancias de repositorios y `adapters/http/routes.py` admite el servicio opcional para preservar consumidores actuales. No añadir repositorios, migraciones, estados de dominio ni llamadas `list_all`/escrituras. GET usa el CORS vigente.

`frontend/src/lib/tracking.ts` y un controlador de panel normalizan el contrato y hacen una lectura explícita por Enter/botón: UUID validado antes de red, GET sin credenciales y `no-store`, timeout de cinco segundos, sin polling. Editar UUID, otro intento o cambiar de pestaña aborta/invalida respuestas y retira resultados anteriores. Distinguir carga, 404, 409, fallo de red/HTTP/payload y éxito con reintento explícito; nunca descargar `/deliveries` o `/returns`. Traducciones: pendiente de recogida, recogido, devuelto al transportista, pendiente de entrega al transportista y entregado al transportista. Un UUID de cotización no es un UUID de paquete.

El marcador de seguimiento pertenece a una capa separada: encuadrar solo coordenadas válidas con etiqueta «Locker actual» o «Último locker registrado», sin cambiar disponibilidad, contadores o destino de cotización. En seguimiento, abrir el popup no cambia de pestaña ni selección. Solo una acción explícita de recogida/entrega sobre un locker disponible activa cotización, según la sección 5; un marcador de seguimiento sin correspondencia disponible permanece informativo. Sin coordenadas, mantener el estado y texto de locker, sin fallback geográfico. El seguimiento funciona incluso si falla la carga de lockers disponibles; cambiar de modo conserva los campos y no hace consultas automáticas.

Archivos de la fase de seguimiento ya completada: `frontend/src/components/LockerExplorer.astro`, `pages/index.astro`, `styles/global.css`, `scripts/locker-map.ts`, `scripts/shipping-panel.ts`, helper de autocomplete instanciable, `lib/geocoder.ts`, cliente/controlador de seguimiento y pruebas. Backend: nuevo `application/tracking/`, `adapters/http/tracking/`, `main.py`, `adapters/http/routes.py`, unitarias e integración específicas; README documenta ambas pestañas, CP y semántica actual/último. No cambiar CORS, Compose, dependencias o persistencia.

La fase anterior verificó dos autocompletes aislados (CP estructurado/ausente, ceros, edición y respuestas cruzadas), cambio de pestañas y foco, cancelación sin reenvío, regresiones de cotización, contrato mínimo sin PII/listados/escrituras, cinco estados, colisión de UUID, sin asignación/metadata, locker lleno/inactivo y marcador separado. Probar escritorio/375×480, build estático y CORS real GET tracking; integración de recepción→salida→consulta en stack desechable. Ejecutar check/test/build/E2E y unitarias backend relevantes, Pyright obligatorio sin errores/advertencias, validación estricta y revisión. Su evidencia queda conservada con las 39 tareas completas; las búsquedas y acciones actuales se rigen por la sección 5 y se verifican según la sección 9.

### 11. Alcance de la selección por rol

La ampliación aprobada modifica `frontend/src/components/LockerExplorer.astro`, `src/scripts/locker-map.ts`, `src/scripts/shipping-panel.ts`, `src/styles/global.css`, `src/pages/index.astro`, pruebas frontend y README. Reutilizar geocoder/autocomplete y cliente de cotización; extraer un helper/componente de selección local si simplifica estado y pruebas. Eliminar referencias ARIA y eventos del formulario lateral retirado. No cambiar contratos/backend, Compose, dependencias ni datos. Se elige el filtrado de la colección disponible frente a nuevas búsquedas HTTP/proximidad porque Photon ya permite explorar zonas y el registro disponible identifica el locker sin inventar datos.

## Risks / Trade-offs

- Los lockers sintéticos carecen de CP -> solicitarlo sin inventar ubicación ni modificar datos.
- El worker puede dejar PENDING/PROCESSING indefinidamente -> espera local acotada y lectura manual del mismo UUID, sin falsas garantías de cancelación o reenvío.
- POST puede completarse aunque el navegador pierda la respuesta -> informar que no se confirmó y no reintentar automáticamente.
- Proveedores simulados pueden fallar aleatoriamente -> mostrar estados fieles y pruebas deterministas para casos concretos; no prometer tarifas comerciales.
- Origen público/API HTTPS y servicios backend requieren configuración propia -> mantener requisitos de Pages, sin incluir despliegue ni alojamiento del backend.
- OSM/Photon pueden fallar -> estados independientes y selectores de ambos roles accesibles sin teselas; no inferir datos ausentes.

## Migration Plan

El usuario ha aprobado esta ampliación con «sí, adelante». Reconstruir únicamente los assets/frontend estático; no hay migraciones ni cambios de backend. Los UUID elegidos y CP suplementarios son estado local, mientras las cotizaciones explícitas siguen persistiendo por el contrato actual aunque se cierre el panel. Revertir la interfaz no elimina registros. Sustituir los dos autocompletes de rol, apertura automática de cotizador y formulario lateral por el recorrido de la sección 5; conservar tareas/evidencia histórica. No sincronizar, archivar ni publicar como parte de la implementación.
