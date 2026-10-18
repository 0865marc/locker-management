# asynchronous-shipping-quotations Specification

## Purpose

Queue shipping comparisons for a single worker and preserve requests, provider outcomes and offers for later consultation, without automatic retries or recovery.

## Requirements

### Requirement: Save and enqueue a quotation once

POST /quotations SHALL validate the existing shipping input, save a new PENDING request and publish its identifier once. It SHALL return 202 with id, PENDING status and Location only after publication confirmation, without calling providers. Invalid input or unknown fields SHALL return 422 without stored work. A failed initial write SHALL return 503 without publication.

#### Scenario: Enqueue valid input
- **WHEN** valid ES transport input is submitted and persistence and publication succeed
- **THEN** the request, including postal leading zeroes, is saved and 202 identifies it before any provider comparison is required to finish

#### Scenario: Invalid input
- **WHEN** countries, postal codes, weight, dimensions or extra fields violate the existing input contract
- **THEN** 422 is returned without storing or publishing a quotation

### Requirement: Report publication failure without provider results

A failed publication SHALL return 503 with the saved quotation identifier and SHALL attempt to mark that still-pending request FAILED with process_error_code PUBLISH_ERROR when persistence is available. It SHALL not retry publication or fabricate provider results. Saving and publication SHALL have no atomicity or automatic repair guarantee.

#### Scenario: Broker rejects or cannot receive publication
- **WHEN** the request is saved but its single publication attempt fails
- **THEN** 503 identifies the saved request, FAILED/PUBLISH_ERROR is recorded if possible, and no provider is reported as failed merely because publication failed

### Requirement: Execute one comparison and retain provider outcomes

A single worker SHALL process quotations sequentially using the current provider configuration. It SHALL mark a pending request PROCESSING, compare once and atomically store all results/offers with COMPLETED. Existing QUOTED/NOT_COVERED/FAILED statuses, error codes, pricing and provider/service ordering SHALL remain unchanged. Provider errors and timeouts SHALL not be retried.

#### Scenario: Successful and failed providers together
- **WHEN** comparison returns offers from one provider, a technical error from another and no coverage from a third
- **THEN** the quotation completes with QUOTED offers, FAILED/PROVIDER_ERROR and NOT_COVERED, preserving each provider and any multiple services

#### Scenario: No response times out without retry
- **WHEN** one provider does not answer within the existing admitted-call timeout
- **THEN** it is called once and recorded as FAILED/PROVIDER_TIMEOUT while other outcomes are retained; even an all-failed result set completes the quotation

### Requirement: Consume without requeue or automatic recovery

El consumidor SHALL reconocer cada entrega antes de leer/procesar su cotización y no comenzar si falla el reconocimiento. SHALL no reencolar, republicar ni recuperar automáticamente trabajos consumidos. Mensajes inválidos y solicitudes no PENDING SHALL ignorarse. En Queues SHALL solicitarse ack explícito y desactivarse los reintentos del consumidor. Una caída puede dejar PENDING/PROCESSING indefinidamente; SHALL no prometerse exactamente una vez.

#### Scenario: Acknowledge before execution
- **WHEN** se recibe un mensaje válido y la comparación termina con fallos de proveedores
- **THEN** el reconocimiento precede a consultas/proveedores, se guarda el resultado una vez y el trabajo consumido no se reencola ni repite automáticamente

#### Scenario: Unexpected processing failure
- **WHEN** aparece un error inesperado después del consumo
- **THEN** se intenta guardar FAILED/PROCESSING_ERROR si la persistencia lo permite, sin inventar resultados ni repetir la comparación
- **AND** no se garantiza registrar el error final si proceso o base no están disponibles

#### Scenario: Cloudflare acknowledgement fails
- **WHEN** falla la llamada de reconocimiento explícito del mensaje Queues
- **THEN** no se lee ni procesa la cotización, y no se solicita retry ni se publica otro mensaje

### Requirement: Retrieve saved requests and results

GET /quotations/{id} SHALL return id, original request, status, UTC created_at/finished_at, process_error_code and results. PENDING/PROCESSING SHALL have empty results and null finished_at; COMPLETED SHALL expose the complete normalized result set; FAILED SHALL expose its process error. Unknown UUID SHALL return 404, malformed UUID 422 and unavailable persistence 503. Reads SHALL remain coherent with the committed state.

#### Scenario: Read from a new instance
- **WHEN** an API instance reads a pending, completed or failed quotation saved by another instance
- **THEN** it retrieves the same request and committed state, with preserved offers/provider errors or process error, without ranking offers or invoking providers

### Requirement: Confirm Cloudflare publication before acceptance

El perfil Cloudflare SHALL conservar la secuencia guardar PENDING, publicar una vez y devolver 202 únicamente tras confirmación persistente de Queues. El fallo inicial de almacenamiento SHALL impedir publicar. El fallo de publicación SHALL conservar el 503 con id y el intento de marcar FAILED/PUBLISH_ERROR. Guardado/publicación SHALL no presentarse como transacción atómica ni repararse automáticamente.

#### Scenario: Queue publication is accepted
- **WHEN** D1 guarda la solicitud y Queues confirma el envío
- **THEN** POST devuelve 202 con id, PENDING y Location sin esperar a comparar proveedores

#### Scenario: Publication is not confirmed
- **WHEN** no se confirma la publicación después de guardar la solicitud
- **THEN** POST devuelve 503 con el id y se intenta marcar PUBLISH_ERROR solo si sigue PENDING, sin republicar ni fabricar resultados

### Requirement: Ignore duplicate deliveries after the first state transition

Ante entregas duplicadas, D1 SHALL permitir una sola transición PENDING a PROCESSING. Solo el ganador SHALL comparar proveedores. Copias posteriores SHALL reconocerse e ignorarse si la solicitud no existe o ya está PROCESSING, COMPLETED o FAILED. Un trabajo bloqueado tras una caída SHALL no volver a PENDING para facilitar otra ejecución.

#### Scenario: Duplicate messages compete
- **WHEN** dos mensajes válidos identifican la misma cotización PENDING
- **THEN** como máximo uno inicia la comparación y solo existe un conjunto final de resultados

#### Scenario: Repeat a consumed or unknown identifier
- **WHEN** llega una copia para un id inexistente, en proceso o finalizado
- **THEN** se consume sin invocar proveedores, alterar fechas/resultados o reabrir el trabajo

### Requirement: Commit and read complete quotation outcomes in D1

D1 SHALL guardar todos los resultados/ofertas y COMPLETED en una única operación atómica aceptada solo desde PROCESSING. Otro estado SHALL provocar rechazo sin cambios, no éxito silencioso. Consultas SHALL devolver una representación coherente, con resultados completos solo para COMPLETED y vacíos para estados sin resultados, conservando errores, orden, precios y fechas del contrato vigente.

#### Scenario: Fail during result persistence
- **WHEN** falla una escritura interior del lote final
- **THEN** no queda ningún resultado/oferta parcial ni transición COMPLETED; el tratamiento de fallo conserva el contrato actual sin otra comparación

#### Scenario: Complete from an unexpected state
- **WHEN** se intenta completar una cotización PENDING, COMPLETED, FAILED o inexistente
- **THEN** se informa del rechazo y no se insertan resultados ni se altera el estado o la fecha existente

#### Scenario: Read while completion commits
- **WHEN** GET compite con la confirmación de resultados
- **THEN** observa el estado previo coherente o COMPLETED con todo el lote, nunca una mezcla parcial
