# Tasks

Las tareas 1–7 registran los 23 trabajos anteriores aprobados, implementados y verificados. El usuario ha aprobado explícitamente la ampliación de navegación, búsqueda y generador de la sección 8; su implementación, verificación y revisión independiente están completadas. Las exclusiones históricas de búsqueda geográfica y datos de ejemplo quedan sustituidas únicamente por búsqueda de consultas del usuario y generación manual; no hay geocodificación de lockers ni seeds al arrancar. Publicación, sincronización y archivo quedan fuera de este alcance.

## 1. Astro estático y preparación de publicación

- [x] 1.1 Crear `frontend/` con Astro estático, TypeScript, Leaflet, lockfile, scripts dev/check/build/preview/test/e2e e ignores. Verificar `npm ci`, check y build con API apagada; confirmar que `dist` contiene solo archivos estáticos y ninguna instantánea de lockers.
- [x] 1.2 Añadir `frontend/.env.example` con `PUBLIC_API_BASE_URL` local explícita y documentar desarrollo, preview y servicio HTTP estático de `dist`. Verificar que cambiar la URL exige nuevo build y que Node solo se utiliza para herramientas.
- [x] 1.3 Documentar Cloudflare Pages: raíz `frontend`, build `npm run build`, salida `dist`, Node 24, instalación bloqueada con `npm ci`, variable pública de build y prerrequisitos HTTPS/CORS con placeholders. Revisar que la guía contempla instalación explícita si la automática no garantiza `npm ci`, y no promete alojamiento del backend ni efectúa publicación.

## 2. Datos y conexión desde el navegador

- [x] 2.1 Implementar contrato/normalización/proyección con pruebas Vitest para disponibilidad, celdas vacías/deshabilitadas/ocupadas, etiquetas nullable y coordenadas inválidas. Verificar que solo cuentan celdas habilitadas y libres de lockers activos, que coordenadas inválidas conservan la fila y que campos esenciales inválidos rechazan la carga.
- [x] 2.2 Implementar fetch directo al API público con credenciales omitidas, `no-store` y cancelación a cinco segundos. Probar URL ausente/inválida, HTTP bajo página HTTPS, HTTP fallido, red/CORS, timeout y respuesta malformada; verificar error visible, ausencia de fallback y ninguna escritura o lectura durante build.

## 3. CORS del backend y uso local

- [x] 3.1 Configurar CORS en composición/adaptador HTTP mediante `CORS_ALLOWED_ORIGINS`, orígenes exactos, GET preflight y sin credenciales ni comodines. Añadir pruebas con la aplicación y fakes para allow/deny, preflight GET/escritura, lista vacía/inválida y solicitudes sin Origin; verificar preservación de rutas y contratos existentes.
- [x] 3.2 Pasar la variable CORS al servicio API en `compose.yaml` con orígenes locales explícitos y documentar sustitución por Pages/dominio propio y previews concretos. Verificar configuración Compose y ejemplos locales. En esta fase inicial se excluyeron el servicio frontend y cambios en `compose.ci.yaml`; la fase 6 incorporó ambos preservando volúmenes.

## 4. Mapa, listado y estados

- [x] 4.1 Implementar página española, Leaflet/OSM con atribución, vista «España», lista/detalle y selección por UUID en ambos sentidos. Añadir pruebas Playwright para península, Baleares, Canarias, Ceuta, Melilla y coordenadas coincidentes; verificar acceso individual y posiciones reales.
- [x] 4.2 Incorporar etiquetas alias/dirección/UUID, capacidad y contadores de disponibles/posicionables. Probar nulls, todos los disponibles sin coordenadas, códigos postales textuales y markup renderizado literalmente; verificar ausencia de fixtures o seeds en producción.
- [x] 4.3 Implementar carga, vacío, error, reintento y actualización manual, eliminando disponibilidad obsoleta tras fallo y selección desaparecida tras éxito. Probar transiciones y cambio de capacidad, con nuevas lecturas y sin solicitudes de escritura; documentar significado y límites de disponibilidad en README.
- [x] 4.4 Completar fallback ante fallo de teselas, adaptación móvil/escritorio, controles etiquetados, foco y anuncios. Verificar teselas fallidas con lista utilizable, teclado y 375 px sin desbordamiento; documentar dependencia y atribución OSM.

## 5. Verificación integrada y revisión

