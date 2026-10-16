# Proposal: organizar módulos y responsabilidades hexagonales

## Why

La separación por área ya existe, pero HTTP conserva nombres planos repetitivos, la aplicación mezcla nombres de casos de uso y servicios, y algunos resultados técnicos están en dominio. Se propone una organización uniforme que haga visibles las responsabilidades sin añadir dominios ni capas.

## What Changes

- Agrupar HTTP en deliveries, returns y lockers, cada uno con routes.py y schemas.py; agregar sus routers desde http/routes.py y conservar recursos/composición en main.py.
- Usar módulos de aplicación deliveries.py, returns.py, lockers.py y shipping_quotes.py con servicios por área; QuoteShipping pasa a ShippingQuoteService.
- Eliminar application/clock.py y errors.py: reloj obligatorio inyectado desde main y errores específicos junto a cada servicio.
- Eliminar domain/validation.py: validadores privados locales y errores de transición propios de Delivery/Return, conservando reglas y mensajes.
- Situar ProviderResult/ProviderStatus/ProviderErrorCode en aplicación; mantener solicitud/ofertas/cobertura y puerto del proveedor en dominio.
- **BREAKING interno:** cambian imports, nombre del comparador, clases de excepciones y construcción Python de servicios con reloj. Se actualizan todos los consumidores del repositorio sin alias de compatibilidad. HTTP, OpenAPI y persistencia conservan sus contratos.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

Ninguna. Se declara skip_specs: true: los requisitos funcionales existentes, incluidos los del cambio anterior pendiente de sincronización, siguen vigentes. Los cambios de contrato Python interno se detallan en el diseño.

## Impact

Módulos HTTP, aplicación, domain/deliveries.py, returns.py y shipping_quotes.py; main.py, imports afectados, pruebas y README. Sin dependencias, endpoints, wiring de proveedores, cambios de esquema ni migraciones. Dimensions, puertos y organización de repositorios permanecen.

El usuario aprobó este plan para implementación el 2026-10-15 con «adelante, sí». Los dos cambios anteriores no se modifican, sincronizan ni archivan.
