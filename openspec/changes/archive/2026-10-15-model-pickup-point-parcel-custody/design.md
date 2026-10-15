# Design

## Context

Ver `proposal.md` para la motivación. Actualmente ambas entidades son dataclasses inmutables con UUID y un único texto; los servicios solo crean/listan, los repositorios insertan en una transacción y Alembic conserva una revisión `0001`. Las especificaciones actuales exigen independencia entre Delivery y Return. El cambio cruza dominio, HTTP, persistencia y migraciones, por lo que requiere diseño explícito.

## Goals / Non-Goals

**Goals:** mantener el dominio independiente de frameworks, expresar transiciones de custodia verificables y asegurar que una salida concurrente no sobrescribe otra. Conservar la identidad y los datos ante errores.

**Non-Goals:** no introducir repositorios genéricos, event sourcing, colas, una unidad de trabajo compartida entre entidades ni una migración automática de datos comerciales incompletos. Las exclusiones funcionales están en la propuesta.

## Decisions

### Modelo y reloj

- Mantener entidades inmutables y enums Python en `domain/models.py`. Crear métodos de transición que devuelvan una nueva instancia válida. No usar modelos HTTP o SQLModel en dominio.
- Campos comunes: `id: UUID`, `tracking_number: str`, `carrier_code: str`, `received_at: datetime` con zona UTC. Una entidad representa un paquete; no hay clave foránea entre ambas.
- Delivery añade `recipient_name: str`, `recipient_phone: str | None`, `pickup_deadline_at: datetime | None`, estado y dos fechas de salida opcionales. Return añade solamente `sender_name: str | None`, estado y fecha de entrega opcional. Los estados y campos exactos son los de las delta specs.
- Recortar espacios exteriores sin alterar mayúsculas, guiones ni contenido interno de seguimiento/transportista. Rechazar textos obligatorios vacíos; normalizar textos opcionales blancos a `None`. No verificar formatos de teléfono ni catálogos externos de transportistas.
- Los servicios obtienen fechas de un reloj UTC inyectable mediante un callable, con valor de producción basado en el reloj del sistema. El dominio recibe las fechas y verifica zona y cronología; no consulta el reloj. La reconstrucción desde base de datos valida las mismas invariantes.
- La fecha límite acepta un instante con zona, se normaliza a UTC y puede preceder a la recepción. No desencadena transición ni impide recogida. Ante una salida cuya fecha de sistema sea anterior a recepción, devolver conflicto sin cambiar datos.
- No imponer unicidad de seguimiento global ni por transportista: el UUID sigue siendo la identidad. Definir deduplicación necesitaría requisitos nuevos.

Alternativa descartada: entidades mutables con estados y fechas editables libremente, porque admitirían combinaciones incoherentes y ocultarían las reglas de custodia.

### Casos de uso, puertos y concurrencia

Ampliar los puertos de repositorio con consulta por UUID y una operación específica que guarda una transición solo si el registro sigue pendiente. Los servicios consultan, rechazan ausencia, solicitan la transición al dominio e invocan esa escritura condicional; un resultado sin actualización se traduce en conflicto. Mantener `save` como inserción, sin convertirlo en un upsert.

El adaptador SQLModel ejecutará un `UPDATE` con condición de UUID y estado pendiente, modificando exclusivamente estado y fechas de salida. Comprobará la fila actualizada dentro de la transacción y confirmará antes de retornar. Dos procesos pueden leer el mismo estado, pero solo uno puede actualizarlo; el perdedor recibe conflicto. No hay eliminación de registros en este alcance, por lo que una lectura encontrada seguida de fallo condicional es un `409`.

La exclusión se expresa además mediante restricciones de tabla: pendiente implica fechas de salida nulas; recogido implica solo `collected_at`; devuelto implica solo `returned_to_carrier_at`; Return entregada implica `handed_over_at`. Las fechas de salida no pueden preceder a la recepción. Usar texto con restricciones de valores para estados y columnas PostgreSQL con zona horaria para fechas, evitando tipos enum nativos innecesarios.

Conservar el soporte SQLite de las pruebas locales: normalizar a UTC antes de guardar y reponer la zona UTC al rehidratar valores SQLite que pierdan el indicador de zona. Las pruebas locales verifican instantes equivalentes y siguen funcionando sin PostgreSQL; las garantías de concurrencia y los bloqueos de migración se verifican adicionalmente sobre PostgreSQL real.

Alternativas descartadas: comprobar solo en memoria no evita carreras; una unidad de trabajo con bloqueos mantenidos entre lectura y dominio sería más invasiva para esta única transición de una fila.