- [x] 5.1 Servir `dist` con un servidor estático genérico y una API en otro origen local; probar mediante navegador CORS permitido/denegado atravesando el middleware real FastAPI, sin interceptar esas peticiones. Ejecutar check/test/build/e2e finales e inspección visual; registrar uso de teselas controladas y limitación de acceso real a OSM.
- [x] 5.2 Realizar smoke del frontend estático contra backend real en entorno desechable con colección vacía y ejecutar `scripts/ci/smoke.sh`. Verificar página HTTP 200 y lectura directa de lockers con `[]`, sin seeds ni alteración de datos existentes; registrar comandos y posibles limitaciones del entorno.
- [x] 5.3 Desde `backend/`, ejecutar `uv run --extra dev pyright --project .. --warnings` con cero errores y cero advertencias y `env -u TEST_DATABASE_URL -u TEST_RABBITMQ_URL uv run --extra dev python -m unittest discover -s tests/unit -t . -v`. Resolver regresiones y conservar evidencia real.
- [x] 5.4 Validar `openspec validate add-astro-locker-map --strict` y obtener revisión independiente de `sdd_reviewer` contra escenarios, CORS y arquitectura estática. Resolver hallazgos y repetir comprobaciones afectadas; entregar estado de implementación sin sincronizar, archivar ni publicar implícitamente.

## 6. Frontend estático en Compose

- [x] 6.1 Añadir `frontend/Dockerfile` multietapa con Node 24, `npm ci`, argumento `PUBLIC_API_BASE_URL` y build Astro, copiando solo `dist` a Nginx Alpine; añadir `.dockerignore` para dependencias, salidas y entornos locales. Verificar build sin API, URL incorporada y runtime que sirve HTML/assets sin Node, npm, proxy ni sustitución de variables.
- [x] 6.2 Añadir servicio `frontend` en `compose.yaml` con puerto `127.0.0.1:4321:80` y argumento de build por defecto `http://127.0.0.1:8000`; resetear sus puertos en `compose.ci.yaml`. Actualizar README para arranque completo con Compose, desarrollo npm opcional, configuración/rebuild y exclusividad del puerto 4321. Verificar `docker compose config` normal/CI, URL personalizada y preservación del flujo Pages y de servicios/volúmenes existentes.
- [x] 6.3 Ejecutar smoke manual en stack Compose desechable: página y assets de Nginx accesibles, lectura real del navegador a FastAPI con CORS y estado vacío `[]` sin interceptar la API. Ejecutar `scripts/ci/smoke.sh` y limpiar únicamente recursos temporales; registrar evidencia y limitación de teselas sin ampliar workflows o funcionalidad UI.
- [x] 6.4 Ejecutar desde `backend/` `uv run --extra dev pyright --project .. --warnings` con cero errores y cero advertencias; validar `openspec validate add-astro-locker-map --strict` y obtener revisión independiente de la ampliación. Resolver hallazgos y registrar resultados antes de marcar las tareas nuevas completas.

## 7. Mapa a pantalla completa y entrada local de paquete

- [x] 7.1 Adaptar página, componente y estilos existentes para mapa a todo el viewport y panel compacto «Tu paquete» arriba a la izquierda, con largo/ancho/alto (cm) y peso (kg) vacíos. Añadir comprobaciones E2E de geometría, ubicación, etiquetas y accesibilidad de controles/atribución en escritorio y 375 px; verificar que no hay cabecera, pie o márgenes que resten área al mapa.
- [x] 7.2 Incorporar entrada numérica decimal positiva con validación mínima y valores locales, sin submit, persistencia, filtros o cotizaciones. Verificar edición, vaciado, valores no positivos, tabulación y scroll del panel sin navegación del mapa ni peticiones nuevas; conservar valores al actualizar disponibilidad o abrir/cerrar la lista.
- [x] 7.3 Convertir resultados en panel plegable independiente, cerrado inicialmente y accesible mediante «Ver lockers», conservando detalles y estados/acciones visibles con panel cerrado. Ajustar E2E para apertura/cierre/foco, selección por marcador, lista larga, coordenadas ausentes/coincidentes y error/reintento; actualizar README para explicar el formulario local y el acceso al listado.
- [x] 7.4 Ejecutar `npm run check`, `npm run build` y E2E afectados; inspeccionar escritorio/móvil y comprobar que el flujo GET existente se conserva. Ejecutar desde `backend/` `uv run --extra dev pyright --project .. --warnings` con cero errores y advertencias, validar OpenSpec y obtener revisión independiente antes de completar las cuatro tareas nuevas.

## 8. Navegación, búsqueda geográfica y lockers sintéticos

