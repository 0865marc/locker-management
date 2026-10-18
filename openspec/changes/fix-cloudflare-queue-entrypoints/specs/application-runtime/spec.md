# Spec Delta

## ADDED Requirements

### Requirement: Accept the Cloudflare queue event invocation

Las entradas Queues de producción y del spike SHALL aceptar el lote, entorno y contexto suministrados por el runtime, además de la llamada abreviada con solo lote. SHALL conservar los bindings de la instancia del evento, el reconocimiento previo y la restauración del contexto, sin reintentos ni cambios en el procesamiento.

#### Scenario: Invoke with the complete platform arguments
- **WHEN** el runtime entrega lote, entorno y contexto a cualquiera de las dos entradas
- **THEN** la entrada alcanza el consumidor sin error por número de argumentos y utiliza el entorno de su instancia, sin sustituirlo por el argumento adicional del callback
- **AND** reconoce cada mensaje antes de leer su cuerpo o realizar trabajo de persistencia o aplicación

#### Scenario: Preserve the abbreviated invocation
- **WHEN** una llamada suministra únicamente el lote a una instancia con su entorno establecido
- **THEN** conserva la misma delegación y procesamiento que la invocación completa

#### Scenario: Restore the event context after success or failure
- **WHEN** termina el procesamiento o falla el reconocimiento o el trabajo posterior
- **THEN** el contexto anterior queda restaurado; un reconocimiento fallido impide leer el cuerpo o iniciar trabajo y no se añade ningún reintento
