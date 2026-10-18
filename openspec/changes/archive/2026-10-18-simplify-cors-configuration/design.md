# Design

## Context

El wrapper actual selecciona entre dos instancias del middleware estándar según si la ruta es exactamente `/quotations`. El usuario solicita eliminar esa distinción; `get_cors_allowed_origins` ya valida la configuración que se conservará.

## Goals / Non-Goals

**Goals:** una configuración CORS global y explícita en la composición de FastAPI.

**Non-Goals:** alterar endpoints, dominio, validadores de payload, frontend o configuración de orígenes; añadir autenticación o un middleware propio alternativo.

## Decisions

- Registrar una sola vez `CORSMiddleware` estándar en `main.py`, con `allow_origins=get_cors_allowed_origins()` resuelto antes de crear infraestructura, `allow_methods=["GET", "POST"]`, `allow_headers=["Content-Type"]` y `allow_credentials=False`. Eliminar la clase `ScopedCORSMiddleware` y sus imports; mantener el validador existente en `adapters/http/cors.py`.
- Actualizar los casos de `test_cors.py` que esperaban rechazo de POST fuera de `/quotations`. Conservar cobertura de orígenes exactos, configuración vacía/inválida, ausencia de credenciales, GET/POST reales de cotizaciones y peticiones sin Origin; verificar rechazo preflight de PATCH/DELETE y cabeceras ajenas.
- README describirá la política global y aclarará que permitir un preflight no crea rutas ni valida JSON ni autoriza operaciones. No se necesita migración, nueva dependencia ni cambio de variables de entorno.

## Risks / Trade-offs

- [Los orígenes permitidos podrán superar el preflight POST en otras rutas] → Es el cambio solicitado; los handlers y sus contratos permanecen iguales. La uniformidad se prueba incluso para una ruta inexistente, cuya petición real sigue devolviendo 404.
- [Confundir CORS con control de acceso] → Mantener explícito que `allow_methods` controla preflight y no filtra todas las peticiones HTTP reales.
