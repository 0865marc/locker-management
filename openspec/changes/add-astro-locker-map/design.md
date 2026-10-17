# Design

## Context

Ver `proposal.md`. El frontend estático y las cotizaciones asíncronas existen. El usuario ha aprobado orientar la web a comparar envíos hacia el locker elegido, simplificando el menú y sustituyendo el catálogo técnico. `shipping-quotes` y `asynchronous-shipping-quotations` definen los contratos que se reutilizan; API/worker ya componen tres proveedores simulados.

## Goals / Non-Goals

**Goals:** mantener Astro estático, interacción en navegador y fronteras hexagonales; reutilizar los datos del paquete y cotizaciones persistidas existentes sin asociar nuevos campos al contrato HTTP.

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

### 5. Mapa, menú y selección de destino

Leaflet conserva teselas OSM con atribución visible, vista inicial peninsular aproximadamente `[35.8, -9.4]` a `[43.9, 3.4]`, rueda y controles de zoom. Retirar «Ver España»: península, islas, Ceuta y Melilla siguen accesibles mediante navegación y selección de destino. No aplicar geocerca, inventar coordenadas ni desplazar lockers coincidentes. El mapa mantiene todo el viewport (`100dvh`, fallback `100vh`) y el encuadre durante cargas/reintentos; ningún panel modifica sus dimensiones.

El menú superior contiene únicamente buscador, Largo/Ancho/Alto (cm), Peso (kg) y contadores vivos al final. Retirar la sección de éxito, «Ver lockers», «Actualizar», hora, «Ver España» y nota informativa, incluyendo referencias/eventos huérfanos. Carga, vacío, error/reintento y aviso de teselas se muestran de forma compacta solo cuando corresponda. La lectura inicial y reintento conservan GET sin caché; el éxito actualiza contadores/marcadores y oculta el estado, sin mensaje redundante. Un fallo no conserva datos como disponibilidad vigente. No añadir actualización periódica de lockers.

Los campos del paquete empiezan vacíos, admiten edición decimal positiva y permanecen locales hasta la comparación explícita. No duplicarlos en otro formulario. Cambiarlos no mueve el mapa ni consulta la API; sí invalida una comparación anterior para impedir mostrar precios como si correspondieran a los nuevos datos. La validación precisa de unidades/límites se aplica al comparar.

Seleccionar un marcador abre el panel «Enviar a este locker», cerrado inicialmente, con alias/dirección del destino, selector compacto de lockers y formulario de cotización. Sustituye por completo el catálogo y la ficha técnica; no abrir una lista heredada ni popup técnico. El selector permite elegir individualmente lockers coincidentes o sin coordenadas, indicando estas últimas sin situarlas ficticiamente. Renombrar el enlace de salto a «Elegir destino y cotizar» para abrir el mismo panel y enfocar el selector sin necesitar un marcador. Cerrar/Escape devuelve el foco al marcador o enlace que lo abrió, con fallback accesible si desaparece.

El panel se superpone a la derecha en escritorio o en la zona inferior en móvil, con scroll interno; la selección encuadra coordenadas reales en el área libre sin cambiar el tamaño del mapa. Conservar etiquetas, foco, atribución, aislamiento de clic/arrastre/rueda/teclado y uso a 375×480 px. El fallo de teselas deja accesibles selector y cotización. No reintroducir botones retirados en el menú superior.

#### Búsqueda de dirección o código postal

Colocar el campo etiquetado encima de dimensiones, sin botón «Buscar» ni formularios anidados; el selector de validación numérica sigue limitado a los cuatro campos del paquete. Una edición real recorta la consulta, cancela temporizador/petición anterior e invalida su generación. Con al menos tres caracteres, esperar 350 ms desde la última edición antes de consultar; menos caracteres limpian estados/sugerencias sin petición. Enter no añade una búsqueda duplicada ni envía el formulario de medidas. Conservar estado independiente, timeout de cinco segundos y reintento manual del último texto válido, sin reintentos automáticos.

