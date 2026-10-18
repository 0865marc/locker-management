# Design

## Context

La comparación con `origin/main` identifica seis archivos exclusivos en `backend/application/tracking/` y `backend/adapters/http/tracking/`, dos suites propias y su montaje en `main.py`/`adapters/http/routes.py`. No se añadieron tablas ni puertos para seguimiento: reutiliza las lecturas existentes de entregas, devoluciones y lockers. El motivo de retirada consta en la propuesta.

`frontend/tests/cors_server.py` compone la aplicación real con repositorios falsos; algunos E2E dependen del endpoint que desaparece. Conservar esos casos sin ajustarlos dejaría la suite incoherente aunque el cliente permanezca intacto.

## Goals / Non-Goals

**Goals:** retirada completa del servicio añadido, ausencia observable de la ruta y pruebas/documentación coherentes con un cliente conservado pero sin backend de seguimiento.

**Non-Goals:** modificar `frontend/src`, crear una ruta sustituta, alterar custodia o datos, modificar CORS/cotizaciones o revertir indiscriminadamente otros cambios de la rama. `tracking_number` pertenece al negocio previo y se conserva.

## Decisions

1. **Retirada selectiva de capas.** Eliminar ambos paquetes exclusivos, importaciones, construcción, `app.state.tracking_service`, parámetro y registro de router. Mantener los servicios/repositorios previos y CORS. No restaurar `main.py` íntegramente desde `origin/main`, pues eliminaría cambios ajenos. No dejar una ruta 410 ni un servicio vacío: una URL retirada responde 404, incluso para un identificador mal formado, y no existe en OpenAPI.
2. **Pruebas que distinguen ausencia real de contrato del cliente.** Eliminar las dos suites exclusivas del backend y añadir una regresión compacta a `backend/tests/unit/test_main.py` que compruebe ruta/esquemas ausentes y 404, usando la composición real con infraestructura falsa. Sustituir los dos E2E de seguimiento con CORS real por ausencia 404 observable desde el navegador y recuperación hacia cotización. Mantener los casos de cliente ya interceptados; los casos de ciclo de vida que precisen una respuesta válida usarán `page.route` y el fixture `tracked` existente, explícitamente como pruebas del cliente. Limpiar los fixtures exclusivos de entregas/devoluciones en `cors_server.py`; no registrar allí otro endpoint de seguimiento. La API de lockers/cotizaciones y CORS siguen siendo reales en ese servidor.
3. **Documentación y especificación vigentes.** README indicará que la pestaña está conservada, el backend no publica seguimiento y sus intentos reciben 404; no presentará el antiguo contrato como API disponible. El delta retira cuatro requisitos, añade la ausencia del endpoint y condiciona los dos de cliente a respuestas compatibles. `locker-map` conserva su comportamiento de interfaz, cuyos escenarios de seguimiento exitoso solo aplican con esa integración. El historial archivado permanece intacto.

## Risks / Trade-offs

- [El 404 de ruta inexistente se muestra como paquete no encontrado] → Es la limitación aceptada al conservar el frontend sin cambios; README explicará que no equivale a una búsqueda real en esta API.
- [Un test simulado podría aparentar integración de seguimiento real] → Los E2E de ausencia usan la API real sin interceptar tracking; los de respuestas válidas se identifican como pruebas del cliente mediante interceptación explícita.
- [Una retirada amplia afectaría funcionalidades anteriores] → Contrastar el diff con `origin/main` y ejecutar regresiones de composición, HTTP, CORS y cotizaciones, además de comprobar que no cambian dominio, puertos ni persistencia.

## Migration Plan

No hay migración de datos ni cambio de configuración. Desplegar la API actualizada deja la ruta ausente; una reversión de código podría restaurarla sin transformar datos. En una futura sincronización autorizada, aplicar este delta y reemplazar únicamente el Purpose de `openspec/specs/parcel-tracking/spec.md` por:

> Preserve the existing parcel-tracking browser interface as a pending integration, including cancellation, error handling and conditional map presentation, without providing a tracking endpoint in this backend.

El Purpose existente no se actualiza automáticamente mediante un delta; ese ajuste queda documentado para el coordinador al sincronizar. Esta fase solo crea los artefactos del cambio, sin modificar bases ni el archivo anterior.
