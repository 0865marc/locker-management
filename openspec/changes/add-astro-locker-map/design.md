# Design

## Context

Ver la motivación en `proposal.md`. El backend FastAPI expone `GET /lockers` con UUID, `active`, celdas no retiradas y geografía nullable. El frontend estático y CORS ya están implementados y verificados. El usuario ha aprobado añadir Nginx a Compose para arrancar también la web, conservando toda consulta e interacción en el navegador y la compatibilidad con Cloudflare Pages.

## Goals / Non-Goals

**Goals:** archivos estáticos independientes del backend durante el build, lectura directa de la API y acceso CORS explícito, conservando la experiencia de mapa/lista definida en `specs/locker-map/spec.md`.

**Non-Goals:** servidor de aplicación frontend, funciones de Cloudflare, nueva autenticación o cambios de dominio, capacidad o persistencia. Nginx solo sirve archivos estáticos; este cambio no publica en Cloudflare ni proporciona alojamiento para FastAPI/PostgreSQL/RabbitMQ.

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

Leaflet usa `https://tile.openstreetmap.org/{z}/{x}/{y}.png` con atribución y enlace visibles. Vista inicial y «Ver España»: límites aproximados `[27.5, -18.5]` a `[44, 4.5]`, incluyendo península, Baleares, Canarias, Ceuta y Melilla. No inferir coordenadas ni aplicar geocerca. La lista puede seleccionar cualquier posición válida almacenada, incluso fuera del encuadre inicial.

Seleccionar fila centra y abre el marcador correspondiente; seleccionar marcador muestra el mismo detalle. Dos lockers coincidentes conservan sus coordenadas y filas independientes, y la selección trae al frente su marcador. Mostrar disponibles y posicionables, con «Sin coordenadas válidas» cuando corresponda. Sin resultados, el mapa conserva la vista de España.

Carga inicial, actualizar y reintentar comparten flujo; impedir intentos simultáneos. Tras fallo se eliminan resultados/posiciones que podrían confundirse con disponibilidad vigente. Cada éxito reemplaza resultados y limpia una selección desaparecida. Los errores de teselas generan aviso independiente y conservan la lista utilizable. No precargar mapas ni incluir teselas de prueba en producción; respetar atribución, caché HTTP y Referer del proveedor.

Mapa/lista se adaptan a escritorio y móvil de 375 px sin desbordamiento horizontal. Controles nativos, foco visible y estados anunciados permiten consultar detalles por teclado. La interfaz describe disponibilidad como última lectura, sin reserva ni garantía de tamaño; una hora visible representa actualización del cliente, no un timestamp inventado del backend.

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

### 8. Verificación

- `npm ci`, check y build con API apagada; inspeccionar salida y servir `dist` mediante HTTP estático genérico. Comprobar que solo el navegador pide lockers y que cambiar la URL requiere nuevo build.
- Vitest para contrato, disponibilidad, coordenadas inválidas, URL/configuración, errores y timeout. Tests backend de CORS en aplicación real con dependencias simuladas, siguiendo las pruebas actuales de `create_app`.
- Playwright sobre `dist`, con API HTTP en otro origen local y peticiones reales para comprobar CORS permitido/denegado. No basta interceptar `/lockers`: al menos esa prueba debe atravesar el middleware real de FastAPI. Las demás pruebas pueden usar fixtures controladas para estados y selección.
- Teselas interceptadas con imagen local solo en pruebas; cubrir fallo de teselas, territorios, solapamientos, nulls, texto no ejecutable, teclado y móvil. La red actual bloquea OSM real: registrar esa limitación separadamente.
- Smoke del frontend estático contra `GET /lockers` real con base nueva del backend en entorno desechable, esperando `[]` sin seeds. Usar solo recursos temporales y ejecutar `scripts/ci/smoke.sh` para verificar regresión de Compose; registrar cualquier limitación real del entorno.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings` debe dar cero errores y cero advertencias; ejecutar `env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL uv run --extra dev python -m unittest discover -s tests/unit -t . -v`. Ejecutar check/test/build/e2e finales del frontend, validar OpenSpec y obtener revisión independiente.

La ampliación Nginx conserva la evidencia anterior y añade comprobaciones proporcionadas: construir la imagen sin API, inspeccionar que solo sirve archivos estáticos sin Node, resolver Compose normal/CI y comprobar el argumento de URL personalizado. En un stack temporal real, abrir la página de Nginx y verificar lectura directa a FastAPI con CORS sin interceptar la API; las teselas pueden seguir controladas. Repetir smoke backend y Pyright obligatorio, validar OpenSpec y realizar revisión independiente de los archivos afectados. No ampliar la suite CI ni repetir pruebas funcionales ajenas a estos cambios.

## Risks / Trade-offs

- API pública o CORS todavía sin configurar -> placeholders y requisitos explícitos; un build local no demuestra que la futura URL pública funcione.
- El plan gratuito de Pages cubre el frontend estático -> no presupone alojamiento del backend ni sus dependencias.
- OSM puede fallar y la colección completa puede crecer -> listado disponible y pruebas deterministas; paginación o cambio de proveedor quedan para una necesidad posterior.
- Capacidad cambia entre lecturas y existen datos sin coordenadas -> refresco manual y mensajes honestos, sin reservar ni inventar posiciones.

## Migration Plan

No hay migraciones. Incorporar la ampliación Nginx aprobada, verificar Compose y documentar el arranque completo. Retirar el servicio estático y sus archivos revierte esta ampliación sin tocar datos ni revisiones Alembic. Preparar posteriormente una API HTTPS y los orígenes exactos antes de publicar en Pages. Publicación efectiva, sincronización y archivo no forman parte de esta actualización de planificación.
