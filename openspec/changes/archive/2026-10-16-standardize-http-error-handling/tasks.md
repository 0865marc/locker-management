# Tasks

El coordinador mantiene este checklist y registra evidencia antes de marcar tareas completas. La implementación requiere la aprobación explícita del plan en un mensaje posterior. Las especificaciones existentes no cambian; `specs` se omite mediante `skip_specs: true`.

## 1. Preparación aprobada

- [x] 1.1 Coordinador: tras recibir aprobación del plan, crear la rama nueva `refactor/explicit-http-error-handling` desde `main` y comprobar con Git la rama activa y que no se incorporan cambios ajenos.

## 2. Refactorización y verificación

- [x] 2.1 `sdd_builder`: reemplazar las ocho llamadas de `backend/adapters/http/lockers/routes.py` por `try/except` explícitos, conservar la creación de cada operación fuera del `try` y `Response(204)` fuera del bloque, retirar `invoke` y sus tipos/imports exclusivos; verificar el diff contra los escenarios del diseño y que la búsqueda en `backend/adapters/http/` ya no encuentra `invoke`.
- [x] 2.2 `sdd_builder`: preparar PostgreSQL y una base dedicada de pruebas cuando sea viable, configurar `TEST_DATABASE_URL` según `README.md` y ejecutar desde `backend/` `uv run --extra dev python -m unittest discover -s tests -v`; registrar resultado y recuento reales. Si faltan prerrequisitos, ejecutar la suite unitaria documentada e informar del bloqueo de integración dejando pendiente esta verificación completa; no modificar pruebas ni afirmar que los controles no ejecutados han pasado.
- [x] 2.3 `sdd_builder`: ejecutar desde `backend/` `uv run --extra dev pyright --project .. --warnings` y acreditar cero errores y cero advertencias; corregir causas reales dentro del alcance y repetirlo si procede, sin debilitar la configuración compartida.

## 3. Revisión y publicación

- [x] 3.1 `sdd_reviewer`: revisar independientemente los escenarios de aceptación, arquitectura, ocho políticas de errores, frontera de captura, respuesta 204 y evidencia de pruebas/tipos; devolver hallazgos. `sdd_builder` corrige los accionables dentro del alcance y repite los controles afectados; el revisor confirma su resolución.
- [x] 3.2 Coordinador: ejecutar `openspec validate standardize-http-error-handling --strict` y `git diff --check`, verificar que solo cambian el archivo de rutas y estos artefactos, y registrar resultados sin confundir validación documental con verificación de comportamiento.
- [x] 3.3 Coordinador: después de verificar y revisar, crear el commit y publicar la rama nueva en `origin`; comprobar que su referencia remota coincide con el commit local e informar de rama, commit, verificación, revisión y cualquier pendiente. No crear un PR, fusionar, sincronizar especificaciones ni archivar este cambio.

## Evidencia de ejecución

- Plan aprobado por el usuario el 2026-10-16. Rama creada desde `main` en `19bfa9d523f84aa094007c4511f60af40d04e22b`; los artefactos de planificación estaban sin commit y se conservaron al cambiar de rama.
- `sdd_builder` modificó únicamente `backend/adapters/http/lockers/routes.py`; la búsqueda de `invoke` en los adaptadores HTTP no devuelve coincidencias.
- Desde `backend/`, con `UV_CACHE_DIR` temporal: `uv run --extra dev pyright --project .. --warnings` terminó con código 0: **0 errores, 0 advertencias, 0 informaciones**. El intento inicial sin acceso de red falló al resolver dependencias; la ejecución con permisos de red pasó sin cambiar la configuración.
- Desde `backend/`: `uv run --extra dev python -m unittest discover -s tests -v` terminó con código 0: **95 pruebas, OK, ninguna omitida**, en 17,161 segundos. `TEST_DATABASE_URL` apuntó a una base dedicada en un contenedor PostgreSQL 17 temporal, sin volúmenes y accesible solo por localhost.
- `sdd_reviewer` revisó independientemente los ocho endpoints, los escenarios y los logs: **sin hallazgos bloqueantes**. La cobertura funcional existente y la revisión del diff acreditan la equivalencia; no hay inyección individual de errores en cada endpoint para comprobar todas las causas y fronteras de captura.
- `openspec validate standardize-http-error-handling --strict` y `git diff --check` pasaron. No hay cambios de producción fuera del archivo de rutas ni cambios de configuración o pruebas.
- Implementación publicada en `origin/refactor/explicit-http-error-handling`: commit `d3e3f708e332239ddc8bb14f4a5ce7c872a47773`, verificado idéntico en local y remoto. Se utilizó el conector autenticado de GitHub porque Git local no tenía credenciales HTTPS. `main` conserva el commit de partida; no se creó PR ni se fusionó, sincronizó o archivó el cambio.
