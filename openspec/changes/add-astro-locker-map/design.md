# Design

## Context

Ver la motivación en `proposal.md`. El frontend estático, formulario local, navegación con rueda, búsqueda geográfica, CORS, Nginx y generador manual están implementados. La ampliación actual unifica los dos menús superiores izquierdos y sustituye la búsqueda explícita por sugerencias automáticas con selección y cierre animado. Conserva contratos, disponibilidad y persistencia.

## Goals / Non-Goals

**Goals:** archivos estáticos independientes del backend durante el build, lectura directa de la API y acceso CORS explícito; mapa a toda pantalla con entrada local de paquete y acceso plegable a la consulta/lista definida en `specs/locker-map/spec.md`.

**Non-Goals:** servidor de aplicación frontend, funciones de Cloudflare, nueva autenticación o cambios de dominio, capacidad o persistencia. Los datos del paquete no disparan filtros, cotizaciones, reservas o envíos. Nginx solo sirve archivos estáticos; este cambio no publica en Cloudflare ni proporciona alojamiento para FastAPI/PostgreSQL/RabbitMQ.

## Decisions

### 1. Build Astro estático

Crear `frontend/` con `output: 'static'`, TypeScript estricto y Leaflet importado solo por código de navegador. Astro genera el documento español y estructura de la interfaz; JavaScript carga y valida los lockers, calcula disponibilidad y gestiona mapa/lista. El build no consulta la API ni incorpora snapshots o fixtures de lockers. CSS, iconos y scripts se empaquetan localmente; no hace falta React/Vue.

Node 24 LTS se utiliza exclusivamente para herramientas. Fijar dependencias compatibles en `package-lock.json`, instalar con `npm ci` y ofrecer scripts `dev`, `check`, `build`, `preview`, `test` y `test:e2e`. La salida `dist` debe funcionar servida por cualquier servidor HTTP estático. Desarrollo y preview local usarán el puerto 4321 para compartir los orígenes documentados.

### 2. Conexión directa configurada al compilar

`PUBLIC_API_BASE_URL` se incorpora a los assets en build time: es una URL pública, no un secreto. `frontend/.env.example` propone explícitamente `http://127.0.0.1:8000` para uso local, sin fallback oculto en código. En producción debe apuntar a una API HTTPS accesible desde el navegador; el nombre de servicio Docker `api` no sirve como URL pública. Cambiar la variable requiere recompilar y volver a publicar los archivos.

El cliente valida la URL configurada antes de consultar: HTTP(S), sin credenciales, query ni fragmento; construye la ruta de lockers de forma determinista. Si falta o es inválida, o si la página HTTPS apunta a HTTP, muestra un error de configuración sin pedir datos. Una configuración local HTTP explícita permite probar `dist` contra otro origen local. La aplicación no conoce ni necesita la URL definitiva durante esta planificación.

Usar fetch GET con `credentials: 'omit'`, `cache: 'no-store'`, sin headers personalizados y `AbortController` con cinco segundos para completar la lectura. Cada actualización hace una nueva petición; no almacenar disponibilidad en localStorage, service worker o caché propia. Red/CORS, HTTP no exitoso, timeout o payload malformado se reflejan como errores en la interfaz, sin inventar códigos de respuesta. El navegador no distingue de forma fiable CORS de otros fallos de red: el mensaje no afirmará una causa que desconoce.

### 3. CORS limitado a la capa HTTP

Usar el middleware CORS estándar de FastAPI/Starlette, configurado en el punto de composición; si se necesita un helper, ubicarlo en `backend/adapters/http/cors.py`. `CORS_ALLOWED_ORIGINS` contendrá orígenes exactos HTTP(S) separados por comas, recortando espacios. Ausente o vacío significa lista vacía. Rechazar comodines, credenciales, rutas, query, fragmentos y entradas inválidas con diagnóstico claro. No usar expresiones que admitan todos los proyectos `pages.dev`.

Permitir los orígenes listados, preflight para GET y headers estándar necesarios, con `allow_credentials=False`; el cliente no necesita headers personalizados. CORS controla exposición de respuestas al navegador y permisos preflight, no autentica ni impide que clientes HTTP usen las rutas existentes. Conservar sus contratos y el comportamiento sin `Origin`. Probar origen permitido/denegado, preflight GET y de escritura, configuración vacía/inválida y solicitudes sin `Origin`.

