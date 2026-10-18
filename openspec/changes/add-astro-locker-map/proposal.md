# Proposal

## Why

Las selecciones de origen y destino ya identifican lockers concretos. El mapa debe mostrar su relación mediante una línea directa orientativa y encuadrar ambos extremos, sin calcular una ruta de transporte ni crear un envío.

## What Changes

- Conservar las pestañas accesibles «Cotizar envío» y «Localizar paquete», inicialmente en cotización. Mantener campos locales al cambiar y cancelar consultas pendientes, dejando el contenido inactivo oculto y sin interacción.
- Situar un buscador Photon independiente por encima de las pestañas: buscar dirección/CP solo centra el mapa y no selecciona lockers ni completa CP de cotización.
- En cotización, seleccionar obligatoriamente un locker de origen y otro de destino mediante búsquedas locales por nombre, dirección o CP registrado. Abrir candidatos solo con consulta no vacía y entre 1 y 20 coincidencias; pedir concretar si hay más, sin truncar. La selección se identifica por UUID; editar su texto la invalida, mientras abrir/cerrar o reseleccionar el mismo UUID conserva su selección.
- Dibujar localmente una línea orientativa entre las coordenadas registradas de ambos lockers, identificar origen/destino y encuadrarlos en el área visible al completar o cambiar el par. Retirarla al invalidar un rol, informar si falta una posición y tratar puntos coincidentes sin desplazar datos ni aplicar zoom excesivo. Ocultarla en seguimiento y restaurarla al volver; la geobúsqueda conserva su navegación independiente.
- Mantener retirados el mensaje repetido de éxito, «Ver lockers», «Actualizar», hora, «Ver España» y nota informativa; conservar estados necesarios solo cuando corresponda.
- Mostrar el popup por encima del icono con separación visible, también tras zoom/desplazamiento y en móvil. Conservar nombre/dirección, añadir el texto común «Seleccionar como:» y botones «Locker de destino»/«Locker de origen». Abrirlo no selecciona ni cambia de pestaña; la acción explícita fija el rol, cierra y activa cotización. El marcador exclusivo de seguimiento sigue siendo informativo cuando no está disponible.
- Eliminar los campos CP de origen/destino y su suplemento manual, sin sustituirlos por inputs ocultos. Derivar cada CP exclusivamente del locker seleccionado; si falta o es inválido, mostrar un aviso junto al rol y bloquear la comparación hasta elegir otro locker, sin inferir ni modificar datos. «Comparar envíos» permanece en el menú principal y se habilita solo con ambas selecciones, CP y medidas/peso válidos, y ninguna solicitud en curso.
- Mostrar a la derecha únicamente estados/resultados de cotización y sus controles de cierre/continuación. Invalidar resultados y trabajo pendiente al cambiar cualquier locker, sus datos postales o las medidas, incluso cuando los lockers compartan CP.
- Crear una cotización mediante `POST /quotations` y consultar su resultado mediante GET, con espera acotada, cancelación local y sin repetir escrituras automáticamente. Mostrar proveedor, servicio, precio EUR, plazo y fallos independientes; identificar claramente las tarifas de demostración de los proveedores simulados actuales.
- Localizar explícitamente un UUID de entrega/devolución con `GET /tracking/{id}`: estado y locker actual, último registrado o no asignado. Devolver solo la proyección necesaria, sin datos personales ni listados completos; representar seguimiento con un marcador independiente de la disponibilidad.
- Mantener disponibilidad como locker activo con alguna celda habilitada libre, coordenadas reales, atribución OSM y acceso a todos los territorios mediante navegación/selección. No inferir dirección, CP ni coordenadas.
- Conservar Astro completamente estático, llamadas directas del navegador y `PUBLIC_API_BASE_URL` al compilar. Ampliar CORS solo para POST JSON a `/quotations`, manteniendo GET, orígenes exactos y ausencia de credenciales.
- Sustituir el muestreo aleatorio terrestre con dirección nula del generador por un catálogo local de direcciones/CP/coordenadas reales de estaciones de servicio, con procedencia MITECO verificada documentalmente. Elegir registros completos sin desplazar coordenadas ni inventar campos; los lockers siguen siendo DEMO y no representan instalaciones reales.
- Mantener 250 por defecto, `--count`, `--seed`, `--base-url`, `--dry-run` y ejecución sin consultas externas de direcciones. Documentar la versión del catálogo y posibles repeticiones si se supera su tamaño; no completar, borrar ni regenerar registros existentes. Nginx/Compose y preparación de Pages se conservan.

Esta ampliación se limita al trayecto visual local. Se conservan «Ver comparación existente», «Localizar paquete» y el POST nuevo de cada comparación explícita habilitada. No incluye Shipment, idempotencia, ruta por carretera, distancia/ETA ni cambios de contratos o datos. Siguen fuera reservas, contratación/pago, envíos reales, comprobación de encaje, proveedores reales, geocodificación durante el seed, backfill de lockers existentes, administración, autenticación, seeds automáticos y publicación efectiva.

## Capabilities

### New Capabilities

- `locker-map`: Localización accesible de lockers, trayecto visual orientativo y comparación pública entre lockers seleccionados de origen y destino, con búsqueda geográfica independiente, formulario, estados y resultados.
- `parcel-tracking`: Consulta pública mínima por UUID del estado de custodia y su relación con el locker, sin escrituras ni exposición de datos personales.

### Modified Capabilities

- `application-runtime`: Distribución estática, configuración pública, CORS acotado y generador manual de lockers sintéticos sobre direcciones reales de un catálogo local versionado.

Las capacidades existentes de entregas/devoluciones y `shipping-quotes`/`asynchronous-shipping-quotations` conservan estados, contratos y procesamiento. La nueva lectura de seguimiento usa sus repositorios actuales.

## Impact

- Frontend: `frontend/src/scripts/locker-map.ts`, componente/estilos solo para identificación y aviso, E2E afectados y una nota en README. Extraer un helper pequeño únicamente si simplifica el encuadre o sus pruebas. El generador, catálogo y resultados simulados se conservan.
- Se conservan contratos HTTP, seguimiento, dominio, worker, persistencia, migraciones y CORS; no se añaden dependencias ni cambios Compose. El generador sigue usando POST /lockers manualmente; el POST de cotización sigue recibiendo únicamente CP, países y medidas/peso.
- El backend existente requiere API, PostgreSQL, RabbitMQ y worker. Cloudflare aloja solo los archivos estáticos; la API pública necesita HTTPS y origen autorizado, sin despliegue incluido.
- Verificación frontend proporcional con teselas/Photon controlados y el fixture CORS real existente, sin stack Docker adicional para este ajuste. La conectividad real de OSM/Photon sigue sin comprobarse en esta red.
