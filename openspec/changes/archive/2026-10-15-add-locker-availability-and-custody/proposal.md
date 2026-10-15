# Proposal

## Why

El proyecto registra custodia de paquetes, pero no conoce dónde se guardan ni si existe espacio físico. Añadir lockers con celdas configurables permite consultar disponibilidad real y demostrar que una entrega y una devolución no pueden ocupar simultáneamente la última celda.

## What Changes

- Crear lockers por ubicación estable y celdas individuales con dimensiones útiles, cantidades configurables y habilitación; conservar la identidad de las celdas ocupadas.
- Consultar disponibilidad por ubicación y dimensiones como fotografía del momento, sin reservas ni promesas de disponibilidad futura.
- Admitir opcionalmente `locker_id` y `parcel_dimensions` juntos en las recepciones existentes; asignar la celda libre compatible de menor volumen y devolver su identificador.
- Compartir capacidad entre Delivery y Return; confirmar recepción y ocupación en una transacción, y confirmar salida y liberación en otra transacción indivisible.
- Conservar recepciones sin locker y filas históricas sin inventar asignaciones. Añadir campos nullable a sus respuestas existentes.
- Añadir revisión Alembic `0003` sobre `0002`, compatible con paquetes existentes, y pruebas PostgreSQL de concurrencia, rollback y reocupación.
- Excluir reservas, TTL, geodistancia, RabbitMQ, outbox, cotizaciones, contratación de envíos y autenticación. Las cotizaciones serán una fase independiente posterior.

## Capabilities

### New Capabilities

- `locker-management`: configuración de lockers/celdas y consulta de capacidad física por ubicación y dimensiones.

### Modified Capabilities

- `delivery-management`: recepción opcional en locker, representación de asignación y liberación durante las dos salidas existentes.
- `return-management`: recepción opcional en locker y liberación al entregar al transportista.
- `record-persistence`: atomicidad de paquete/ocupación y capacidad compartida bajo concurrencia.
- `database-migrations`: evolución aditiva a lockers desde `0002` poblado y downgrade que conserva datos.

## Impact

Cambios en dominio/puertos, casos de uso, adaptadores HTTP/SQLModel, composición, Alembic, pruebas y README. Se añaden endpoints de lockers y campos opcionales a los siete endpoints actuales; los clientes con validación estricta de respuestas deben admitir los nuevos campos nullable. No se requieren dependencias ni servicios nuevos. PostgreSQL es la referencia de concurrencia; SQLite verifica contratos y persistencia secuencial.
