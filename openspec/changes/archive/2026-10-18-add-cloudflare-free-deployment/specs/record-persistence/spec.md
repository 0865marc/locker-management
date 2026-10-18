# Spec Delta

## MODIFIED Requirements

### Requirement: Commit reception and occupancy together

En ambos perfiles, una recepción SHALL confirmar el paquete y su asignación juntos, o ninguno. Entregas y devoluciones SHALL compartir la capacidad física. Ante dos recepciones válidas que compiten por la última celda compatible, exactamente una SHALL confirmarse y la otra SHALL observar el conflicto de capacidad tras el commit ganador, sin dejar un paquete sin asignar.

#### Scenario: Last cell across both flows
- **WHEN** peticiones independientes PostgreSQL o D1 reciben concurrentemente una entrega y una devolución en la última celda compatible
- **THEN** una responde 201 y la otra 409 FULL, con exactamente un paquete nuevo y una asignación activa

#### Scenario: Failed reception before commit
- **WHEN** se inyecta un fallo después de las escrituras de paquete/asignación pero antes del commit
- **THEN** no persiste ninguno, la capacidad sigue libre y una recepción posterior puede completarse

### Requirement: Serialize capacity changes with reception and release

Configuración, recepción y salida del mismo locker SHALL resolverse sobre estado confirmado sin invalidar celdas ocupadas. Una recepción SHALL reevaluar configuración y capacidad cuando una operación concurrente invalide su lectura. La contención temporal SHALL no comunicarse como capacidad llena y los fallos de infraestructura SHALL permanecer distinguibles de conflictos de negocio en ambos perfiles.

#### Scenario: Reception competes with configuration
- **WHEN** una recepción compite con redimensionar, deshabilitar o retirar su celda candidata
- **THEN** o gana recepción y la modificación devuelve 409, o gana configuración y recepción usa el nuevo estado válido o devuelve conflicto de capacidad sin guardar un paquete

#### Scenario: Competing reception rolls back
- **WHEN** el primer contendiente por la última celda revierte antes del commit
- **THEN** el otro puede adquirirla y no informa FULL solo porque existió contención temporal

#### Scenario: Every capacity writer participates
- **WHEN** activación, metadata, ampliación, modificación o retiro de celdas y recepciones/salidas de ambos tipos compiten en D1
- **THEN** cada resultado exitoso respeta el estado confirmado y ninguna escritura omite la protección de ocupación ni sobrescribe una operación ganadora

## ADDED Requirements

### Requirement: Preserve persistence contracts in the D1 profile

D1 SHALL satisfacer los requisitos existentes de identidad, opcionales, UTC, aislamiento de fallos, referencias, historial, única salida y salida/liberación atómica. SHALL conservar la selección exacta por volumen y UUID, incluidas dimensiones máximas, sin degradar enteros a flotantes. Sus metadatos internos SHALL no aparecer en respuestas públicas.

#### Scenario: Preserve precise identity and ordering
- **WHEN** se recuperan datos con microsegundos, zonas originales distintas, opcionales nulos y celdas con volúmenes superiores a 64 bits o casi iguales
- **THEN** se conservan UUID, instantes UTC y contenido y se elige exactamente la misma celda que determina el dominio, con desempate por UUID

#### Scenario: Competing exits cannot release a later occupant
- **WHEN** dos salidas compiten por A, la ganadora libera su asignación, B ocupa la celda y se repite la salida perdedora de A
- **THEN** solo una salida de A tiene éxito, su fecha no cambia y B conserva su propia asignación activa

#### Scenario: A failed multi-write operation leaves no partial data
- **WHEN** falla una sentencia interior de una recepción, salida o modificación múltiple D1
- **THEN** todas sus escrituras revierten, incluidas las marcas internas de concurrencia, y una operación posterior válida puede completarse

### Requirement: Distinguish unavailable persistence from business conflicts

El perfil D1 SHALL responder 503 cuando una operación no puede completarse por contención agotada, cuota o error de acceso manejable por la aplicación. SHALL no inventar FULL, éxito ni errores de validación para esos fallos. Solo SHALL repetir una decisión de concurrencia si tiene evidencia de cero cambios; un resultado de commit desconocido SHALL no provocar una segunda escritura automática.

#### Scenario: Repeated contention is not a full locker
- **WHEN** cambios concurrentes impiden confirmar una operación dentro de sus intentos acotados aunque exista capacidad
- **THEN** se devuelve 503 sin escrituras parciales ni un 409 FULL falso

#### Scenario: A write result is unknown
- **WHEN** el transporte falla y no se conoce si D1 confirmó la operación
- **THEN** se comunica indisponibilidad sin SQL ni datos sensibles y no se reejecuta automáticamente la escritura ni se afirma que hubo rollback
