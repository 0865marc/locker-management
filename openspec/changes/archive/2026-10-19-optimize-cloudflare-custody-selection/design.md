# Design

## Context

Véase `proposal.md` para la evidencia remota y sus límites. `CustodyStore.receive` comparte la recepción de entregas y devoluciones: actualmente obtiene `snapshot`, construye un `Locker` completo y ejecuta `choose_cell` antes de un batch protegido por revisión/token. Los escritores de capacidad ya participan en ese protocolo. Las dimensiones del dominio permiten productos de hasta 93 bits, superiores al entero SQLite y al número exacto JavaScript.

## Goals / Non-Goals

**Goals:** sustituir únicamente la lectura/selección de recepción por una decisión compacta y equivalente al dominio, conservando la confirmación actual.

**Non-Goals:** cambiar puertos, dominio, HTTP, PostgreSQL, salidas, configuración/listados de lockers, esquema, índices, dependencias o recursos remotos. No se promete resolver todo el presupuesto CPU de Workers.

## Decisions

### Una lectura coherente dentro del adaptador D1

Crear `selection.py` con un resultado tipado que contenga revisión y UUID candidato. Una única sentencia SELECT con CTE, anclada en el locker solicitado, devuelve cero filas si falta o una fila con `id`, `active`, `revision`, `has_compatible` y `candidate_id`. No se transportan celdas, dimensiones ni claves de volumen. Los metadatos y la candidata pertenecen a la misma lectura; no se separan en consultas susceptibles de intercalado.

Las compatibles son habilitadas, no retiradas y capaces de alojar los ejes ordenados del paquete. SQL calcula mínimo, máximo y eje intermedio de cada celda para conservar todas las rotaciones ortogonales. La existencia de compatibles incluye ocupadas; la candidata excluye asignaciones activas de ambos tipos. Se resuelven ausencia, inactividad, ausencia de compatibles y ocupación total en ese orden, con los errores actuales.

### Orden entero exacto sin migración

Para ejes positivos `w`, `h`, `d`, usar CTE sucesivos y aritmética SQLite entera con `B = 2^31`:

```text
p = w * h
q = (p & (B - 1)) * d
high = (p >> 31) * d + (q >> 31)
low = q & (B - 1)
```

El volumen exacto es `high * B + low`. `p`, `q` y `high` son menores que `2^62`, por lo que los cálculos caben en enteros SQLite con signo. Ordenar por `high`, `low` y UUID canónico con colación BINARY equivale al volumen Python y su desempate; nunca calcular el producto triple en SQLite ni usar REAL. `high` puede superar `2^53`: permanece exclusivamente en SQL, fuera del puente JavaScript/Python.

Una columna de volumen normalizado e índice podría reducir ordenación, pero exigiría migración, mantenimiento en cada modificación y más almacenamiento/escrituras. Se descarta para este cambio: primero se elimina la transferencia masiva sin alterar datos. Las reglas SQL se verifican contra el selector del dominio, que sigue siendo la referencia.

### Conservar CAS y transacción

`custody.py` consume revisión/candidata y mantiene el batch de CAS, inserción del paquete e inserción de la asignación, con las mismas guardas. Solo un CAS con cero cambios demostrado permite releer. Se conservan tres intentos totales y 503 al agotarlos; errores o commit desconocido no se reintentan. Un intento exitoso requiere una lectura y tres sentencias del batch: cuatro consultas, como ahora; tres intentos completos suman doce.

### Verificación proporcional

En `backend/tests/unit/test_d1_selection.py`, ejecutar el SQL real contra SQLite y comparar con el dominio sobre permutaciones, empates, fronteras enteras y datos deterministas variados. En `deploy/cloudflare/tests/test_d1_repositories.py`, verificar ambos tipos, errores, 2000 celdas, una fila transferida y cuatro sentencias sin contención, aprovechando el registro existente del puente. Reutilizar las regresiones de última celda compartida, configuración concurrente, rollback, agotamiento y commit desconocido.

Preparar fuentes y comprobar frescura; la inclusión recursiva D1 ya incorpora el nuevo módulo. Ejecutar unidades afectadas, `scripts/cloudflare/check.sh --d1-only`, Ruff y ambos proyectos Pyright con cero errores/advertencias. El puente ejecuta D1 real local desde CPython, sin demostrar CPU Python Workers. No requiere modificar harnesses ni repetir descargas bloqueadas.

## Risks / Trade-offs

- Duplicación técnica del orden del dominio en SQL → pruebas diferenciales, límites máximos y regresiones de concurrencia.
- D1 aún examina/ordena celdas y consume filas leídas → no confundir una fila devuelta con una fila facturada; registrar consultas/filas al medir el despliegue.
- Coste residual de FastAPI, listas completas y creación de 1000 celdas → mantener pendiente la aceptación global Free, aunque mejore recepción. Éxitos anteriores pueden aprovechar tolerancia temporal de CPU y no prueban estar siempre bajo 10 ms.
- Red del entorno bloquea Python Workers nativo → separar evidencia SQLite/D1 local de una posterior comprobación nativa y medición remota de esta versión. No reiniciar la campaña sobre sus fixtures existentes, borrar datos ni crear recursos remotos automáticamente.

## Migration Plan

No hay migración de datos. Tras aprobación, implementar y verificar localmente; una publicación posterior autorizada sustituye solo código compatible con el esquema actual. Se puede revertir ese código preservando D1. Antes de declarar viabilidad Free, medir recepciones asignadas de ambos tipos contra 2000 celdas y completar los demás casos obligatorios; este cambio por sí solo no cierra esa aceptación.
