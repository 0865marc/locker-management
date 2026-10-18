# Proposal

## Why

La web ya permite cotizar y localizar paquetes. Ahora debe separar la búsqueda geográfica de la elección obligatoria de lockers de recogida y entrega, reunir la entrada de la cotización en el menú principal y reservar el panel derecho para sus resultados.

## What Changes

- Conservar las pestañas accesibles «Cotizar envío» y «Localizar paquete», inicialmente en cotización. Mantener campos locales al cambiar y cancelar consultas pendientes, dejando el contenido inactivo oculto y sin interacción.
- Situar un buscador Photon independiente por encima de las pestañas: buscar dirección/CP solo centra el mapa y no selecciona lockers ni completa CP de cotización.
- En cotización, seleccionar obligatoriamente un locker de recogida y otro de entrega mediante búsquedas locales por nombre, dirección o CP registrado. La selección se identifica por UUID; editar su texto la invalida. Mantener mapa completo, paquete y contadores, incluidos lockers coincidentes o sin coordenadas.
- Mantener retirados el mensaje repetido de éxito, «Ver lockers», «Actualizar», hora, «Ver España» y nota informativa; conservar estados necesarios solo cuando corresponda.
- Sustituir la apertura de «Enviar a este locker» por un popup de nombre/dirección con acciones «Seleccionar como locker de entrega» y «Seleccionar como locker de recogida». Abrirlo no selecciona ni cambia de pestaña; una acción explícita fija el rol, cierra el popup y activa cotización. El marcador exclusivo de seguimiento permanece informativo si no corresponde a un locker disponible.
- Usar el CP estructurado de cada locker o pedir un suplemento manual por rol cuando falte, sin inventar ni modificar datos. «Comparar envíos» permanece en el menú principal y se habilita solo con ambas selecciones, CP y medidas/peso válidos, y ninguna solicitud en curso.
- Mostrar a la derecha únicamente estados/resultados de cotización y sus controles de cierre/continuación. Invalidar resultados y trabajo pendiente al cambiar cualquier locker, CP o medida, incluso cuando los lockers compartan CP.
- Crear una cotización mediante `POST /quotations` y consultar su resultado mediante GET, con espera acotada, cancelación local y sin repetir escrituras automáticamente. Mostrar proveedor, servicio, precio EUR, plazo y fallos independientes; identificar claramente las tarifas de demostración de los proveedores simulados actuales.
- Localizar explícitamente un UUID de entrega/devolución con `GET /tracking/{id}`: estado y locker actual, último registrado o no asignado. Devolver solo la proyección necesaria, sin datos personales ni listados completos; representar seguimiento con un marcador independiente de la disponibilidad.
- Mantener disponibilidad como locker activo con alguna celda habilitada libre, coordenadas reales, atribución OSM y acceso a todos los territorios mediante navegación/selección. No inferir dirección, CP ni coordenadas.
- Conservar Astro completamente estático, llamadas directas del navegador y `PUBLIC_API_BASE_URL` al compilar. Ampliar CORS solo para POST JSON a `/quotations`, manteniendo GET, orígenes exactos y ausencia de credenciales.
- Conservar Nginx/Compose, preparación de Cloudflare Pages y generador manual de 250 lockers por defecto con cantidad configurable; esta ampliación no modifica esos flujos.

Esta ampliación sustituye los dos buscadores geográficos de recogida/entrega y el formulario lateral por selección de lockers, un buscador geográfico independiente y resultados laterales. Las retiradas anteriores de catálogo, actualización manual, «Ver España» y mensajes redundantes siguen vigentes. Siguen fuera reservas, contratación/pago, creación de envíos, comprobación de encaje en celdas, proveedores reales, geocodificación de lockers, administración, autenticación, seeds automáticos y publicación efectiva.

## Capabilities

### New Capabilities

- `locker-map`: Localización accesible de lockers y comparación pública entre lockers seleccionados de recogida y entrega, con búsqueda geográfica independiente, formulario, estados y resultados.
- `parcel-tracking`: Consulta pública mínima por UUID del estado de custodia y su relación con el locker, sin escrituras ni exposición de datos personales.

### Modified Capabilities

- `application-runtime`: Distribución estática, configuración pública, CORS acotado para las cotizaciones y herramienta manual de datos sintéticos.

Las capacidades existentes de entregas/devoluciones y `shipping-quotes`/`asynchronous-shipping-quotations` conservan estados, contratos y procesamiento. La nueva lectura de seguimiento usa sus repositorios actuales.

## Impact

- Frontend: componente, selectores locales, popup, controlador de mapa/cotización, estilos, acceso de teclado y pruebas; README explica búsqueda, selección por rol, CP suplementario y resultados simulados.
- Esta ampliación conserva backend, contrato de seguimiento, endpoints de cotización, dominio, worker, persistencia, migraciones y CORS; no añade dependencias ni cambia Compose. Los UUID de los lockers son contexto local: el POST existente sigue recibiendo CP, países y medidas/peso.
- El backend existente requiere API, PostgreSQL, RabbitMQ y worker. Cloudflare aloja solo los archivos estáticos; la API pública necesita HTTPS y origen autorizado, sin despliegue incluido.
- Pruebas deterministas con teselas y Photon controlados, CORS real entre orígenes y cotización completa en un entorno desechable. La conectividad real de OSM/Photon sigue sin comprobarse en esta red.
