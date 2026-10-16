# Design

## Context

Véase la motivación en `proposal.md`. La búsqueda en `backend/adapters/http/` encuentra un único helper `invoke()` y ocho llamadas, todas en `lockers/routes.py`. Deliveries y returns ya usan capturas explícitas y necesitan excepciones propias para sus salidas de custodia. Ambos importan `capacity_http()` desde las rutas de lockers.

Se incluye este diseño para resolver antes de implementar la frontera de evaluación de argumentos y de captura de excepciones. Las especificaciones vigentes de locker-management, delivery-management y return-management no cambian.

## Goals / Non-Goals

**Goals:** mostrar la traducción de errores en cada endpoint de lockers y conservar exactamente sus resultados, excepciones traducidas y errores propagados.

**Non-Goals:** no crear un manejador universal ni nuevas jerarquías de errores; no ampliar las capturas de otros endpoints ni modificar la validación o la lógica de negocio.

## Decisions

1. **Capturas locales equivalentes en los ocho endpoints.** Cada uno conserva, en ese orden, `LockerNotFoundError` a 404 con `detail=str(error)`, `CapacityConflictError` mediante el `capacity_http()` existente a 409 con `detail={code, message}`, y `ValueError` a 422 con `detail=str(error)`. Todos los `raise` conservan `from error`. El orden importa porque `CapacityConflictError` hereda de `ValueError`. Mantener un helper local seguiría siendo válido, pero conservaría la diferencia de estilo que se quiere resolver; un helper universal introduciría mapeos ajenos a cada funcionalidad.

2. **Conservar la frontera exacta de captura.** Actualmente, tanto las conversiones `.domain()`/`Dimensions(...)` como la llamada que crea la corrutina se evalúan antes de entrar en `invoke()`. La opción mínima es guardar esa operación en una variable local antes del `try` y ejecutar únicamente `await operation` dentro. Así, cualquier error previo continúa propagándose y los errores al esperar el servicio se traducen igual. No introducir callbacks, decoradores o gestores de contexto. En `retire`, construir y devolver `Response(status_code=204)` después del bloque de captura, como ahora.

3. **Conservar la separación hexagonal.** La conversión a `HTTPException` sigue en el adaptador HTTP. Los servicios y el dominio no conocen FastAPI. `capacity_http()` conserva implementación y ubicación para no cambiar los imports de deliveries/returns. Se eliminan únicamente `invoke`, `T`, `TypeVar` y `Awaitable` cuando dejen de usarse; los demás helpers, decoradores, modelos y firmas permanecen iguales.

### Escenarios de aceptación

| Escenario | Resultado que debe conservarse |
| --- | --- |
| Crear locker o añadir compartimentos válidos | 201 y la misma configuración completa, tras persistir. |
| Listar, consultar por UUID, consultar disponibilidad, actualizar locker o actualizar compartimento | 200 con el mismo esquema y valores de respuesta; se delega una vez en el mismo método del servicio. |
| Retirar un compartimento libre | 204 sin cuerpo; se espera la operación antes de responder. |
| El servicio lanza `LockerNotFoundError` | 404 con `{"detail": str(error)}` y causa original conservada. |
| El servicio lanza `CapacityConflictError`, incluida una celda ocupada | 409 con `{"detail": {"code": error.code, "message": str(error)}}`; no deriva a 422. |
| El servicio lanza otro `ValueError` | 422 con `{"detail": str(error)}`. La validación previa de FastAPI/Pydantic mantiene sus respuestas actuales. |
| Se produce una excepción no contemplada al esperar el servicio | Se propaga; no se transforma en un error de entrada ni en una respuesta de éxito. |
| Falla la evaluación de un argumento o la creación de la operación antes del `await` | Sigue fuera de las capturas añadidas; no se amplía el conjunto de errores traducidos. |
| Se crean o finalizan deliveries/returns | Sus códigos, cuerpos y mapeos particulares de 404/409/422 siguen iguales. |

### Verificación

- Validación documental desde la raíz: `openspec validate standardize-http-error-handling --strict`.
- Desde `backend/`: `uv run --extra dev pyright --project .. --warnings`, con **cero errores y cero advertencias**, sin modificar configuración ni suprimir diagnósticos.
- Desde `backend/`: `uv run --extra dev python -m unittest discover -s tests -v`, con `TEST_DATABASE_URL` apuntando explícitamente a una base PostgreSQL dedicada mediante `postgresql+asyncpg` y permisos para crear/eliminar los esquemas aislados que preparan las pruebas. Seguir los prerrequisitos de `README.md`; no utilizar la base de demostración o producción. Preparar una base de pruebas dedicada en el entorno local cuando sea viable, sin modificar archivos del proyecto.
- La suite existente `tests/integration/test_locker_http.py` recorre las ocho rutas, validación, identidades, ocupación, geografía y custodia compartida. `tests/unit/test_http.py` comprueba los mapeos y propagación de fallos de deliveries/returns. Se reutiliza esta cobertura; no se añaden pruebas que reproduzcan la estructura de la refactorización.
- Si PostgreSQL no está disponible, ejecutar al menos `uv run --extra dev python -m unittest discover -s tests/unit -t . -v` y documentar el bloqueo real de integración. No informar como verificación completa ni como pruebas omitidas deliberadamente: la suite falla por falta de prerrequisitos. Al planificar, `TEST_DATABASE_URL` aún no está configurada.
- El revisor independiente comprueba los ocho bloques, orden de excepciones, payloads, propagación, frontera del `try`, respuesta 204 y diff limitado. Estas comprobaciones complementan las pruebas existentes; no sustituyen el comando de Pyright.

## Risks / Trade-offs

- Repetir los mismos bloques aumenta líneas y mantenimiento futuro → mantenerlos pequeños y revisar equivalencia en los ocho endpoints.
- Mover conversiones dentro del `try` ampliaría la traducción de errores → construir la operación antes del bloque.
- Capturar `ValueError` puede clasificar como entrada inválida un fallo interno de ese tipo → conservar la política actual para que esta refactorización no cambie el contrato; revisar la taxonomía de errores sería otro cambio.
- La integración requiere PostgreSQL y una base dedicada → preparar el entorno durante implementación o informar con precisión del impedimento.

## Migration Plan

Tras la aprobación explícita del plan, el coordinador crea la rama nueva `refactor/explicit-http-error-handling`; `sdd_builder` implementa el único archivo previsto y ejecuta verificaciones; `sdd_reviewer` revisa de forma independiente y el builder corrige hallazgos dentro del alcance. Después, el coordinador registra la evidencia, crea el commit y publica la rama en `origin`, comprobando su referencia remota. No se requiere PR, merge ni despliegue. No hay migración de datos; una reversión del commit restaura la implementación previa. La sincronización y el archivado necesitan autorización separada.
