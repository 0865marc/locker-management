# Design

## Context

Ver `proposal.md`. El frontend estático y las cotizaciones asíncronas existen. Las dos pestañas y el seguimiento mínimo por UUID están implementados. La selección por rol ya está implementada. El usuario ha aprobado retirar ambos campos CP y usar «Locker de origen»/«Locker de destino» en la interfaz, derivando los códigos exclusivamente de los registros seleccionados. `shipping-quotes` y `asynchronous-shipping-quotations` definen los contratos que se reutilizan; API/worker ya componen tres proveedores simulados.

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

`freeCount` cuenta `enabled === true && occupied === false`; disponible requiere además `active === true`. UUID permanece como identidad interna. Conservar todos los disponibles para el selector compacto, incluidos los que no tienen coordenadas. Mostrar alias o dirección y, si faltan, una etiqueta neutra numerada; distinguir etiquetas repetidas sin una ficha técnica con UUID/celdas. Conservar `postalCode: string | null` desde `address.postal_code` estructurado, válido solo con país ES y cinco dígitos ASCII. Un CP ausente/inválido bloquea cotizar y se comunica junto al selector; nunca analizar la dirección formateada ni deducirlo de coordenadas/Photon. Usar DOM/textContent para todos los datos externos. La disponibilidad no implica encaje ni reserva.

### 5. Mapa, selección de lockers y cotización

Leaflet conserva teselas OSM con atribución, vista inicial peninsular aproximadamente `[35.8, -9.4]` a `[43.9, 3.4]`, rueda y controles de zoom. Península, islas, Ceuta y Melilla siguen accesibles mediante navegación y selección; no reaparece «Ver España». El mapa ocupa `100dvh` con fallback `100vh`, conserva su encuadre durante cargas y no desplaza coordenadas reales para separar lockers coincidentes. Los paneles no cambian sus dimensiones.

Un pequeño panel geográfico precede a las pestañas «Cotizar envío» y «Localizar paquete». Cotización, inicialmente activa, reúne los selectores «Locker de origen»/«Locker de destino», Largo/Ancho/Alto (cm), Peso (kg), «Comparar envíos» y contadores vivos al final. Seguimiento conserva UUID, acción y resultado propios. Mantener retirados el catálogo técnico, sección de éxito, «Ver lockers», «Actualizar», hora y nota informativa. Carga, vacío, error/reintento y aviso de teselas aparecen solo cuando proceda; no añadir polling de disponibilidad.

#### Búsqueda geográfica independiente

Reutilizar una instancia de `LocationSearch.astro`/`setupAutocomplete` fuera de los paneles de pestaña. Conservar mínimo de tres caracteres, debounce de 350 ms, hasta cinco sugerencias, selección explícita incluso con una, timeout de cinco segundos, cancelación/generación y reintento manual. Dirección usa `https://photon.komoot.io/api/?q=...&countrycode=ES&limit=5`; cinco dígitos ASCII usan `/structured?postcode=...&countrycode=ES&limit=5`, manteniendo ceros iniciales. Photon es un servicio público de demostración sin garantía de disponibilidad; no añadir claves, proxy ni Nominatim. Su acceso real/CORS no están verificados en esta red.

Elegir una sugerencia rellena solo ese buscador, centra/marca su zona (zoom aproximado 16 para dirección y 13 para CP) y cierra sin otra petición. No completa CP, selecciona lockers, cambia pestaña, invalida cotizaciones ni modifica seguimiento. El CP que pueda conservar el helper geográfico no se utiliza para el formulario. Las ubicaciones arbitrarias se encuentran aquí; los selectores locales no prometen búsqueda por proximidad ni consultan Photon.

Mantener normalización de GeoJSON desde `unknown`, solo puntos finitos españoles, texto seguro y estados independientes. La animación breve de sugerencias respeta `prefers-reduced-motion`; Escape/foco/blur/clic seguros, cierre inmediatamente inerte y generaciones de animación evitan reaperturas obsoletas. No formularios anidados ni validación numérica sobre campos de búsqueda. Cambiar de pestaña cierra/cancela sugerencias pendientes, conserva el texto geográfico y no consulta de nuevo.

#### Selecciones locales por rol y popup

