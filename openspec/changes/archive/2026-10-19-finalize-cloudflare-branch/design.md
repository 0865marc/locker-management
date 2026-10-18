# Design

## Context

Ver `proposal.md`. Los cuatro cambios previos tienen todas sus tareas marcadas; sus deltas añaden seis requisitos ausentes de las specs principales. Los dos deltas de `test-execution` añaden nombres distintos y no colisionan. `fix-cloudflare-acceptance-client/tasks.md` documenta la omisión deliberada del diseño condicional; se propone conservarla al archivar aunque `status` muestre ese artefacto como `ready`.

## Goals / Non-Goals

**Goals:** cerrar preservando especificaciones y evidencia escrita, retirar archivos históricos y publicar el resultado revisado en la PR existente.

**Non-Goals:** modificar comportamiento de aplicación, fronteras hexagonales, herramientas de prueba, despliegues remotos, datos o migraciones; acreditar resultados nativos/Free pendientes; fusionar la PR.

## Decisions

1. **Cambio separado sin delta.** Registrar la limpieza con `skip_specs: true` conserva la trazabilidad de los cuatro cambios terminados. No añadir tareas de limpieza a su historia ni inventar nuevos requisitos.
2. **Salida local ignorada.** Retirar los once archivos versionados y reemplazar las dieciséis excepciones específicas de logs por `/deploy/cloudflare/evidence/` y `/cloudflare/evidence/`. El harness ya crea el directorio al ejecutarse; mantenerlo evita cambiar su diagnóstico. Conservar los restantes ignores antiguos para transiciones manuales.
3. **Referencias históricas honestas.** En `FEASIBILITY.md`, explicar que los archivos retirados se consultan en el historial Git y corregir frases que los presentan como disponibles en el checkout. Conservar resultados, comandos, limitaciones y pendientes; no trasladar los logs a otro directorio versionado ni reescribir artefactos archivados.
4. **Sincronización anterior al archivo.** Incorporar los deltas con merge semántico, preservando títulos, propósitos y contenido existente. `test-execution` pasa de 15 a 19 requisitos; `application-runtime`, de 15 a 16; `record-persistence`, de 9 a 10. Verificar los seis bloques completos antes de mover ninguno de sus cambios al archivo fechado. No hay dependencia de orden entre deltas aditivos, pero un único escritor actualizará las specs y el coordinador esperará la verificación de cada sincronización.
5. **Publicación sobre la rama existente.** Commit/push normal en `codex/cloudflare-free-deployment`, reutilizando la PR abierta #10 con base `main`. Evitar una segunda PR y no hacer force push ni merge. Revisar estado remoto antes de publicar si ha cambiado durante el trabajo.

## Acceptance Scenarios

- **Cierre íntegro:** cuando termine la sincronización, los seis requisitos y sus escenarios estarán presentes junto con todo el contenido anterior; tras archivar los cinco cambios, `openspec list --json` no mostrará activos y `scripts/ci/check-openspec-closed.sh` pasará.
- **Limpieza coherente:** cuando se revise el diff, desaparecerán exactamente los once archivos de evidencia solicitados, las dos rutas estarán ignoradas y `FEASIBILITY.md` no afirmará que esos resultados históricos siguen disponibles localmente. El código del harness permanecerá intacto.
- **Verificación honesta:** el nuevo Pyright obligatorio terminará con cero errores y advertencias. Las verificaciones históricas se conservarán con su alcance; los bloqueos nativos/Free no se convertirán en éxitos por cerrar cambios administrativos.
- **Entrega en GitHub:** el commit publicado estará en la rama actual y la PR #10 seguirá abierta hacia `main`, reflejando cierre, limpieza y comprobaciones reales; no se creará otra PR ni se fusionará.

## Risks / Trade-offs

- Perder escenarios al actualizar una spec compartida → comparar los bloques completos, preservar contenido previo y validar todas las specs antes de archivar.
- Logs regenerados tras la limpieza → ignorar el directorio completo; no ejecutar el harness nativo solo para esta limpieza.
- Confundir tareas terminadas con aceptación Free → mantener las limitaciones históricas y separar verificaciones nuevas de las ya registradas.

## Migration Plan

Tras aprobación: limpieza, comprobaciones y revisión independiente; sincronización y validación; archivo de los cuatro cambios previos y de este cambio ya completado; comprobación de cierre; commit/push y actualización de la PR #10. Los archivos retirados y la historia anterior serán recuperables desde Git; no hay migración de datos ni despliegue.
