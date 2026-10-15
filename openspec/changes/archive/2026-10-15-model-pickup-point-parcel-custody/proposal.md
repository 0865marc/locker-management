# Proposal

## Why

La PoC registra una dirección por entrega y un motivo comercial por devolución, pero el negocio real es la custodia de paquetes en un único punto de recogida. Necesitamos identificar cada paquete y registrar su entrada y salida sin introducir pedidos, productos ni integraciones externas.

## What Changes

- **BREAKING**: reemplazar `Delivery.address` y `Return.reason` por datos de paquetería; los payloads antiguos dejan de ser válidos.
- Registrar una entidad por paquete con UUID, seguimiento de una etiqueta existente, transportista y fecha de recepción UTC asignada por el sistema. Delivery y Return continúan siendo independientes.
- Delivery incorpora destinatario, teléfono opcional, plazo informativo opcional y estados de espera, recogida o devolución al transportista, con fechas de salida.
- Return incorpora remitente opcional y estados de espera o entrega al transportista, con fecha de salida.
- Mantener creación/listado e introducir tres operaciones explícitas de salida, con exclusión de salidas repetidas o incompatibles incluso ante concurrencia.
- Evolucionar la base de datos mediante una migración que rechaza de forma accionable registros legacy sin información necesaria, conservando los datos y el esquema previos; no inventa información ni borra registros.
- Quedan fuera ubicación de almacenamiento, direcciones, instrucciones de entrega, pedidos, productos, cantidades, resolución comercial, relación entre entidades, múltiples puntos, autenticación, notificaciones e integración con transportistas.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `delivery-management`: datos de recepción de paquetes y salidas exclusivas por recogida o devolución al transportista.
- `return-management`: recepción independiente de paquetes de devolución y entrega única al transportista.
- `record-persistence`: conservación de todos los campos y transiciones atómicas frente a concurrencia.
- `database-migrations`: evolución segura desde `0001`, diferenciando revisión inicial y esquema actual.

## Impact

Afecta a `backend/domain/models.py`, `backend/domain/ports.py`, `backend/application/use_cases.py`, los adaptadores HTTP y SQLModel, una nueva revisión Alembic, pruebas relevantes y ejemplos de `README.md`. `backend/main.py` solo necesitará cambios si los nuevos puertos requieren composición adicional. No se prevén nuevas dependencias. Esta propuesta no implementa, sincroniza ni archiva el cambio; requiere revisión del plan antes de ejecutar tareas.
