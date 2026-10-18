# Proposal

## Why

La web ya permite seleccionar lockers, cotizar y localizar paquetes. El generador debe crear nuevos lockers de demostración con direcciones reales completas, y la selección debe evitar desplegar miles de opciones y mostrar el popup claramente por encima del icono.

## What Changes

- Conservar las pestañas accesibles «Cotizar envío» y «Localizar paquete», inicialmente en cotización. Mantener campos locales al cambiar y cancelar consultas pendientes, dejando el contenido inactivo oculto y sin interacción.
- Situar un buscador Photon independiente por encima de las pestañas: buscar dirección/CP solo centra el mapa y no selecciona lockers ni completa CP de cotización.
- En cotización, seleccionar obligatoriamente un locker de recogida y otro de entrega mediante búsquedas locales por nombre, dirección o CP registrado. Abrir candidatos solo con consulta no vacía y entre 1 y 20 coincidencias; pedir concretar si hay más, sin truncar. La selección se identifica por UUID; editar su texto la invalida, mientras abrir/cerrar o reseleccionar el mismo UUID conserva su CP manual.
- Mantener retirados el mensaje repetido de éxito, «Ver lockers», «Actualizar», hora, «Ver España» y nota informativa; conservar estados necesarios solo cuando corresponda.
- Mostrar el popup por encima del icono con separación visible, también tras zoom/desplazamiento y en móvil. Conservar nombre/dirección, añadir el texto común «Seleccionar como:» y botones «Locker de entrega»/«Locker de recogida». Abrirlo no selecciona ni cambia de pestaña; la acción explícita fija el rol, cierra y activa cotización. El marcador exclusivo de seguimiento sigue siendo informativo cuando no está disponible.
- Usar el CP estructurado de cada locker o pedir un suplemento manual por rol cuando falte, sin inventar ni modificar datos. «Comparar envíos» permanece en el menú principal y se habilita solo con ambas selecciones, CP y medidas/peso válidos, y ninguna solicitud en curso.
- Mostrar a la derecha únicamente estados/resultados de cotización y sus controles de cierre/continuación. Invalidar resultados y trabajo pendiente al cambiar cualquier locker, CP o medida, incluso cuando los lockers compartan CP.
- Crear una cotización mediante `POST /quotations` y consultar su resultado mediante GET, con espera acotada, cancelación local y sin repetir escrituras automáticamente. Mostrar proveedor, servicio, precio EUR, plazo y fallos independientes; identificar claramente las tarifas de demostración de los proveedores simulados actuales.
- Localizar explícitamente un UUID de entrega/devolución con `GET /tracking/{id}`: estado y locker actual, último registrado o no asignado. Devolver solo la proyección necesaria, sin datos personales ni listados completos; representar seguimiento con un marcador independiente de la disponibilidad.
- Mantener disponibilidad como locker activo con alguna celda habilitada libre, coordenadas reales, atribución OSM y acceso a todos los territorios mediante navegación/selección. No inferir dirección, CP ni coordenadas.
- Conservar Astro completamente estático, llamadas directas del navegador y `PUBLIC_API_BASE_URL` al compilar. Ampliar CORS solo para POST JSON a `/quotations`, manteniendo GET, orígenes exactos y ausencia de credenciales.
- Sustituir el muestreo aleatorio terrestre con dirección nula del generador por un catálogo local de direcciones/CP/coordenadas reales de estaciones de servicio, con procedencia MITECO verificada documentalmente. Elegir registros completos sin desplazar coordenadas ni inventar campos; los lockers siguen siendo DEMO y no representan instalaciones reales.
- Mantener 250 por defecto, `--count`, `--seed`, `--base-url`, `--dry-run` y ejecución sin consultas externas de direcciones. Documentar la versión del catálogo y posibles repeticiones si se supera su tamaño; no completar, borrar ni regenerar registros existentes. Nginx/Compose y preparación de Pages se conservan.

Esta ampliación sustituye la generación con dirección nula/puntos aleatorios y la apertura ilimitada de candidatos. Se mantienen búsqueda geográfica independiente, selección por rol y resultados laterales, junto con las retiradas anteriores de catálogo técnico y controles redundantes. Siguen fuera reservas, contratación/pago, envíos reales, comprobación de encaje, proveedores reales, geocodificación durante el seed, backfill de lockers existentes, administración, autenticación, seeds automáticos y publicación efectiva.

## Capabilities

### New Capabilities

- `locker-map`: Localización accesible de lockers y comparación pública entre lockers seleccionados de recogida y entrega, con búsqueda geográfica independiente, formulario, estados y resultados.
- `parcel-tracking`: Consulta pública mínima por UUID del estado de custodia y su relación con el locker, sin escrituras ni exposición de datos personales.

### Modified Capabilities

- `application-runtime`: Distribución estática, configuración pública, CORS acotado y generador manual de lockers sintéticos sobre direcciones reales de un catálogo local versionado.

Las capacidades existentes de entregas/devoluciones y `shipping-quotes`/`asynchronous-shipping-quotations` conservan estados, contratos y procesamiento. La nueva lectura de seguimiento usa sus repositorios actuales.

## Impact

- Frontend: selector local, estados/animación, anclaje/texto del popup y pruebas; generador Python, nuevo catálogo con procedencia, pruebas unitarias y README. Se conserva la selección por rol, CP suplementario y resultados simulados.
- Se conservan contratos HTTP, seguimiento, dominio, worker, persistencia, migraciones y CORS; no se añaden dependencias ni cambios Compose. El generador sigue usando POST /lockers manualmente; el POST de cotización sigue recibiendo únicamente CP, países y medidas/peso.
- El backend existente requiere API, PostgreSQL, RabbitMQ y worker. Cloudflare aloja solo los archivos estáticos; la API pública necesita HTTPS y origen autorizado, sin despliegue incluido.
- Pruebas deterministas con teselas y Photon controlados, CORS real entre orígenes y cotización completa en un entorno desechable. La conectividad real de OSM/Photon sigue sin comprobarse en esta red.
