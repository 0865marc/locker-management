# Tasks

## 1. Reubicar el proyecto Python

- [x] 1.1 Mover `main.py`, `domain/`, `application/`, `adapters/`, `tests/`, `pyproject.toml`, `alembic.ini`, `Dockerfile` y `.dockerignore` a `backend/`; verificar el inventario y todos los SHA-256 contra la referencia previa, la ausencia de los originales en la raíz y la conservación de los archivos generales y la `.venv` existente.
- [x] 1.2 Actualizar en README el árbol, las referencias a archivos y los directorios de trabajo de instalación, Alembic, adopción de esquema y pruebas; verificar que las rutas documentadas existen y que cada comando local identifica correctamente `backend/` como directorio del proyecto Python.
- [x] 1.3 Ejecutar desde `backend/` la suite existente con `uv run --extra dev python -m unittest discover -s tests -v`, o con un entorno equivalente preparado a partir del mismo `pyproject.toml` si el entorno local lo requiere; comprobar imports y migraciones y registrar los resultados y cualquier omisión de PostgreSQL sin modificar código ni dependencias.

## 2. Adaptar Docker Compose

- [x] 2.1 Cambiar únicamente los contextos de construcción de `api` y `migrate` a `./backend` y aclarar en README que Compose se ejecuta desde la raíz; verificar con `docker compose config` que todos los demás valores de servicios y volumen coinciden con la configuración previa.

## 3. Verificación integrada y revisión

- [x] 3.1 Construir y arrancar la composición con PostgreSQL en un proyecto de verificación aislado, comprobar salud de `db`, salida correcta de `migrate` y disponibilidad de la API; ejecutar la suite con `TEST_DATABASE_URL` en el contenedor para verificar creación, validaciones, listado y persistencia. Conservar recursos ajenos, no eliminar volúmenes existentes y registrar separadamente cualquier bloqueo que impida verificar este escenario.
- [x] 3.2 Obtener revisión independiente de los escenarios del diseño, preservación de archivos y límites de arquitectura; resolver los hallazgos aplicables y ejecutar `openspec validate move-backend-into-directory --strict`, dejando evidencia de revisión y verificación antes de marcar esta tarea como completada.

## Workflow follow-up

- La sincronización y el archivado no están solicitados; este cambio permanece activo al terminar la implementación y la revisión.
- Una comprobación que no se haya podido ejecutar debe informarse como pendiente o limitada, no como prueba superada.

## Verification evidence

- 1.1: inventario de 26 archivos comparado con `/tmp/hexagonal-backend-before.json`; todos los SHA-256 coinciden tras el traslado. Las rutas originales ya no existen; archivos generales y `.venv` permanecen en la raíz.
- 1.2: árbol y comandos revisados; las 14 rutas `backend/...` citadas existen. Los bloques Python identifican `backend/` como directorio de trabajo y Compose se ejecuta desde la raíz.
- 1.3: desde `backend/`, `timeout 60s /tmp/hexagonal-backend-verification/bin/python -m unittest discover -s tests -v` ejecutó 10 pruebas: 9 correctas y 1 omitida por falta de `TEST_DATABASE_URL`. El entorno temporal Python 3.13 contiene las dependencias del mismo `pyproject.toml`; la ejecución requirió salir del sandbox por su bloqueo previo de TestClient. Imports y migraciones SQLite de subida, bajada y comparación con modelos correctos. `python -m alembic heads` devuelve `0001 (head)`. Advertencias existentes de dependencias; ningún archivo de backend modificado.
- 2.1: `docker compose config --format json` correcto. Comparación normalizada con la configuración previa usando el mismo directorio y nombre de proyecto: solo cambian los contextos de `api` y `migrate` a `backend/`; el resto coincide exactamente.
- 3.1: verificación del coordinador en el proyecto aislado `hexagonal-layout-check-20261014`: `docker compose -p hexagonal-layout-check-20261014 up -d --build` correcto, PostgreSQL 17 saludable, migración `0001` con salida 0 y API disponible. Suite dentro de `api` con `TEST_DATABASE_URL`: 10 pruebas correctas, ninguna omitida. HTTP: `/docs` devuelve 200; entregas y devoluciones mantienen creación 201, listado 200 y espacios vacíos 422. Tras `down` sin eliminar volúmenes y `up -d`, ambos registros creados seguían listados sin cambios (referencia en `/tmp/hexagonal-layout-persistence.json`). Limpieza limitada a los recursos nuevos del proyecto aislado; recursos preexistentes conservados.
- 3.2: revisión independiente de `sdd_reviewer` sin hallazgos accionables: preservación de los 26 archivos, configuración Compose, documentación, límites de arquitectura y evidencia integrada correctos. Dependencia `service_completed_successfully` conservada y verificada estáticamente; no se inyectó un fallo de migración. `openspec validate move-backend-into-directory --strict` correcto; `skip_specs: true` acepta cero deltas funcionales. El coordinador confirmó la limpieza completa de contenedores y volúmenes del proyecto temporal. Implementación y revisión completas; sin sincronización ni archivado solicitados.
