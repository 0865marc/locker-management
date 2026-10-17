# Tasks

Plan revisado aprobado por el usuario. Implementación y verificación completadas; publicación, sincronización y archivo quedan pendientes de autorización separada.

## 1. Astro estático y preparación de publicación

- [x] 1.1 Crear `frontend/` con Astro estático, TypeScript, Leaflet, lockfile, scripts dev/check/build/preview/test/e2e e ignores. Verificar `npm ci`, check y build con API apagada; confirmar que `dist` contiene solo archivos estáticos y ninguna instantánea de lockers.
- [x] 1.2 Añadir `frontend/.env.example` con `PUBLIC_API_BASE_URL` local explícita y documentar desarrollo, preview y servicio HTTP estático de `dist`. Verificar que cambiar la URL exige nuevo build y que Node solo se utiliza para herramientas.
- [x] 1.3 Documentar Cloudflare Pages: raíz `frontend`, build `npm run build`, salida `dist`, Node 24, instalación bloqueada con `npm ci`, variable pública de build y prerrequisitos HTTPS/CORS con placeholders. Revisar que la guía contempla instalación explícita si la automática no garantiza `npm ci`, y no promete alojamiento del backend ni efectúa publicación.

## 2. Datos y conexión desde el navegador

- [x] 2.1 Implementar contrato/normalización/proyección con pruebas Vitest para disponibilidad, celdas vacías/deshabilitadas/ocupadas, etiquetas nullable y coordenadas inválidas. Verificar que solo cuentan celdas habilitadas y libres de lockers activos, que coordenadas inválidas conservan la fila y que campos esenciales inválidos rechazan la carga.
- [x] 2.2 Implementar fetch directo al API público con credenciales omitidas, `no-store` y cancelación a cinco segundos. Probar URL ausente/inválida, HTTP bajo página HTTPS, HTTP fallido, red/CORS, timeout y respuesta malformada; verificar error visible, ausencia de fallback y ninguna escritura o lectura durante build.

## 3. CORS del backend y uso local

- [x] 3.1 Configurar CORS en composición/adaptador HTTP mediante `CORS_ALLOWED_ORIGINS`, orígenes exactos, GET preflight y sin credenciales ni comodines. Añadir pruebas con la aplicación y fakes para allow/deny, preflight GET/escritura, lista vacía/inválida y solicitudes sin Origin; verificar preservación de rutas y contratos existentes.
- [x] 3.2 Pasar la variable CORS al servicio API en `compose.yaml` con orígenes locales explícitos y documentar sustitución por Pages/dominio propio y previews concretos. Verificar configuración Compose y ejemplos locales; no añadir servicio frontend ni cambiar `compose.ci.yaml` o volúmenes.

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

## Evidencia de verificación — 2026-10-17

- `npm ci` con lockfile: correcto. `npm run check`: cero errores, advertencias y hints; `npm test`: 37 pruebas; `npm run test:e2e`: 10 pruebas en Chromium, incluidas peticiones reales entre orígenes a FastAPI.
- Build con API apagada: correcto, salida formada por HTML/CSS/JavaScript. Cambiar `PUBLIC_API_BASE_URL` solo cambia los assets después de recompilar. Build local final preparado para `http://127.0.0.1:8000`.
- Desde `backend/`, `uv run --extra dev pyright --project .. --warnings`: cero errores y advertencias. Suite unitaria: 84 pruebas correctas. Ruff de archivos Python modificados: correcto.
- Configuración Compose comprobada con CORS por defecto, vacío y personalizado; servicios y volúmenes originales conservados.
- `scripts/ci/smoke.sh`: correcto, `GET /lockers` devuelve 200 y `[]` sobre base nueva. El entorno cloud requirió un Dockerfile temporal que monta su CA para instalar dependencias; el Dockerfile del repositorio no se modificó.
- Navegador sirviendo el build con HTTP estático frente a FastAPI/PostgreSQL/RabbitMQ reales: página 200, API 200 con `[]`, origen CORS exacto, estado vacío correcto y cero errores JavaScript. Stacks y volúmenes temporales eliminados al terminar.
- Revisión independiente de `sdd_reviewer`: sin hallazgos pendientes. Corregidos y comprobados el detalle fuera de vista en listas largas y la restauración del encuadre de España tras resultados vacíos.
- Las pruebas interceptan las teselas de OpenStreetMap y verifican su fallo por separado; el acceso real al proveedor no se comprobó por la política de red del entorno.
