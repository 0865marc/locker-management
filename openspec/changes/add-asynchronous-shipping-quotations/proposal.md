# Proposal

## Why

La comparación entre proveedores debe ejecutarse fuera de la petición HTTP y conservar su solicitud y resultados en PostgreSQL. Esta primera fase añade una cola sencilla y fallos simulados observables, sin mecanismos de reintento o recuperación de trabajos.

## What Changes

- Crear y consultar cotizaciones con POST/GET `/quotations`: guardar la solicitud, publicar una vez en RabbitMQ y responder `202` solo tras confirmación de publicación.
- Ejecutar un único worker secuencial que confirme el consumo antes de llamar una vez a `ShippingQuoteService.compare` y guarde el lote final.
- Conservar ofertas y resultados `QUOTED`, `NOT_COVERED` y `FAILED`, incluidos `PROVIDER_ERROR` y `PROVIDER_TIMEOUT`; los fallos de un proveedor no eliminan los demás resultados.
- Añadir demora aleatoria, probabilidad de error y de no respuesta configurables, preservando precios, servicios, timeout y uso directo determinista.
- Persistir únicamente solicitudes, resultados y ofertas, con estado de proceso `PENDING`, `PROCESSING`, `COMPLETED` o `FAILED` y un error de proceso cuando corresponda.
- Añadir migración `0005`, configuración de API/broker/worker y verificación proporcional.

No se incluyen reintentos, republicación, recuperación automática, snapshots de configuración, resultados parciales, reservas, contratación, proveedores reales ni selección de una oferta ganadora. Si el worker muere o no puede escribir, una solicitud puede quedar pendiente sin reparación automática.

## Capabilities

### New Capabilities

- `asynchronous-shipping-quotations`: encolado, ejecución única y consulta persistente de solicitudes y resultados.

### Modified Capabilities

- `shipping-quotes`: simulación configurable manteniendo el contrato del comparador.
- `application-runtime`: conexiones RabbitMQ y un worker separado.
- `database-migrations`: almacenamiento de cotizaciones y downgrade protegido en `0005`.
- `test-execution`: unidades deterministas, persistencia PostgreSQL y smoke de cola, conservando Pyright obligatorio.

## Impact

Se añaden modelos/puertos y casos de uso en aplicación, adaptadores HTTP por área, SQLModel y RabbitMQ, y `worker.py`. Se ajustan `main.py`, el router agregado, simuladores, metadatos Alembic, dependencias bloqueadas (`aio-pika`), Docker/Compose, README, pruebas y alcance estricto del worker en Pyright. Se mantienen los tipos de resultado en aplicación y las revisiones `0001`–`0004` sin cambios. No se implementa código en esta revisión del plan.
