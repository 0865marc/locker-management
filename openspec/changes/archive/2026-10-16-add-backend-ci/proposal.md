# Proposal

## Why

El desarrollo mediante ramas y PR necesita detectar inconsistencias de estilo, regresiones y problemas de empaquetado antes de integrar cambios. El proyecto ya tiene pruebas y comprobación de tipos, pero carece de un CI que las ejecute de forma reproducible y visible.

## What Changes

- Añadir un workflow de GitHub Actions para PR hacia `main` y pushes a `main`, con cinco resultados independientes: Ruff, Pyright, unitarias, integración PostgreSQL con migraciones y Docker con smoke de la API.
- Incorporar Ruff para lint e imports y para formato, con configuración compartida entre desarrollo y CI, y normalizar mecánicamente el Python existente sin cambiar comportamiento ni migraciones históricas.
- Ejecutar Pyright con cero errores y advertencias, las unitarias sin servicios y la integración contra PostgreSQL real, conservando los escenarios de Alembic existentes.
- Construir la imagen con las dependencias de `uv.lock` y comprobar que la API arranca con sus dependencias actuales y responde mediante un endpoint que consulta PostgreSQL.
- Mantener ejecuciones ágiles con jobs paralelos, caché de dependencias, cancelación de ejecuciones anteriores de la misma PR y tiempos máximos; documentar los comandos equivalentes locales.

Quedan fuera despliegue, publicación de imágenes, cobertura, Dependabot, protecciones remotas de ramas, nuevos controles de arquitectura, validación OpenSpec dentro del workflow y la suite de mensajería en CI. RabbitMQ se levanta únicamente porque el arranque real de la API ya lo requiere.

## Capabilities

### New Capabilities

- `backend-ci`: comprobación automática y reproducible de los cinco bloques de calidad y ejecución del backend en GitHub Actions.

### Modified Capabilities

Ninguna. El CI ejecuta los contratos de pruebas, tipos, migraciones y runtime existentes; no modifica su comportamiento funcional.

## Impact

Se añaden `.github/workflows/backend-ci.yml`, `compose.ci.yaml` y `scripts/ci/smoke.sh`; se ajustan `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`, `README.md` y el formato/imports de los archivos Python de backend, incluidos tests. El override de Compose evita publicar puertos y permite reproducir el smoke sin ocupar los del entorno de desarrollo. Las revisiones Alembic `0001`–`0005` permanecen intactas; no se amplían exclusiones ni se reduce la exigencia de Pyright. No hay cambios de API, negocio, puertos de dominio o límites hexagonales.

La propuesta parte del árbol actual que incluye `add-asynchronous-shipping-quotations`, completo pero aún activo. La implementación futura se aislará de esa PR sobre una base que ya contenga sus cambios; esta propuesta no sincroniza, archiva ni modifica aquel cambio.
