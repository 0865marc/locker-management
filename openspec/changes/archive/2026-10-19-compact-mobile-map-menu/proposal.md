# Proposal

## Why

El menú móvil muestra de entrada búsqueda, selectores y formulario sobre casi toda la altura disponible: a 375×480 su caja puede ocupar 299×436 píxeles. El mapa sigue funcionando, pero queda demasiado poco espacio para utilizarlo; basta corregir la presentación móvil sin deshabilitar el frontend.

## What Changes

- En anchos de hasta 760 px, iniciar con el menú plegado y un botón visible en español para abrirlo o volver al mapa.
- Limitar el menú abierto al 60 % de la altura visible, con desplazamiento interno y controles accesibles por toque y teclado.
- Compactar moderadamente tipografías no editables y espacios del menú móvil, conservando legibilidad, foco, áreas táctiles y campos editables a 16 px.
- Conservar campos, lockers, modo y resultados al plegar; coordinar menú, comparación y popups para evitar paneles grandes superpuestos y mantener visibles los puntos del mapa.
- Mantener el menú de escritorio y los contratos actuales de búsqueda, cotización y seguimiento.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `locker-map`: presentación móvil plegable, foco accesible y convivencia con resultados y geometría del mapa.

## Impact

- Implementación prevista: `frontend/src/components/LockerExplorer.astro`, `frontend/src/styles/global.css` y `frontend/src/scripts/locker-map.ts`.
- Verificación: adaptar y ampliar casos relevantes de `frontend/tests/e2e/explorer.spec.ts`.
- Sin dependencias nuevas, cambios de API, backend o persistencia. El seguimiento conserva su integración pendiente y el 404 actual del backend.
