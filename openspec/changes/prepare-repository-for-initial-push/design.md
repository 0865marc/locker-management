# Design

## Context

Véase `proposal.md` para la motivación. El repositorio está en `main`, sin commits ni remotos y con los archivos compartibles todavía sin seguimiento. `.gitignore` ya excluye `.venv/`, bytecode, `.pytest_cache/`, `.env`, `*.egg-info/`, `build/` y `dist/`; no cubre variantes como `.env.local` ni el directorio local `.aws/`, actualmente vacío.

El backend vive en `backend/`: el README instala con `uv sync --extra dev` y Docker instala `.[dev]` con pip. `pyproject.toml` declara `setuptools>=68` y `[tool.setuptools]`, pero ha perdido la declaración explícita de `build-backend`. Esta ausencia no se toma como prueba de que la instalación actual falle. El lock conserva el proyecto editable y coincide con sus dependencias y extras.

`.vscode/settings.json` contiene exclusivamente `python.analysis.extraPaths = ["./backend"]`, sin rutas personales. El usuario ha decidido mantener toda `.vscode/` fuera de Git; la configuración seguirá existiendo localmente sin modificación. `AGENTS.md`, los tres agentes de `.codex/agents/` y las seis skills de `.agents/skills/` forman parte del flujo exigido por el proyecto. `.agents/skills/.openspec-target` contiene `codex`, un destino portable; se conserva junto a las skills.

La revisión inicial ejecutó la suite con el intérprete de `.venv` y sin `TEST_DATABASE_URL`: dentro del sandbox se bloqueó en el primer test HTTP. Una repetición autorizada fuera del sandbox, con el mismo entorno y un límite de 60 segundos, terminó correctamente: 10 tests en 0,285 segundos, 9 correctos y 1 omitido por no disponer de PostgreSQL. No se instalaron dependencias ni se modificó código para esa comprobación.

## Goals / Non-Goals

**Goals:** dejar comprobable la selección del primer commit y conservar una instalación explícita, sin modificar los contratos de la API ni los límites de la arquitectura hexagonal.

**Non-Goals:** crear historial Git o publicar; añadir CI, licencia, herramientas, archivos de ejemplo innecesarios o una guía adicional; reorganizar paquetes, migrar el backend de construcción o modificar dependencias. El archivado del change anterior es una operación separada del coordinador.

## Decisions

### 1. Completar `.gitignore` con reglas específicas y excepciones verificables

Conservar las reglas existentes y agruparlas con comentarios breves. Añadir:

