# Proposal

## Why

El mapa crea un marcador y un popup por locker y recorre toda la colección al inspeccionar uno, degradando la interacción con miles de registros. Debe representar esa colección mediante agrupación y renderizado de la vista, con pines centrados y origen/destino destacados cuando se muestra el trayecto.

## What Changes

- Conservar las pestañas accesibles «Cotizar envío» y «Localizar paquete», inicialmente en cotización. Mantener campos locales al cambiar y cancelar consultas pendientes, dejando el contenido inactivo oculto y sin interacción.
- Situar un buscador Photon independiente por encima de las pestañas: buscar dirección/CP solo centra el mapa y no selecciona lockers ni completa CP de cotización.
- En cotización, seleccionar obligatoriamente un locker de origen y otro de destino mediante búsquedas locales por nombre, dirección o CP registrado. Sin selección, abrir candidatos solo con consulta no vacía y entre 1 y 20 coincidencias; pedir concretar si hay más, sin truncar. El UUID seleccionado bloquea el campo, que sigue enfocable sin abrir sugerencias. Su X vacía el rol y devuelve foco al buscador; otra acción explícita de popup puede sustituirlo.
- Dibujar localmente una línea orientativa entre las coordenadas registradas de ambos lockers, identificar origen/destino y encuadrarlos en el área visible al completar o cambiar el par. Retirarla al invalidar un rol, informar si falta una posición y tratar puntos coincidentes sin desplazar datos ni aplicar zoom excesivo. Ocultarla en seguimiento y restaurarla al volver; la geobúsqueda conserva su navegación independiente.
- Usar pines SVG locales simétricos con pictograma de locker centrado, borde blanco y sombra ligera. Con ruta visible, atenuar los demás pines/grupos aproximadamente al 30%, manteniendo origen/destino y foco/inspección legibles; restaurar opacidad al quitar la ruta o entrar en seguimiento.
- Agrupar puntos cercanos con Supercluster empaquetado localmente y materializar solo grupos/puntos de la vista con margen. Las burbujas muestran cantidad y permiten acercar con clic/teclado; las coincidencias irreductibles ofrecen miembros paginados, sin desplazar coordenadas. Mantener roles, inspección y seguimiento fuera de grupos, todos los UUID accesibles y contadores/selectores basados en la colección completa.
- Crear popup/contenido bajo demanda y actualizar solo estados visuales afectados. Evitar recorridos DOM globales por clic, trabajo de agrupación por frame y normalización repetida de todas las direcciones al buscar. Medir carga, nodos, clic y animación con 250/1.000/5.000 registros frente al baseline controlado, sin prometer FPS universales.
- Mantener retirados el mensaje repetido de éxito, «Ver lockers», «Actualizar», hora, «Ver España» y nota informativa; conservar estados necesarios solo cuando corresponda.
- Mostrar el popup por encima del icono con separación visible y encuadre suave, respetando movimiento reducido y cancelando animaciones obsoletas. Conservar nombre/dirección y «Seleccionar como:», con «Locker de origen» primero y «Locker de destino» después. Abrirlo no selecciona ni cambia de pestaña; la acción fija el rol, cierra, activa cotización y enfoca su X. Asignar/quitar un rol no mueve el mapa salvo el encuadre del par posicionable al completar/cambiar el trayecto. El marcador exclusivo de seguimiento sigue siendo informativo cuando no está disponible.
- Eliminar los campos CP de origen/destino y su suplemento manual, sin sustituirlos por inputs ocultos. Derivar cada CP exclusivamente del locker seleccionado; si falta o es inválido, mostrar un aviso junto al rol y bloquear la comparación hasta elegir otro locker, sin inferir ni modificar datos. «Comparar envíos» permanece en el menú principal y se habilita solo con ambas selecciones, CP y medidas/peso válidos, y ninguna solicitud en curso.
- Mostrar a la derecha únicamente estados/resultados de cotización y sus controles de cierre/continuación. Invalidar resultados y trabajo pendiente al cambiar cualquier locker, sus datos postales o las medidas, incluso cuando los lockers compartan CP.
- Crear una cotización mediante `POST /quotations` y consultar su resultado mediante GET, con espera acotada, cancelación local y sin repetir escrituras automáticamente. Mostrar proveedor, servicio, precio EUR, plazo y fallos independientes; identificar claramente las tarifas de demostración de los proveedores simulados actuales.
- Localizar explícitamente un UUID de entrega/devolución con `GET /tracking/{id}`: estado y locker actual, último registrado o no asignado. Devolver solo la proyección necesaria, sin datos personales ni listados completos; representar seguimiento con un marcador independiente de la disponibilidad.
- Mantener disponibilidad como locker activo con alguna celda habilitada libre, coordenadas reales, atribución OSM y acceso a todos los territorios mediante navegación/selección. No inferir dirección, CP ni coordenadas.
- Conservar Astro completamente estático, llamadas directas del navegador y `PUBLIC_API_BASE_URL` al compilar. Ampliar CORS solo para POST JSON a `/quotations`, manteniendo GET, orígenes exactos y ausencia de credenciales.
- Sustituir el muestreo aleatorio terrestre con dirección nula del generador por un catálogo local de direcciones/CP/coordenadas reales de estaciones de servicio, con procedencia MITECO verificada documentalmente. Elegir registros completos sin desplazar coordenadas ni inventar campos; los lockers siguen siendo DEMO y no representan instalaciones reales.
- Mantener 250 por defecto, `--count`, `--seed`, `--base-url`, `--dry-run` y ejecución sin consultas externas de direcciones. Documentar la versión del catálogo y posibles repeticiones si se supera su tamaño; no completar, borrar ni regenerar registros existentes. Nginx/Compose y preparación de Pages se conservan.

