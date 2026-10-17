# Design

## Context

Ver `proposal.md` para la motivación y el alcance aprobado. La base es `10ee425`; el cambio `add-asynchronous-shipping-quotations` está implementado y queda intacto, incluidos sus deltas y evidencia histórica.

Actualmente `quotation_models.py` y `quotation_ports.py` importan resultados desde `shipping_quotes.py`, que también implementa el comparador. `domain/ports.py` reúne los repositorios y el proveedor de transporte. No existe una dependencia del dominio hacia aplicación ni una filtración de frameworks que haya que reparar: el problema es organización y propiedad de contratos.

## Goals / Non-Goals

**Goals:** módulos cohesionados por área, modelos independientes de sus ejecutores y puertos propiedad de los casos de uso consumidores; conservar firmas, validaciones y comportamiento salvo rutas Python y el nombre explícitamente acordado del comparador.

**Non-Goals:** CQRS, nuevas clases por operación, puertos para llamadas internas entre clases de aplicación, repositorios genéricos, nuevos frameworks, cambios funcionales o de almacenamiento. No reclasificar modelos como entidades de dominio por tener identidad o persistencia.

## Decisions

### 1. Un paquete de aplicación por área

Cada paquete contiene un `__init__.py` vacío. Los consumidores importan desde el módulo que posee el símbolo; no habrá reexports ni wrappers.

| Destino en `backend/application/` | Responsabilidad y origen |
| --- | --- |
| `quotations/models.py` | `Quotation`, `QuotationStatus`, `ProcessErrorCode` desde `quotation_models.py`; `ProviderResult`, `ProviderStatus`, `ProviderErrorCode` y su validación desde `shipping_quotes.py`. |
| `quotations/ports.py` | `QuotationRepository` y `QuotationPublisher` desde `quotation_ports.py`; `ShippingProvider` desde `domain/ports.py`. |
| `quotations/errors.py` | `QuotationStorageError`, `PublicationError`, `SubmissionError` desde `quotation_models.py`; `ProviderTechnicalError` desde `domain/ports.py`. |
| `quotations/comparison.py` | Comparación y sus auxiliares desde `shipping_quotes.py`; clase renombrada `ShippingQuoteComparator`. |
| `quotations/use_cases.py` | `QuotationService` y `QuotationProcessor` desde `quotations.py`. |
| `deliveries/ports.py` | `DeliveryRepository` desde `domain/ports.py`. |
| `deliveries/use_cases.py` | Contenido de `deliveries.py`, incluidos `DeliveryService` y `DeliveryNotFoundError`. |
| `returns/ports.py` | `ReturnRepository` desde `domain/ports.py`. |
| `returns/use_cases.py` | Contenido de `returns.py`, incluidos `ReturnService` y `ReturnNotFoundError`. |
| `lockers/ports.py` | `LockerRepository` desde `domain/ports.py`. |
| `lockers/use_cases.py` | Contenido de `lockers.py`, incluido `LockerService`. |

Agrupar los casos de uso existentes conserva la convención del refactor previo; crear una clase o archivo por operación añadiría fragmentación. Los errores de búsqueda de entregas/devoluciones siguen junto a su servicio porque solo representan ese flujo. Cotizaciones sí separa errores compartidos por varios módulos y adaptadores.

### 2. Modelos y dependencias explícitas

`Quotation` representa el seguimiento del proceso y su lectura; `ProviderResult` representa el resultado de una invocación, incluidos fallos técnicos. Ambos permanecen en aplicación. `ShippingQuoteRequest`, `ShippingOffer`, `QuoteOffers`, `NoCoverage`, entidades y reglas existentes permanecen en dominio.

Los modelos de cotización dependen de biblioteca estándar y datos del dominio; nunca del comparador, los puertos ni los adaptadores. Los puertos dependen de esos modelos y del dominio. El comparador depende del puerto `ShippingProvider`, modelos y errores que necesite. Los casos de uso dependen de los puertos, modelos y comparador concreto, sin añadir un protocolo para esta colaboración interna.