Ambos selectores usan la colección de lockers disponibles ya cargada, incluidos los no posicionables. Filtrar localmente por etiqueta, dirección o CP registrados, sin distinguir mayúsculas y sin llamadas HTTP. Abrir la lista solo si la consulta recortada no está vacía y tiene entre una y veinte coincidencias, mostrando todas. Con más de veinte, mantenerla cerrada y anunciar «Concreta la búsqueda»; con cero, cerrada y «Sin coincidencias»; vacía, cerrada y sin resultados. No mostrar los primeros veinte ni imponer otro mínimo fijo de caracteres. Foco, clic, Enter o flechas deben pasar por la misma condición. Las consultas elegibles permiten teclado y scroll, incluidos lockers coincidentes; una consulta demasiado amplia requiere concretar nombre, dirección o CP. Los resultados siempre representan lockers, y su identidad es el UUID, nunca el texto o las coordenadas. La etiqueta neutra existente identifica también registros sin alias/dirección.

Mantener por rol el locker seleccionado y el texto de búsqueda; obtener su CP directamente del registro, sin estado postal editable separado. Seleccionar un candidato o una acción de popup fija ese rol y no altera el otro ni los datos del paquete. Editar el texto de un rol invalida inmediatamente su UUID y comparación previa, aunque después se vuelva a escribir la misma etiqueta. Elegir otro UUID usa exclusivamente el CP del nuevo registro; no reutilizar el anterior si falta. Mantener la selección actual sin borrados espurios al abrir/cerrar sugerencias o volver a elegir el mismo UUID. En una nueva carga, dejar de ofrecer selecciones que ya no estén disponibles y descartar sus resultados anteriores. No filtrar por tamaño del paquete ni prometer compatibilidad/stock reservado.

Pulsar un marcador disponible, también con Enter/Espacio, abre un popup con nombre, dirección registrada o ausencia, el texto común «Seleccionar como:» y botones «Locker de destino» y «Locker de origen». Abrirlo no cambia roles, pestaña o cotización. Una acción explícita activa cotización si es necesario, fija el rol, cierra el popup y dirige el foco a su selección en el menú. Escape/cerrar devuelve foco al marcador cuando exista. Configurar anclaje/offset según la altura y anchor de cada icono para que el popup y su punta queden por encima de su borde superior con separación visible; no desplazar coordenadas ni resolverlo solo cambiando z-index. Conservar la relación tras pan/zoom/resize y encuadrar popup e icono en el área visible, con scroll interno móvil sin omitir acciones. Usar DOM/textContent para el contenido externo y aislar eventos del mapa. Los selectores permiten elegir individualmente puntos coincidentes sin desplazar coordenadas.

El enlace de salto activa cotización y enfoca el selector de origen del menú, sin abrir resultados. Los marcadores de seguimiento conservan su relación actual/histórica; si su UUID coincide con un locker actualmente disponible, las acciones pueden usar ese registro disponible, nunca asumir disponibilidad de los metadatos de tracking. Sin esa correspondencia, el marcador de seguimiento es informativo y no ofrece selección. Pulsar un marcador nunca cambia de modo por sí solo. Esta excepción de acción expresa sustituye la prohibición anterior absoluta en seguimiento.

#### CP y validación del paquete

Para cada rol, derivar el CP exclusivamente de `roles.pickup.postalCode` / `roles.delivery.postalCode`, normalizados como ES y cinco dígitos ASCII. Eliminar por completo ambos campos, sus props/listeners/errores DOM y estilos sin uso; no sustituirlos por inputs ocultos ni extraer CP de la dirección formateada. La dirección visible ya incluye el CP. Si falta o es inválido, mantener el locker visible/seleccionable, mostrar junto al selector «Este locker no tiene un CP válido. Elige otro» y bloquear comparación hasta elegir uno completo. Conservar ceros iniciales y no inferir desde Photon/coordenadas ni actualizar datos antiguos.

Los cuatro campos existentes empiezan vacíos y permanecen locales. Convertir decimal exacto ancho→`width_mm`, alto→`height_mm`, largo→`depth_mm` (cm×10) y peso→`weight_grams` (kg×1000); exigir enteros 1–2000 mm y 1–30000 g sin redondeo silencioso. «Comparar envíos» se habilita solo con los dos UUID vigentes, ambos CP y las cuatro medidas válidos, y sin solicitud/espera en curso. Mostrar errores junto a los campos y revalidar en submit para impedir envíos por Enter o eventos programáticos inválidos. Seleccionar, editar o buscar no envía automáticamente.

