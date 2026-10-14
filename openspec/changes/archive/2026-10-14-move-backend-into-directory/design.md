# Design

## Context

Ver `proposal.md` para la motivación. El `compose.yaml` actual ya define `db` con `postgres:17`, un servicio `migrate` que ejecuta `alembic upgrade head` y una API que espera a que la migración termine correctamente. Ambos servicios Python construyen desde `.`. El Dockerfile copia rutas relativas al contexto y utiliza `main:app`; Alembic resuelve su historial respecto a `%(here)s`. Las pruebas de migraciones abren `alembic.ini` desde el directorio de trabajo.

No existen especificaciones principales. Este cambio de organización conserva los contratos actuales y utiliza `skip_specs: true`. Los escenarios siguientes son criterios de aceptación de la reorganización, sin introducir funcionalidades.

## Goals / Non-Goals

**Goals:** conservar la identidad del proyecto Compose y el contenido del backend; hacer inequívocos los directorios de trabajo de construcción, desarrollo y pruebas.

**Non-Goals:** refactorizar imports o paquetes, convertir `backend` en un paquete Python, modificar pruebas o migraciones, actualizar dependencias, cambiar infraestructura, regenerar entornos existentes, añadir frontend o adoptar una base de datos antigua automáticamente.

## Decisions

1. **Reubicar el proyecto Python completo conservando los bytes.** Mover `main.py`, `domain/`, `application/`, `adapters/`, `tests/`, `pyproject.toml`, `alembic.ini`, `Dockerfile` y `.dockerignore` a `backend/`. Los imports siguen siendo `domain`, `application`, `adapters` y `main`; `main.py` continúa como punto de composición. Añadir prefijos `backend.` o adaptar código sería innecesario y vulneraría la petición de no cambiar el backend. No se añaden dependencias de FastAPI o persistencia al dominio ni a los casos de uso.
2. **Mantener Compose en la raíz y cambiar exclusivamente sus dos contextos de build a `./backend`.** Así el Dockerfile funciona sin cambios y se conservan nombres de servicios, `DATABASE_URL`, puertos de loopback, PostgreSQL 17, credenciales, healthcheck, dependencias de arranque y `postgres_data`. Mover Compose a `backend/` o crear un segundo archivo podría cambiar la identidad del proyecto y del volumen; reconstruirlo desde cero no aporta nada.
3. **Mantener la documentación general y las herramientas del repositorio en la raíz.** No mover `README.md`, `.gitignore`, `AGENTS.md`, `openspec/`, `.agents/`, `.codex/` ni otros archivos de configuración generales. Los entornos virtuales y cachés son generados: no trasladar la `.venv` existente ni introducirlos en el inventario de archivos preservados.
4. **Documentar Python desde `backend/` y Compose desde la raíz.** Actualizar el árbol y las referencias del README, distinguiendo rutas relativas a la raíz de las relativas al proyecto Python. Mostrar el directorio de trabajo de todos los bloques de instalación, migraciones, adopción de esquema y pruebas. La alternativa de introducir envoltorios o reconfigurar Alembic para seguir trabajando desde la raíz añade cambios innecesarios. `uv sync --extra dev` desde `backend/` puede crear su entorno local habitual; cualquier archivo generado queda fuera del cambio intencionado.
5. **Verificar con evidencias existentes.** Comparar inventarios y SHA-256 antes/después y ejecutar las pruebas actuales, sin añadir pruebas que solo dupliquen el movimiento de archivos. Validar el modelo Compose y, si el entorno lo permite, su construcción y arranque con PostgreSQL. La falta de dependencias, red o acceso al daemon se registra como limitación de verificación y no como resultado satisfactorio.

## Acceptance Scenarios

### Escenario: traslado íntegro del backend

- **GIVEN** un inventario previo de los archivos del backend y sus hashes SHA-256, excluyendo cachés y entornos generados.
- **WHEN** se compara cada ruta original con `backend/<ruta-original>` después del traslado.
- **THEN** todos los archivos conservan exactamente su contenido, desaparecen de su ubicación original y no se añaden cambios funcionales, de dependencias ni de migraciones.
- **AND** Compose, README, instrucciones y herramientas generales permanecen en la raíz.

### Escenario: Compose utiliza el backend reubicado

- **GIVEN** el repositorio reorganizado y Docker Compose instalado.
- **WHEN** se ejecuta `docker compose config` desde la raíz.
- **THEN** los servicios `api` y `migrate` utilizan `backend/` como contexto y encuentran el Dockerfile movido.
- **AND** el resto de la configuración conserva los valores anteriores, incluidos imagen PostgreSQL, credenciales, URLs, healthcheck, dependencias, puertos y volumen.

### Escenario: arranque y persistencia conservados

- **GIVEN** Docker operativo y una base de datos compatible con las migraciones actuales.
- **WHEN** se ejecuta `docker compose up --build` desde la raíz.
- **THEN** PostgreSQL alcanza el estado saludable, `migrate` termina correctamente y después la API ofrece `/docs`, `/deliveries` y `/returns` en `127.0.0.1:8000`.
- **AND** las operaciones mantienen respuestas de creación `201`, listado `200` y entrada inválida `422`, y el volumen `postgres_data` sigue conservando los datos al detener los servicios sin eliminar volúmenes.
- **AND** un fallo de migración sigue impidiendo el arranque dependiente de la API.

### Escenario: desarrollo y pruebas desde el nuevo directorio

- **GIVEN** las dependencias de desarrollo instaladas y un terminal situado en `backend/` siguiendo el README.
- **WHEN** se ejecutan Alembic y `uv run --extra dev python -m unittest discover -s tests -v`.
- **THEN** se resuelven imports, `alembic.ini` y el historial existente sin cambios en su contenido, y las pruebas actuales conservan sus resultados funcionales.
- **AND** la prueba PostgreSQL sigue omitiéndose si falta `TEST_DATABASE_URL`; con esa variable y una base previamente migrada, verifica creación, listado y persistencia entre instancias de la aplicación.

## Risks / Trade-offs

- [Comandos ejecutados en la raíz ya no encuentran el proyecto Python] → Indicar `cd backend` y el directorio de trabajo en cada sección local del README.
- [Pérdida de archivos o cambios accidentales durante el traslado] → Comparar el inventario completo y los hashes previos, no solo una selección de módulos.
- [Cambio accidental de proyecto o volumen Compose] → Conservar `compose.yaml` en la raíz y no cambiar nombres ni borrar volúmenes durante la verificación.
- [Entorno de pruebas sin dependencias o Docker] → Separar validación documental, comprobaciones estáticas y pruebas de ejecución; informar fallos previos y verificaciones no disponibles sin rebajar los criterios de aceptación.

## Migration Plan

1. Conservar la referencia de contenido previa y trasladar únicamente los archivos del backend.
2. Ajustar los dos contextos Compose y las instrucciones del README.
3. Verificar contenido, configuración, pruebas y ejecución disponible; obtener revisión independiente.

No hay migración nueva de datos ni cambio del esquema. Para revertir esta reorganización, devolver los mismos archivos a la raíz y restaurar los contextos y las referencias documentales; no modificar ni eliminar el volumen PostgreSQL.