`compose.yaml` solo pasa esta variable al servicio API, con valores locales explícitos por defecto `http://localhost:4321,http://127.0.0.1:4321`. Para producción se sustituirán por el origen Pages concreto y/o dominio propio. Un preview de Pages necesita autorizar explícitamente su origen si debe acceder al backend. El backend y sus volúmenes siguen gestionados por el Compose existente.

### 4. Disponibilidad y representación

Validar en el cliente los campos usados a partir de `unknown`: lista, UUID, activo booleano, alias/dirección nullable y estados booleanos de celdas. Una forma esencial inválida invalida la carga; coordenadas null, incompletas, no numéricas, no finitas o fuera de rango conservan el locker como no posicionable. No convertir valores falsy ni cadenas en booleanos.

`freeCount` cuenta `enabled === true && occupied === false`; disponible requiere además `active === true`. Mantener todos los disponibles en la lista, con UUID como identidad. Etiqueta: alias, dirección y finalmente UUID; detalle con UUID, dirección o ausencia y celdas libres. Preservar códigos postales textuales. Usar nodos DOM/textContent también en popups; ninguna cadena API se ejecuta como HTML. Las funciones de presentación no alteran reglas de asignación ni comprueban tamaños de paquetes.

### 5. Mapa y estados

Leaflet usa `https://tile.openstreetmap.org/{z}/{x}/{y}.png` con atribución y enlace visibles. La vista inicial ajusta aproximadamente `[35.8, -9.4]` a `[43.9, 3.4]`, centrada en la península y más cercana que el encuadre global; «Ver España» conserva `[27.5, -18.5]` a `[44, 4.5]`, incluyendo ambos archipiélagos, Ceuta y Melilla. Habilitar `scrollWheelZoom` sobre el mapa y conservar el aislamiento de rueda de los paneles. No inferir coordenadas de lockers ni aplicar geocerca. La lista puede seleccionar cualquier posición válida almacenada, incluso fuera del encuadre inicial.

Seleccionar una fila o un marcador encuadra su posición en el área visible entre paneles sin cambiar coordenadas ni tamaño del mapa y muestra el popup cuando el espacio libre permita mostrarlo sin cubrir paneles o marcador; si no cabe, el detalle completo permanece en la lista. Dos lockers coincidentes conservan sus coordenadas y filas independientes, y la selección trae al frente su marcador. Mostrar disponibles y posicionables, con «Sin coordenadas válidas» cuando corresponda. Carga, actualización o ausencia de marcadores conservan el encuadre actual: retirar el `fitBounds` incondicional de `render()` para no deshacer la vista inicial o una búsqueda.

Carga inicial, actualizar y reintentar comparten flujo; impedir intentos simultáneos. Tras fallo se eliminan resultados/posiciones que podrían confundirse con disponibilidad vigente. Cada éxito reemplaza resultados y limpia una selección desaparecida. Los errores de teselas generan aviso independiente y conservan la lista utilizable. No precargar mapas ni incluir teselas de prueba en producción; respetar atribución, caché HTTP y Referer del proveedor.

El mapa ocupa todo el viewport: contenedor de ancho completo y altura `100dvh` con fallback `100vh`, sin cabecera/pie visibles ni márgenes exteriores que reduzcan el mapa. Conservar un título accesible y navegación por teclado. Los elementos flotan sobre el mapa; abrirlos no cambia sus dimensiones. El `ResizeObserver` existente ajusta Leaflet al viewport.

Arriba a la izquierda, un único panel compacto «Tu paquete» reúne buscador, cuatro campos etiquetados —Largo (cm), Ancho (cm), Alto (cm) y Peso (kg)—, acciones/estados y contadores al final. Sustituye los dos contenedores visuales actuales, sin una segunda tarjeta de disponibilidad. Los campos de paquete empiezan vacíos, usan controles numéricos nativos con decimales positivos y permiten vaciarse; sus valores son locales, sin persistencia, submit, filtros ni llamadas de red. Retirar la nota visible de medidas y cualquier `aria-describedby` que apunte a contenido eliminado, conservando etiquetas y validación independientes. El marcado y lógica siguen en el componente y script existentes, sin framework ni validador de negocio nuevos.