La API recibe exclusivamente países ES, CP y medidas/peso mediante el contrato existente; no `locker_id`, direcciones ni otros extras. Los UUID de origen y destino forman parte de la instantánea local junto al payload, por lo que cambiar de locker invalida resultados incluso si conserva el mismo CP. Esto contextualiza una simulación postal y no crea un traslado entre instalaciones ni verifica encaje en celdas.

#### Panel de resultados y asincronía

El panel derecho, cerrado inicialmente, contiene solo estado/referencia, tarjetas, aviso de simulación y cierre/continuación; se eliminan su selector, CP y botón de comparación. Comparar explícitamente abre resultados y anuncia el estado; cerrar/Escape restaura foco al botón principal y detiene espera local sin borrar los campos. En móvil se superpone abajo con scroll interno; preservar acceso al menú, popup, pestañas y atribución a 375×480 sin desbordamiento. Las acciones de lectura de una referencia conocida deben seguir accesibles tras cerrar/volver, solo para la instantánea vigente, y nunca crear un POST como efecto de reabrir resultados.

Reutilizar `quotations.ts` y `quotation-api.ts`: POST JSON `/quotations` con credenciales omitidas y timeout de cinco segundos, aceptación 202/id validada y bloqueo de doble envío; GET `/quotations/{id}` secuencial aproximadamente cada segundo con `no-store`, timeout de cinco segundos y límite local de treinta segundos. Validar id, solicitud, estados y ofertas desde `unknown`. PENDING/PROCESSING esperan; COMPLETED/FAILED detienen polling. Error de lectura o plazo agotado permite «Seguir consultando» el mismo UUID sin POST nuevo. Cerrar o cambiar de modo cancela el trabajo local y permite continuar explícitamente solo si la instantánea no cambió.

Cambiar cualquier selección, sus datos postales o las medidas invalida instantánea, ofertas, referencia reanudable y generación; abortar peticiones y no permitir que una respuesta antigua reabra resultados. Distinguir error 422, creación incierta y fallo de proceso; POST fallido nunca se reintenta automáticamente. Si 503 incluye PUBLISH_ERROR/id, conservarlo para lectura explícita mientras los datos sigan vigentes. La cancelación no elimina registros ni cancela el worker.

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

### 8. Generador manual con catálogo real de direcciones

Conservar el CLI de biblioteca estándar: desde `backend/`, `uv run python scripts/seed_lockers.py`, o en Compose `docker compose exec api python scripts/seed_lockers.py` tras incorporar los scripts a la imagen. Opciones sin cambios: `--count` positivo por defecto 250, `--seed` entero por defecto 42, `--base-url` local explícita y `--dry-run` sin HTTP. Cargar y validar el catálogo completo antes de escribir. No consultar geocodificadores, actualizar datos externos ni ejecutar el seed durante build/startup.