| Categoría | Patrones nuevos |
| --- | --- |
| Entornos locales y credenciales | `.env.*`, `!.env.example`, `/.aws/` |
| Cachés y cobertura Python | `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `.coverage.*`, `htmlcov/`, `coverage.xml` |
| Archivos locales del editor | `.vscode/`, `*.swp`, `*.swo`, `*~` |
| Salidas y metadatos locales | `*.log`, `.DS_Store`, `Thumbs.db` |

La excepción de `.env.example` se aplica en cualquier nivel. No se crea ese archivo: solo se garantiza que un futuro ejemplo revisado pueda versionarse. Otros `.env.*` permanecen excluidos. La regla `.vscode/` ignora íntegramente esas carpetas en cualquier nivel, incluido `settings.json`, sin excepciones. No se borra ni modifica la configuración local del editor.

No ignorar `.agents/`, `.codex/`, `openspec/`, `uv.lock` ni todas las carpetas ocultas. Tampoco añadir una regla general `*.db`: las pruebas observadas usan SQLite en memoria o en un directorio temporal fuera del repositorio, y ocultar posibles fixtures no resuelve un artefacto presente. Se prefiere esta selección acotada a copiar una plantilla genérica extensa.

### 2. Explicitar el backend de construcción existente

Añadir solo `build-backend = "setuptools.build_meta"` bajo `[build-system]` en `backend/pyproject.toml`. Esto deja declarada la herramienta ya elegida por `requires` y sus secciones de configuración, sin depender de una selección implícita. No recuperar `package-dir`, cambiar imports, añadir marcadores `py.typed` ni tocar `.vscode/settings.json`: el usuario ya resolvió Pylance con la ruta de análisis.

No modificar `backend/uv.lock`: no cambian requisitos de proyecto. Una sincronización con `--locked` comprobará esa decisión; una discrepancia imprevista se investigará antes de ampliar el alcance.

### 3. Proponer tres commits iniciales en orden, sin ejecutarlos

Los títulos se proponen en inglés. Las rutas son explícitas, relativas a la raíz, e incluyen los archivos ocultos compartibles:

| Orden | Título propuesto | Rutas |
| --- | --- | --- |
| 1 | `chore: configure repository ignore rules` | `.gitignore` |
| 2 | `feat: add hexagonal FastAPI delivery and return service` | `backend/main.py`, `backend/domain/`, `backend/application/`, `backend/adapters/`, `backend/tests/`, `backend/pyproject.toml`, `backend/uv.lock`, `backend/alembic.ini`, `backend/Dockerfile`, `backend/.dockerignore`, `compose.yaml`, `README.md` |
| 3 | `docs: add OpenSpec specifications and SDD workflow` | `AGENTS.md`, `.codex/agents/sdd_planner.toml`, `.codex/agents/sdd_builder.toml`, `.codex/agents/sdd_reviewer.toml`, `.agents/skills/.openspec-target`, las seis carpetas `.agents/skills/openspec-{apply-change,archive-change,explore,propose,sync-specs,update-change}/`, `openspec/config.yaml`, `openspec/specs/`, `openspec/changes/` |

El segundo commit mantiene producto, pruebas, instalación e instrucciones juntos; el tercero conserva las especificaciones y el historial de decisiones, incluido `archive/2026-10-14-document-existing-capabilities/` y este change. Las rutas de directorio significan únicamente sus archivos elegibles según `.gitignore`, nunca usar `git add --force`. Se entregará el inventario final para revisar estos grupos; no se necesita añadir otra guía al repositorio.

### 4. Verificar sin modificar el índice Git

Consultar `git check-ignore --no-index` sobre rutas de ejemplo, existentes o hipotéticas. No es necesario crear archivos sensibles de prueba. Para comprobar la elegibilidad usar `-q` por ruta: código 0 significa ignorada y 1 significa elegible. Si se usa `-v`, una línea con patrón negado describe una excepción y no debe contarse como exclusión.

Revisar `git ls-files --others --exclude-standard` y `git add --dry-run --all` desde la raíz para inventariar candidatos sin staging real. Contrastar el conjunto con los tres grupos y revisar que no contiene artefactos generados ni credenciales privadas. La lectura se limita a los archivos elegibles; no se vuelca el contenido de posibles secretos al informe. Las credenciales `hexagonal` documentadas en Compose son datos públicos de demostración, no un secreto descubierto.

## Acceptance Scenarios

| Escenario | Comprobación | Resultado esperado |
| --- | --- | --- |
| Instalación y artefactos generados | Consultar `.venv/bin/python`, `backend/.venv/bin/python`, `backend/__pycache__/main.cpython-314.pyc`, `backend/hexagonal_fastapi.egg-info/PKG-INFO`, `backend/build/artifact`, `backend/dist/package.whl` | Todas las rutas están ignoradas. |
| Datos locales | Consultar `.env`, `.env.local`, `backend/.env.test`, `.aws/credentials` | Todas están ignoradas; no es necesario que existan. |
| Ejemplos revisables | Consultar `.env.example` y `backend/.env.example` | Ambas son elegibles. No se crean por este change. |
| Cachés, cobertura y editor | Consultar `backend/.pytest_cache/x`, `backend/.mypy_cache/x`, `backend/.ruff_cache/x`, `backend/.coverage`, `backend/.coverage.worker`, `backend/htmlcov/index.html`, `backend/coverage.xml`, `.vscode/settings.json`, `.vscode/local.json`, `backend/debug.log`, `backend/main.py.swp` | Todas están ignoradas; `.vscode/settings.json` sigue existiendo localmente sin modificación. |
| Archivos compartibles | Consultar `backend/uv.lock`, `backend/pyproject.toml`, código, pruebas, Docker, README, `AGENTS.md`, definiciones de agentes, skills y archivos OpenSpec | Ninguna ruta compartible queda ignorada. |
| Construcción explícita | Leer el TOML y reinstalar el proyecto con `uv sync --locked --extra dev --reinstall-package hexagonal-fastapi` desde `backend/` | Se declara `setuptools.build_meta`; la sincronización funciona sin modificar el lock ni las dependencias. |
| Propuesta de publicación | Revisar inventario Git y los tres grupos | Todo candidato está asignado a un grupo y no hay artefactos generados ni credenciales privadas conocidas. No se crean commits, remotos ni cambios en el índice. |

## Verification

1. Ejecutar la matriz de exclusiones y elegibilidad y revisar el inventario final, incluido el dry-run de Git. Comparar índice, HEAD y remotos antes/después de la preparación para confirmar que siguen sin cambios.
2. Comprobar la sintaxis y el backend declarado de `pyproject.toml`, sincronizar el proyecto con el comando `--locked` anterior y verificar que `uv.lock` no cambia.
3. Tras la sincronización, ejecutar desde `backend/` la suite documentada: `uv run --extra dev python -m unittest discover -s tests -v`, con un límite de 60 segundos para que un bloqueo no deje la revisión pendiente indefinidamente. Tener en cuenta la limitación de ejecución dentro del sandbox comprobada en la revisión inicial y gestionar el permiso de ejecución mediante el mecanismo del entorno cuando proceda. Registrar por separado la prueba PostgreSQL omitida si no hay `TEST_DATABASE_URL`; no declarar validado PostgreSQL ni Docker con esta comprobación. Si aparece un fallo nuevo, conservar la evidencia y escalar el diagnóstico al coordinador; no ampliar este change con correcciones funcionales sin un plan aprobado.
4. Validar `openspec validate prepare-repository-for-initial-push --strict` y realizar revisión independiente de la configuración, los escenarios y la evidencia. No añadir tests permanentes para reflejar reglas de `.gitignore`.

## Risks / Trade-offs

- Una regla de exclusión demasiado amplia podría esconder un archivo útil → conservar excepciones concretas y comprobar tanto rutas ignoradas como elegibles.
- `.gitignore` no detecta secretos incrustados en código ni elimina archivos ya versionados → revisar el inventario y contenido elegible; en el estado observado no hay commits ni archivos en el índice. No prometer una garantía absoluta a partir de patrones.
- La sincronización puede necesitar acceso a paquetes no disponibles en caché → reportar la limitación real sin cambiar dependencias, lock ni configuración de red para ocultarla.
- El sandbox bloqueó la suite HTTP, que pasó fuera de él con el mismo entorno → usar un límite de tiempo y las capacidades de ejecución autorizadas; reportar cualquier comprobación no completada.
- Las pruebas locales no prueban una instalación completa en Docker/PostgreSQL → informar esa frontera; esta preparación no modifica esos componentes.

## Migration Plan

Después de la aprobación explícita del plan, aplicar únicamente los dos archivos previstos y verificar. Si hay que revertir, restaurar las reglas y la declaración de backend al estado anterior sin borrar archivos locales. La implementación termina con revisión y propuesta de commits; staging, commits, remoto, push y cierre de este nuevo change requieren las instrucciones posteriores correspondientes.