Esta ampliación incorpora agrupación visible, diseño de pines y rendimiento en navegador. Se conservan cámara suave, origen primero, readonly/X, trayecto orientativo, «Ver comparación existente», «Localizar paquete» y POST nuevo de cada comparación explícita habilitada. No incluye Shipment, idempotencia, ruta por carretera, distancia/ETA ni cambios de contratos o datos. Siguen fuera reservas, contratación/pago, envíos reales, comprobación de encaje, proveedores reales, geocodificación durante el seed, backfill, administración, autenticación, seeds automáticos y publicación efectiva.

## Capabilities

### New Capabilities

- `locker-map`: Localización accesible de lockers, trayecto visual orientativo y comparación pública entre lockers seleccionados de origen y destino, con búsqueda geográfica independiente, formulario, estados y resultados.
- `parcel-tracking`: Consulta pública mínima por UUID del estado de custodia y su relación con el locker, sin escrituras ni exposición de datos personales.

### Modified Capabilities

- `application-runtime`: Distribución estática, configuración pública, CORS acotado y generador manual de lockers sintéticos sobre direcciones reales de un catálogo local versionado.

Las capacidades existentes de entregas/devoluciones y `shipping-quotes`/`asynchronous-shipping-quotations` conservan estados, contratos y procesamiento. La nueva lectura de seguimiento usa sus repositorios actuales.

## Impact

- Frontend: `frontend/src/scripts/locker-map.ts`, `locker-route.ts`, nuevo módulo de marcadores/índice, `locker-selector.ts`/`lib/locker-selection.ts`, estilos, pruebas funcionales y de rendimiento, README. Añadir Supercluster y tipos necesarios en package/lockfile; mantener componentes/cámara salvo integración imprescindible. El generador y resultados simulados se conservan.
- Se conservan contratos HTTP, seguimiento, dominio, worker, persistencia, migraciones, CORS y Compose. La nueva dependencia se empaqueta en el build estático, sin servicio externo ni backend nuevo. El POST de cotización sigue recibiendo únicamente CP, países y medidas/peso.
- El backend existente requiere API, PostgreSQL, RabbitMQ y worker. Cloudflare aloja solo los archivos estáticos; la API pública necesita HTTPS y origen autorizado, sin despliegue incluido.
- Verificación frontend proporcional con teselas/Photon controlados y el fixture CORS real existente, sin stack Docker adicional para este ajuste. La conectividad real de OSM/Photon sigue sin comprobarse en esta red.
