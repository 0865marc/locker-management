# Spec Delta

## ADDED Requirements

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
