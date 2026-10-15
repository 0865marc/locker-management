# Proposal: tipado, ubicación de lockers y comparador de proveedores

## Why

Los lockers necesitan una dirección explícita y las funciones existentes necesitan anotaciones de tipos completas y coherentes. Una utilidad independiente permite comparar proveedores de transporte y demostrar extensibilidad hexagonal sin añadir todavía un flujo HTTP de cotización.

## What Changes

- Completar anotaciones estándar y corregir incompatibilidades en todo el backend analizado. Añadir Pyright como dependencia de desarrollo, configuración compartida con Pylance y obligación de ejecutar el chequeo al terminar cada spec, con cero errores y advertencias.
- Persistir Address/Coordinates opcionales en Locker, manteniendo clientes e históricos con location_id y admitiendo altas con dirección sin alias. Añadir migración geográfica segura y ampliar alta, lectura y PATCH.
- Incorporar QuoteShipping como utilidad interna asíncrona: recibe origen/destino, códigos postales, peso y Dimensions; consulta proveedores inyectados y devuelve sus ofertas normalizadas, falta de cobertura o error. Tres adaptadores simulados demuestran el contrato abierto a más proveedores y modalidades.

Se aplazan el dominio Parcel, mover Dimensions, integración locker→cotización, endpoints de cotización y búsqueda postal. También quedan fuera RabbitMQ, colas, persistencia de cotizaciones, clientes reales, reservas y contratación. El comparador se demuestra directamente con pruebas/ejemplo Python; no se conecta a FastAPI.

## Capabilities

### New Capabilities

- `shipping-quotes`: comparar ofertas de proveedores intercambiables a partir de datos de transporte, sin requerir locker, HTTP o persistencia.

### Modified Capabilities

- `locker-management`: dirección/coordenadas, alias nullable y administración compatible.
- `database-migrations`: revisión 0004 geográfica aditiva, con downgrade protegido.
- `test-execution`: verificación reproducible de tipos obligatoria al completar cada spec, junto con unitarias sin servicios e integración PostgreSQL.

## Impact

Cambian modelos/servicios/HTTP/persistencia de lockers, sus pruebas y migraciones; se añaden contratos puros de transporte, el comparador y tres adaptadores. Se actualizan backend/pyproject.toml y uv.lock, pyrightconfig.json en raíz, README, AGENTS.md y las instrucciones de builder/reviewer para exigir evidencia del chequeo; no cambian modelos ni ajustes de esos agentes. Dimensions permanece en domain/lockers.py. No se añade wiring de proveedores en main, infraestructura, dependencia de transporte ni API de cotizaciones.

La funcionalidad y las correcciones anteriores tienen evidencia histórica en tasks.md. La nueva petición explícita del usuario autoriza Pyright, la regla final y corregir todos sus diagnósticos, sustituyendo la restricción anterior de no añadir checker. Este ajuste no cambia el alcance funcional ni introduce CI externa.