Usar el servicio público Photon directamente desde el navegador, sin claves ni proxy: direcciones en `https://photon.komoot.io/api/?q=...&countrycode=ES&limit=5`; cinco dígitos ASCII se mantienen como texto y usan `https://photon.komoot.io/structured?postcode=...&countrycode=ES&limit=5`. El contrato se documenta en [Photon API v1](https://github.com/komoot/photon/blob/master/docs/api-v1.md). Es un servicio de demostración para uso razonable, sin garantía de disponibilidad: el umbral y debounce evitan consultar por cada pulsación; no añadir polling ni fallback a Nominatim. El acceso público real y CORS no pudieron comprobarse en esta red: no confundir los mocks con prueba de conectividad.

Un helper tipado `frontend/src/lib/geocoder.ts` construye URLs con `URLSearchParams`, hace GET sin credenciales con timeout de cinco segundos y normaliza GeoJSON `FeatureCollection` desde `unknown`. Aceptar solo puntos finitos WGS84 de país ES, manteniendo orden y como máximo cinco; renderizar etiquetas con texto DOM, nunca HTML. Una colección válida sin candidatos españoles se trata como vacío, mientras una estructura malformada o HTTP/red/timeout es error de búsqueda. No guardar consultas ni generar ubicaciones ficticias.

Mostrar de uno a cinco candidatos debajo del campo; incluso una coincidencia requiere selección y escribir/recibir resultados no mueve el mapa. Al elegir, rellenar el campo con su etiqueta, mantener marcador de ubicación y zoom aproximado 16 para dirección o 13 para CP, y cerrar sugerencias sin disparar otra consulta. Conservar encuadre visible con el panel de cotización abierto/cerrado y móvil, sin abrirlo ni alterar el destino seleccionado. La búsqueda no llama a la API de lockers, filtra resultados ni completa coordenadas ausentes. Una generación de solicitud descarta respuestas antiguas incluso si el transporte ignora cancelación. Retirar el párrafo visible de Photon y «Ubicación localizada…», además de referencias ARIA huérfanas; conservar carga/vacío/error, reintento y atribución OSM del mapa. README conserva proveedor, envío externo de consultas y límites; un anuncio de selección solo para lectores de pantalla es opcional.

La lista animada bajo el campo contiene únicamente sugerencias geográficas, independientes del selector de destino. Animar su apertura/cierre brevemente (aproximadamente 160 ms, altura/opacidad y desplazamiento suave), sin cambiar dimensiones del mapa, y desactivar movimiento con `prefers-reduced-motion`. Exponer expansión y relación con el campo; los botones permiten Tab y Enter/Espacio. Escape cierra y devuelve foco al campo; salir del conjunto campo/sugerencias también cierra, sin impedir el clic de selección ni consultar al perder foco. Al cerrar, cancelar trabajo pendiente, invalidar respuestas y retirar interacción/foco inmediatamente; completar ocultación visual sin que callbacks antiguos reabran u oculten una lista más reciente. La asignación programática de la etiqueta seleccionada no agenda búsquedas. Reabrir requiere nueva edición válida; scroll y teclado siguen aislados del mapa.

#### Cotización hacia el locker seleccionado

El panel usa el locker como destino. Pedir «CP de origen» obligatorio; mostrar «CP de destino» desde la dirección estructurada si es válido, sin editarlo. Si falta, permitir introducirlo con indicación «CP del locker no registrado»; es un dato de esta consulta y no modifica el locker. Al cambiar de locker, descartar ese CP manual y cargar el del nuevo destino; conservar origen y medidas. Ambos países son ES y los CP son cadenas de cinco dígitos, incluidos ceros iniciales. La búsqueda del mapa no rellena estos CP.

«Comparar envíos» valida selección, CP y los cuatro campos existentes. Convertir de manera decimal exacta ancho→`width_mm`, alto→`height_mm`, largo→`depth_mm` multiplicando cm por 10, y peso→`weight_grams` multiplicando kg por 1000. Exigir enteros de 1–2000 mm y 1–30000 g; rechazar fracciones no representables o fuera de rango, sin redondeo silencioso. Errores junto al campo y foco en el primero inválido, sin POST. La API no acepta `locker_id` ni extras: el vínculo con el destino es contexto local y no afirma compatibilidad con celdas.

Separar normalización/conversión y cliente HTTP tipados en `frontend/src/lib/quotations.ts` y `quotation-api.ts`, reutilizando la validación de URL pública sin mezclar dominio backend con UI. POST JSON a `/quotations`, `credentials: 'omit'`, timeout de cinco segundos incluyendo lectura; bloquear doble envío. Validar desde `unknown` la aceptación 202/id y los GET, incluyendo id, solicitud coincidente con la instantánea enviada, estados y ofertas coherentes. Construir GET con el id validado, no seguir un `Location` externo. No calcular tarifas, inventar resultados ni limitar la UI a tres proveedores.

Tras 202, consultar GET `/quotations/{id}` secuencialmente aproximadamente cada segundo, sin caché ni peticiones solapadas; timeout por petición de cinco segundos y deadline total de treinta segundos para la espera local. PENDING/PROCESSING mantienen estado de espera; COMPLETED/FAILED detienen polling. Al agotar el plazo o fallar la lectura, conservar UUID y ofrecer «Seguir consultando» para leer esa misma solicitud con otra ventana acotada, sin nuevo POST. Un cambio de destino/CP/medidas, cierre o salida cancela temporizadores/HTTP e invalida la generación; ninguna respuesta antigua modifica el panel. Esto no cancela el trabajo persistido del worker y no se presenta como cancelación del envío.

Distinguir 422 de datos, fallo/timeout/red de creación y fallo de proceso. POST fallido o de resultado incierto nunca se repite automáticamente; si 503 trae `PUBLISH_ERROR` e id, conservar la referencia sin fabricar fallos de proveedor. Una nueva creación solo procede de otro clic explícito. Los resultados dejan de presentarse como actuales al editar sus datos; las lecturas pueden reanudarse solo para la misma instantánea vigente.

Mostrar tarjetas por proveedor y servicio devueltos: precio desde céntimos con formato EUR y plazo/rango en días, sin reinterpretar el tipo de días. QUOTED conserva todas las ofertas; NOT_COVERED indica ausencia de cobertura; FAILED distingue error y timeout. COMPLETED con todos los proveedores fallidos no equivale a fallo del proceso. Identificar visiblemente los proveedores simulados actuales y sus tarifas de demostración; no inventar marcas reales, ranking o garantía de cobertura/reserva. README explica que API, PostgreSQL, RabbitMQ y worker ya existentes son necesarios y que cerrar el panel no borra ni cancela una cotización.

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

La evidencia histórica de las 31 tareas previas se conserva en `tasks.md`. Para esta ampliación:

- Vitest para CP estructurado/nulo, conversión exacta, límites, request sin extras, aceptación y estados/resultados desde `unknown`, precios/plazos, HTTP/timeout, respuestas antiguas y polling acotado sin repetir POST.
- E2E de menú simplificado, contador real y estados excepcionales; destino por marcador/selector/enlace, coincidencias y coordenadas ausentes, CP faltante, medidas reutilizadas y errores antes de enviar. Cubrir doble clic, espera/completado/fallos parciales o totales, deadline/reanudar mismo UUID y cierre/edición durante POST o GET. Verificar foco, teclado, scroll, encuadre y 375×480, manteniendo regresiones relevantes de sugerencias y mapa.
- CORS unitario con composición real: GET conserva política, POST JSON `/quotations` permitido para origen exacto, POST `/lockers` y otros métodos/orígenes/headers denegados, solicitudes sin Origin intactas. Ampliar el servidor de pruebas con repositorio/publicador falsos para verificar POST+GET en navegador entre orígenes sin interceptar la API.
- `npm run check`, `npm test`, `npm run build` con API apagada y E2E afectados. Smoke en stack desechable Nginx/API/PostgreSQL/RabbitMQ/worker: solicitud real desde navegador, UUID y resultado terminal coherentes; los simuladores pueden fallar sin que eso invalide el smoke. No tocar datos del usuario ni repetir el seed de 1000 lockers.
- Desde `backend/`, unitarias relevantes y `uv run --extra dev pyright --project .. --warnings` con cero errores y advertencias. Validación OpenSpec estricta y revisión independiente antes de marcar tareas completas.

Teselas/Photon controlados solo en pruebas; la conectividad externa real sigue sin verificarse. Los mocks no sustituyen las pruebas reales de CORS o del flujo API/worker.

## Risks / Trade-offs

- Los lockers sintéticos carecen de CP -> solicitarlo sin inventar ubicación ni modificar datos.
- El worker puede dejar PENDING/PROCESSING indefinidamente -> espera local acotada y lectura manual del mismo UUID, sin falsas garantías de cancelación o reenvío.
- POST puede completarse aunque el navegador pierda la respuesta -> informar que no se confirmó y no reintentar automáticamente.
- Proveedores simulados pueden fallar aleatoriamente -> mostrar estados fieles y pruebas deterministas para casos concretos; no prometer tarifas comerciales.
- Origen público/API HTTPS y servicios backend requieren configuración propia -> mantener requisitos de Pages, sin incluir despliegue ni alojamiento del backend.
- OSM/Photon pueden fallar -> estados independientes y selector de destino accesible sin teselas; no inferir datos ausentes.

## Migration Plan

El usuario ha aprobado esta ampliación con «adelante». No hay migraciones: reconstruir API para CORS y frontend estático para la interfaz. Se conservan datos existentes; las cotizaciones explícitas crean registros mediante el contrato actual y persisten aunque se cierre el panel. Retirar el frontend nuevo no elimina esos registros. El cambio reemplaza los requisitos anteriores de catálogo, controles retirados y exclusión de cotizaciones web; las tareas/evidencias anteriores permanecen históricas. No sincronizar, archivar ni publicar como parte de la implementación.
