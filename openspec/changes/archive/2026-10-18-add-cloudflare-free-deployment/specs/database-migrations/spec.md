# Spec Delta

## MODIFIED Requirements

### Requirement: Manage a shared and reversible history

En PostgreSQL, las migraciones SHALL gestionar paquetes, lockers y cotizaciones mediante el historial Alembic existente: 0001 conserva UUID/textos legacy; 0002 introduce custodia; 0003 lockers/celdas/asignaciones; 0004 geografía y alias opcional; 0005 solicitudes/resultados/ofertas. Revisiones 0001–0005 SHALL permanecer intactas. Los downgrades SHALL mantener sus guardas de datos y el historial vacío SHALL ser reversible hasta base. D1 SHALL usar un historial independiente.

#### Scenario: Apply the initial revision
- **WHEN** `alembic upgrade 0001` se ejecuta sobre una base PostgreSQL vacía
- **THEN** deliveries contiene UUID id y address no nulo, returns contiene UUID id y reason no nulo, y se registra 0001

#### Scenario: Apply the current schema
- **WHEN** `alembic upgrade head` se ejecuta sobre una base PostgreSQL vacía
- **THEN** existen custodia, lockers/geografía y solicitudes/resultados/ofertas, se registra 0005 y no reaparecen address/reason legacy de paquetes

#### Scenario: Revert the initial revision
- **WHEN** `alembic downgrade base` se ejecuta con todas las tablas de negocio vacías
- **THEN** se revierte el historial y se eliminan las tablas conforme al comportamiento existente

### Requirement: Prepare the schema outside API startup

La API y los consumidores de ambos perfiles SHALL iniciar sin crear tablas ni ejecutar migraciones. Cada esquema SHALL prepararse mediante el procedimiento de migración correspondiente antes de usar operaciones de datos. Un esquema ausente SHALL no provocar inicialización automática ni selección silenciosa de otro almacenamiento.

#### Scenario: Startup without schema changes
- **WHEN** se construye y arranca una instancia API de cualquier perfil
- **THEN** su lifecycle no crea tablas ni ejecuta migraciones

#### Scenario: Start a consumer with an unprepared database
- **WHEN** un consumidor intenta trabajar con una base sin preparar
- **THEN** comunica el fallo de persistencia sin modificar el esquema ni fabricar datos

## ADDED Requirements

### Requirement: Prepare an independent D1 schema history

D1 SHALL disponer de migraciones SQL versionadas, aplicables local y remotamente antes de desplegar código. La primera revisión SHALL crear el esquema vigente de paquetes, lockers, celdas, asignaciones y cotizaciones sin importar datos PostgreSQL ni simular sus revisiones legacy. Reaplicar el procedimiento SHALL no repetir migraciones ya registradas ni alterar datos existentes.

#### Scenario: Prepare and reopen a fresh D1 database
- **WHEN** se aplican migraciones sobre D1 vacío, se guardan datos y se ejecuta nuevamente el procedimiento
- **THEN** se conserva la revisión y todos los datos, y otra instancia puede leerlos con sus contratos actuales

### Requirement: Enforce D1 storage integrity

El esquema D1 SHALL preservar claves, relaciones, estados válidos, dimensiones, geografía y cronología, con una asignación por paquete y como máximo una activa por celda compartida. SHALL conservar historial después de liberar o retirar celdas. Las conversiones de UUID, UTC y valores numéricos SHALL ser verificadas contra los contratos de dominio sin coerciones que oculten entradas inválidas.

#### Scenario: Reject invalid direct writes
- **WHEN** se intenta insertar una referencia inexistente, doble ocupación, asignación sin paquete o con ambos tipos, dimensiones inválidas, geografía parcial o estado/fecha incoherente
- **THEN** D1 rechaza la escritura sin modificar los datos previos

#### Scenario: Keep historical assignments readable
- **WHEN** se libera una asignación y después se cambia o retira su celda
- **THEN** se mantienen identidad, dimensiones del paquete y fechas de su custodia original

### Requirement: Preserve D1 data when reverting application code

La estrategia de migraciones D1 SHALL evolucionar hacia delante y declarar la compatibilidad de esquema de las versiones desplegables. Una reversión ordinaria SHALL no eliminar tablas o registros para restaurar código. Cuando no haya código anterior compatible, SHALL requerir una intervención explícita con copia/export de datos, conservando el estado y explicando el bloqueo.

#### Scenario: Reject an incompatible rollback
- **WHEN** se intenta restaurar una versión que no admite el esquema D1 instalado
- **THEN** el procedimiento se detiene con un diagnóstico y mantiene esquema, revisión y datos, sin reset ni downgrade destructivo