- [x] 8.1 Habilitar rueda sobre el mapa, encuadre inicial peninsular más cercano y «Ver España» con todos los territorios; eliminar el reset de vista causado por renders sin marcadores. Actualizar pruebas E2E y nota de uso para verificar zoom en ambos sentidos, aislamiento de overlays, diferencia de encuadres y conservación de navegación tras carga/refresh vacío en escritorio y móvil.
- [x] 8.2 Incorporar búsqueda de dirección/CP encima de dimensiones, con formulario independiente, helper Photon tipado, envío explícito, hasta cinco candidatos, estados propios, timeout/cancelación y descarte de respuestas obsoletas. Añadir Vitest/E2E para CP con ceros iniciales, consulta única/ambigua, país ES, errores, texto seguro y encuadre visible con lista abierta/cerrada sin alterar lockers o valores del paquete; documentar proveedor, atribución y límite de conectividad real.
- [x] 8.3 Añadir `backend/scripts/seed_lockers.py`, extracto español Natural Earth con procedencia/licencia y pruebas unitarias; documentar count=1000, seed, base URL, dry-run y ejecución manual local o mediante `docker compose exec api python scripts/seed_lockers.py` tras rebuild. Verificar 1000 payloads disponibles con posiciones dentro de polígonos/huecos, reproducibilidad, dry-run sin HTTP, validación de opciones y creación secuencial con fallo parcial sin reintento ni borrado; no modificar API, dominio o migraciones.
- [x] 8.4 Ejecutar check/test/build y E2E afectados, unitarias backend y `uv run --extra dev pyright --project .. --warnings` desde `backend/` con cero errores y advertencias. Comprobar generador/API/mapa con 1000 lockers en stack desechable, conservando los datos del usuario; registrar conectividad externa no comprobada, validar OpenSpec y obtener revisión independiente antes de completar las nuevas tareas.

## Evidencia de verificación — 2026-10-17

- `npm ci` con lockfile: correcto. `npm run check`: cero errores, advertencias y hints; `npm test`: 37 pruebas; `npm run test:e2e`: 10 pruebas en Chromium, incluidas peticiones reales entre orígenes a FastAPI.
- Build con API apagada: correcto, salida formada por HTML/CSS/JavaScript. Cambiar `PUBLIC_API_BASE_URL` solo cambia los assets después de recompilar. Build local final preparado para `http://127.0.0.1:8000`.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings`: cero errores y advertencias. Suite unitaria: 84 pruebas correctas. Ruff de archivos Python modificados: correcto.
- Configuración Compose comprobada con CORS por defecto, vacío y personalizado; servicios y volúmenes originales conservados.
- `scripts/ci/smoke.sh`: correcto, `GET /lockers` devuelve 200 y `[]` sobre base nueva. El entorno cloud requirió un Dockerfile temporal que monta su CA para instalar dependencias; el Dockerfile del repositorio no se modificó.
- Navegador sirviendo el build con HTTP estático frente a FastAPI/PostgreSQL/RabbitMQ reales: página 200, API 200 con `[]`, origen CORS exacto, estado vacío correcto y cero errores JavaScript. Stacks y volúmenes temporales eliminados al terminar.
- Revisión independiente de `sdd_reviewer`: sin hallazgos pendientes. Corregidos y comprobados el detalle fuera de vista en listas largas y la restauración del encuadre de España tras resultados vacíos.
- Las pruebas interceptan las teselas de OpenStreetMap y verifican su fallo por separado; el acceso real al proveedor no se comprobó por la política de red del entorno.


## Evidencia de ampliación Compose — 2026-10-17

- Imagen frontend construida con la API apagada: `npm ci` y build Astro correctos. La imagen Nginx contiene solo los cuatro archivos HTML/CSS/JS de `dist`, sin Node, npm ni fuentes; `nginx -t` correcto. La CA del proxy de este entorno se montó mediante un Dockerfile/override temporal, sin alterar los archivos del repositorio ni desactivar TLS.
- `docker compose config`: puerto `127.0.0.1:4321:80`, argumento de URL local, personalizado y vacío explícito comprobados; sin dependencias de arranque del frontend. Configuración CI sin puertos frontend/API/DB. Servicios backend y volúmenes iguales a los anteriores.
- Reconstruir con `PUBLIC_API_BASE_URL=https://lockers.example.test/v1` incorpora esa URL y elimina la local del bundle. Una variable de runtime diferente no modifica el contenido compilado.
- Nginx arrancado solo: página HTTP 200 con error recuperable y botón de reintento mientras la API está apagada. Stack completo desechable: migraciones, API, worker, PostgreSQL, RabbitMQ y frontend arrancan correctamente.
- Navegador real tras comprobar disponibilidad de la API: desde `localhost:4321` y `127.0.0.1:4321`, página HTTP 200, tres assets con tipo correcto, `GET /lockers` HTTP 200 con `[]`, CORS exacto, mapa inicializado y cero errores JavaScript. La primera visita durante el arranque no recibió respuesta de API; tras estar lista la prueba pasó. Solo se interceptaron las teselas, nunca la API.
- `scripts/ci/smoke.sh`: correcto, `GET /lockers` HTTP 200 con `[]`. Ambos proyectos y sus volúmenes temporales se eliminaron tras verificar; se conservaron los datos existentes.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings`: cero errores y advertencias, comprobado también por el revisor. `openspec validate add-astro-locker-map --strict` y `git diff --check`: correctos.
- Revisión independiente de `sdd_reviewer` de la ampliación: sin hallazgos pendientes. No se han sincronizado ni archivado las especificaciones.


## Evidencia de pantalla completa y formulario — 2026-10-17

- Mapa del tamaño exacto del viewport y panel de paquete arriba a la izquierda comprobados en 1280×800, 375×667 y 375×480. Capturas inspeccionadas con listado cerrado, abierto y selección; controles de zoom y atribución accesibles sin solaparse con paneles.
- Campos inicialmente vacíos, decimales positivos y validación de cero/negativos: correctos. Editar, tabular, arrastrar o desplazar el panel no mueve el mapa ni añade peticiones. Los valores sobreviven a actualización y apertura/cierre del listado; no se persisten.
- Listado plegable, enlace de salto, Escape, retorno de foco, detalles, lockers sin coordenadas y coincidentes, carga/error/reintento y CORS real comprobados. La selección conserva las coordenadas y encuadra el marcador entre paneles; el hit-test demuestra que se puede pulsar también en móvil. El detalle completo permanece en la lista cuando no hay espacio para un popup.
- `npm run check`: cero errores, advertencias y hints. `npm test`: 37 pruebas correctas. `npm run test:e2e`: 15 pruebas correctas en Chromium. `npm run build`: salida estática correcta. Las teselas están controladas en pruebas; no se ha comprobado acceso real al proveedor OSM.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings`: cero errores y cero advertencias. Se conservan configuración y alcance de tipos, dependencias, backend, Compose y despliegue estático.
- Revisión independiente de `sdd_reviewer`: sin hallazgos pendientes. Se corrigió y revalidó el marcador oculto por paneles en móvil con tres hit-tests por tamaño de pantalla. OpenSpec estricto y `git diff --check` correctos; sin sincronización ni archivo.

