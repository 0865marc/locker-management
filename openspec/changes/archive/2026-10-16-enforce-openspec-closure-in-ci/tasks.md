# Tasks

Las tareas 1–3 y la evidencia del 2026-10-16 conservan la implementación inicial. La sección 4 recoge la corrección explícita del usuario del 2026-10-17 para la PR #7. El coordinador mantendrá las casillas y gestionará sincronización/archivo; cada tarea exige su evidencia, no solo documentación.

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

## 4. Corrección solicitada: ejecutar únicamente en PR a main

- [x] 4.1 Retirar `push` de `.github/workflows/openspec-ci.yml` y ajustar README para explicar `pull_request` hacia `main` y su actualización por `synchronize`; verificar el diff y que no se modifican el checker, los cinco checks del backend ni hooks locales.
- [x] 4.2 Ejecutar actionlint y comprobar en el YAML la matriz de eventos: PR abierta/reabierta/actualizada hacia `main` ejecuta; PR a otra base, commit local y push sin PR —incluidos rama nueva y push directo a `main`— no ejecutan; push a una rama con PR abierta hacia `main` ejecuta por `synchronize`. Registrar evidencia de configuración y distinguirla de ejecución remota.
- [x] 4.3 Ejecutar desde `backend/` `uv run --extra dev pyright --project .. --warnings` con cero errores y cero advertencias, validar `openspec validate 2026-10-16-enforce-openspec-closure-in-ci --strict` y `git diff --check`, y obtener revisión independiente de `sdd_reviewer`; registrar resultados y resolver hallazgos antes de completar la corrección.

## Workflow follow-up

- Corrección del 2026-10-17 en la PR #7: una vez verificadas las tareas 4.1–4.3, sincronizar el requisito actualizado y su propósito en `openspec/specs/openspec-closure/spec.md`, validar las specs y rearchivar este cambio en `archive/2026-10-16-enforce-openspec-closure-in-ci`. Comprobar el checker y la ausencia de cambios activos antes de actualizar la PR; conservar intactos los otros dos cambios históricos.
- Sobre el resultado archivado, ejecutar el script local, `openspec validate --specs --strict`, `openspec list --json` y `git diff --check`: deben pasar y no quedar cambios activos. Registrar la ejecución real de Actions al actualizar la PR separadamente de las comprobaciones locales.

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

## Corrección solicitada para la PR #7 (2026-10-17)

- El usuario limitó explícitamente la comprobación a PR: retirado únicamente el evento `push` de OpenSpec CI. Se mantienen `pull_request` a `main` y sus tipos predeterminados `opened`, `reopened`, `synchronize`; commits locales y pushes independientes no ejecutan el check. README y contratos actualizados con esa distinción.
- `actionlint` 1.7.11 y 9 casos de configuración de eventos correctos; no se presentan como ejecuciones remotas. Checker, cinco checks backend, aplicación y configuración de tipos intactos.
- Desde `backend/`, `UV_CACHE_DIR=/tmp/locker-openspec-uv-cache uv run --extra dev pyright --project .. --warnings`: 0 errores, 0 advertencias, 0 informaciones, exit 0. Evidencia: `/tmp/openspec-pr-only-pyright.log`. Validación estricta del cambio y `git diff --check` correctos.
- Revisión independiente de `sdd_reviewer`: sin hallazgos accionables ni pruebas relevantes pendientes. Sincronizados propósito y requisito de eventos de la spec principal conforme a esta corrección; los otros cuatro requisitos permanecen idénticos.
- Cierre de la corrección: 10/10 tareas completas, 11 specs válidas; rearchivado con validación en la misma ruta mediante `--skip-specs`, tras sincronización explícita. El checker final pasa y `openspec list --json` devuelve `changes: []`. Los otros dos cambios archivados permanecen intactos.
