# Proposal

## Why

El runtime entrega `batch, env, ctx` al consumidor, pero las entradas del spike y de producción solo aceptan `batch`. El log nativo confirma que esto aborta el evento antes de reconocer el mensaje; la misma incompatibilidad se reproduce en producción sin ejecutar WASM.

## What Changes

- Aceptar explícitamente los argumentos del callback en ambas entradas, conservando las llamadas abreviadas y el entorno de instancia envuelto por el SDK.
- Añadir regresiones de las dos formas de invocación, delegación, reconocimiento previo y restauración del contexto; incluir las nuevas unidades del spike antes del sync nativo.
- Verificar unidades afectadas, Ruff y ambos proyectos Pyright sin ampliar el comportamiento de las colas.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `application-runtime`: aceptar la invocación completa del evento Queues y conservar la composición y aislamiento actuales.

## Impact

`backend/entrypoints/cloudflare/api.py`, `deploy/cloudflare/runtime_spike/worker.py` y sus pruebas en `backend/tests/unit/test_cloudflare_context.py` y `deploy/cloudflare/tests/`. El ejecutor del spike solo se ajustará si hace falta incluir las nuevas unidades. No cambian dependencias, CI, mensajes, reintentos, tiempos de espera ni contratos de negocio. La evidencia nativa y Free pendiente se informa por separado.
