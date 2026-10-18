# Record Persistence Specification

## Purpose

Keep deliveries and returns in persistent storage separated by type, preserving their identity and allowing operations to continue after a failed write.

## Requirements

### Requirement: Preserve identity and content by record type

Persistence SHALL preserve each valid parcel's UUID, tracking data, contact data, optional deadline, custody state, and reception and exit timestamps, retaining null optional values and timezone-aware instants. It SHALL keep deliveries separate from returns and support retrieval from new instances connected to the same prepared database.

#### Scenario: Retrieve records from another instance
- **WHEN** a delivery and an independent return are saved and retrieved through new instances connected to the same database
- **THEN** each list contains its complete saved representation without mixing record types or losing optional values or timestamp precision

#### Scenario: Retrieve a completed parcel
- **WHEN** a successful custody exit is retrieved through another instance
- **THEN** the final state and its single corresponding exit timestamp are preserved with the original identity and reception data

### Requirement: Isolate a failed write

Each write SHALL be committed when completed successfully or rolled back if it fails. An insertion with a duplicate UUID SHALL fail without replacing the existing record or preventing a subsequent valid write.

#### Scenario: Duplicate UUID followed by a valid write
- **WHEN** an attempt is made to save an entity with the UUID of another already saved in its collection, followed by saving an entity with a new UUID
- **THEN** the duplicate insertion fails, the original record remains, and the subsequent write can complete and be retrieved

### Requirement: Commit at most one exit per parcel

Persistence SHALL atomically accept an exit only while its parcel is in the corresponding pending state. Concurrent repeated or incompatible exit requests MUST commit at most one transition; a rejected contender SHALL observe a conflict without changing the winning state or timestamp. A successful HTTP response SHALL follow the successful commit.

#### Scenario: Competing delivery exits
- **WHEN** independent requests attempt collection and carrier return for the same pending delivery concurrently
- **THEN** exactly one returns `200`, the other returns `409`, and subsequent reads contain only the winning state and its exit timestamp

#### Scenario: Competing repeated handovers
- **WHEN** independent requests attempt to hand over the same pending return concurrently
- **THEN** exactly one returns `200`, the other returns `409`, and the winning handover timestamp remains unchanged

#### Scenario: Failed exit persistence
- **WHEN** persisting a custody transition fails before commit
- **THEN** the pending parcel remains unchanged and a later valid transition can still succeed

### Requirement: Persist shared physical capacity with referential integrity

Persistence SHALL preserve lockers, identifiable cells and parcel assignments, including assignment history after release. Every assignment SHALL reference exactly one existing delivery or return and one existing cell. Each parcel SHALL have at most one assignment, and each cell SHALL have at most one active assignment across both parcel types. Missing references, invalid dimensions and release before assignment SHALL be rejected.

#### Scenario: Invalid shared occupancy
- **WHEN** a write attempts two active assignments for one cell, references a missing parcel/cell, references both parcel types or neither, or assigns the same parcel twice
- **THEN** persistence rejects it without altering existing records

#### Scenario: Retrieve assignment after release
- **WHEN** a completed parcel is retrieved using new repository instances after its cell is resized or retired
- **THEN** its original assignment identity, parcel dimensions and reception/exit timestamps remain available

### Requirement: Commit reception and occupancy together

En ambos perfiles, una recepción SHALL confirmar el paquete y su asignación juntos, o ninguno. Entregas y devoluciones SHALL compartir la capacidad física. Ante dos recepciones válidas que compiten por la última celda compatible, exactamente una SHALL confirmarse y la otra SHALL observar el conflicto de capacidad tras el commit ganador, sin dejar un paquete sin asignar.

#### Scenario: Last cell across both flows
- **WHEN** peticiones independientes PostgreSQL o D1 reciben concurrentemente una entrega y una devolución en la última celda compatible
- **THEN** una responde 201 y la otra 409 FULL, con exactamente un paquete nuevo y una asignación activa

#### Scenario: Failed reception before commit
- **WHEN** se inyecta un fallo después de las escrituras de paquete/asignación pero antes del commit
- **THEN** no persiste ninguno, la capacidad sigue libre y una recepción posterior puede completarse

### Requirement: Commit exit and specific assignment release together

An assigned parcel's successful custody exit SHALL commit its state/timestamp and release of its own active assignment atomically. Failed or losing exits SHALL not release capacity. A later occupant of the same cell SHALL never be affected by an operation on a previously completed parcel. Successful responses SHALL follow commit.

#### Scenario: Failure between custody update and commit
- **WHEN** an assigned parcel's exit fails after its state update and before commit
- **THEN** the parcel remains pending and its assignment remains active; a later valid exit can succeed

#### Scenario: Concurrent exits and reoccupation
- **WHEN** two exits compete for parcel A, the winner releases it, parcel B occupies the cell and the old loser is retried
- **THEN** only one A exit succeeds, A's timestamp remains unchanged and B's active assignment is preserved

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

### Requirement: Bound D1 reception selection transfer independently of locker size

La selección para una recepción D1 SHALL transferir al runtime como máximo una fila de decisión de tamaño independiente del número de celdas por intento, sin reconstruir la configuración completa. SHALL conservar selección exacta, errores de negocio, reevaluación concurrente y atomicidad existentes para entregas y devoluciones, sin reducir la capacidad pública ni ocultar fallos de infraestructura.

#### Scenario: Receive against accumulated capacity
- **WHEN** se recibe una entrega o devolución válida en un locker con 2000 celdas
- **THEN** la lectura de selección transfiere una fila de decisión y se confirma la misma celda que elegiría el dominio
- **AND** las consultas públicas siguen devolviendo todas las celdas y la recepción no requiere transferirlas ni reconstruirlas

#### Scenario: Preserve exact selection across dimension boundaries
- **WHEN** las candidatas incluyen rotaciones, volúmenes iguales o casi iguales superiores a 64 bits y dimensiones de hasta 2147483647 por eje
- **THEN** se selecciona el menor volumen entero exacto y después el menor UUID entre las celdas habilitadas, no retiradas y libres, sin pérdida de precisión

#### Scenario: Preserve decision errors with a bounded result
- **WHEN** el locker no existe, está inactivo, carece de celdas habilitadas compatibles o tiene ocupadas todas las compatibles
- **THEN** se conserva respectivamente 404, 409 LOCKER_INACTIVE, 409 NO_COMPATIBLE_CELL o 409 FULL, con esa precedencia y sin guardar un paquete

#### Scenario: Reevaluate a stale compact decision
- **WHEN** otra recepción o un cambio de configuración invalida la decisión antes de confirmar
- **THEN** se reevalúa el estado confirmado dentro de los intentos acotados existentes, sin ocupaciones dobles ni escrituras parciales
- **AND** la contención agotada sigue siendo 503 y un commit desconocido no provoca una segunda escritura automática
