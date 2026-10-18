# Design

## Context

Ver `proposal.md`. `LockerExplorer.astro` monta siempre `#map-panels`; `global.css:438` conserva en móvil casi toda la altura (`100% - 44px`). `locker-map.ts` calcula posiciones y rutas desde el borde derecho de ese menú, dejando una franja estrecha. Sus flujos de resultados y foco ya están centralizados. `tracking.leave()` borra resultados; `shipping.close()` detiene espera local pero conserva una referencia conocida. Ninguno debe usarse para un mero plegado.

## Goals / Non-Goals

**Goals:** añadir un estado de presentación móvil independiente del modo y reutilizar el DOM y las integraciones existentes.

**Non-Goals:** rediseñar escritorio, duplicar formularios, añadir un framework, cambiar APIs o habilitar seguimiento en backend. No se modifican capas de dominio/aplicación ni persistencia.

## Decisions

1. **Un control persistente y contenido plegable.** Añadir en `LockerExplorer.astro` un botón móvil con `aria-controls` y `aria-expanded`, rotulado «Abrir menú»/«Volver al mapa». Conservar los nodos de campos y resultados; ocultar e inertizar solo el contenido plegable. El botón tendrá al menos 44 px de altura y quedará fuera del área desplazable. Añadir indicación compacta de carga, vacío/error o cartografía cuando corresponda, con acceso al detalle/reintento del menú. Reducir solo tipografía o padding no resuelve la ocupación inicial.

2. **Presupuesto de pantalla.** Mantener el breakpoint de 760 px. Con CSS limitar el conjunto expandido, botón incluido, a `60dvh`, con fallback en `vh`, margen superior y desplazamiento interno. Reservar el lateral de zoom y la atribución inferior. Resultados conservan normalmente su panel inferior de aproximadamente media pantalla, adaptándolo temporalmente durante la inspección móvil según la decisión 5. No usar un diálogo modal ni bloquear el mapa con un fondo opaco. Mantener estilos de escritorio.

3. **Estado y foco en `locker-map.ts`.** Recordar el estado móvil, inicialmente plegado, y resolver cambios de breakpoint sin desmontar controles ni perder foco. Abrir con toque/Enter/Espacio; cerrar con botón o Escape no consumido por sugerencias, devolviendo foco al botón. Antes de ocultar, cerrar las sugerencias mediante sus métodos actuales. El skip-link abre cotización antes de su foco habitual. Inspeccionar un marcador pliega el menú; elegir rol lo abre antes de `select()`, conservando foco y desplazamiento hacia su X. Plegar no llama a `setMode`, `tracking.leave`, `shipping.close` ni invalida entradas/resultados; una respuesta pendiente no abre el menú.

4. **Un panel grande cada vez.** `setResultsOpen(true)` pliega el menú sin cancelar envío/polling y conserva foco en el título de resultados. Abrir el menú desde resultados usa el cierre existente sin reenviar ni reanudar automáticamente; conserva ofertas/referencia como hoy. Close/Escape de resultados abre el menú antes de devolver foco a comparar. Adaptar también `hideResults` para no dejar foco oculto tras invalidaciones. En escritorio se mantiene la coexistencia actual.

5. **Geometría según los controles visibles.** Ajustar en `locker-map.ts` el cálculo usado por `revealPosition`, la función de área de `setupLockerRoute` y el encuadre del popup. En móvil usar el ancho útil debajo del menú expandido; con resultados, usar la región superior disponible; plegado, medir solo el control compacto. No seguir usando el borde derecho de un menú invisible. Limitar altura desplazable de popups a su región disponible y mantener icono, acciones y separación. Cancelar correcciones de cámara obsoletas tras cambios de panel; no añadir encuadre continuo que anule navegación manual. Reutilizar los módulos de ruta/cámara sin cambiar su contrato.

   Con resultados abiertos durante una inspección móvil, mostrar temporalmente solo su cabecera con título y cierre. Activar este estado antes de medir/encuadrar el popup; conservar el cuerpo de resultados montado pero oculto y no interactivo. Reservar la altura real de pin, separación, contenedor y al menos un botón de rol completo dentro del scroll; un mínimo fijo de 40 px no basta para botones de 48 px. Cada acción debe poder verse completa al desplazar o enfocar. No cerrar resultados ni llamar a `shipping.close`: conservar datos, referencia y polling. En `popupclose`, restaurar cuerpo y altura normal; al redimensionar, recalcular esta coordinación. Esto libera espacio sin depender de otro porcentaje rígido.

6. **Densidad móvil moderada.** En las reglas móviles de `global.css`, reducir padding, gaps y márgenes del menú y ajustar ligeramente títulos y textos no editables que admitan reducción; no reducir textos ya pequeños. Conservar campos editables a 16 px para evitar zoom de iOS, el foco visible y las áreas táctiles actuales, incluido el botón de menú de al menos 44 px. Verificar la legibilidad mediante las capturas móviles y la interacción existente; no aplicar estos ajustes a escritorio.

## Risks / Trade-offs

- Más desplazamiento para rellenar el formulario → el control de regreso permanece fijo; comprobar campos, listas y X con teclado y toque en pantallas cortas.
- Foco o geometría calculados antes de revelar contenido → revelar primero, medir después y verificar puntos reales con hit-testing, sin cambiar coordenadas.
- Nuevos estados visuales frente a pruebas que asumen menú visible → conservar `openPanel()` mediante el skip-link y abrir explícitamente donde corresponda; probar el inicio plegado por separado.

## Verification

Ampliar `frontend/tests/e2e/explorer.spec.ts` con inicio plegado, abrir/cerrar por toque y teclado, conservación de datos/seguimiento y comparación, respuesta tardía sin reapertura, scroll y geometría a 320×568, 375×480 y 667×375; mantener regresión de escritorio a 1280×800 y cambio de breakpoint. Reutilizar fixtures y casos existentes de popups, rutas, geografía y cotización; el seguimiento exitoso usa respuestas simuladas y el backend real conserva 404.

En 375×480 y 667×375, inspeccionar con resultados abiertos pendientes y completados: medir que cada botón de rol pueda quedar completo dentro del scroll y recibir toque/foco, que el pin no invada resultados y que título/cierre sigan accesibles; comprobar continuidad de polling, conservación de ofertas y restauración del panel al cerrar el popup.

Tras implementar: desde `frontend/`, `npm run check`, `npm test`, `npm run build` y `npm run test:e2e` (Node 24, Chromium y `backend/.venv`, según README). Desde `backend/`, ejecutar obligatoriamente `uv run --extra dev pyright --project .. --warnings` con cero errores y avisos. Validar artefactos con `openspec validate compact-mobile-map-menu --strict`. En esta fase solo se valida el plan, sin afirmar comprobación de navegador.

## Migration Plan

Publicar el build estático por el proceso habitual tras aprobación, implementación y revisión; sin migración de datos ni variables nuevas. La reversión consiste en restaurar el build anterior.