Conservar listado y detalles en un panel independiente cerrado inicialmente, abierto con «Ver lockers» fuera del formulario. Se superpone a la derecha en escritorio o en la zona inferior en móvil, con scroll interno y cierre accesible. Seleccionar un marcador abre el panel para mostrar su detalle; cerrar devuelve el foco al control de apertura cuando proceda. Un enlace de salto al listado también debe abrirlo. Así siguen accesibles los lockers sin coordenadas y los coincidentes, sin restar espacio permanente al mapa.

Dentro del panel único, controles compactos de actualizar, reintentar, «Ver España» y «Ver lockers», junto con los estados necesarios, siguen accesibles aunque el listado esté cerrado; permanecen fuera del formulario de medidas. Los contadores de disponibles y en mapa cierran el panel y conservan los datos vivos, nunca cifras fijas. Reubicar controles Leaflet para evitar el menú y mantener visible la atribución. Aislar clic, arrastre, rueda y teclado sin impedir edición, tabulación o scroll interno. En 375×480 px, limitar ancho/altura y permitir scroll del panel conservando mapa, controles y campos accesibles. La disponibilidad sigue correspondiendo a la última consulta, sin relacionarla con las medidas.

#### Búsqueda de dirección o código postal

Colocar el campo etiquetado encima de dimensiones, sin botón «Buscar» ni formularios anidados; el selector de validación numérica sigue limitado a los cuatro campos del paquete. Una edición real recorta la consulta, cancela temporizador/petición anterior e invalida su generación. Con al menos tres caracteres, esperar 350 ms desde la última edición antes de consultar; menos caracteres limpian estados/sugerencias sin petición. Enter no añade una búsqueda duplicada ni envía el formulario de medidas. Conservar estado independiente, timeout de cinco segundos y reintento manual del último texto válido, sin reintentos automáticos.

