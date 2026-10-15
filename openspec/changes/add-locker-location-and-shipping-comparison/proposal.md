# Proposal: tipado, ubicación de lockers y comparador de proveedores

## Why

Los lockers necesitan una dirección explícita y las funciones existentes necesitan anotaciones de tipos completas y coherentes. Una utilidad independiente permite comparar proveedores de transporte y demostrar extensibilidad hexagonal sin añadir todavía un flujo HTTP de cotización.

## What Changes

- Completar anotaciones estándar de Python y corregir incompatibilidades reales de tipos en funciones existentes afectadas y nuevas, sin añadir herramientas ni dependencias.
- Persistir Address/Coordinates opcionales en Locker, manteniendo clientes e históricos con location_id y admitiendo altas con dirección sin alias. Añadir migración geográfica segura y ampliar alta, lectura y PATCH.
- Incorporar QuoteShipping como utilidad interna asíncrona: recibe origen/destino, códigos postales, peso y Dimensions; consulta proveedores inyectados y devuelve sus ofertas normalizadas, falta de cobertura o error. Tres adaptadores simulados demuestran el contrato abierto a más proveedores y modalidades.

Se aplazan el dominio Parcel, mover Dimensions, integración locker→cotización, endpoints de cotización y búsqueda postal. También quedan fuera RabbitMQ, colas, persistencia de cotizaciones, clientes reales, reservas y contratación. El comparador se demuestra directamente con pruebas/ejemplo Python; no se conecta a FastAPI.

## Capabilities

### New Capabilities

- `shipping-quotes`: comparar ofertas de proveedores intercambiables a partir de datos de transporte, sin requerir locker, HTTP o persistencia.

### Modified Capabilities

- `locker-management`: dirección/coordenadas, alias nullable y administración compatible.
- `database-migrations`: revisión 0004 geográfica aditiva, con downgrade protegido.
- `test-execution`: revisión de contratos/anotaciones y comprobación del comparador sin servicios, conservando integración PostgreSQL.

## Impact

Cambian modelos/servicios/HTTP/persistencia de lockers, sus pruebas y migraciones; se añaden contratos puros de transporte, el comparador y tres adaptadores. Se actualiza README para los contratos/comandos, sin cambios de dependencias por tipado. Dimensions permanece en domain/lockers.py. No se añade wiring de proveedores en main, infraestructura, dependencia de transporte ni API de cotizaciones.

El 2026-10-15 el usuario ratificó este alcance, precisó que el tipado debía ser estándar de Python y solicitó un nombre acorde con el recorte: add-locker-location-and-shipping-comparison. Esta revisión documental no ha iniciado la implementación.
