# Proposal

## Why

La web ya permite comparar envíos hacia un locker. Debe separar ese recorrido de la localización de un paquete existente y distinguir dirección de recogida y zona de entrega, reutilizando los estados de custodia y cotizaciones actuales.

## What Changes

- Sustituir la cabecera del menú por las pestañas accesibles «Cotizar envío» y «Localizar paquete», inicialmente en cotización. Conservar campos locales al cambiar y cancelar consultas pendientes, dejando el contenido inactivo oculto y sin interacción.
- En cotización, mantener mapa a pantalla completa, rueda, paquete y contadores; ofrecer «Dirección de recogida» y «Dirección de entrega» con sugerencias independientes. Recogida completa el CP de origen desde datos estructurados de Photon o permite entrada manual; entrega solo centra una zona para elegir un locker, sin seleccionar ni cambiar CP de destino automáticamente.
- Mantener retirados el mensaje repetido de éxito, «Ver lockers», «Actualizar», hora, «Ver España» y nota informativa; conservar estados necesarios solo cuando corresponda.
- Sustituir el catálogo/detalle técnico por «Enviar a este locker», abierto al seleccionar un marcador o mediante un acceso de teclado. Un selector compacto permite elegir también lockers coincidentes o sin coordenadas.
- Usar el locker como destino: CP de origen obligatorio, obtenido de la recogida seleccionada o introducido manualmente, y CP de destino desde el locker o solicitado cuando falte. Editar la recogida invalida su CP derivado anterior. Reutilizar dimensiones y peso, validándolos al pulsar «Comparar envíos».
- Crear una cotización mediante `POST /quotations` y consultar su resultado mediante GET, con espera acotada, cancelación local y sin repetir escrituras automáticamente. Mostrar proveedor, servicio, precio EUR, plazo y fallos independientes; identificar claramente las tarifas de demostración de los proveedores simulados actuales.
- Localizar explícitamente un UUID de entrega/devolución con `GET /tracking/{id}`: estado y locker actual, último registrado o no asignado. Devolver solo la proyección necesaria, sin datos personales ni listados completos; representar seguimiento con un marcador independiente de la disponibilidad.
- Mantener disponibilidad como locker activo con alguna celda habilitada libre, coordenadas reales, atribución OSM y acceso a todos los territorios mediante navegación/selección. No inferir dirección, CP ni coordenadas.
- Conservar Astro completamente estático, llamadas directas del navegador y `PUBLIC_API_BASE_URL` al compilar. Ampliar CORS solo para POST JSON a `/quotations`, manteniendo GET, orígenes exactos y ausencia de credenciales.
- Conservar Nginx/Compose, preparación de Cloudflare Pages y generador manual de 250 lockers por defecto con cantidad configurable; esta ampliación no modifica esos flujos.

Esta ampliación sustituye las exclusiones anteriores de cotización desde la web y los requisitos de catálogo, actualización manual, «Ver España» y mensajes retirados. Siguen fuera reservas, contratación/pago, creación de envíos, comprobación de encaje en celdas, proveedores reales, geocodificación de lockers, administración, autenticación, seeds automáticos y publicación efectiva.

## Capabilities

### New Capabilities

- `locker-map`: Localización accesible de lockers y comparación pública de envíos hacia el destino seleccionado, con búsqueda, formulario, estados y resultados.
- `parcel-tracking`: Consulta pública mínima por UUID del estado de custodia y su relación con el locker, sin escrituras ni exposición de datos personales.

### Modified Capabilities

- `application-runtime`: Distribución estática, configuración pública, CORS acotado para las cotizaciones y herramienta manual de datos sintéticos.

Las capacidades existentes de entregas/devoluciones y `shipping-quotes`/`asynchronous-shipping-quotations` conservan estados, contratos y procesamiento. La nueva lectura de seguimiento usa sus repositorios actuales.

## Impact

- Frontend: pestañas, componente, estilos, geocodificador con CP estructurado, integración de recogida y cliente/panel de seguimiento con pruebas; README explica ambos recorridos y los simuladores.
- Backend: nuevo caso de lectura y adaptador HTTP de seguimiento, composición y pruebas, reutilizando `get_by_id` de entregas, devoluciones y lockers. Se conservan endpoints existentes, dominio, worker, persistencia, migraciones y CORS; no se añaden dependencias ni cambios Compose.
- El backend existente requiere API, PostgreSQL, RabbitMQ y worker. Cloudflare aloja solo los archivos estáticos; la API pública necesita HTTPS y origen autorizado, sin despliegue incluido.
- Pruebas deterministas con teselas y Photon controlados, CORS real entre orígenes y cotización completa en un entorno desechable. La conectividad real de OSM/Photon sigue sin comprobarse en esta red.
