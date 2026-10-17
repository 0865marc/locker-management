# Proposal

## Why

El mapa estático ya permite encontrar lockers disponibles. La web pública debe ayudar a comparar cuánto cuesta enviar un paquete al locker elegido, reutilizando las cotizaciones asíncronas existentes y simplificando los controles que distraen de ese recorrido.

## What Changes

- Mantener el mapa de España a pantalla completa, zoom con rueda, búsqueda automática de dirección/CP con sugerencias animadas y el formulario de dimensiones/peso.
- Dejar en el menú superior buscador, paquete y contadores vivos. Retirar el mensaje repetido de éxito, «Ver lockers», «Actualizar», hora de lectura, «Ver España» y nota informativa; conservar carga, vacío, errores y reintento solo cuando corresponda.
- Sustituir el catálogo/detalle técnico por «Enviar a este locker», abierto al seleccionar un marcador o mediante un acceso de teclado. Un selector compacto permite elegir también lockers coincidentes o sin coordenadas.
- Usar el locker como destino: CP de origen obligatorio y CP de destino obtenido de su dirección estructurada o solicitado cuando falte. Reutilizar las dimensiones y peso superiores, validándolos al pulsar «Comparar envíos».
- Crear una cotización mediante `POST /quotations` y consultar su resultado mediante GET, con espera acotada, cancelación local y sin repetir escrituras automáticamente. Mostrar proveedor, servicio, precio EUR, plazo y fallos independientes; identificar claramente las tarifas de demostración de los proveedores simulados actuales.
- Mantener disponibilidad como locker activo con alguna celda habilitada libre, coordenadas reales, atribución OSM y acceso a todos los territorios mediante navegación/selección. No inferir dirección, CP ni coordenadas.
- Conservar Astro completamente estático, llamadas directas del navegador y `PUBLIC_API_BASE_URL` al compilar. Ampliar CORS solo para POST JSON a `/quotations`, manteniendo GET, orígenes exactos y ausencia de credenciales.
- Conservar Nginx/Compose, preparación de Cloudflare Pages y generador manual de 250 lockers por defecto con cantidad configurable; esta ampliación no modifica esos flujos.

Esta ampliación sustituye las exclusiones anteriores de cotización desde la web y los requisitos de catálogo, actualización manual, «Ver España» y mensajes retirados. Siguen fuera reservas, contratación/pago, creación de envíos, comprobación de encaje en celdas, proveedores reales, geocodificación de lockers, administración, autenticación, seeds automáticos y publicación efectiva.

## Capabilities

### New Capabilities

- `locker-map`: Localización accesible de lockers y comparación pública de envíos hacia el destino seleccionado, con búsqueda, formulario, estados y resultados.

### Modified Capabilities

- `application-runtime`: Distribución estática, configuración pública, CORS acotado para las cotizaciones y herramienta manual de datos sintéticos.

Las capacidades existentes `shipping-quotes` y `asynchronous-shipping-quotations` se consumen sin cambiar sus contratos, modelos o procesamiento.

## Impact

- Frontend: página, componente, script, estilos, proyección de dirección/CP, cliente tipado de cotizaciones y pruebas unitarias/E2E; README explica el recorrido público y los simuladores.
- Backend: únicamente composición/adaptador CORS y sus pruebas. Se conservan endpoints, dominio, aplicación, worker, persistencia y migraciones; no se añaden dependencias ni cambios Compose.
- El backend existente requiere API, PostgreSQL, RabbitMQ y worker. Cloudflare aloja solo los archivos estáticos; la API pública necesita HTTPS y origen autorizado, sin despliegue incluido.
- Pruebas deterministas con teselas y Photon controlados, CORS real entre orígenes y cotización completa en un entorno desechable. La conectividad real de OSM/Photon sigue sin comprobarse en esta red.
