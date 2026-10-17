# Proposal

## Why

La comparación entre proveedores debe ejecutarse fuera de la petición HTTP y conservar su solicitud y resultados en PostgreSQL. Esta primera fase añade una cola sencilla y fallos simulados observables, sin mecanismos de reintento o recuperación de trabajos.

## What Changes

- Crear y consultar cotizaciones con POST/GET `/quotations`: guardar la solicitud, publicar una vez en RabbitMQ y responder `202` solo tras confirmación de publicación.
- Ejecutar un único worker secuencial que confirme el consumo antes de llamar una vez a `ShippingQuoteService.compare` y guarde el lote final.
- Conservar ofertas y resultados `QUOTED`, `NOT_COVERED` y `FAILED`, incluidos `PROVIDER_ERROR` y `PROVIDER_TIMEOUT`; los fallos de un proveedor no eliminan los demás resultados.
- Dar a cada simulador un perfil propio, privado e inmutable de demora aleatoria, error y no respuesta; sus constructores no aceptan argumentos. Las tarifas, servicios y timeout se conservan; la ejecución directa también es estocástica.
- Persistir únicamente solicitudes, resultados y ofertas, con estado de proceso `PENDING`, `PROCESSING`, `COMPLETED` o `FAILED` y un error de proceso cuando corresponda.
- Añadir migración `0005`, configuración de API/broker/worker y verificación proporcional.

No se incluyen reintentos, republicación, recuperación automática, snapshots de configuración, resultados parciales, reservas, contratación, proveedores reales ni selección de una oferta ganadora. Si el worker muere o no puede escribir, una solicitud puede quedar pendiente sin reparación automática.

## Capabilities

### New Capabilities

- `asynchronous-shipping-quotations`: encolado, ejecución única y consulta persistente de solicitudes y resultados.

### Modified Capabilities

- `shipping-quotes`: simuladores autónomos con perfiles fijos diferenciados y tarifas deterministas.
- `application-runtime`: conexiones RabbitMQ y un worker separado que instancia los simuladores sin configurarlos.
- `database-migrations`: almacenamiento de cotizaciones y downgrade protegido en `0005`.
- `test-execution`: unidades deterministas, persistencia PostgreSQL y smoke de cola, conservando Pyright obligatorio.

## Impact

El cambio original añade modelos/puertos y casos de uso en aplicación, adaptadores HTTP por área, SQLModel y RabbitMQ, y `worker.py`, con los ajustes de composición, migración `0005`, dependencias, Docker/Compose y pruebas correspondientes.

La revisión aprobada de proveedores afecta solo a `adapters/providers/simulated_shipping.py`, `worker.py`, Compose, README y pruebas de simulación/comparación/quotations/mensajería. **BREAKING:** se elimina la configuración pública de perfil/RNG/espera, incluidos `SimulationProfile` y `SimulationRandom`, y las cuatro variables `SHIPPING_*` de simulación; construir sin argumentos deja de garantizar ejecución inmediata y determinista. No cambia colas, API, persistencia, tarifas ni reintentos y no requiere migración adicional.
