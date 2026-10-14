# Proposal

## Why

El backend ocupa actualmente la raíz del repositorio y debe quedar agrupado en `backend/` sin modificar su implementación. Docker Compose con PostgreSQL ya existe; hay que mantener su funcionamiento al reorganizar los archivos.

## What Changes

- Mover a `backend/` el código, pruebas, migraciones, configuración de Python y Alembic, `Dockerfile` y `.dockerignore`, conservando exactamente su contenido.
- Ajustar los contextos de construcción de los servicios `api` y `migrate` del `compose.yaml` existente.
- Mantener en la raíz Compose, README, instrucciones del repositorio, OpenSpec y configuración de agentes.
- **BREAKING** para rutas locales: ejecutar herramientas Python y Alembic desde `backend/`; actualizar en README el árbol, las referencias y el directorio de trabajo de los comandos.
- Conservar los servicios, PostgreSQL, credenciales locales, puertos, volumen y secuencia de arranque actuales.

## Capabilities

### New Capabilities

Ninguna. La API y el arranque con PostgreSQL ya existen; este cambio solo reorganiza archivos y adapta las rutas de desarrollo y construcción.

### Modified Capabilities

Ninguna. No hay especificaciones existentes ni cambios funcionales. `.openspec.yaml` declara `skip_specs: true`; los criterios de aceptación de esta reorganización se documentan en el diseño.

## Impact

Se reubican `main.py`, `domain/`, `application/`, `adapters/`, `tests/`, `pyproject.toml`, `alembic.ini`, `Dockerfile` y `.dockerignore`. Solo `compose.yaml` y `README.md` necesitan modificaciones de contenido fuera de los artefactos de planificación. No se modifican imports, dependencias, endpoints, reglas de negocio, esquema de base de datos ni arquitectura hexagonal. Los entornos virtuales y cachés locales son archivos generados y no forman parte de la migración del backend.