Todos los puertos de salida pasan al área de aplicación que los utiliza. Esta decisión actualiza deliberadamente la ubicación de `ShippingProvider` y `ProviderTechnicalError` elegida en `refactor-hexagonal-module-boundaries`; no se reescribe aquel diseño histórico. Se elimina `domain/ports.py`. El dominio no importa aplicación; aplicación no importa adaptadores, FastAPI, SQLModel ni RabbitMQ.

### 3. Integración por cambio de imports

Actualizar `main.py`, `worker.py`, rutas y esquemas HTTP, repositorio de cotizaciones, adaptador RabbitMQ, simuladores y pruebas que consumen símbolos movidos. Los repositorios siguen implementando protocolos estructuralmente, sin herencia o capas nuevas. Mantener la composición explícita y `MessageDelivery` como contrato local del adaptador de cola.

Actualizar los destinos de `patch`, especialmente `application.shipping_quotes.asyncio.timeout`, para que sigan interceptando el módulo ejecutado. El README mostrará el árbol y los imports nuevos, el nombre del comparador y la propiedad de los puertos. Eliminar los módulos planos sustituidos; conservar `domain/shipping_quotes.py`.

### 4. Aceptación mediante regresión y comparación

- El comparador importado desde `application.quotations.comparison` sigue funcionando sin base de datos ni broker, conserva validación de resultados, orden por proveedor/servicio, concurrencia 3, timeout admitido de 2 segundos, cancelación y ausencia de reintentos.
- Encolado, confirmación de publicación, ack temprano, ejecución secuencial, resultados/fallos y lectura persistida conservan su contrato. No cambian firmas de puertos, valores de enums, mensajes de errores ni perfiles estocásticos de los simuladores.
- Entregas, devoluciones, lockers y custodia mantienen sus reglas y transacciones; todas las suites existentes continúan pasando con imports actualizados.
- OpenAPI y DDL/metadatos SQL coinciden con la captura anterior al cambio. Las revisiones Alembic `0001`–`0005` quedan sin modificaciones y no aparece una nueva migración.
- No quedan imports ejecutables a módulos retirados ni ciclos introducidos. Los cuatro `__init__.py` nuevos están vacíos, y los adaptadores consumen modelos o puertos sin importar sus tipos desde el comparador.

Usar las suites documentadas: 77 pruebas unitarias, 50 de PostgreSQL y 1 de mensajería en la base actual, sin omisiones; conservar pruebas deterministas mediante los dobles y parches existentes. Ejecutar desde `backend/` `uv run --extra dev pyright --project .. --warnings`, exigiendo cero errores y cero advertencias. La revisión independiente comprobará estos límites y la evidencia; no se necesitan nuevas pruebas que solo reproduzcan el movimiento de archivos.

## Risks / Trade-offs

- Imports y destinos de parches obsoletos → búsqueda de referencias y ejecución de las suites completas, incluidos arranque y mensajería.
- Ciclos al mezclar modelos y ejecutores → modelos/errores sin dependencias hacia ejecutores; imports explícitos y `__init__.py` vacíos.
- Consumidores Python externos deben actualizarse → cambio de rutas y nombre documentado, sin compatibilidad transitoria que oculte la estructura final.
- Diferencias entre specs principales y el cambio asíncrono aún sin sincronizar → preservar conjuntamente el comportamiento implementado y sus deltas; no sincronizar ni archivar como parte de este refactor.

## Migration Plan

Conservar la captura inicial de OpenAPI y metadatos, mover definiciones sin alterar sus cuerpos salvo imports y el nombre del comparador, actualizar consumidores y comparar con la captura. Desplegar API y worker desde el mismo código revisado; la base de datos y los mensajes UUID existentes no requieren conversión. Un rollback revierte el código y sus imports sin modificar datos. El coordinador registrará resultados reales y cierre de tareas tras verificación y revisión.
