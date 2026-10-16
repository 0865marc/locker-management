# Design

## Context

Base inspeccionada: 02b932c. Ver proposal.md para motivación. Hay dos cambios completados aún sin sincronizar; sus contratos y artefactos se conservan. El usuario aprobó implementar este plan el 2026-10-15. `skip_specs: true` evita inventar comportamiento funcional para una reorganización.

## Goals / Non-Goals

**Goals:** organización coherente por área, dependencias hacia dentro y contratos internos explícitos.

**Non-Goals:** nuevos dominios, paquetes common, jerarquías de servicios, Clock Protocol, extracción de Dimensions, endpoints/proveedores reales, cambios transaccionales o nuevas dependencias.

## Decisions

### 1. HTTP por área y agregación limitada

Rutas relativas a backend:

| Actual | Destino |
| --- | --- |
| adapters/http/delivery_routes.py, delivery_schemas.py | adapters/http/deliveries/routes.py, schemas.py |
| adapters/http/return_routes.py, return_schemas.py | adapters/http/returns/routes.py, schemas.py |
| adapters/http/locker_routes.py, locker_schemas.py | adapters/http/lockers/routes.py, schemas.py |

Añadir __init__.py sin composición ni efectos laterales a esos paquetes. ReceptionInput/AssignmentResponse y DimensionsInput permanecen con los esquemas de Locker. require_empty_action_body permanece en request_validation.py; capacity_http queda en lockers/routes.py, reutilizado desde las rutas Delivery/Return. No crear otro archivo para ese pequeño mapeo.

Nuevo adapters/http/routes.py define create_router(delivery_service, return_service, locker_service), recibe servicios ya construidos e incluye los routers Locker/Delivery/Return en ese orden. No construye dependencias ni contiene handlers, esquemas o helpers. main.py conserva repositorios, servicios, app.state, motor y lifespan; incluye el router agregado. Mantener nombres de handlers, modelos, etiquetas y configuración para preservar OpenAPI completo.

### 2. Servicios de aplicación uniformes

| Actual | Destino y clase |
| --- | --- |
| application/delivery_use_cases.py | application/deliveries.py: DeliveryService |
| application/return_use_cases.py | application/returns.py: ReturnService |
| application/locker_use_cases.py | application/lockers.py: LockerService |
| application/shipping_quote_use_cases.py | application/shipping_quotes.py: ShippingQuoteService |

Un servicio de aplicación agrupa casos de uso del área y coordina puertos; no es un servicio de dominio. Cada método conserva su operación. Se elige esta organización frente a crear una clase/archivo por operación, innecesario a esta escala. ShippingQuoteService conserva compare y sus parámetros de concurrencia/timeout.

DeliveryService y ReturnService requieren clock: Callable[[], datetime] sin default, manteniendo su posición como segundo argumento. main.py proporciona un helper local utc_now que devuelve datetime.now(timezone.utc); pruebas y consumidores directos suministran su reloj. LockerService y shipping no reciben un reloj innecesario. Eliminar application/clock.py.

### 3. Errores y reglas junto a cada flujo

DeliveryNotFoundError y ReturnNotFoundError, subclases de LookupError, viven junto a sus servicios. DeliveryConflictError y ReturnConflictError, subclases de ValueError, viven en domain/deliveries.py y returns.py; cubren transiciones inválidas, fechas de salida y conflicto CAS del flujo correspondiente. Eliminar application/errors.py y los nombres ParcelNotFoundError/CustodyConflictError; los routers capturan la clase exacta de su flujo y conservan 404/409 y mensajes. Los errores existentes de Locker permanecen allí.

Eliminar domain/validation.py. Cada módulo Delivery/Return recibe los helpers privados escalares que utiliza y su validación temporal de salida. Mantener orden, recorte de textos, blancos opcionales, UUID, normalización UTC, comparaciones y mensajes. Se acepta esa duplicación pequeña y visible; no crear otro dominio, un normalizador de entidades ni un archivo genérico sustituto. Las reglas de asignación/recepción y Dimensions siguen en domain/lockers.py. Obtener ahora desde un reloj UTC no sustituye validar los instantes recibidos.

### 4. Contrato de proveedor y resultado de aplicación

domain/shipping_quotes.py conserva ShippingQuoteRequest, ShippingOffer, QuoteOffers y NoCoverage, con todas sus invariantes. ShippingProvider y ProviderTechnicalError permanecen en domain/ports.py. Los adaptadores continúan utilizando únicamente solicitud/ofertas de dominio.

Mover ProviderResult, ProviderStatus y ProviderErrorCode a application/shipping_quotes.py: describen el resultado de coordinar proveedores, incluidos fallos técnicos. ProviderResult valida código, tipo tupla y ofertas antes de estado/error, como hoy; para ofertas no vacías reutiliza la validación pública de QuoteOffers. Las vacías conservan su validación según estado. Mantener mensajes, orden, unicidad y rechazos de valores mal construidos sin importar helpers privados ni introducir domain → application.

El servicio conserva proveedores abiertos, ordenación, resultados parciales, no cobertura, concurrencia, timeout y cancelación. No se conecta a FastAPI ni a persistencia.

### 5. Compatibilidad y verificación

Imports, excepciones, nombre QuoteShipping y construcción sin reloj dejan de ser compatibles: actualizar consumidores internos y README, sin wrappers. Repositorios, tablas, metadata y migraciones 0001–0004 permanecen; solo adaptar imports imprescindibles. Puertos y conexión mantienen su organización.

Antes de editar código, registrar HEAD y capturar OpenAPI completo y DDL/índices de las cinco tablas. Después exigir igualdad; además:

- HTTP inválido/no encontrado/transición fallida conserva 422/404/409, cuerpo y mensajes; parametrizar errores exactos por flujo, sin capturar ambos indiscriminadamente.
- Relojes fijos determinan recepción/salida. Trasladar la cobertura del antiguo reloj por defecto a test_main: demostrar que la composición proporciona un reloj real consciente de UTC; no sustituirla por una prueba tautológica con lambda.
- Preservar los escenarios de las 95 pruebas actuales: 52 unitarias y 43 PostgreSQL. Pueden cambiar nombres o distribución, nunca perder cobertura de rollback, última celda, reocupación, geografía, migraciones y cotizaciones.

Desde backend ejecutar Pyright con `uv run --extra dev pyright --project .. --warnings` (0 errores/0 advertencias); unitarias con `uv run --extra dev python -m unittest discover -s tests/unit -t . -v` sin BD; suite completa con `uv run --extra dev python -m unittest discover -s tests -t . -v -f` y TEST_DATABASE_URL PostgreSQL, sin skips. Mantener configuración y dependencias. sdd_reviewer revisa contratos, fronteras y evidencia real.

## Risks / Trade-offs

La duplicación local puede divergir: conservar escenarios equivalentes por flujo. Los cambios de imports pueden alterar composición o tipos: verificar OpenAPI, Pyright y suite completa, incluyendo el ejemplo directo de README.

## Migration Plan

Sin migración de datos. Adaptar módulos y consumidores conjuntamente; revertir código restaura organización anterior sin tocar datos. No sincronizar ni archivar los cambios previos como parte de este trabajo.
