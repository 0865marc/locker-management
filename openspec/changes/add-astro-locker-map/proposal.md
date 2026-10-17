# Proposal

## Why

La API ya conoce la ubicación y la capacidad de los lockers, pero no existe una interfaz para encontrarlos visualmente. Un frontend estático con Astro permitirá consultar los datos reales sobre un mapa de España y publicar sus archivos en el alojamiento gratuito de Cloudflare Pages.

## What Changes

- Añadir una página en español con mapa interactivo a toda pantalla, adaptable a móvil y escritorio, y listado/detalle de lockers en un panel plegable superpuesto.
- Situar arriba a la izquierda un menú compacto «Tu paquete», con largo, ancho y alto en centímetros y peso en kilogramos. Los campos empiezan vacíos y solo permiten introducir datos locales; no filtran, cotizan ni envían solicitudes.
- Habilitar zoom con la rueda sobre el mapa y una vista inicial más cercana a la España peninsular; «Ver España» conserva el encuadre de todos los territorios.
- Añadir encima de las dimensiones una búsqueda explícita por dirección o código postal español mediante Photon, con hasta cinco candidatos seleccionables y estados independientes. Elegir un resultado acerca el mapa sin filtrar lockers ni enviar los datos del paquete.
- Proporcionar un script manual para crear por API 250 lockers sintéticos disponibles por defecto en posiciones terrestres de España, con cantidad configurable mediante `--count`, semilla, URL API y simulación sin escrituras configurables.
- Mostrar como disponibles los lockers activos con al menos una celda habilitada y libre. La consulta será informativa, sin comprobar tamaños de paquetes ni reservar capacidad.
- Representar las coordenadas guardadas, cubriendo península, Baleares, Canarias, Ceuta y Melilla. Conservar en el listado los disponibles sin coordenadas, identificándolos explícitamente.
- Resolver carga, ausencia de resultados, errores, actualización manual y recuperación; mantener el listado utilizable si falla la cartografía externa.
- Generar únicamente HTML, CSS y JavaScript estáticos con Astro. Cargar lockers, validar datos, filtrar disponibilidad y gestionar Leaflet/OSM íntegramente en el navegador, consultando directamente `GET /lockers`.
- Configurar la URL pública de la API al compilar mediante `PUBLIC_API_BASE_URL`, y añadir en FastAPI una lista explícita de orígenes CORS permitidos para el frontend.
- Servir el build estático con Nginx en un servicio `frontend` de Compose, accesible en `http://127.0.0.1:4321`, para arrancar aplicación y backend con `docker compose up --build`.
- Documentar arranque completo con Compose, desarrollo npm opcional, build reproducible y preparación de Cloudflare Pages: directorio `frontend`, salida `dist`, API HTTPS y orígenes concretos.

Quedan fuera administración desde la web, autenticación, reservas, búsquedas de lockers por cercanía, nuevas reglas de capacidad, geocodificación de lockers guardados, seeds automáticos al arrancar, publicación efectiva y ampliaciones generales de CI. La búsqueda solo localiza una consulta del usuario; el generador se ejecuta manualmente. El contenedor frontend sigue sirviendo archivos estáticos.

## Capabilities

### New Capabilities

- `locker-map`: Consulta visual y accesible de lockers disponibles, navegación del mapa, búsqueda de dirección/CP, detalle y estados independientes.

### Modified Capabilities

- `application-runtime`: Build y distribución estáticos, Compose, configuración pública/CORS y herramienta manual de creación de datos sintéticos mediante la API existente.

## Impact

- Nuevos archivos bajo `frontend/`: aplicación Astro/TypeScript, estilos, Leaflet, cliente HTTP, configuración npm y lockfile, `.env.example`, pruebas, Dockerfile multietapa y `.dockerignore`.
- Cambios acotados en `backend/main.py`, configuración HTTP CORS y sus pruebas, `compose.yaml`, `compose.ci.yaml`, `.gitignore` y `README.md`. La ampliación Nginx solo añade empaquetado estático, servicio Compose, aislamiento de puertos CI y documentación.
- Se conserva el contrato de lockers, dominio, aplicación Python, persistencia y migraciones. Node se utiliza solo como herramienta de desarrollo, build y pruebas.
- Cloudflare Pages alojará archivos estáticos; la API de producción debe estar accesible por HTTPS desde el navegador. No se presupone ni incluye alojamiento gratuito de FastAPI/PostgreSQL/RabbitMQ.
- Las pruebas de interfaz interceptarán las teselas de OSM, bloqueadas por la red actual; la integración CORS se comprobará con peticiones reales entre orígenes locales distintos.
- La ampliación de pantalla completa y formulario afecta únicamente a la página/componente, estilos y script existentes, pruebas E2E y una explicación breve en README. Conserva backend, disponibilidad, configuración estática, Compose y Cloudflare sin cambios.
- La nueva ampliación añade un cliente Photon y pruebas de búsqueda en `frontend/`, `backend/scripts/seed_lockers.py`, un polígono local de España con procedencia/licencia y pruebas unitarias del generador; `backend/Dockerfile` incluirá `COPY scripts ./scripts` para permitir su ejecución manual desde Compose. README documentará ambos usos. No cambia endpoints, dominio ni migraciones. Photon es externo y su acceso real no se ha podido comprobar en este entorno; las pruebas usarán respuestas controladas.
