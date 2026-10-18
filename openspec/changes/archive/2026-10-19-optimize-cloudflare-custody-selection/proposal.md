# Proposal

## Why

La campaña remota recibió un 503 durante una recepción y Cloudflare registró un exceso de CPU en ese intervalo; las últimas entregas persistidas apuntan a la siguiente recepción en el locker de 2000 celdas. Actualmente D1 transfiere y reconstruye todas sus celdas para elegir una: evitar ese trabajo aborda un coste concreto, sin afirmar todavía que explique todo el consumo ni que baste para cumplir Free.

## What Changes

- Seleccionar en D1 una candidata y transferir una sola fila de decisión por intento, tanto para entregas como para devoluciones.
- Conservar rotaciones, volumen entero exacto hasta las dimensiones máximas, desempate por UUID, precedencia de errores y confirmación atómica con el control de concurrencia actual.
- Añadir comprobaciones contra el selector del dominio y regresiones sobre D1 local, incluido un locker de 2000 celdas.
- Mantener API, listas completas, límites públicos, PostgreSQL, esquema, dependencias y despliegue. La aceptación Python Workers/Free de esta optimización requiere mediciones posteriores.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `record-persistence`: acotar la transferencia de datos necesaria para seleccionar capacidad en una recepción D1, preservando los contratos existentes.

## Impact

Nuevo `backend/adapters/database/d1/selection.py` e integración en `custody.py`; pruebas en `backend/tests/unit/test_d1_selection.py` y `deploy/cloudflare/tests/test_d1_repositories.py`. La preparación existente incluye automáticamente el nuevo módulo. No requiere migraciones, nuevos recursos remotos ni cambios en los harnesses o la configuración.
