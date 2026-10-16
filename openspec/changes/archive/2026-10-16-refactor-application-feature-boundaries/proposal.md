# Proposal

## Why

La comparación y el proceso asíncrono de cotización están repartidos entre cuatro módulos de aplicación, y sus modelos importan resultados desde el módulo que también ejecuta la comparación. Agrupar la aplicación por área y situar los puertos junto a los casos de uso que los consumen aclara responsabilidades y dependencias sin cambiar el comportamiento.

## What Changes

- Organizar cotizaciones en `application/quotations/`, separando modelos, puertos, comparación, casos de uso y errores.
- Mover `ProviderResult` y sus enums a modelos de aplicación; renombrar `ShippingQuoteService` a `ShippingQuoteComparator`, conservando `QuotationService` y `QuotationProcessor`.
- Situar todos los puertos de salida en su área de aplicación: cotizaciones, entregas, devoluciones y lockers. El dominio conserva sus datos, entidades y reglas, sin depender de aplicación.
- Organizar las otras tres áreas en paquetes con `ports.py` y `use_cases.py`, manteniendo sus servicios actuales y su lógica.
- **BREAKING** para consumidores Python: sustituir las rutas de importación anteriores y el nombre del comparador, sin wrappers de compatibilidad ni reexports. Actualizar todos los consumidores del repositorio y los ejemplos del README.
- Preservar contratos HTTP/OpenAPI, resultados y errores, colas, persistencia, migraciones y perfiles de los proveedores.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

Ninguna. Se declara `skip_specs: true` porque solo cambian organización y nombres internos. El contrato vigente incluye las especificaciones y los deltas implementados de `add-asynchronous-shipping-quotations`, todavía sin sincronizar.

## Impact

Afecta a `backend/application/`, `backend/domain/ports.py`, imports en adaptadores, `main.py`, `worker.py`, pruebas y README. No añade dependencias, tablas, migraciones, operaciones ni reglas; conserva `0001`–`0005` y el cambio asíncrono anterior intactos.

Este documento registra la estructura y la propiedad de los puertos revisadas con el usuario, cuya instrucción posterior «adelante, implementa» autoriza este alcance. La verificación comparará OpenAPI y metadatos SQL con la base `10ee425`, ejecutará las suites existentes y exigirá Pyright sin errores ni advertencias y revisión independiente.
