# Design

## Context

Ver `proposal.md`. El log del usuario muestra `workers/entrypoints.py:352` reenviando argumentos y `TypeError: Default.queue() takes 2 positional arguments but 4 were given`. La reproducción CPython de la entrada productiva confirma el mismo defecto. El test existente de delegación solo llama con un lote.

La [documentación oficial de Queues](https://developers.cloudflare.com/queues/configuration/javascript-apis/) muestra `queue(batch, env, ctx)` para la plataforma y una forma Python abreviada. La corrección admite ambas sin depender de que cambie el SDK.

## Goals / Non-Goals

**Goals:** compatibilidad de la frontera del evento conservando la composición actual.

**Non-Goals:** mover lógica, alterar mensajes, conversión del cuerpo, reconocimiento, reintentos, tiempos, versiones o workflows.

## Decisions

1. Añadir `_env: object = None, _ctx: object = None` después del lote en `backend/entrypoints/cloudflare/api.py` y `deploy/cloudflare/runtime_spike/worker.py`. Los parámetros explícitos permiten las dos formas documentada/observada sin un `*args` que oculte otras incompatibilidades.
2. Mantener `self.env`, envuelto por el SDK, como origen de los bindings. Los argumentos adicionales son opacos y no se leen ni sustituyen ese entorno. Conservar delegación, procesador reutilizado, secuencia, ack previo y `finally`/scope de limpieza existentes.
3. Invocar las entradas reales en unidades CPython con tres argumentos y con uno. Usar un entorno adicional distinto como testigo para detectar sustituciones accidentales. Verificar delegación y restauración en éxito/fallo, reconocimiento anterior al cuerpo/trabajo y ausencia de trabajo cuando ack falla. Extender las pruebas existentes y la selección previa a `pywrangler sync` si es necesario; no crear otro harness ni servicios.

## Risks / Trade-offs

- Las unidades con dobles no acreditan el runtime → informarlas como regresiones locales y repetir el smoke nativo cuando haya un entorno accesible.
- El usuario informó cuatro de cinco pruebas nativas aprobadas en `b954d83`, con Queues fallando antes del consumidor → conservar esa evidencia parcial; esta corrección no completa por sí sola Queues, el perfil productivo nativo ni Free.
- El entorno gestionado bloquea la descarga nativa con 403 → no reintentar ni cambiar dependencias para sortearlo; completar verificaciones locales y declarar el pendiente.

## Migration Plan

No requiere migración, cambios de datos ni despliegue. Verificar la corrección local y revisión independiente; la comprobación nativa posterior debe conservar los marcadores de éxito/fallo y la ausencia de reejecución del smoke existente.