Sustituir puntos aleatorios y `address: null` por registros de `backend/scripts/data/spain-addresses.json`, extraídos del snapshot oficial MITECO reproducido sin transformación en [stations.json del commit 5e9e8770d97ccb882127e6cd4cd60b302fc0a1d2](https://raw.githubusercontent.com/ioritzarroyuelos-ai/gasolineras-espana/5e9e8770d97ccb882127e6cd4cd60b302fc0a1d2/public/data/stations.json). El script `fetch-prices.mjs` del mismo commit se comprobó: descarga la API oficial y guarda `JSON.stringify(all)`. Snapshot: Fecha `17/10/2026 23:09:30`, 11.431 registros, 12.149.531 bytes y SHA-256 `91ee3c584c20563d60f5f9389dec011cef0e3d8a69a2fc89ab9cc5aadbf26f9b`. La API oficial no es accesible desde la allowlist actual; la copia pública fijada sí se verificó. El coordinador dispone del snapshot y del script en `/tmp/locker-address-research/` para preparar el extracto, sin añadir dependencias de red a ejecución/pruebas.

Usar solo registros con calle y número final inequívoco, CP de cinco dígitos cuyo prefijo coincide con IDProvincia, municipio/provincia completos y coordenadas WGS84 plausibles para España, excluyendo el registro IDEESS 12883 con posición 0,0. El filtro explorado admite tipos CALLE/AVENIDA/PLAZA/PASEO/RONDA/TRAVESIA/TRAVESÍA/CARRER/AVINGUDA/RAMBLA, sin comas internas ambiguas, y encontró 3.423 candidatos en los 52 IDs provinciales. Conservar esos registros aptos con identificador fuente; excluir carreteras o kilómetros ambiguos como `CR CM-332, 46,4`, nunca convertir el último 4 en número de portal. Separar calle/número solo cuando lo respalde el texto original, preservar CP como cadena y convertir la coma decimal de coordenadas sin jitter. Guardar la dirección original/procedencia para auditar la normalización; esos metadatos no se envían al API.

Documentar en `backend/scripts/data/README.md` fuente oficial, URL/commit de la copia, fecha, hashes del snapshot y extracto, identificadores, filtro y correspondencia de campos. El [aviso legal de MITECO](https://www.miteco.gob.es/es/atencion-al-ciudadano/aviso-legal.html) permite reutilización con fuente/fecha y sin insinuar respaldo; no aplicar a los datos la licencia MIT del código del mirror. Las direcciones y coordenadas se verifican documentalmente contra la fuente, sin afirmar inspección física, exactitud catastral ni existencia de lockers en las estaciones.

Cada registro aporta juntos dirección completa (street, street_number, postal_code, city, province, country_code ES) y coordenadas. No combinar un CP con otro punto ni perturbar posiciones para dispersar marcadores. Usar `random.Random(seed)` sobre un orden estable del catálogo, recorriendo ciclos barajados: no repetir un registro antes de agotar el ciclo y permitir nuevos ciclos para cantidades superiores al catálogo. Documentar repeticiones y que la distribución queda limitada a esas ubicaciones, no a puntos uniformes por España. La semilla reproduce payloads con la misma versión del catálogo, nunca UUID del servidor. Natural Earth deja de determinar las ubicaciones del seed; sus límites generalizados no rechazarán una dirección costera oficial.

Conservar alias `DEMO-<seed>-<índice>`, active true y seis celdas habilitadas de 400×400×600 mm, libres al crearse. Validar estructura/campos, identificadores y coordenadas del catálogo antes de cualquier petición. `--dry-run` imprime esos mismos payloads completos sin HTTP. Enviar POST /lockers secuencialmente con timeout; detenerse en primer fallo o respuesta incierta, informar confirmados y no reintentar ni borrar. Cada ejecución añade registros, sin backfill de lockers antiguos ni idempotencia. README muestra dry-run, uso local/Compose y ausencia de instalaciones reales. Las verificaciones con escritura usan únicamente stack desechable.

### 9. Verificación

Conservar las 47 tareas/evidencias previas. Para este ajuste, probar ausencia de campos CP (también ocultos), nombres públicos nuevos en selectores/popup/mensajes, CP exactos derivados de ambos lockers con ceros iniciales, selección sin CP que bloquea sin POST y recuperación al elegir un registro completo. Mantener invalidación por UUID aunque comparta CP, cancelación, conservación de estado al volver a pestañas y geobúsqueda independiente. Los errores/foco deben apuntar a selectores existentes, sin referencias ARIA huérfanas.

Actualizar únicamente pruebas frontend afectadas y README. Ejecutar `npm run check`, `npm test`, build con API apagada y E2E afectados en escritorio/375×480, incluido el fixture de CORS real existente, sin otro stack Docker ni repetir seed. Desde `backend/`, ejecutar `uv run --extra dev pyright --project .. --warnings` con cero errores y advertencias, validar OpenSpec estricto y obtener revisión independiente. Backend, contratos y servicios no cambian; teselas/Photon siguen controlados en pruebas.

### 10. Pestañas y seguimiento por UUID

Pestañas con `tablist`/`tab`/`tabpanel`, selección anunciada, foco y navegación de teclado; el contenido inactivo queda `hidden` e `inert`. Conservar los textos y selecciones de ambos lockers, búsqueda geográfica, medidas, CP y UUID de tracking al cambiar, sin persistencia ni envíos automáticos. Cancelar autocomplete geográfico, espera de cotización y lectura de tracking mediante sus controladores/generaciones; cerrar resultados/sugerencias/popup al cambiar y ocultar el marcador de tracking al salir de seguimiento. No cancelar ni borrar trabajo del worker. Volver permite acciones explícitas, incluida reanudación de una cotización conocida solo con su instantánea vigente.

Contrato estable: `GET /tracking/{id}` devuelve 200 con exactamente `{id, kind, status, locker_relation, locker_id, locker}`. `id` es UUID; `kind` es `delivery` o `return`; `status` conserva el enum del flujo. `locker_relation` es `current`, `last_known` o `unassigned`; `locker_id` es UUID/null; `locker` es null o `{location_id: string|null, address: Address|null, coordinates: Coordinates|null}`. Address conserva los seis textos públicos existentes y Coordinates latitude/longitude finitos en límites WGS84. No incluir nombres, teléfonos, tracking_number, compartimentos ni modelos completos de recepción.

AWAITING_PICKUP/AWAITING_CARRIER con asignación significan `current`; COLLECTED/RETURNED_TO_CARRIER/HANDED_OVER con asignación significan `last_known`. Sin asignación: `unassigned`, locker_id y locker null. Metadata ausente: conservar id y relación del locker, devolver locker null y mostrar «Datos del locker no disponibles». Dirección/coordenadas ausentes no se inventan. Usar metadata registrada actual del locker sin afirmar snapshot histórico; un plazo de recogida vencido no cambia estado. El resumen de locker no se filtra por activo/capacidad.

Nuevo `application/tracking/` con DTO y caso de lectura que recibe DeliveryRepository, ReturnRepository y LockerRepository existentes. Consultar ambos `get_by_id` una vez: ninguno→404; ambos→409 sin elegir arbitrariamente; uno→proyectar y consultar su locker si está asignado. UUID inválido→422 antes del caso de uso. Fallos de infraestructura no se convierten en 404. El adaptador `adapters/http/tracking/` define schema/router; `main.py` reutiliza instancias de repositorios y `adapters/http/routes.py` admite el servicio opcional para preservar consumidores actuales. No añadir repositorios, migraciones, estados de dominio ni llamadas `list_all`/escrituras. GET usa el CORS vigente.

`frontend/src/lib/tracking.ts` y un controlador de panel normalizan el contrato y hacen una lectura explícita por Enter/botón: UUID validado antes de red, GET sin credenciales y `no-store`, timeout de cinco segundos, sin polling. Editar UUID, otro intento o cambiar de pestaña aborta/invalida respuestas y retira resultados anteriores. Distinguir carga, 404, 409, fallo de red/HTTP/payload y éxito con reintento explícito; nunca descargar `/deliveries` o `/returns`. Traducciones: pendiente de recogida, recogido, devuelto al transportista, pendiente de entrega al transportista y entregado al transportista. Un UUID de cotización no es un UUID de paquete.

El marcador de seguimiento pertenece a una capa separada: encuadrar solo coordenadas válidas con etiqueta «Locker actual» o «Último locker registrado», sin cambiar disponibilidad, contadores o destino de cotización. En seguimiento, abrir el popup no cambia de pestaña ni selección. Solo una acción explícita de origen/destino sobre un locker disponible activa cotización, según la sección 5; un marcador de seguimiento sin correspondencia disponible permanece informativo. Sin coordenadas, mantener el estado y texto de locker, sin fallback geográfico. El seguimiento funciona incluso si falla la carga de lockers disponibles; cambiar de modo conserva los campos y no hace consultas automáticas.

Archivos de la fase de seguimiento ya completada: `frontend/src/components/LockerExplorer.astro`, `pages/index.astro`, `styles/global.css`, `scripts/locker-map.ts`, `scripts/shipping-panel.ts`, helper de autocomplete instanciable, `lib/geocoder.ts`, cliente/controlador de seguimiento y pruebas. Backend: nuevo `application/tracking/`, `adapters/http/tracking/`, `main.py`, `adapters/http/routes.py`, unitarias e integración específicas; README documenta ambas pestañas, CP y semántica actual/último. No cambiar CORS, Compose, dependencias o persistencia.

La fase anterior verificó dos autocompletes aislados (CP estructurado/ausente, ceros, edición y respuestas cruzadas), cambio de pestañas y foco, cancelación sin reenvío, regresiones de cotización, contrato mínimo sin PII/listados/escrituras, cinco estados, colisión de UUID, sin asignación/metadata, locker lleno/inactivo y marcador separado. Probar escritorio/375×480, build estático y CORS real GET tracking; integración de recepción→salida→consulta en stack desechable. Ejecutar check/test/build/E2E y unitarias backend relevantes, Pyright obligatorio sin errores/advertencias, validación estricta y revisión. Su evidencia queda conservada con las 39 tareas completas; las búsquedas y acciones actuales se rigen por la sección 5 y se verifican según la sección 9.

### 11. Alcance de la selección por rol

La fase de selección por rol ya completada modificó `frontend/src/components/LockerExplorer.astro`, `src/scripts/locker-map.ts`, `src/scripts/shipping-panel.ts`, `src/styles/global.css`, `src/pages/index.astro`, pruebas frontend y README. Reutilizar geocoder/autocomplete y cliente de cotización; extraer un helper/componente de selección local si simplifica estado y pruebas. Eliminar referencias ARIA y eventos del formulario lateral retirado. No cambiar contratos/backend, Compose, dependencias ni datos. Se elige el filtrado de la colección disponible frente a nuevas búsquedas HTTP/proximidad porque Photon ya permite explorar zonas y el registro disponible identifica el locker sin inventar datos.

### 12. Alcance del catálogo y ajustes de interacción

Modificar `backend/scripts/seed_lockers.py`, añadir `backend/scripts/data/spain-addresses.json` y actualizar su README/procedencia y `backend/tests/unit/test_seed_lockers.py`. El COPY existente de scripts incluye el catálogo: no requiere cambiar Dockerfile ni Compose. Frontend: `src/scripts/locker-selector.ts`, `src/lib/locker-selection.ts`, `src/components/LockerExplorer.astro` y `src/styles/global.css` para avisos si procede, `src/scripts/locker-map.ts`, pruebas unitarias/E2E y README. Centralizar la condición de apertura para todos los eventos; un cierre inmediato deja opciones inertes, invalida animaciones antiguas y nunca borra por sí mismo selección/CP. Preferir un catálogo fijado a geocodificación masiva por ejecución para mantener trazabilidad, reproducibilidad y funcionamiento offline.

### 13. CP derivados y nombres públicos de origen/destino

Reutilizar `validateShipping` pasando los CP de los lockers y los cuatro valores del paquete. Adaptar sus errores postales a los selectores de origen/destino, nunca buscar o enfocar los inputs retirados; revalidar también al enviar. Mantener `pickup`/`delivery`, IDs internos y contrato HTTP para evitar una migración innecesaria. Renombrar únicamente textos públicos del formulario, popup, mensajes, nombres accesibles y README; no alterar estados de seguimiento como «pendiente de recogida» o «entregado al transportista».

Modificar `frontend/src/components/LockerSelector.astro`, `LockerExplorer.astro`, `src/scripts/shipping-panel.ts`, textos de `src/scripts/locker-map.ts`, estilos postales sin uso en `src/styles/global.css`, E2E afectados y README. El helper de cotización puede conservar su validación; no cambiar backend, seed, catálogo, dependencias o Compose. Esta decisión sustituye el suplemento manual de fases anteriores; la evidencia histórica sigue en tareas.

## Risks / Trade-offs

- Los registros antiguos pueden carecer de CP -> aviso por rol y comparación bloqueada hasta elegir otro locker; no se rellenan automáticamente.
- El catálogo describe estaciones, no lockers, y puede envejecer o repetir ubicaciones -> atribución/fecha y alias DEMO explícitos, pares inseparables y sin prometer verificación física.
- El worker puede dejar PENDING/PROCESSING indefinidamente -> espera local acotada y lectura manual del mismo UUID, sin falsas garantías de cancelación o reenvío.
- POST puede completarse aunque el navegador pierda la respuesta -> informar que no se confirmó y no reintentar automáticamente.
- Proveedores simulados pueden fallar aleatoriamente -> mostrar estados fieles y pruebas deterministas para casos concretos; no prometer tarifas comerciales.
- Origen público/API HTTPS y servicios backend requieren configuración propia -> mantener requisitos de Pages, sin incluir despliegue ni alojamiento del backend.
- OSM/Photon pueden fallar -> estados independientes y selectores de ambos roles accesibles sin teselas; no inferir datos ausentes.

## Migration Plan

El usuario ha aprobado retirar campos CP y renombrar los roles visibles a origen/destino. Reconstruir únicamente assets/frontend; no hay migraciones ni cambios de backend. Los lockers existentes sin CP continúan visibles, pero no pueden cotizar hasta elegir otros con datos completos. Conservar tareas/evidencia histórica y no sincronizar, archivar ni publicar como parte de esta implementación.