Usar el servicio público Photon directamente desde el navegador, sin claves ni proxy: direcciones en `https://photon.komoot.io/api/?q=...&countrycode=ES&limit=5`; cinco dígitos ASCII se mantienen como texto y usan `https://photon.komoot.io/structured?postcode=...&countrycode=ES&limit=5`. El contrato se documenta en [Photon API v1](https://github.com/komoot/photon/blob/master/docs/api-v1.md). Es un servicio de demostración para uso razonable, sin garantía de disponibilidad: el umbral y debounce evitan consultar por cada pulsación; no añadir polling ni fallback a Nominatim. El acceso público real y CORS no pudieron comprobarse en esta red: no confundir los mocks con prueba de conectividad.

Un helper tipado `frontend/src/lib/geocoder.ts` construye URLs con `URLSearchParams`, hace GET sin credenciales con timeout de cinco segundos y normaliza GeoJSON `FeatureCollection` desde `unknown`. Aceptar solo puntos finitos WGS84 de país ES, manteniendo orden y como máximo cinco; renderizar etiquetas con texto DOM, nunca HTML. Una colección válida sin candidatos españoles se trata como vacío, mientras una estructura malformada o HTTP/red/timeout es error de búsqueda. No guardar consultas ni generar ubicaciones ficticias.

Mostrar de uno a cinco candidatos debajo del campo; incluso una coincidencia requiere selección y escribir/recibir resultados no mueve el mapa. Al elegir, rellenar el campo con su etiqueta, mantener marcador de ubicación y zoom aproximado 16 para dirección o 13 para CP, y cerrar sugerencias sin disparar otra consulta. Conservar encuadre visible con listado de lockers abierto/cerrado y móvil, sin abrirlo ni alterar su selección. La búsqueda no llama a la API de lockers, filtra resultados ni completa coordenadas ausentes. Una generación de solicitud descarta respuestas antiguas incluso si el transporte ignora cancelación. Retirar el párrafo visible de Photon y «Ubicación localizada…», además de referencias ARIA huérfanas; conservar carga/vacío/error, reintento y atribución OSM del mapa. README conserva proveedor, envío externo de consultas y límites; un anuncio de selección solo para lectores de pantalla es opcional.

«La lista de abajo» designa las sugerencias del buscador, no el listado general de lockers. Animar su apertura/cierre brevemente (aproximadamente 160 ms, altura/opacidad y desplazamiento suave), sin cambiar dimensiones del mapa, y desactivar movimiento con `prefers-reduced-motion`. Exponer expansión y relación con el campo; los botones permiten Tab y Enter/Espacio. Escape cierra y devuelve foco al campo; salir del conjunto campo/sugerencias también cierra, sin impedir el clic de selección ni consultar al perder foco. Al cerrar, cancelar trabajo pendiente, invalidar respuestas y retirar interacción/foco inmediatamente; completar ocultación visual sin que callbacks antiguos reabran u oculten una lista más reciente. La asignación programática de la etiqueta seleccionada no agenda búsquedas. Reabrir requiere nueva edición válida; scroll y teclado siguen aislados del mapa.

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

### 8. Generador manual de lockers de demostración

Crear un CLI Python con biblioteca estándar, invocable desde `backend/` mediante `uv run python scripts/seed_lockers.py` o, tras reconstruir la imagen API, con `docker compose exec api python scripts/seed_lockers.py`, apuntando al puerto 8000 del mismo contenedor. Opciones: `--count` positivo, por defecto 250; `--seed` entero, por defecto 42; `--base-url`, por defecto `http://127.0.0.1:8000`; y `--dry-run`, que imprime los payloads JSON sin efectuar ninguna petición. Validar opciones y cargar geografía antes de escribir. El script es un cliente externo del contrato HTTP, sin acceso directo a repositorios o base de datos y sin integrarse en startup/build.

Bundlear el extracto `ADM0_A3 == ESP` de [Natural Earth admin 0 a escala 1:10m](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson), fijando commit de origen y registrando procedencia y [dominio público](https://www.naturalearthdata.com/about/terms-of-use/) junto al archivo. El extracto inspeccionado contiene 23 polígonos e incluye península, islas, Ceuta, Melilla y Llívia. Muestrear con `random.Random(seed)` y rechazo contra esos polígonos, respetando huecos; comprobar también el par redondeado que se enviará. Una caja rectangular sin comprobar pertenencia no es suficiente. Los límites son generalizados: estos puntos son datos sintéticos, no instalaciones o direcciones reales; no se promete distribución idéntica por territorio ni precisión catastral.

Generar alias deterministas `DEMO-<seed>-<índice>`, `address: null`, coordenadas válidas y `active: true`. Una configuración sencilla de seis celdas habilitadas de 400×400×600 mm por locker basta; la API crea las celdas libres. La semilla reproduce los payloads y coordenadas con el mismo dato de referencia, no los UUID del servidor. No usar Photon para generar puntos ni inventar direcciones.

Enviar `POST /lockers` secuencialmente con timeout acotado, contando únicamente respuestas de creación confirmadas. Ante primer fallo o respuesta incierta, detenerse, informar del índice y número confirmado y salir con código no cero, sin reintentar escrituras, borrar existentes o simular rollback global. Otra ejecución añade nuevos registros, aunque repita semilla/alias: no se añade idempotencia. README muestra primero dry-run y después ejecución explícita contra una API de demostración; las comprobaciones escribirán solo en un stack desechable, nunca en los datos del usuario.

### 9. Verificación

- `npm ci`, check y build con API apagada; inspeccionar salida y servir `dist` mediante HTTP estático genérico. Comprobar que solo el navegador pide lockers y que cambiar la URL requiere nuevo build.
- Vitest para contrato, disponibilidad, coordenadas inválidas, URL/configuración, errores y timeout. Tests backend de CORS en aplicación real con dependencias simuladas, siguiendo las pruebas actuales de `create_app`.
- Playwright sobre `dist`, con API HTTP en otro origen local y peticiones reales para comprobar CORS permitido/denegado. No basta interceptar `/lockers`: al menos esa prueba debe atravesar el middleware real de FastAPI. Las demás pruebas pueden usar fixtures controladas para estados y selección.
- Teselas interceptadas con imagen local solo en pruebas; cubrir fallo de teselas, territorios, solapamientos, nulls, texto no ejecutable, teclado y móvil. La red actual bloquea OSM real: registrar esa limitación separadamente.
- Smoke del frontend estático contra `GET /lockers` real con base nueva del backend en entorno desechable, esperando `[]` sin seeds. Usar solo recursos temporales y ejecutar `scripts/ci/smoke.sh` para verificar regresión de Compose; registrar cualquier limitación real del entorno.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings` debe dar cero errores y cero advertencias; ejecutar `env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL uv run --extra dev python -m unittest discover -s tests/unit -t . -v`. Ejecutar check/test/build/e2e finales del frontend, validar OpenSpec y obtener revisión independiente.

La ampliación Nginx conserva la evidencia anterior y añade comprobaciones proporcionadas: construir la imagen sin API, inspeccionar que solo sirve archivos estáticos sin Node, resolver Compose normal/CI y comprobar el argumento de URL personalizado. En un stack temporal real, abrir la página de Nginx y verificar lectura directa a FastAPI con CORS sin interceptar la API; las teselas pueden seguir controladas. Repetir smoke backend y Pyright obligatorio, validar OpenSpec y realizar revisión independiente de los archivos afectados. No ampliar la suite CI ni repetir pruebas funcionales ajenas a estos cambios.

Para pantalla completa y formulario: comprobar geometría del mapa contra el viewport y ubicación del menú en escritorio/móvil; etiquetas, campos vacíos y decimales positivos; edición/tabulación/scroll sin mover el mapa ni añadir peticiones; apertura/cierre de lista y selección de detalles, incluidos lockers sin coordenadas y coincidentes; errores/reintento visibles con panel cerrado. Ejecutar check, build y E2E afectados, inspección visual, Pyright obligatorio con cero errores/advertencias, validación OpenSpec y revisión independiente. La evidencia anterior no sustituye estas verificaciones nuevas.

Para la nueva ampliación: Vitest de URLs dirección/CP con cero inicial, país, normalización y errores/cancelación; E2E de rueda dentro/fuera de overlays, inicial frente a «Ver España», búsqueda única/ambigua/vacía/fallida, respuestas obsoletas y encuadre visible con lista abierta/cerrada en móvil. Verificar que las búsquedas no llaman a la API de lockers y que una carga vacía no deshace el encuadre. Pruebas unitarias Python de 1000 payloads, pertenencia geográfica y huecos, determinismo, dry-run sin HTTP, contrato de creación y fallo parcial sin reintento. Smoke API y navegador con los 1000 lockers en un stack temporal, sin seeds automáticos. Ejecutar check/test/build/E2E afectados, unitarias backend y Pyright obligatorio, validación estricta y revisión independiente; documentar por separado la conectividad externa no comprobada.

Para el panel único y sugerencias: comprobar disposición, contadores vivos al final y controles conservados en escritorio y 375×480; debounce/umbral, CP con cero, uno y varios candidatos sin pan previo, cierre/rellenado al elegir sin petición adicional, respuestas antiguas, Escape/foco/blur y ausencia de controles ocultos enfocables. Verificar animación interrumpida y movimiento reducido, carga/vacío/error/reintento y regresiones de medidas, encuadre, listado/detalle y aislamiento del mapa. Usar respuestas Photon y teselas controladas; ejecutar check/test/build/E2E afectados, Pyright obligatorio con cero errores/advertencias, validación estricta y revisión independiente. No repetir el smoke de 1000 lockers para este ajuste de interfaz.

## Risks / Trade-offs

- API pública o CORS todavía sin configurar -> placeholders y requisitos explícitos; un build local no demuestra que la futura URL pública funcione.
- El plan gratuito de Pages cubre el frontend estático -> no presupone alojamiento del backend ni sus dependencias.
- OSM puede fallar y la colección completa puede crecer -> listado disponible y pruebas deterministas; paginación o cambio de proveedor quedan para una necesidad posterior.
- Capacidad cambia entre lecturas y existen datos sin coordenadas -> refresco manual y mensajes honestos, sin reservar ni inventar posiciones.
- Photon puede fallar o no localizar una dirección/CP -> estado independiente y reintento explícito, sin alterar lockers; las pruebas controladas no garantizan cobertura del proveedor.
- El generador puede terminar con creaciones parciales y sus límites son cartográficos -> informar progreso confirmado, no reintentar automáticamente y documentar datos sintéticos y procedencia.

## Migration Plan

No hay migraciones. Las ampliaciones anteriores y el panel único con sugerencias automáticas están aprobados, implementados y verificados. El generador sigue siendo manual y los datos existentes se conservan. Publicación efectiva, sincronización y archivo no forman parte de esta actualización de planificación.
