# Proposal

## Why

El repositorio ya tiene una implementación documentada y un historial OpenSpec, pero todavía no tiene commits ni remoto. Antes de proponer su primera publicación necesitamos distinguir los archivos compartibles de los artefactos locales y dejar explícita la configuración de empaquetado existente.

## What Changes

- Completar `.gitignore` para los entornos y artefactos Python, cachés de análisis/pruebas, cobertura, variantes locales de `.env` y archivos locales del editor; conservar elegibles los ejemplos de entorno e ignorar toda `.vscode/`, sin excepciones, por decisión del usuario.
- Restaurar únicamente `build-backend = "setuptools.build_meta"` en el bloque `[build-system]` de `backend/pyproject.toml`, que ya declara setuptools y su configuración. No se cambian dependencias ni el diseño del paquete.
- Verificar qué archivos entrarían en el primer commit y proponer tres grupos con títulos en inglés y rutas concretas. Mantener `backend/uv.lock`, el código, las pruebas, la documentación y el flujo OpenSpec compartibles.
- La preparación no incluye añadir archivos al índice, crear commits, configurar un remoto ni hacer push.

## Capabilities

### New Capabilities

Ninguna. Es un cambio de configuración y preparación del repositorio, con `skip_specs: true` conforme al esquema instalado. Sus escenarios de aceptación se recogen en `design.md`.

### Modified Capabilities

Ninguna. Las cinco especificaciones funcionales existentes permanecen sin cambios.

## Impact

- Archivos de implementación previstos: `.gitignore` y `backend/pyproject.toml`.
- La configuración local `.vscode/settings.json` se conserva sin modificación, pero queda fuera de Git. Se conservan compartibles y sin modificación `backend/uv.lock`, `AGENTS.md`, `.codex/agents/`, `.agents/skills/`, `README.md`, Compose, Docker, código, pruebas y especificaciones existentes.
- El plan y su evidencia se mantienen en este change; no se añade un documento de publicación separado.
- No hay cambios de API, dominio, casos de uso, persistencia, migraciones ni versiones de dependencias. CI, licencia y configuración de hosting quedan fuera del alcance.
