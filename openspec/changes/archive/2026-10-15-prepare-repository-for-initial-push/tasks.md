# Tasks

Plan aprobado explícitamente por el usuario con «perfecto, adelante», incluida la exclusión completa de `.vscode/`. Las únicas ediciones de configuración previstas son `.gitignore` y `backend/pyproject.toml`; la evidencia se registra aquí, sin crear otra guía ni alterar el índice Git.

## 1. Exclusiones del repositorio

- [x] 1.1 Completar `.gitignore` con los patrones y excepciones de `design.md`; verificar mediante `git check-ignore --no-index` que toda `.vscode/`, incluidos `settings.json` y `local.json`, queda ignorada y que `.env.example`, `backend/uv.lock` y el flujo OpenSpec siguen elegibles, junto con los demás escenarios previstos. Conservar intacta la configuración local del editor.

## 2. Configuración de construcción

- [x] 2.1 Restaurar únicamente `build-backend = "setuptools.build_meta"` en `[build-system]`; comprobar el TOML, ejecutar desde `backend/` `uv sync --locked --extra dev --reinstall-package hexagonal-fastapi` y verificar que `uv.lock` no cambia. Ejecutar después la suite documentada con límite de 60 segundos, teniendo en cuenta la restricción del sandbox observada, y registrar resultados reales y omisiones; las correcciones funcionales ajenas a esta configuración requieren revisión del alcance.

## 3. Inventario y propuesta de commits

- [x] 3.1 Revisar `git ls-files --others --exclude-standard` y `git add --dry-run --all`; confirmar que no aparecen artefactos generados ni credenciales privadas conocidas y que cada candidato pertenece a uno de los tres grupos de `design.md`. Entregar la propuesta de títulos y rutas, y comprobar que índice, HEAD y remotos permanecen sin cambios.

## 4. Revisión integrada

- [x] 4.1 Obtener la revisión independiente de los dos archivos, los escenarios y la evidencia; resolver hallazgos dentro del alcance aprobado y ejecutar `openspec validate prepare-repository-for-initial-push --strict`. Registrar por separado cualquier comprobación no completada antes de declarar el estado final.

## Workflow follow-up

- Los commits propuestos, el remoto y el push se ejecutarán solamente si el usuario los solicita posteriormente.
- No hay deltas que sincronizar. El cierre de este change se gestiona por separado cuando esté implementado y revisado y el usuario autorice archivarlo.

## Evidencia de implementación (2026-10-14)

- `.gitignore` conserva las reglas previas y añade exactamente las categorías aprobadas. Matriz con `git check-ignore --no-index -q`: 26 rutas ignoradas y 18 elegibles, todas con el resultado esperado. Incluye `.vscode/settings.json`, `.vscode/local.json` y `backend/.vscode/settings.json` ignorados; `.env.example` en raíz y backend, lock, código y flujo OpenSpec elegibles. No se crearon archivos de ejemplo ni se modificó `.vscode/settings.json`; su SHA-256 coincide con el inicial.
- TOML parseado correctamente con `tomllib`; única edición de `backend/pyproject.toml`: `build-backend = "setuptools.build_meta"`. `uv sync --locked --extra dev --reinstall-package hexagonal-fastapi` terminó con código 0 y reinstaló únicamente el proyecto local. El primer intento estuvo bloqueado por la caché uv de solo lectura; la repetición mediante escalación autorizada funcionó. SHA-256 de `backend/uv.lock` idéntico antes y después.
- Suite documentada ejecutada fuera del sandbox mediante escalación autorizada, con `env -u TEST_DATABASE_URL PYTHONDONTWRITEBYTECODE=1 timeout 60s uv run --extra dev python -m unittest discover -s tests -v` (comando presentado con el nombre portable de `uv`): código 0, 10 tests en 0,269 s, 9 correctos y 1 omitido (`TEST_DATABASE_URL` ausente). Avisos observados: deprecación Starlette/httpx, deprecación Alembic `path_separator` y `ResourceWarning` de SQLite; no se ampliaron las modificaciones para corregirlos. PostgreSQL y Docker no comprobados.
- `git ls-files --others --exclude-standard`: 70 candidatos, todos asignados a los tres grupos de `design.md`: 1 archivo para `chore: configure repository ignore rules`, 29 para `feat: add hexagonal FastAPI delivery and return service` y 40 para `docs: add OpenSpec specifications and SDD workflow`. Incluye los archivos ocultos compartibles y todo el historial OpenSpec. No aparecen entornos, cachés, metadatos egg-info, `.vscode/` ni `.aws/`. La inspección de contenido elegible no encontró patrones de claves privadas, claves AWS o tokens GitHub/OpenAI; no constituye garantía exhaustiva de ausencia de secretos.
- `git add --dry-run --all`: código 0 y los mismos 70 candidatos. El sandbox impedía crear el bloqueo temporal del índice; el dry-run mediante escalación autorizada funcionó. No se hizo staging real. SHA-256 de `.git/HEAD` y `.git/config` iguales al inicial; `.git/index` sigue ausente, `git ls-files` vacío y `git remote -v` vacío. No se crearon commits ni remoto ni se hizo push.
- Revisión independiente de `sdd_reviewer` terminada sin hallazgos pendientes: 42 rutas de exclusión/elegibilidad correctas y 70 candidatos asignados a los tres commits propuestos. Se corrigió la única observación menor, una ruta personal del ejecutable en esta evidencia, usando el nombre portable `uv`; el reviewer confirmó la corrección. `openspec validate prepare-repository-for-initial-push --strict` correcto. El coordinador comparó los hashes de 71 archivos: únicamente cambiaron `.gitignore`, `backend/pyproject.toml` y este seguimiento; no se añadieron ni eliminaron archivos. Lockfile, configuración local del editor, HEAD, índice y configuración Git intactos. Implementación completa y revisada; no hay deltas que sincronizar y el change permanece sin archivar.
