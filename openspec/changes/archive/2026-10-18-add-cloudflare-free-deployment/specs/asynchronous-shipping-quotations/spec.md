# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
