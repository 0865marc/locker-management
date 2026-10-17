# Tasks

Implementar únicamente tras aprobar este plan. El coordinador mantendrá las casillas y gestionará sincronización/archivo; cada tarea exige su evidencia, no solo documentación.

## 1. Base actual y comprobación local

- [x] 1.1 Preparar una base que incluya `main` inspeccionado en `1b8c4f0afbeb27063c0174be4f211f79ca4110e3`, conservando el nuevo plan; comprobar que los deltas asíncronos vigentes incluyen perfiles fijos, renombrado del requisito de tarifas y escenarios de identidad, y validar estrictamente ambos cambios existentes antes de sincronizar.
- [x] 1.2 Crear `scripts/ci/check-openspec-closed.sh` y verificar con `bash -n` y árboles temporales: éxito con directorio vacío o solo archive/archivos auxiliares; fallo ante propuestas, tareas incompletas, tareas completas sin archivar, carpetas ocultas/enlaces a directorios y directorio ausente o ilegible. Comprobar todos los nombres en el diagnóstico, ejecución desde otro directorio y ausencia de mutaciones; registrar los resultados sin añadir una suite permanente innecesaria.

## 2. GitHub Actions y documentación

- [x] 2.1 Añadir `.github/workflows/openspec-ci.yml` con el check independiente `OpenSpec closure`; verificar YAML y actionlint, eventos PR/push a `main` sin filtros de rutas, permisos, timeout, concurrencia y propagación del código del script. Confirmar que permanecen intactos los cinco jobs y nombres de `backend-ci.yml`.
- [x] 2.2 Documentar en README la política, el comando local, completar/validar/sincronizar/archivar antes de merge y el check requerido en protección de rama; ejecutar el comando documentado y comprobar que identifica los cambios todavía activos sin moverlos ni cambiar casillas.

## 3. Sincronización y verificación integrada

- [x] 3.1 Sincronizar los deltas actuales de `add-asynchronous-shipping-quotations` y `add-backend-ci` en las seis specs descritas en el diseño; verificar requisitos/escenarios preservados, identidad actual y perfiles fijos, y validar `openspec validate --specs --strict`. Si el límite de longitud lo exige, condensar las dos descripciones identificadas sin perder obligaciones, fórmulas ni escenarios.
- [x] 3.2 Ejecutar desde `backend/` `uv run --extra dev pyright --project .. --warnings` y exigir cero errores y cero advertencias; ejecutar `openspec validate enforce-openspec-closure-in-ci --strict` y `git diff --check`, registrar resultados y confirmar que no se alteraron aplicación, dependencias, migraciones ni el workflow del backend.
- [x] 3.3 Obtener revisión independiente de `sdd_reviewer` sobre escenarios, workflow/script, documentación y sincronización; corregir los hallazgos y repetir solo verificaciones afectadas antes de declarar completas las tareas de implementación.

## Workflow follow-up

- El coordinador archivará los dos cambios previos después de verificar su sincronización, preservando tareas y evidencia. Si ya se sincronizaron explícitamente, usar `--skip-specs` para no reaplicar deltas; comprobar las rutas fechadas y no sobrescribir archivos existentes.
- Con implementación y revisión verificadas, sincronizar `openspec-closure`, validar las specs y archivar `enforce-openspec-closure-in-ci`. No marcar la implementación completa anticipadamente para eludir el checker.
- Sobre el resultado archivado, ejecutar el script local, `openspec validate --specs --strict`, `openspec list --json` y `git diff --check`: deben pasar y no quedar cambios activos. Registrar por separado implementación, sincronización y archivo.
- La ejecución real de Actions y la protección de rama se comprobarán cuando se publique el cambio; este trabajo no configura protección remota ni implica commit/push autorizado.

## Evidencia de implementación (2026-10-16)

- Plan aprobado por el usuario antes de implementar. Base actualizada por fast-forward a `1b8c4f0afbeb27063c0174be4f211f79ca4110e3`; trabajo local en `ci/require-openspec-closure`. Ambos cambios previos pasaron validación estricta antes de sincronizar (12/12 y 8/8 tareas).
- `sdd_builder`: 10 comprobaciones temporales de aceptación correctas, incluyendo directorios ocultos/enlaces, propuestas/tareas incompletas/completas, ausencia/ilegibilidad y ejecución desde otro directorio; snapshots sin mutaciones. Evidencia reproducible temporal: `/tmp/verify-openspec-closure.py`.
- `bash -n scripts/ci/check-openspec-closed.sh`, `actionlint` 1.7.11 y aserciones de eventos/permisos/concurrencia/timeout del YAML: correctos. El comando documentado devuelve 1 y enumera los tres cambios activos antes del cierre, sin modificar sus artefactos.
- Desde `backend/`, `UV_CACHE_DIR=/tmp/locker-openspec-uv-cache uv run --extra dev pyright --project .. --warnings`: 0 errores, 0 advertencias y 0 informaciones, exit 0. No se requieren servicios para estos cambios de CI/documentación; no se reejecutaron las suites PostgreSQL/RabbitMQ ni Docker.
- Se sincronizaron seis capacidades previas; 27 requisitos incorporados o actualizados conservan escenarios, propósito y bloques ajenos. Las dos descripciones largas identificadas se condensaron sin alterar obligaciones ni fórmulas. `openspec validate --specs --strict`: 10 correctas, 0 fallos. Comparación de contenido registrada en `/tmp/openspec-closure-sync-verification.log`.
- `openspec validate enforce-openspec-closure-in-ci --strict` y `git diff --check`: correctos. `git diff --exit-code HEAD -- backend .github/workflows/backend-ci.yml pyrightconfig.json`: sin diferencias.
- Revisión independiente de `sdd_reviewer`: sin hallazgos accionables. Repitió los 10 escenarios, sintaxis shell, actionlint, Pyright (0 errores/advertencias), validación estricta y comparación de las seis specs/27 requisitos. No faltan pruebas relevantes para este alcance. La validación local no constituye ejecución remota de Actions.

## Evidencia de cierre (2026-10-16)

- Sincronizada también `openspec-closure`: propósito y cinco requisitos conservados íntegramente. Las 11 specs principales pasan `openspec validate --specs --strict`.
- Archivados `add-asynchronous-shipping-quotations`, `add-backend-ci` y `enforce-openspec-closure-in-ci` con fecha 2026-10-16, después de validar la sincronización y completar todas las tareas. Se usó `archive --skip-specs --yes --json` para no reaplicar los deltas ya incorporados, manteniendo la validación del archivo.
- Verificados los archivos trasladados mediante SHA-256: 9, 5 y 5 archivos respectivamente, idénticos antes y después del movimiento. Esta evidencia de cierre se añadió posteriormente al seguimiento de este cambio; los dos cambios históricos permanecen intactos.
- Resultado final: `scripts/ci/check-openspec-closed.sh` pasa; `openspec list --json` devuelve `changes: []`; validación estricta de las 11 specs y `git diff --check` correctos.
- Cambios preparados localmente en `ci/require-openspec-closure`; sin commit ni push. La ejecución remota de Actions y la configuración del check requerido en la protección de `main` quedan para la publicación.