### Contrato HTTP

| Operación | Ruta | Respuesta correcta |
|---|---|---|
| Registrar recepción Delivery | `POST /deliveries` | `201`, representación completa |
| Consultar entregas | `GET /deliveries` | `200`, lista completa |
| Registrar recogida | `POST /deliveries/{id}/collect` | `200`, representación actualizada |
| Devolver al transportista | `POST /deliveries/{id}/return-to-carrier` | `200`, representación actualizada |
| Registrar recepción Return | `POST /returns` | `201`, representación completa |
| Consultar devoluciones | `GET /returns` | `200`, lista completa |
| Entregar al transportista | `POST /returns/{id}/hand-over` | `200`, representación actualizada |

Los schemas de creación solo aceptan los campos de entrada definidos en las specs, con campos adicionales prohibidos. Los endpoints de salida aceptan ausencia de cuerpo o `{}`; rechazan cualquier otro cuerpo. Ninguna operación admite UUID, estado o fechas de sistema suministrados por el cliente. La fecha límite es la excepción explícita porque procede del transportista. Las respuestas incluyen opcionales nulos y fechas con zona UTC.

Los adaptadores traducen ausencia a `404`, salida repetida/incompatible, carrera perdida o cronología inválida a `409`, y UUID/body/campos inválidos a `422`, conservando `detail` como explicación legible. Los errores de infraestructura no se convierten en validación de negocio y no deben producir respuesta de éxito.

Alternativa descartada: un `PATCH` genérico permitiría editar estados y fechas fuera de las operaciones de negocio.

## Risks / Trade-offs

- [Cambio incompatible del contrato] → actualizar ejemplos y pruebas conjuntamente; clientes deben enviar datos de etiqueta y no `address`/`reason`.
- [Datos legacy insuficientes] → bloquear la migración sin pérdida; completar/importar datos reales requeriría otro plan explícito. Este cambio no promete migrar bases ya pobladas.
- [Reloj del sistema retrocede] → rechazar cronología inválida sin modificar registros; pruebas usan reloj controlado.
- [Mock de repositorio no demuestra atomicidad] → verificar las carreras con sesiones PostgreSQL independientes y sincronización controlada en las pruebas.
- [Propósito descriptivo de main specs aún menciona address/reason] → no editar main specs durante planificación; actualizar esos propósitos al sincronizar de forma autorizada para que reflejen los nuevos requisitos.

## Migration Plan

1. Crear revisión `0002` sobre `0001`, sin reescribir la migración histórica. Preparar copia de seguridad y detener escrituras durante despliegue según README; la API sigue sin crear ni migrar tablas al arrancar.
2. Dentro de una transacción PostgreSQL, bloquear ambas tablas para impedir escrituras entre comprobación y cambio. Antes de cualquier DDL, comprobar si alguna contiene filas.
3. Si hay filas legacy, abortar con tablas afectadas y explicación de que faltan datos de paquetería. Conservar filas, columnas y revisión `0001`; indicar que se necesita una migración explícita con información real, sin sugerir reset ni valores ficticios.
4. Con tablas vacías, retirar `address`/`reason`, incorporar los campos y restricciones descritos y registrar `0002`. Cualquier fallo revierte la transacción completa.
5. El downgrade de `0002` aplica la misma comprobación bajo bloqueo: rechaza tablas pobladas antes de modificar nada; con tablas vacías restaura exactamente `0001`. Restaurar una copia de seguridad permite recuperar el despliegue previo cuando corresponda; no hacer downgrade destructivo de paquetes nuevos.
6. Verificar upgrade limpio, recorrido vacío `0001 → 0002 → 0001 → 0002`, rechazo por filas en cualquiera de las dos tablas y conservación íntegra en ambos sentidos. Después arrancar la API con el nuevo contrato.

## Verification

Pruebas de dominio/aplicación para normalización, estado inicial, fechas, salidas y errores; HTTP para contratos completos y `201/200/404/409/422`; repositorios locales SQLite para round trip, rollback y UUID duplicado; pruebas adicionales PostgreSQL para transiciones concurrentes y migraciones no destructivas. Ejecutar desde `backend/` la suite documentada `uv run --extra dev python -m unittest discover -s tests -v`, manteniendo su funcionamiento local sin servidor, y preparar `TEST_DATABASE_URL` según README para las comprobaciones PostgreSQL. Registrar con precisión cualquier comprobación no disponible. Validar también el cambio con `openspec validate model-pickup-point-parcel-custody --strict`; esa validación no demuestra la implementación.
