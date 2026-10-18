# Tasks

## 1. Menú móvil accesible

- [x] 1.1 Añadir el control persistente, estado plegado inicial y estilos con límite total de 60dvh en `LockerExplorer.astro`, `global.css` y `locker-map.ts`; compactar moderadamente textos no editables y espacios solo en móvil, conservando inputs a 16 px, legibilidad, foco y áreas táctiles. Incorporar en `explorer.spec.ts` casos de inicio, toque/teclado, Escape, foco oculto, scroll y cambio de breakpoint a 320×568, 375×480 y 667×375, verificando mapa/zoom/atribución accesibles, densidad y legibilidad en capturas y escritorio a 1280×800 sin cambios.
- [x] 1.2 Conservar campos, UUIDs seleccionados, modo, seguimiento y comparación al plegar; mantener indicación compacta de estados excepcionales. Verificar con casos E2E de cerrar/reabrir, reintento de carga, selección geográfica y respuesta pendiente sin reapertura ni solicitudes adicionales; preservar el helper `openPanel()` mediante el skip-link.

## 2. Resultados, popups y encuadre

- [x] 2.1 Coordinar menú/resultados en `locker-map.ts` sin cancelar cotización al plegar el menú; comprobar en E2E envío y polling hasta completar, cierre/Escape con foco visible en comparar y reapertura/continuación sin POST duplicado ni reanudación automática.
- [x] 2.2 Ajustar los cálculos de posición, área de ruta y popup a los controles visibles; abrir menú antes del foco en X y plegarlo al inspeccionar. Corregir el hallazgo P2 con resultados móviles abiertos: reservar espacio real para popup/pin y un botón de rol completo, adaptando temporalmente resultados sin perder título/cierre, datos ni polling y restaurándolos al cerrar popup. Verificar en E2E a 375×480 y 667×375 acciones completas por scroll/toque/teclado, pin sin solapamiento, continuidad de polling y restauración; mantener las comprobaciones de geografía/rutas, coordenadas, foco, atribución y navegación manual.

## 3. Verificación integrada y revisión

- [x] 3.1 Revalidar tras corregir P2: ejecutar desde `frontend/` `npm run check`, `npm test`, `npm run build` y `npm run test:e2e` con los prerrequisitos del README; registrar resultados y cualquier comprobación no disponible, incluyendo capturas móviles con popup y resultados abiertos para revisión visual.
- [x] 3.2 Ejecutar desde `backend/` `uv run --extra dev pyright --project .. --warnings`, exigiendo cero errores y cero avisos; ejecutar `openspec validate compact-mobile-map-menu --strict` y entregar la corrección y sus evidencias al agente revisor para verificar el cierre del P2 antes de declarar implementación completa.