## Evidencia de navegación, búsqueda y generador — 2026-10-17

- Rueda en ambos sentidos sobre el mapa, aislamiento de overlays, vista inicial peninsular y «Ver España» comprobados. Carga y actualización sin posiciones conservan la navegación elegida.
- Búsqueda explícita de dirección y CP con ceros iniciales, país ES, una coincidencia o selección entre varias, etiquetas duplicadas, texto seguro, vacío/error/reintento, timeout y descarte de respuestas obsoletas verificados. El punto buscado queda accesible con listado abierto o cerrado en escritorio y móvil; medidas y disponibilidad mantienen su estado independiente.
- `npm run check`: cero errores, advertencias y hints. `npm test`: 57 pruebas correctas, incluidas 20 del cliente de búsqueda. `npm run test:e2e`: 21 pruebas correctas. `npm run build`: salida estática correcta; `dist` local final apunta a `http://127.0.0.1:8000`.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings`: cero errores y cero advertencias, reejecutado también por el revisor. Suite unitaria: 98 pruebas correctas, incluidas 14 del generador. Ruff check y formato de los archivos Python nuevos: correctos.
- Generador empaquetado mediante `COPY scripts ./scripts`, con GeoJSON local de Natural Earth fijado al commit `ca96624a56bd078437bca8184e78163e5039ad19` y procedencia/licencia documentadas. Verificados 1000 payloads reproducibles, pertenencia y huecos, coordenadas redondeadas, opciones inválidas, dry-run sin HTTP y fallos parciales/lectura HTTP truncada sin reintentar ni borrar.
- Smoke de Compose en proyecto desechable: colección inicialmente vacía y ejecución real `docker compose exec -T api python scripts/seed_lockers.py` con `Confirmados: 1000/1000`. `GET /lockers` confirma 1000 UUID únicos y 6000 celdas habilitadas libres. La imagen API final incluye la última validación de hostname y produce 1000 payloads en dry-run; conserva los 1000 registros tras reemplazar el contenedor.
- Nginx estático en puerto 4322 frente a FastAPI/PostgreSQL/RabbitMQ reales en puerto 8770: 1000 filas y marcadores, mapa a todo el viewport y selección accesible por hit-test en 1280×800, 375×667 y 375×480. Tres lecturas HTTP 200 con CORS exacto y cero errores JavaScript. La API no se interceptó. La CA del entorno se montó solo en Dockerfiles/overrides temporales, sin cambios de confianza TLS en el repositorio.
- Las pruebas controlan Photon y las teselas OSM; su conectividad pública real no se ha verificado por la política de red. Revisión independiente de `sdd_reviewer`: sin hallazgos pendientes. Eliminados únicamente contenedores, red y volúmenes del proyecto temporal de prueba. No se han sincronizado ni archivado las especificaciones.
