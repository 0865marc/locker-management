# Proposal

## Why

La API ya conoce la ubicación y la capacidad de los lockers, pero no existe una interfaz para encontrarlos visualmente. Un frontend estático con Astro permitirá consultar los datos reales sobre un mapa de España y publicar sus archivos en el alojamiento gratuito de Cloudflare Pages.

## What Changes

- Añadir una página en español con mapa interactivo, listado y detalle de lockers, adaptable a móvil y escritorio.
- Mostrar como disponibles los lockers activos con al menos una celda habilitada y libre. La consulta será informativa, sin comprobar tamaños de paquetes ni reservar capacidad.
- Representar las coordenadas guardadas, cubriendo península, Baleares, Canarias, Ceuta y Melilla. Conservar en el listado los disponibles sin coordenadas, identificándolos explícitamente.
- Resolver carga, ausencia de resultados, errores, actualización manual y recuperación; mantener el listado utilizable si falla la cartografía externa.
- Generar únicamente HTML, CSS y JavaScript estáticos con Astro. Cargar lockers, validar datos, filtrar disponibilidad y gestionar Leaflet/OSM íntegramente en el navegador, consultando directamente `GET /lockers`.
- Configurar la URL pública de la API al compilar mediante `PUBLIC_API_BASE_URL`, y añadir en FastAPI una lista explícita de orígenes CORS permitidos para el frontend.
- Documentar desarrollo con el backend Compose existente, build reproducible, servicio estático local y preparación de Cloudflare Pages: directorio `frontend`, salida `dist`, API HTTPS y orígenes concretos.

Quedan fuera administración, autenticación, reservas, geocodificación, búsquedas por cercanía, nuevas reglas de capacidad, datos automáticos de ejemplo, publicación efectiva y ampliaciones generales de CI. El frontend no requiere servidor de aplicación, funciones de Cloudflare ni contenedor propio. El alojamiento del backend se mantiene separado.

## Capabilities

### New Capabilities

- `locker-map`: Consulta visual y accesible de lockers disponibles, geografía real, detalle y estados de carga/error.

### Modified Capabilities

- `application-runtime`: Incorporar build y distribución estáticos, configuración pública de API y política CORS explícita en el backend.

## Impact

- Nuevos archivos bajo `frontend/`: aplicación Astro/TypeScript, estilos, Leaflet, cliente HTTP, configuración npm y lockfile, `.env.example` y pruebas.
- Cambios acotados en `backend/main.py`, configuración HTTP CORS y sus pruebas, `compose.yaml` para pasar los orígenes a API, `.gitignore` y `README.md`.
- Se conserva el contrato de lockers, dominio, aplicación Python, persistencia y migraciones. Node se utiliza solo como herramienta de desarrollo, build y pruebas.
- Cloudflare Pages alojará archivos estáticos; la API de producción debe estar accesible por HTTPS desde el navegador. No se presupone ni incluye alojamiento gratuito de FastAPI/PostgreSQL/RabbitMQ.
- Las pruebas de interfaz interceptarán las teselas de OSM, bloqueadas por la red actual; la integración CORS se comprobará con peticiones reales entre orígenes locales distintos.
